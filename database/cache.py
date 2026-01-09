"""
Redis 缓存管理模块
提供缓存功能用于提升读取性能
"""
import json
from typing import Any, Optional, List
from datetime import timedelta
import redis
from loguru import logger

from config.settings import settings


class RedisCache:
    """Redis 缓存管理类"""

    _pool: redis.ConnectionPool = None
    _client: redis.Redis = None

    # 缓存键前缀
    PREFIX = "trading:"

    # 默认过期时间（秒）
    DEFAULT_TTL = 300  # 5分钟

    def __init__(self):
        """初始化 Redis 连接"""
        self._ensure_client()

    @classmethod
    def _ensure_client(cls):
        """确保 Redis 客户端已创建"""
        if cls._client is None:
            try:
                cls._pool = redis.ConnectionPool(
                    host=settings.redis.host,
                    port=settings.redis.port,
                    password=settings.redis.password or None,
                    db=settings.redis.db,
                    max_connections=settings.redis.max_connections,
                    decode_responses=True
                )
                cls._client = redis.Redis(connection_pool=cls._pool)
                # 测试连接
                cls._client.ping()
                logger.info(f"Redis 连接成功: {settings.redis.host}:{settings.redis.port}")
            except Exception as e:
                logger.warning(f"Redis 连接失败，缓存功能将被禁用: {e}")
                cls._client = None

    @classmethod
    def close(cls):
        """关闭 Redis 连接"""
        if cls._pool is not None:
            cls._pool.disconnect()
            cls._pool = None
            cls._client = None
            logger.info("Redis 连接已关闭")

    @property
    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except:
            return False

    def _make_key(self, key: str) -> str:
        """生成带前缀的缓存键"""
        return f"{self.PREFIX}{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        if not self.is_available:
            return None

        try:
            value = self._client.get(self._make_key(key))
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.debug(f"获取缓存失败 [{key}]: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认 5 分钟

        Returns:
            是否设置成功
        """
        if not self.is_available:
            return False

        try:
            ttl = ttl or self.DEFAULT_TTL
            self._client.setex(
                self._make_key(key),
                ttl,
                json.dumps(value, ensure_ascii=False, default=str)
            )
            return True
        except Exception as e:
            logger.debug(f"设置缓存失败 [{key}]: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否删除成功
        """
        if not self.is_available:
            return False

        try:
            self._client.delete(self._make_key(key))
            return True
        except Exception as e:
            logger.debug(f"删除缓存失败 [{key}]: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """
        根据模式删除缓存

        Args:
            pattern: 键模式，如 "trader:*"

        Returns:
            删除的键数量
        """
        if not self.is_available:
            return 0

        try:
            keys = self._client.keys(self._make_key(pattern))
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.debug(f"批量删除缓存失败 [{pattern}]: {e}")
            return 0

    def get_or_set(self, key: str, getter, ttl: int = None) -> Any:
        """
        获取缓存，如果不存在则调用 getter 获取并缓存

        Args:
            key: 缓存键
            getter: 获取数据的函数
            ttl: 过期时间（秒）

        Returns:
            缓存值或新获取的值
        """
        value = self.get(key)
        if value is not None:
            return value

        # 调用 getter 获取数据
        value = getter()
        if value is not None:
            self.set(key, value, ttl)
        return value

    # ==================== 特定缓存操作 ====================

    def cache_trader(self, address: str, data: dict, ttl: int = 600) -> bool:
        """缓存交易者数据"""
        return self.set(f"trader:{address}", data, ttl)

    def get_trader(self, address: str) -> Optional[dict]:
        """获取交易者缓存"""
        return self.get(f"trader:{address}")

    def invalidate_trader(self, address: str) -> bool:
        """使交易者缓存失效"""
        return self.delete(f"trader:{address}")

    def cache_positions(self, address: str, positions: list, ttl: int = 60) -> bool:
        """缓存持仓数据（较短过期时间）"""
        return self.set(f"positions:{address}", positions, ttl)

    def get_positions(self, address: str) -> Optional[list]:
        """获取持仓缓存"""
        return self.get(f"positions:{address}")

    def cache_top_traders(self, rating: str, traders: list, ttl: int = 300) -> bool:
        """缓存排行榜数据"""
        return self.set(f"top_traders:{rating}", traders, ttl)

    def get_top_traders(self, rating: str) -> Optional[list]:
        """获取排行榜缓存"""
        return self.get(f"top_traders:{rating}")

    def cache_coins(self, coins: list, ttl: int = 3600) -> bool:
        """缓存币种列表（较长过期时间）"""
        return self.set("coins:all", coins, ttl)

    def get_coins(self) -> Optional[list]:
        """获取币种缓存"""
        return self.get("coins:all")


# 全局缓存实例
cache = RedisCache()
