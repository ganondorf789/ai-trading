"""
WebSocket 模块
通过 Redis Pub/Sub 接收新仓位通知和跟单通知并广播给连接的客户端
支持 JWT 认证，通知按用户定向发送
"""
import json
import logging
from typing import Optional, Dict

import redis
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from config.settings import settings
from .shared import get_redis_client, reset_redis_client
from .routes.middleware import verify_token

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

# 用户会话管理 (session_id -> user_info)
_user_sessions: Dict[str, Dict] = {}

# 单点登录：用户ID -> session_id 映射（确保每个用户只有一个活跃连接）
_user_active_sessions: Dict[int, str] = {}


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
        logger.info(f"WebSocket 客户端已连接: {request.sid}")
        # 确保 Redis 监听已启动
        _ensure_redis_listener_started()
        emit('connected', {'message': '已连接，请发送 authenticate 事件进行认证'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        session_id = request.sid
        # 清理用户会话
        if session_id in _user_sessions:
            user_info = _user_sessions.pop(session_id)
            user_id = user_info.get('user_id')
            # 离开用户专属房间
            leave_room(f"user_{user_id}")
            # 清理用户活跃会话映射（仅当当前 session 是活跃 session 时）
            if user_id in _user_active_sessions and _user_active_sessions[user_id] == session_id:
                del _user_active_sessions[user_id]
            logger.info(f"WebSocket 客户端已断开: {session_id}, user_id={user_id}")
        else:
            logger.info(f"WebSocket 客户端已断开: {session_id}")
    
    @socketio.on('authenticate')
    def handle_authenticate(data):
        """
        客户端认证（支持单点登录）
        
        Args:
            data: {'token': 'JWT access token'}
        
        单点登录逻辑：
        - 同一用户只能有一个活跃的 WebSocket 连接
        - 新连接认证成功后，会踢掉该用户的旧连接
        """
        session_id = request.sid
        token = data.get('token') if data else None
        
        if not token:
            emit('auth_error', {'error': '未提供认证令牌', 'code': 'TOKEN_MISSING'})
            return
        
        # 验证 token
        payload = verify_token(token, 'access')
        
        if not payload:
            emit('auth_error', {'error': '认证令牌无效或已过期', 'code': 'TOKEN_INVALID'})
            return
        
        user_id = payload.get('user_id')
        account = payload.get('account')
        role = payload.get('role')
        
        # 单点登录：检查是否有该用户的其他活跃连接
        if user_id in _user_active_sessions:
            old_session_id = _user_active_sessions[user_id]
            if old_session_id != session_id and old_session_id in _user_sessions:
                # 向旧连接发送被踢下线通知
                try:
                    socketio.emit('kicked', {
                        'message': '您的账号在其他地方登录，当前连接已断开',
                        'code': 'KICKED_BY_NEW_LOGIN'
                    }, room=old_session_id, namespace='/')
                    logger.info(f"单点登录: 踢掉用户 {user_id} 的旧连接 {old_session_id}")
                except Exception as e:
                    logger.error(f"发送踢下线通知失败: {e}")
                
                # 清理旧会话
                old_user_info = _user_sessions.pop(old_session_id, None)
                if old_user_info:
                    leave_room(f"user_{user_id}", sid=old_session_id)
                
                # 断开旧连接
                try:
                    socketio.server.disconnect(old_session_id, namespace='/')
                except Exception as e:
                    logger.error(f"断开旧连接失败: {e}")
        
        # 保存新会话
        _user_sessions[session_id] = {
            'user_id': user_id,
            'account': account,
            'role': role
        }
        
        # 更新用户活跃会话映射
        _user_active_sessions[user_id] = session_id
        
        # 加入用户专属房间（用于定向发送消息）
        join_room(f"user_{user_id}")
        
        logger.info(f"WebSocket 客户端认证成功: {session_id}, user_id={user_id}, account={account}")
        emit('authenticated', {
            'user_id': user_id,
            'account': account,
            'message': '认证成功，将接收您的专属通知'
        })
    
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
    处理通知消息：保存到数据库并发送给对应用户
    
    Args:
        data: 通知数据，包含:
            - type: 通知类型 ('open' | 'close' | 'adjust' | 'tracking_open' | 'tracking_close' | 'tracking_add' | 'tracking_reduce' | 'error' | 'announcement')
            - title: 通知标题
            - content: Markdown 格式内容
            - target_address: 目标交易员地址
            - symbol: 交易对
            - side: 方向
            - size: 仓位大小
            - pnl: 盈亏
            - timestamp: 时间戳
            - user_id: 目标用户ID（可选，如果指定则只发送给该用户）
            - id: 已保存的通知ID（可选，如已有则跳过数据库保存）
    """
    global socketio
    
    user_id = data.get('user_id')
    
    # 1. 保存通知到数据库（如果消息中已带 id，说明发布端已保存，跳过避免重复插入）
    if not data.get('id'):
        try:
            db = _get_db()
            notification_id = db.save_notification(data)
            if notification_id:
                data['id'] = notification_id
                logger.info(f"通知已保存: id={notification_id}, type={data.get('type')}, symbol={data.get('symbol')}, user_id={user_id}")
        except Exception as e:
            logger.error(f"保存通知到数据库失败: {e}")
    else:
        logger.info(f"通知已由发布端保存: id={data['id']}, type={data.get('type')}")
    
    # 2. 发送通知给 WebSocket 客户端
    if socketio is None:
        logger.warning("SocketIO 未初始化，无法发送通知")
        return
    
    try:
        if user_id:
            # 定向发送给指定用户
            room = f"user_{user_id}"
            socketio.emit('notification', data, room=room, namespace='/')
            logger.info(f"已发送通知给用户 {user_id}: {data.get('type')} - {data.get('title')}")
        else:
            # 没有指定用户时，广播给所有已认证的用户
            socketio.emit('notification', data, namespace='/')
            logger.info(f"已广播通知: {data.get('type')} - {data.get('title')}")
    except Exception as e:
        logger.error(f"发送通知失败: {e}")


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
