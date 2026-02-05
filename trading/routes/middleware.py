"""
API Key 认证中间件
提供简单的 API Key 验证
"""
from functools import wraps
from typing import Optional
from flask import request, jsonify, g
import logging

from trading.settings import settings

logger = logging.getLogger(__name__)


def get_api_key_from_request() -> Optional[str]:
    """
    从请求中提取 API Key
    支持 Header 和 Query Parameter
    
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
    
    # 3. 从 Query Parameter 获取
    api_key = request.args.get('api_key')
    if api_key:
        return api_key
    
    return None


def verify_api_key(api_key: str) -> bool:
    """
    验证 API Key
    
    Args:
        api_key: API Key
        
    Returns:
        验证是否通过
    """
    # 从配置中获取有效的 API Key
    valid_api_key = settings.api.key
    
    if not valid_api_key:
        logger.warning("未配置 API_KEY，API Key 验证已禁用")
        return True  # 未配置时允许所有请求
    
    return api_key == valid_api_key


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
