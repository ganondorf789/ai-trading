"""
缓存管理模块
"""
import time
from typing import Dict, Any, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from threading import RLock
from loguru import logger

from .config import CacheConfig
from .exceptions import CacheError

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    value: T
    created_at: float
    ttl: int
    hits: int = 0
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.created_at > self.ttl
    
    def get(self) -> T:
        """获取值并更新访问计数"""
        self.hits += 1
        return self.value


class TTLCache(Generic[T]):
    """
    带 TTL 的缓存
    
    线程安全的缓存实现，支持自动过期和 LRU 淘汰
    """
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            ttl: 默认 TTL（秒）
        """
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._max_size = max_size
        self._default_ttl = ttl
        self._lock = RLock()
        self._stats = CacheStats()
    
    def get(self, key: str) -> Optional[T]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
        
        Returns:
            缓存值或 None
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                self._stats.expirations += 1
                return None
            
            self._stats.hits += 1
            return entry.get()
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒），None 使用默认值
        """
        with self._lock:
            # 检查容量
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict()
            
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl if ttl is not None else self._default_ttl
            )
            self._stats.sets += 1
    
    def delete(self, key: str) -> bool:
        """
        删除缓存条目
        
        Args:
            key: 缓存键
        
        Returns:
            是否删除成功
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.deletes += 1
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._stats.clears += 1
    
    def _evict(self) -> None:
        """淘汰过期和最少使用的条目"""
        # 首先清理过期条目
        now = time.time()
        expired_keys = [
            k for k, v in self._cache.items()
            if v.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]
            self._stats.evictions += 1
        
        # 如果仍然超出容量，淘汰最少使用的
        if len(self._cache) >= self._max_size:
            # 按访问次数排序，淘汰最少访问的
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: (x[1].hits, -x[1].created_at)
            )
            # 淘汰 10% 的条目
            evict_count = max(1, self._max_size // 10)
            for key, _ in sorted_items[:evict_count]:
                del self._cache[key]
                self._stats.evictions += 1
    
    def __contains__(self, key: str) -> bool:
        """检查键是否存在（不更新统计）"""
        with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired()
    
    def __len__(self) -> int:
        """返回缓存条目数"""
        return len(self._cache)
    
    @property
    def stats(self) -> 'CacheStats':
        """获取缓存统计"""
        return self._stats


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    expirations: int = 0
    clears: int = 0
    
    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'sets': self.sets,
            'deletes': self.deletes,
            'evictions': self.evictions,
            'expirations': self.expirations,
            'clears': self.clears,
            'hit_rate': self.hit_rate,
        }


class CacheManager:
    """
    缓存管理器
    
    管理多个命名空间的缓存
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        初始化缓存管理器
        
        Args:
            config: 缓存配置
        """
        self.config = config or CacheConfig()
        self._enabled = self.config.enabled
        self._caches: Dict[str, TTLCache] = {}
        self._lock = RLock()
        
        # 初始化默认缓存
        if self._enabled:
            self._init_default_caches()
    
    def _init_default_caches(self) -> None:
        """初始化默认缓存"""
        self._caches['metrics'] = TTLCache(
            max_size=self.config.max_size,
            ttl=self.config.metrics_ttl
        )
        self._caches['user_state'] = TTLCache(
            max_size=self.config.max_size // 2,
            ttl=self.config.user_state_ttl
        )
        self._caches['fills'] = TTLCache(
            max_size=self.config.max_size,
            ttl=self.config.metrics_ttl
        )
    
    def get_cache(self, namespace: str) -> TTLCache:
        """
        获取指定命名空间的缓存
        
        Args:
            namespace: 缓存命名空间
        
        Returns:
            TTLCache 实例
        """
        with self._lock:
            if namespace not in self._caches:
                self._caches[namespace] = TTLCache(
                    max_size=self.config.max_size,
                    ttl=self.config.metrics_ttl
                )
            return self._caches[namespace]
    
    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            namespace: 缓存命名空间
            key: 缓存键
        
        Returns:
            缓存值或 None
        """
        if not self._enabled:
            return None
        return self.get_cache(namespace).get(key)
    
    def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        设置缓存值
        
        Args:
            namespace: 缓存命名空间
            key: 缓存键
            value: 缓存值
            ttl: TTL（秒）
        """
        if not self._enabled:
            return
        self.get_cache(namespace).set(key, value, ttl)
    
    def delete(self, namespace: str, key: str) -> bool:
        """删除缓存条目"""
        if not self._enabled:
            return False
        return self.get_cache(namespace).delete(key)
    
    def clear(self, namespace: Optional[str] = None) -> None:
        """
        清空缓存
        
        Args:
            namespace: 缓存命名空间，None 清空所有
        """
        with self._lock:
            if namespace:
                if namespace in self._caches:
                    self._caches[namespace].clear()
            else:
                for cache in self._caches.values():
                    cache.clear()
    
    def enable(self) -> None:
        """启用缓存"""
        self._enabled = True
        if not self._caches:
            self._init_default_caches()
        logger.debug("缓存已启用")
    
    def disable(self) -> None:
        """禁用缓存"""
        self._enabled = False
        self.clear()
        logger.debug("缓存已禁用")
    
    @property
    def enabled(self) -> bool:
        """缓存是否启用"""
        return self._enabled
    
    def get_stats(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        获取缓存统计
        
        Args:
            namespace: 缓存命名空间，None 返回所有
        
        Returns:
            统计信息字典
        """
        with self._lock:
            if namespace:
                if namespace in self._caches:
                    return {
                        namespace: {
                            'size': len(self._caches[namespace]),
                            **self._caches[namespace].stats.to_dict()
                        }
                    }
                return {}
            
            return {
                name: {
                    'size': len(cache),
                    **cache.stats.to_dict()
                }
                for name, cache in self._caches.items()
            }


# 全局缓存管理器实例
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager(config: Optional[CacheConfig] = None) -> CacheManager:
    """
    获取全局缓存管理器
    
    Args:
        config: 缓存配置（仅在首次调用时生效）
    
    Returns:
        CacheManager 实例
    """
    global _global_cache_manager
    
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(config)
    
    return _global_cache_manager


def reset_cache_manager() -> None:
    """重置全局缓存管理器"""
    global _global_cache_manager
    
    if _global_cache_manager:
        _global_cache_manager.clear()
    _global_cache_manager = None
