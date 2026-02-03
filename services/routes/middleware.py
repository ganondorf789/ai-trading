"""
JWT 认证中间件
提供 Token 生成、验证和装饰器
"""
import jwt
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Tuple
from flask import request, jsonify, g
import logging

from config.settings import settings
from .db import db

logger = logging.getLogger(__name__)


def generate_tokens(user_id: int, account: str, role: str, user_expires_at: Optional[datetime] = None) -> Tuple[str, str]:
    """
    生成访问令牌和刷新令牌
    
    Args:
        user_id: 用户 ID
        account: 账号
        role: 用户角色
        user_expires_at: 用户账户过期时间（None 表示永不过期）
        
    Returns:
        (access_token, refresh_token) 元组
    """
    now = datetime.utcnow()
    
    # 访问令牌
    access_payload = {
        'user_id': user_id,
        'account': account,
        'role': role,
        'type': 'access',
        'iat': now,
        'exp': now + timedelta(hours=settings.jwt.access_token_expire_hours),
        # 用户账户过期时间（时间戳，None 表示永不过期）
        'user_expires_at': int(user_expires_at.timestamp()) if user_expires_at else None
    }
    access_token = jwt.encode(
        access_payload,
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm
    )
    
    # 刷新令牌
    refresh_payload = {
        'user_id': user_id,
        'type': 'refresh',
        'iat': now,
        'exp': now + timedelta(days=settings.jwt.refresh_token_expire_days)
    }
    refresh_token = jwt.encode(
        refresh_payload,
        settings.jwt.secret_key,
        algorithm=settings.jwt.algorithm
    )
    
    return access_token, refresh_token


def verify_token(token: str, token_type: str = 'access') -> Optional[Dict]:
    """
    验证并解码 JWT 令牌
    
    Args:
        token: JWT 令牌
        token_type: 令牌类型 ('access' 或 'refresh')
        
    Returns:
        解码后的 payload，验证失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=[settings.jwt.algorithm]
        )
        
        # 验证令牌类型
        if payload.get('type') != token_type:
            logger.warning(f"Token 类型不匹配: 期望 {token_type}, 实际 {payload.get('type')}")
            return None
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token 验证失败: {e}")
        return None


def get_token_from_request() -> Optional[str]:
    """
    从请求中提取 Token
    支持 Authorization Header 和 Query Parameter
    
    Returns:
        Token 字符串，未找到返回 None
    """
    # 1. 从 Authorization Header 获取 (Bearer Token)
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            return parts[1]
    
    # 2. 从 Query Parameter 获取
    token = request.args.get('token')
    if token:
        return token
    
    return None


def login_required(f):
    """
    登录验证装饰器
    验证用户是否已登录，并将用户信息注入到 g.current_user
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        
        if not token:
            return jsonify({
                'success': False,
                'error': '未提供认证令牌',
                'code': 'TOKEN_MISSING'
            }), 401
        
        payload = verify_token(token, 'access')
        
        if not payload:
            return jsonify({
                'success': False,
                'error': '认证令牌无效或已过期',
                'code': 'TOKEN_INVALID'
            }), 401
        
        user_id = payload.get('user_id')
        role = payload.get('role')
        user_expires_at = payload.get('user_expires_at')
        
        # 非管理员用户检查账户是否过期（从 JWT 中获取过期时间）
        if role != 'admin' and user_expires_at:
            if datetime.utcnow().timestamp() > user_expires_at:
                logger.warning(f"用户账户已过期: user_id={user_id}")
                return jsonify({
                    'success': False,
                    'error': '您的账户已过期，请联系管理员续期',
                    'code': 'USER_EXPIRED'
                }), 403
        
        # 将用户信息存储到 g 对象中
        g.current_user = {
            'user_id': user_id,
            'account': payload.get('account'),
            'role': role
        }
        
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """
    管理员权限验证装饰器
    必须与 @login_required 一起使用，放在其后
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查是否已通过 login_required 验证
        if not hasattr(g, 'current_user'):
            return jsonify({
                'success': False,
                'error': '未提供认证令牌',
                'code': 'TOKEN_MISSING'
            }), 401
        
        # 检查是否为管理员
        if g.current_user.get('role') != 'admin':
            return jsonify({
                'success': False,
                'error': '需要管理员权限',
                'code': 'ADMIN_REQUIRED'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def member_required(f):
    """
    会员权限验证装饰器
    必须与 @login_required 一起使用，放在其后
    允许 member 和 admin 角色通过
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查是否已通过 login_required 验证
        if not hasattr(g, 'current_user'):
            return jsonify({
                'success': False,
                'error': '未提供认证令牌',
                'code': 'TOKEN_MISSING'
            }), 401
        
        # 检查是否为会员或管理员
        role = g.current_user.get('role')
        if role not in ['member', 'admin']:
            return jsonify({
                'success': False,
                'error': '需要会员权限',
                'code': 'MEMBER_REQUIRED'
            }), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def get_current_user_id() -> Optional[int]:
    """
    获取当前登录用户的 ID
    
    Returns:
        用户 ID，未登录返回 None
    """
    if hasattr(g, 'current_user'):
        return g.current_user.get('user_id')
    return None


def get_current_user() -> Optional[Dict]:
    """
    获取当前登录用户的信息
    
    Returns:
        用户信息字典，未登录返回 None
    """
    if hasattr(g, 'current_user'):
        return g.current_user
    return None
