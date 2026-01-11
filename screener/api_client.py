"""
API 客户端模块

提供同步和异步的 Hyperliquid API 调用
"""
import time
import asyncio
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

import httpx
from loguru import logger
from hyperliquid.info import Info
from hyperliquid.utils import constants

from .config import APIConfig
from .cache import CacheManager, get_cache_manager
from .exceptions import (
    APIError,
    APIRateLimitError,
    APITimeoutError,
    TraderDataError,
)


class BaseAPIClient(ABC):
    """API 客户端基类"""
    
    @abstractmethod
    def get_user_state(self, address: str) -> Optional[Dict[str, Any]]:
        """获取用户状态"""
        pass
    
    @abstractmethod
    def get_user_fills(self, address: str, limit: int = 0) -> List[Dict]:
        """获取用户成交记录"""
        pass
    
    @abstractmethod
    def get_user_fills_by_time(
        self,
        address: str,
        start_time_ms: int,
        end_time_ms: int
    ) -> List[Dict]:
        """按时间范围获取用户成交记录"""
        pass


class SyncAPIClient(BaseAPIClient):
    """
    同步 API 客户端
    
    基于 hyperliquid-python 库的同步实现
    """
    
    def __init__(
        self,
        config: Optional[APIConfig] = None,
        cache_manager: Optional[CacheManager] = None,
        cache_fills: bool = True
    ):
        """
        初始化同步客户端
        
        Args:
            config: API 配置
            cache_manager: 缓存管理器
            cache_fills: 是否缓存 fills 数据（批量处理时建议关闭以节省内存）
        """
        self.config = config or APIConfig()
        self._cache = cache_manager or get_cache_manager()
        self._cache_fills = cache_fills
        
        # 确定 API URL
        api_url = (
            constants.TESTNET_API_URL 
            if self.config.testnet 
            else self.config.api_url
        )
        self._info = Info(api_url, skip_ws=True)
        
        logger.debug(f"同步 API 客户端初始化完成: {api_url}, 缓存fills: {cache_fills}")
    
    def _call_with_retry(self, func, *args, **kwargs) -> Any:
        """
        带重试的 API 调用
        
        Args:
            func: 要调用的函数
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            API 响应
        
        Raises:
            APIError: API 调用失败
            APIRateLimitError: 频率限制
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # 检查是否是 429 错误
                if "429" in error_str:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    logger.warning(
                        f"请求频率过高，等待 {wait_time}s 后重试 "
                        f"(尝试 {attempt + 1}/{self.config.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                
                # 其他错误
                logger.debug(f"API 调用失败: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                else:
                    raise APIError(str(e))
        
        if last_error:
            if "429" in str(last_error):
                raise APIRateLimitError(self.config.retry_delay)
            raise APIError(str(last_error))
        
        return None
    
    def get_user_state(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取用户状态
        
        Args:
            address: 用户地址
        
        Returns:
            用户状态字典或 None
        """
        # 检查缓存
        cached = self._cache.get('user_state', address)
        if cached is not None:
            return cached
        
        try:
            result = self._call_with_retry(self._info.user_state, address)
            if result:
                self._cache.set('user_state', address, result)
            return result
        except APIError as e:
            logger.debug(f"获取用户状态失败 {address[:10]}...: {e}")
            return None
    
    def get_user_fills(self, address: str, limit: int = 0) -> List[Dict]:
        """
        获取用户成交记录
        
        Args:
            address: 用户地址
            limit: 最大记录数 (0=不限制)
        
        Returns:
            成交记录列表
        """
        # 检查缓存（仅在启用缓存时）
        if self._cache_fills:
            cache_key = f"{address}:{limit}"
            cached = self._cache.get('fills', cache_key)
            if cached is not None:
                return cached
        
        try:
            fills = self._call_with_retry(self._info.user_fills, address)
            if fills is None:
                return []
            
            # 限制数量
            if limit > 0 and len(fills) > limit:
                fills = fills[:limit]
            
            # 仅在启用缓存时缓存数据
            if self._cache_fills:
                cache_key = f"{address}:{limit}"
                self._cache.set('fills', cache_key, fills)
            return fills
        except APIError as e:
            logger.debug(f"获取用户成交记录失败 {address[:10]}...: {e}")
            return []
    
    def get_user_fills_by_time(
        self,
        address: str,
        start_time_ms: int,
        end_time_ms: int
    ) -> List[Dict]:
        """
        按时间范围获取用户成交记录
        
        Args:
            address: 用户地址
            start_time_ms: 开始时间（毫秒）
            end_time_ms: 结束时间（毫秒）
        
        Returns:
            成交记录列表
        """
        # 检查缓存（仅在启用缓存时）
        if self._cache_fills:
            cache_key = f"{address}:{start_time_ms}:{end_time_ms}"
            cached = self._cache.get('fills', cache_key)
            if cached is not None:
                return cached
        
        try:
            fills = self._call_with_retry(
                self._info.user_fills_by_time,
                address,
                start_time_ms,
                end_time_ms
            )
            
            if fills:
                # 仅在启用缓存时缓存数据
                if self._cache_fills:
                    cache_key = f"{address}:{start_time_ms}:{end_time_ms}"
                    self._cache.set('fills', cache_key, fills)
                return fills
            return []
        except APIError as e:
            logger.debug(f"按时间获取成交记录失败 {address[:10]}...: {e}")
            # 回退到普通方法
            time.sleep(self.config.api_call_delay)
            return self.get_user_fills(address)
    
    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """
        获取最近交易
        
        Args:
            symbol: 交易对符号
            limit: 最大记录数
        
        Returns:
            交易记录列表
        """
        try:
            # 注意：hyperliquid-python 可能没有这个方法
            # 这里提供一个占位实现
            if hasattr(self._info, 'recent_trades'):
                trades = self._call_with_retry(self._info.recent_trades, symbol)
                return trades[:limit] if trades else []
            return []
        except Exception as e:
            logger.debug(f"获取最近交易失败 {symbol}: {e}")
            return []
    
    def delay(self) -> None:
        """执行 API 调用延迟"""
        time.sleep(self.config.api_call_delay)


class AsyncAPIClient(BaseAPIClient):
    """
    异步 API 客户端
    
    基于 httpx 的异步实现
    """
    
    def __init__(
        self,
        config: Optional[APIConfig] = None,
        cache_manager: Optional[CacheManager] = None
    ):
        """
        初始化异步客户端
        
        Args:
            config: API 配置
            cache_manager: 缓存管理器
        """
        self.config = config or APIConfig()
        self._cache = cache_manager or get_cache_manager()
        
        # 确定 API URL
        self._base_url = (
            constants.TESTNET_API_URL 
            if self.config.testnet 
            else self.config.api_url
        )
        
        self._client: Optional[httpx.AsyncClient] = None
        
        logger.debug(f"异步 API 客户端初始化完成: {self._base_url}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.read_timeout,
                    write=self.config.read_timeout,
                    pool=self.config.connect_timeout
                ),
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20
                )
            )
        return self._client
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def _post(self, data: Dict[str, Any]) -> Any:
        """
        发送 POST 请求
        
        Args:
            data: 请求数据
        
        Returns:
            响应数据
        """
        client = await self._get_client()
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = await client.post("/info", json=data)
                
                if response.status_code == 429:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    logger.warning(
                        f"请求频率过高，等待 {wait_time}s 后重试 "
                        f"(尝试 {attempt + 1}/{self.config.max_retries})"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.TimeoutException as e:
                last_error = e
                logger.debug(f"请求超时: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    await asyncio.sleep(wait_time)
                else:
                    logger.debug(f"HTTP 错误: {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(self.config.retry_delay)
                    else:
                        raise APIError(str(e), e.response.status_code)
                        
            except Exception as e:
                last_error = e
                logger.debug(f"请求失败: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay)
        
        if last_error:
            if isinstance(last_error, httpx.TimeoutException):
                raise APITimeoutError(self.config.read_timeout)
            raise APIError(str(last_error))
        
        return None
    
    async def get_user_state(self, address: str) -> Optional[Dict[str, Any]]:
        """
        异步获取用户状态
        
        Args:
            address: 用户地址
        
        Returns:
            用户状态字典或 None
        """
        # 检查缓存
        cached = self._cache.get('user_state', address)
        if cached is not None:
            return cached
        
        try:
            result = await self._post({
                "type": "clearinghouseState",
                "user": address
            })
            if result:
                self._cache.set('user_state', address, result)
            return result
        except APIError as e:
            logger.debug(f"获取用户状态失败 {address[:10]}...: {e}")
            return None
    
    async def get_user_fills(self, address: str, limit: int = 0) -> List[Dict]:
        """
        异步获取用户成交记录
        
        Args:
            address: 用户地址
            limit: 最大记录数 (0=不限制)
        
        Returns:
            成交记录列表
        """
        # 检查缓存
        cache_key = f"{address}:{limit}"
        cached = self._cache.get('fills', cache_key)
        if cached is not None:
            return cached
        
        try:
            fills = await self._post({
                "type": "userFills",
                "user": address
            })
            
            if fills is None:
                return []
            
            # 限制数量
            if limit > 0 and len(fills) > limit:
                fills = fills[:limit]
            
            self._cache.set('fills', cache_key, fills)
            return fills
        except APIError as e:
            logger.debug(f"获取用户成交记录失败 {address[:10]}...: {e}")
            return []
    
    async def get_user_fills_by_time(
        self,
        address: str,
        start_time_ms: int,
        end_time_ms: int
    ) -> List[Dict]:
        """
        异步按时间范围获取用户成交记录
        
        Args:
            address: 用户地址
            start_time_ms: 开始时间（毫秒）
            end_time_ms: 结束时间（毫秒）
        
        Returns:
            成交记录列表
        """
        # 检查缓存
        cache_key = f"{address}:{start_time_ms}:{end_time_ms}"
        cached = self._cache.get('fills', cache_key)
        if cached is not None:
            return cached
        
        try:
            fills = await self._post({
                "type": "userFillsByTime",
                "user": address,
                "startTime": start_time_ms,
                "endTime": end_time_ms
            })
            
            if fills:
                self._cache.set('fills', cache_key, fills)
                return fills
            return []
        except APIError as e:
            logger.debug(f"按时间获取成交记录失败 {address[:10]}...: {e}")
            # 回退到普通方法
            await asyncio.sleep(self.config.api_call_delay)
            return await self.get_user_fills(address)
    
    async def delay(self) -> None:
        """执行 API 调用延迟"""
        await asyncio.sleep(self.config.api_call_delay)
    
    # 同步方法的包装（用于兼容 BaseAPIClient）
    def get_user_state_sync(self, address: str) -> Optional[Dict[str, Any]]:
        """同步版本的 get_user_state"""
        return asyncio.get_event_loop().run_until_complete(
            self.get_user_state(address)
        )
    
    def get_user_fills_sync(self, address: str, limit: int = 0) -> List[Dict]:
        """同步版本的 get_user_fills"""
        return asyncio.get_event_loop().run_until_complete(
            self.get_user_fills(address, limit)
        )
    
    def get_user_fills_by_time_sync(
        self,
        address: str,
        start_time_ms: int,
        end_time_ms: int
    ) -> List[Dict]:
        """同步版本的 get_user_fills_by_time"""
        return asyncio.get_event_loop().run_until_complete(
            self.get_user_fills_by_time(address, start_time_ms, end_time_ms)
        )


def create_api_client(
    config: Optional[APIConfig] = None,
    async_mode: bool = False,
    cache_manager: Optional[CacheManager] = None
) -> BaseAPIClient:
    """
    创建 API 客户端
    
    Args:
        config: API 配置
        async_mode: 是否使用异步客户端
        cache_manager: 缓存管理器
    
    Returns:
        API 客户端实例
    """
    if async_mode:
        return AsyncAPIClient(config, cache_manager)
    return SyncAPIClient(config, cache_manager)
