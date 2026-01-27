"""
全局共享资源模块
提供 Redis 客户端等共享资源的延迟初始化
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Redis 客户端（延迟初始化）
_redis_client = None


def get_redis_client():
    """
    获取 Redis 客户端（延迟初始化，单例模式）
    
    Returns:
        Redis 客户端实例，如果连接失败返回 None
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        import redis
        from config.settings import settings
        
        _redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=True
        )
        _redis_client.ping()
        logger.info("Redis 客户端已连接（共享实例）")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}")
        return None


def reset_redis_client():
    """
    重置 Redis 客户端（用于重连）
    """
    global _redis_client
    
    if _redis_client is not None:
        try:
            _redis_client.close()
        except:
            pass
        _redis_client = None
        logger.info("Redis 客户端已重置")
