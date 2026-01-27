"""
WebSocket 模块
通过 Redis Pub/Sub 接收新仓位通知和跟单通知并广播给连接的客户端
"""
import json
import logging
from typing import Optional

import redis
from flask import Flask
from flask_socketio import SocketIO, emit

from config.settings import settings
from .shared import get_redis_client, reset_redis_client

logger = logging.getLogger(__name__)

# Redis 新仓位广播 channel（与 monitor_s_traders_positions.py 一致）
REDIS_WS_CHANNEL = "ws_new_positions"

# Redis 通知 channel（跟单通知）
REDIS_NOTIFICATIONS_CHANNEL = "notifications"

# SocketIO 实例
socketio: Optional[SocketIO] = None

# Redis 订阅状态
_redis_running = False

# 数据库实例（延迟加载）
_db = None


def _get_db():
    """延迟加载数据库实例"""
    global _db
    if _db is None:
        from database import TraderDatabase
        _db = TraderDatabase()
    return _db


def init_socketio(app: Flask) -> SocketIO:
    """
    初始化 Flask-SocketIO
    
    Args:
        app: Flask 应用实例
    
    Returns:
        SocketIO 实例
    """
    global socketio
    
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='eventlet',
        logger=False,
        engineio_logger=False
    )
    
    # 注册事件处理器
    @socketio.on('connect')
    def handle_connect():
        logger.info("WebSocket 客户端已连接")
        # 确保 Redis 监听已启动
        _ensure_redis_listener_started()
        emit('connected', {'message': '已连接到新仓位推送服务'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("WebSocket 客户端已断开")
    
    @socketio.on('ping')
    def handle_ping():
        emit('pong', {'message': 'pong'})
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        """客户端订阅特定频道"""
        channel = data.get('channel', 'new_positions')
        logger.info(f"客户端订阅频道: {channel}")
        emit('subscribed', {'channel': channel})
    
    logger.info("Flask-SocketIO 初始化完成")
    return socketio


def _ensure_redis_listener_started():
    """确保 Redis 监听已启动（在 eventlet 上下文中调用）"""
    global _redis_running
    if not _redis_running and socketio is not None:
        start_redis_listener()


def start_redis_listener():
    """
    启动 Redis 订阅监听
    使用 socketio.start_background_task 确保在 eventlet 上下文中运行
    监听新仓位消息和通知消息并广播给所有 WebSocket 客户端
    """
    global _redis_running
    
    if _redis_running:
        logger.warning("Redis 监听已在运行")
        return
    
    if socketio is None:
        logger.error("SocketIO 未初始化，无法启动 Redis 监听")
        return
    
    _redis_running = True
    # 使用 socketio.start_background_task 启动，确保在正确的 async 上下文中运行
    socketio.start_background_task(_redis_listener_loop)
    logger.info(f"Redis 订阅监听已启动 (channels: {REDIS_WS_CHANNEL}, {REDIS_NOTIFICATIONS_CHANNEL})")


def stop_redis_listener():
    """停止 Redis 订阅监听"""
    global _redis_running
    _redis_running = False
    logger.info("Redis 订阅监听已停止")


def _redis_listener_loop():
    """Redis 订阅监听循环（在 eventlet 上下文中运行）"""
    global _redis_running
    
    # 导入 eventlet sleep 以确保协作式调度
    try:
        import eventlet
        sleep = eventlet.sleep
    except ImportError:
        import time
        sleep = time.sleep
    
    while _redis_running:
        try:
            # 使用共享的 Redis 客户端
            redis_client = get_redis_client()
            
            if redis_client is None:
                logger.error("无法获取 Redis 客户端，5秒后重试...")
                sleep(5)
                continue
            
            pubsub = redis_client.pubsub()
            # 订阅多个频道
            pubsub.subscribe(REDIS_WS_CHANNEL, REDIS_NOTIFICATIONS_CHANNEL)
            
            logger.info(f"已订阅 Redis channels: {REDIS_WS_CHANNEL}, {REDIS_NOTIFICATIONS_CHANNEL}")
            
            # 使用非阻塞方式获取消息，配合 sleep 实现协作式调度
            while _redis_running:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
                if message is not None and message['type'] == 'message':
                    try:
                        channel = message['channel']
                        data = json.loads(message['data'])
                        
                        # 根据频道分发消息
                        if channel == REDIS_WS_CHANNEL:
                            _broadcast_new_position(data)
                        elif channel == REDIS_NOTIFICATIONS_CHANNEL:
                            _handle_notification(data)
                    except json.JSONDecodeError:
                        logger.warning(f"无效的 JSON 消息: {message['data']}")
                    except Exception as e:
                        logger.error(f"处理消息失败: {e}")
                # 让出控制权给其他 greenlet
                sleep(0.01)
            
            pubsub.close()
            
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败: {e}，重置客户端并5秒后重试...")
            reset_redis_client()
            sleep(5)
        except Exception as e:
            logger.error(f"Redis 监听异常: {e}，5秒后重试...")
            sleep(5)


def _broadcast_new_position(data: dict):
    """
    广播新仓位消息给所有连接的客户端
    
    Args:
        data: 新仓位数据
    """
    global socketio
    
    if socketio is None:
        logger.warning("SocketIO 未初始化，无法广播消息")
        return
    
    try:
        socketio.emit('new_position', data, namespace='/')
        logger.info(f"已广播新仓位: {data.get('coin', 'unknown')} - {data.get('direction', 'unknown')}")
    except Exception as e:
        logger.error(f"广播消息失败: {e}")


def _handle_notification(data: dict):
    """
    处理通知消息：保存到数据库并广播给 WebSocket 客户端
    
    Args:
        data: 通知数据，包含:
            - type: 通知类型 ('open' | 'close' | 'adjust' | 'error')
            - title: 通知标题
            - content: Markdown 格式内容
            - target_address: 目标交易员地址
            - symbol: 交易对
            - side: 方向
            - size: 仓位大小
            - pnl: 盈亏
            - timestamp: 时间戳
    """
    global socketio
    
    # 1. 保存通知到数据库
    try:
        db = _get_db()
        notification_id = db.save_notification(data)
        if notification_id:
            data['id'] = notification_id
            logger.info(f"通知已保存: id={notification_id}, type={data.get('type')}, symbol={data.get('symbol')}")
    except Exception as e:
        logger.error(f"保存通知到数据库失败: {e}")
    
    # 2. 广播通知给 WebSocket 客户端
    if socketio is None:
        logger.warning("SocketIO 未初始化，无法广播通知")
        return
    
    try:
        socketio.emit('notification', data, namespace='/')
        logger.info(f"已广播通知: {data.get('type')} - {data.get('title')}")
    except Exception as e:
        logger.error(f"广播通知失败: {e}")


def broadcast_message(event: str, data: dict):
    """
    手动广播消息（供其他模块调用）
    
    Args:
        event: 事件名称
        data: 消息数据
    """
    global socketio
    
    if socketio is None:
        logger.warning("SocketIO 未初始化")
        return
    
    try:
        socketio.emit(event, data, namespace='/')
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
