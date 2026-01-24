"""
WebSocket 模块
通过 Redis Pub/Sub 接收新仓位通知并广播给连接的客户端
"""
import json
import threading
import logging
from typing import Optional

import redis
from flask import Flask
from flask_socketio import SocketIO, emit

from config.settings import settings

logger = logging.getLogger(__name__)

# Redis 新仓位广播 channel（与 monitor_s_traders_positions.py 一致）
REDIS_WS_CHANNEL = "ws_new_positions"

# SocketIO 实例
socketio: Optional[SocketIO] = None

# Redis 订阅线程
_redis_thread: Optional[threading.Thread] = None
_redis_running = False


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


def start_redis_listener():
    """
    启动 Redis 订阅监听线程
    监听新仓位消息并广播给所有 WebSocket 客户端
    """
    global _redis_thread, _redis_running
    
    if _redis_thread and _redis_thread.is_alive():
        logger.warning("Redis 监听线程已在运行")
        return
    
    _redis_running = True
    _redis_thread = threading.Thread(target=_redis_listener_loop, daemon=True)
    _redis_thread.start()
    logger.info(f"Redis 订阅监听已启动 (channel: {REDIS_WS_CHANNEL})")


def stop_redis_listener():
    """停止 Redis 订阅监听"""
    global _redis_running
    _redis_running = False
    logger.info("Redis 订阅监听已停止")


def _redis_listener_loop():
    """Redis 订阅监听循环"""
    global _redis_running
    
    while _redis_running:
        try:
            # 创建新的 Redis 连接用于订阅
            redis_client = redis.Redis(
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password or None,
                db=settings.redis.db,
                decode_responses=True
            )
            
            pubsub = redis_client.pubsub()
            pubsub.subscribe(REDIS_WS_CHANNEL)
            
            logger.info(f"已订阅 Redis channel: {REDIS_WS_CHANNEL}")
            
            for message in pubsub.listen():
                if not _redis_running:
                    break
                    
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        _broadcast_new_position(data)
                    except json.JSONDecodeError:
                        logger.warning(f"无效的 JSON 消息: {message['data']}")
                    except Exception as e:
                        logger.error(f"处理消息失败: {e}")
            
            pubsub.close()
            redis_client.close()
            
        except redis.ConnectionError as e:
            logger.error(f"Redis 连接失败: {e}，5秒后重试...")
            import time
            time.sleep(5)
        except Exception as e:
            logger.error(f"Redis 监听异常: {e}，5秒后重试...")
            import time
            time.sleep(5)


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
