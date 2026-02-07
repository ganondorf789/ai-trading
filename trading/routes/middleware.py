"""
API Key 认证中间件
通过 gRPC 回源验证 API Key，确保认证控制权在服务端
"""
import hmac
from functools import wraps
from typing import Optional
from flask import request, jsonify, g
import logging

from trading.settings import settings

logger = logging.getLogger(__name__)

# gRPC 客户端引用（由 app 初始化时注入）
_grpc_client = None


def init_middleware_grpc(grpc_client):
    """
    注入 gRPC 客户端用于 API Key 远程验证
    
    Args:
        grpc_client: GRPCClient 实例
    """
    global _grpc_client
    _grpc_client = grpc_client
    logger.info("API Key 中间件已初始化 gRPC 远程验证")


def get_api_key_from_request() -> Optional[str]:
    """
    从请求中提取 API Key
    支持 Header 和 Bearer Token
    
    Returns:
        API Key 字符串，未找到返回 None
    """
    # 1. 从 X-API-Key Header 获取
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return api_key
    
    # 2. 从 Authorization Header 获取 (Bearer Token 格式)
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            return parts[1]
    
    return None


def verify_api_key(api_key: str) -> bool:
    """
    验证 API Key
    
    优先通过 gRPC 远程验证（回源到 services 端）。
    若 gRPC 不可用，则回退到本地配置验证。
    
    Args:
        api_key: API Key
        
    Returns:
        验证是否通过
    """
    # 优先使用 gRPC 远程验证
    if _grpc_client:
        try:
            result = _grpc_client.verify_api_key(api_key)
            if result:
                # 将用户信息存储到 g 对象中
                g.api_user = result
                return True
            return False
        except Exception as e:
            logger.warning(f"gRPC 远程验证失败，回退到本地验证: {e}")
    
    # 回退: 从本地配置验证（兼容旧模式）
    valid_api_key = settings.api.key
    
    if not valid_api_key:
        logger.warning("未配置 API_KEY 且 gRPC 验证不可用，API Key 验证已禁用")
        return True
    
    # 使用时间常量比较防止时序攻击
    return hmac.compare_digest(api_key, valid_api_key)


def api_key_required(f):
    """
    API Key 验证装饰器
    验证请求是否携带有效的 API Key
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = get_api_key_from_request()
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': '未提供 API Key',
                'code': 'API_KEY_MISSING'
            }), 401
        
        if not verify_api_key(api_key):
            return jsonify({
                'success': False,
                'error': 'API Key 无效',
                'code': 'API_KEY_INVALID'
            }), 401
        
        # 将认证信息存储到 g 对象中
        g.api_key = api_key
        
        return f(*args, **kwargs)
    
    return decorated_function
