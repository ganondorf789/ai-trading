"""
API 客户端模块

提供同步和异步的 Hyperliquid API 调用
"""
import csv
import os
import random
import time
import asyncio
from dataclasses import dataclass
from pathlib import Path
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


@dataclass
class ProxyInfo:
    """代理信息"""
    host: str
    port: int
    username: str
    password: str
    
    @property
    def url(self) -> str:
        """获取代理 URL"""
        return f"http://{self.username}:{self.password}@{self.host}:{self.port}"


class ProxyManager:
    """
    代理管理器
    
    从 CSV 文件加载代理列表，支持随机轮换
    """
    
    # 默认 CSV 文件路径（相对于当前模块）
    DEFAULT_CSV_PATH = Path(__file__).parent / "iproyal-proxies.csv"
    
    def __init__(self, csv_path: Optional[str] = None, enabled: bool = True):
        """
        初始化代理管理器
        
        Args:
            csv_path: CSV 文件路径，默认使用 screener/iproyal-proxies.csv
            enabled: 是否启用代理
        """
        self.enabled = enabled
        self._proxies: List[ProxyInfo] = []
        self._current_index = 0
        
        if enabled:
            path = Path(csv_path) if csv_path else self.DEFAULT_CSV_PATH
            self._load_proxies(path)
            
            if self._proxies:
                logger.info(f"代理管理器初始化完成，加载了 {len(self._proxies)} 个代理")
            else:
                logger.warning("未加载任何代理，将不使用代理")
                self.enabled = False
    
    def _load_proxies(self, csv_path: Path) -> None:
        """从 CSV 文件加载代理列表"""
        if not csv_path.exists():
            logger.warning(f"代理配置文件不存在: {csv_path}")
            return
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        proxy = ProxyInfo(
                            host=row['Host'].strip(),
                            port=int(row['Port'].strip()),
                            username=row['User'].strip(),
                            password=row['Pass'].strip()
                        )
                        self._proxies.append(proxy)
                    except (KeyError, ValueError) as e:
                        logger.warning(f"解析代理行失败: {row}, 错误: {e}")
        except Exception as e:
            logger.error(f"加载代理配置文件失败: {e}")
    
    def get_proxy_by_index(self, index: int) -> Optional[str]:
        """
        根据索引获取代理 URL（用于为每个 worker 分配固定代理）
        
        Args:
            index: worker 索引，会自动取模以循环分配
        
        Returns:
            代理 URL 或 None
        """
        if not self.enabled or not self._proxies:
            return None
        proxy = self._proxies[index % len(self._proxies)]
        return proxy.url
    
    def get_random_proxy(self) -> Optional[str]:
        """获取随机代理 URL"""
        if not self.enabled or not self._proxies:
            return None
        proxy = random.choice(self._proxies)
        return proxy.url
    
    def get_proxy_count(self) -> int:
        """获取代理数量"""
        return len(self._proxies)
    
    @property
    def proxy_url(self) -> Optional[str]:
        """获取代理 URL（兼容旧接口，使用随机选择）"""
        return self.get_random_proxy()


# 全局代理管理器实例
_proxy_manager: Optional[ProxyManager] = None


def get_proxy_manager(csv_path: Optional[str] = None, enabled: bool = True) -> ProxyManager:
    """
    获取或创建全局代理管理器
    
    Args:
        csv_path: CSV 文件路径
        enabled: 是否启用代理
    
    Returns:
        ProxyManager 实例
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(csv_path, enabled)
    return _proxy_manager


def reset_proxy_manager() -> None:
    """重置全局代理管理器"""
    global _proxy_manager
    _proxy_manager = None


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
    
    基于 hyperliquid-python 库或 httpx 的同步实现，支持为每个 worker 分配固定代理
    """
    
    def __init__(
        self,
        config: Optional[APIConfig] = None,
        cache_manager: Optional[CacheManager] = None,
        cache_fills: bool = True,
        proxy_manager: Optional[ProxyManager] = None,
        worker_index: Optional[int] = None
    ):
        """
        初始化同步客户端
        
        Args:
            config: API 配置
            cache_manager: 缓存管理器
            cache_fills: 是否缓存 fills 数据（批量处理时建议关闭以节省内存）
            proxy_manager: 代理管理器（可选，默认使用全局实例）
            worker_index: worker 索引，用于分配固定代理（None 则随机选择）
        """
        self.config = config or APIConfig()
        self._cache = cache_manager or get_cache_manager()
        self._cache_fills = cache_fills
        self._worker_index = worker_index
        
        # 确定 API URL
        self._api_url = (
            constants.TESTNET_API_URL 
            if self.config.testnet 
            else self.config.api_url
        )
        
        # 代理管理器
        self._proxy_manager = proxy_manager or get_proxy_manager(enabled=self.config.proxy_enabled)
        self._use_proxy = self._proxy_manager.enabled and self._proxy_manager.get_proxy_count() > 0
        
        # 根据 worker_index 获取固定代理
        if self._use_proxy:
            if worker_index is not None:
                self._proxy_url = self._proxy_manager.get_proxy_by_index(worker_index)
            else:
                self._proxy_url = self._proxy_manager.get_random_proxy()
            # 使用 httpx 同步客户端（支持代理）
            self._info = None
            self._http_client: Optional[httpx.Client] = None
            proxy_status = f"代理: {self._proxy_url.split('@')[1] if self._proxy_url and '@' in self._proxy_url else 'N/A'}"
        else:
            self._proxy_url = None
            # 使用 hyperliquid-python 库（无代理时）
            self._info = Info(self._api_url, skip_ws=True)
            self._http_client = None
            proxy_status = "无代理"
        
        logger.debug(f"同步 API 客户端初始化完成: {self._api_url}, {proxy_status}, 缓存fills: {cache_fills}")
    
    def _get_http_client(self) -> httpx.Client:
        """获取或创建 HTTP 同步客户端（代理模式）"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.Client(
                base_url=self._api_url,
                proxy=self._proxy_url,
                timeout=httpx.Timeout(
                    connect=self.config.connect_timeout,
                    read=self.config.read_timeout,
                    write=self.config.read_timeout,
                    pool=self.config.connect_timeout
                )
            )
        return self._http_client
    
    def _post_with_proxy(self, data: Dict[str, Any]) -> Any:
        """使用代理发送 POST 请求"""
        client = self._get_http_client()
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                response = client.post("/info", json=data)
                
                if response.status_code == 429:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    logger.warning(
                        f"请求频率过高，等待 {wait_time}s 后重试 "
                        f"(尝试 {attempt + 1}/{self.config.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.TimeoutException as e:
                last_error = e
                logger.debug(f"请求超时: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
                    
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    time.sleep(wait_time)
                else:
                    logger.debug(f"HTTP 错误: {e}")
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise APIError(str(e), e.response.status_code)
                        
            except Exception as e:
                last_error = e
                logger.debug(f"请求失败: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay)
        
        if last_error:
            if isinstance(last_error, httpx.TimeoutException):
                raise APITimeoutError(self.config.read_timeout)
            raise APIError(str(last_error))
        
        return None
    
    def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._http_client and not self._http_client.is_closed:
            self._http_client.close()
            self._http_client = None
    
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
            if self._use_proxy:
                result = self._post_with_proxy({
                    "type": "clearinghouseState",
                    "user": address
                })
            else:
                result = self._call_with_retry(self._info.user_state, address)
            if result:
                self._cache.set('user_state', address, result)
            return result
        except APIError as e:
            logger.debug(f"获取用户状态失败 {address[:10]}...: {e}")
            return None
    
    def get_portfolio(self, address: str) -> Optional[List]:
        """
        获取用户 portfolio 数据（含各周期 PnL 和账户价值历史）

        Args:
            address: 用户地址

        Returns:
            [[period, {accountValueHistory, pnlHistory, vlm}], ...] 或 None
        """
        data = {"type": "portfolio", "user": address}
        try:
            if self._use_proxy:
                return self._post_with_proxy(data)
            else:
                # portfolio 不在 hyperliquid-python 库中，直接用 HTTP
                import httpx as _httpx
                response = _httpx.post(
                    f"{self._api_url}/info", json=data,
                    timeout=self.config.read_timeout
                )
                response.raise_for_status()
                return response.json()
        except APIError as e:
            logger.debug(f"获取 portfolio 失败 {address[:10]}...: {e}")
            return None
        except Exception as e:
            logger.debug(f"获取 portfolio 失败 {address[:10]}...: {e}")
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
            if self._use_proxy:
                fills = self._post_with_proxy({
                    "type": "userFills",
                    "user": address
                })
            else:
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
            if self._use_proxy:
                fills = self._post_with_proxy({
                    "type": "userFillsByTime",
                    "user": address,
                    "startTime": start_time_ms,
                    "endTime": end_time_ms
                })
            else:
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
            if self.config.api_call_delay > 0:
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
    
    def get_user_funding_history(
        self,
        address: str,
        start_time_ms: int,
        end_time_ms: int = None
    ) -> List[Dict]:
        """
        获取用户资金费历史

        Args:
            address: 用户地址
            start_time_ms: 开始时间（毫秒）
            end_time_ms: 结束时间（毫秒），默认当前时间

        Returns:
            资金费记录列表
        """
        try:
            if self._use_proxy:
                data = {
                    "type": "userFunding",
                    "user": address,
                    "startTime": start_time_ms,
                }
                if end_time_ms is not None:
                    data["endTime"] = end_time_ms
                result = self._post_with_proxy(data)
            else:
                if end_time_ms is not None:
                    result = self._call_with_retry(
                        self._info.user_funding_history,
                        address, start_time_ms, end_time_ms
                    )
                else:
                    result = self._call_with_retry(
                        self._info.user_funding_history,
                        address, start_time_ms
                    )
            return result if result else []
        except APIError as e:
            logger.debug(f"获取资金费历史失败 {address[:10]}...: {e}")
            return []

    def get_historical_orders(self, address: str) -> List[Dict]:
        """
        获取用户历史委托（最多返回 2000 条最近的记录）

        Args:
            address: 用户地址

        Returns:
            历史委托列表
        """
        try:
            if self._use_proxy:
                result = self._post_with_proxy({
                    "type": "historicalOrders",
                    "user": address,
                })
            else:
                result = self._call_with_retry(
                    self._info.historical_orders,
                    address
                )
            return result if result else []
        except APIError as e:
            logger.debug(f"获取历史委托失败 {address[:10]}...: {e}")
            return []

    def get_user_non_funding_ledger(
        self,
        address: str,
        start_time_ms: int,
        end_time_ms: int = None
    ) -> List[Dict]:
        """
        获取用户非资金费账本更新（存款、提款、转账、清算等）

        Args:
            address: 用户地址
            start_time_ms: 开始时间（毫秒）
            end_time_ms: 结束时间（毫秒），默认当前时间

        Returns:
            账本记录列表
        """
        try:
            if self._use_proxy:
                data = {
                    "type": "userNonFundingLedgerUpdates",
                    "user": address,
                    "startTime": start_time_ms,
                }
                if end_time_ms is not None:
                    data["endTime"] = end_time_ms
                result = self._post_with_proxy(data)
            else:
                if end_time_ms is not None:
                    result = self._call_with_retry(
                        self._info.user_non_funding_ledger_updates,
                        address, start_time_ms, end_time_ms
                    )
                else:
                    result = self._call_with_retry(
                        self._info.user_non_funding_ledger_updates,
                        address, start_time_ms
                    )
            return result if result else []
        except APIError as e:
            logger.debug(f"获取账本更新失败 {address[:10]}...: {e}")
            return []

    def delay(self) -> None:
        """执行 API 调用延迟"""
        if self.config.api_call_delay > 0:
            time.sleep(self.config.api_call_delay)


class AsyncAPIClient(BaseAPIClient):
    """
    异步 API 客户端
    
    基于 httpx 的异步实现，支持为每个 worker 分配固定代理
    """
    
    def __init__(
        self,
        config: Optional[APIConfig] = None,
        cache_manager: Optional[CacheManager] = None,
        proxy_manager: Optional[ProxyManager] = None,
        worker_index: Optional[int] = None
    ):
        """
        初始化异步客户端
        
        Args:
            config: API 配置
            cache_manager: 缓存管理器
            proxy_manager: 代理管理器（可选，默认使用全局实例）
            worker_index: worker 索引，用于分配固定代理（None 则随机选择）
        """
        self.config = config or APIConfig()
        self._cache = cache_manager or get_cache_manager()
        self._worker_index = worker_index
        
        # 确定 API URL
        self._base_url = (
            constants.TESTNET_API_URL 
            if self.config.testnet 
            else self.config.api_url
        )
        
        self._client: Optional[httpx.AsyncClient] = None
        
        # 代理管理器
        self._proxy_manager = proxy_manager or get_proxy_manager(enabled=self.config.proxy_enabled)
        self._use_proxy = self._proxy_manager.enabled and self._proxy_manager.get_proxy_count() > 0
        
        # 根据 worker_index 获取固定代理
        if self._use_proxy:
            if worker_index is not None:
                self._proxy_url = self._proxy_manager.get_proxy_by_index(worker_index)
            else:
                self._proxy_url = self._proxy_manager.get_random_proxy()
            proxy_status = f"代理: {self._proxy_url.split('@')[1] if self._proxy_url and '@' in self._proxy_url else 'N/A'}"
        else:
            self._proxy_url = None
            proxy_status = "无代理"
        
        logger.debug(f"异步 API 客户端初始化完成: {self._base_url}, {proxy_status}")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                proxy=self._proxy_url,
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
            if self.config.api_call_delay > 0:
                await asyncio.sleep(self.config.api_call_delay)
            return await self.get_user_fills(address)
    
    async def delay(self) -> None:
        """执行 API 调用延迟"""
        if self.config.api_call_delay > 0:
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
