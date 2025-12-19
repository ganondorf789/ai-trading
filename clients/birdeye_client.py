"""
Birdeye API 客户端
用于获取历史数据进行回测
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import httpx
from loguru import logger

from core.models import OHLCV, OHLCVDataFrame


class BirdeyeClient:
    """
    Birdeye API 客户端
    
    主要用于获取 Solana 链上代币的历史价格数据
    用于策略回测
    """
    
    # 支持的时间间隔
    INTERVALS = {
        '1m': 60,
        '3m': 180,
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600,
        '2h': 7200,
        '4h': 14400,
        '6h': 21600,
        '12h': 43200,
        '1d': 86400,
    }
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://public-api.birdeye.so",
        timeout: float = 30.0
    ):
        """
        初始化 Birdeye 客户端
        
        Args:
            api_key: Birdeye API Key
            base_url: API 基础 URL
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def headers(self) -> Dict[str, str]:
        """请求头"""
        return {
            "X-API-KEY": self.api_key,
            "Accept": "application/json"
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout
            )
        return self._client
    
    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求
        
        Args:
            method: HTTP 方法
            endpoint: API 端点
            params: 查询参数
            **kwargs: 其他请求参数
        
        Returns:
            响应数据
        """
        client = await self._get_client()
        
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                **kwargs
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('success') is False:
                raise Exception(f"API 错误: {data.get('message', 'Unknown error')}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"请求失败: {e}")
            raise
    
    async def get_token_price(
        self,
        address: str,
        chain: str = "solana"
    ) -> Dict[str, Any]:
        """
        获取代币当前价格
        
        Args:
            address: 代币地址
            chain: 区块链网络
        
        Returns:
            价格数据
        """
        params = {
            "address": address
        }
        data = await self._request(
            "GET",
            f"/defi/price",
            params=params,
            headers={**self.headers, "x-chain": chain}
        )
        return data.get('data', {})
    
    async def get_ohlcv(
        self,
        address: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        chain: str = "solana"
    ) -> List[OHLCV]:
        """
        获取 OHLCV 历史数据
        
        Args:
            address: 代币地址
            interval: 时间间隔 (1m, 5m, 15m, 1h, 4h, 1d 等)
            start_time: 开始时间
            end_time: 结束时间
            chain: 区块链网络
        
        Returns:
            OHLCV 数据列表
        """
        if interval not in self.INTERVALS:
            raise ValueError(f"不支持的时间间隔: {interval}")
        
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=7)
        
        # 转换为 Unix 时间戳
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        params = {
            "address": address,
            "type": interval,
            "time_from": start_ts,
            "time_to": end_ts
        }
        
        data = await self._request(
            "GET",
            "/defi/ohlcv",
            params=params,
            headers={**self.headers, "x-chain": chain}
        )
        
        items = data.get('data', {}).get('items', [])
        ohlcv_list = []
        
        for item in items:
            try:
                ohlcv = OHLCV(
                    timestamp=datetime.fromtimestamp(item['unixTime']),
                    open=float(item.get('o', 0)),
                    high=float(item.get('h', 0)),
                    low=float(item.get('l', 0)),
                    close=float(item.get('c', 0)),
                    volume=float(item.get('v', 0))
                )
                ohlcv_list.append(ohlcv)
            except (KeyError, ValueError) as e:
                logger.warning(f"解析 OHLCV 数据失败: {e}")
                continue
        
        # 按时间排序
        ohlcv_list.sort(key=lambda x: x.timestamp)
        return ohlcv_list
    
    async def get_ohlcv_dataframe(
        self,
        address: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        chain: str = "solana"
    ) -> OHLCVDataFrame:
        """
        获取 OHLCV 数据并返回 DataFrame
        
        Args:
            address: 代币地址
            interval: 时间间隔
            start_time: 开始时间
            end_time: 结束时间
            chain: 区块链网络
        
        Returns:
            OHLCVDataFrame 对象
        """
        ohlcv_list = await self.get_ohlcv(
            address=address,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
            chain=chain
        )
        return OHLCVDataFrame(ohlcv_list)
    
    async def get_historical_price(
        self,
        address: str,
        timestamp: datetime,
        chain: str = "solana"
    ) -> float:
        """
        获取指定时间的历史价格
        
        Args:
            address: 代币地址
            timestamp: 时间点
            chain: 区块链网络
        
        Returns:
            历史价格
        """
        unix_ts = int(timestamp.timestamp())
        
        params = {
            "address": address,
            "address_type": "token",
            "type": unix_ts
        }
        
        data = await self._request(
            "GET",
            "/defi/historical_price_unix",
            params=params,
            headers={**self.headers, "x-chain": chain}
        )
        
        return float(data.get('data', {}).get('value', 0))
    
    async def get_token_info(
        self,
        address: str,
        chain: str = "solana"
    ) -> Dict[str, Any]:
        """
        获取代币信息
        
        Args:
            address: 代币地址
            chain: 区块链网络
        
        Returns:
            代币信息
        """
        params = {
            "address": address
        }
        
        data = await self._request(
            "GET",
            "/defi/token_overview",
            params=params,
            headers={**self.headers, "x-chain": chain}
        )
        
        return data.get('data', {})
    
    async def get_token_trades(
        self,
        address: str,
        limit: int = 100,
        chain: str = "solana"
    ) -> List[Dict[str, Any]]:
        """
        获取代币交易记录
        
        Args:
            address: 代币地址
            limit: 返回数量限制
            chain: 区块链网络
        
        Returns:
            交易记录列表
        """
        params = {
            "address": address,
            "limit": limit
        }
        
        data = await self._request(
            "GET",
            "/defi/txs/token",
            params=params,
            headers={**self.headers, "x-chain": chain}
        )
        
        return data.get('data', {}).get('items', [])


class BirdeyeSyncClient:
    """
    Birdeye 同步客户端
    封装异步客户端，提供同步接口
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://public-api.birdeye.so"
    ):
        """
        初始化同步客户端
        
        Args:
            api_key: Birdeye API Key
            base_url: API 基础 URL
        """
        self._async_client = BirdeyeClient(api_key, base_url)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """获取事件循环"""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop
    
    def _run(self, coro):
        """运行协程"""
        loop = self._get_loop()
        return loop.run_until_complete(coro)
    
    def get_ohlcv(
        self,
        address: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        chain: str = "solana"
    ) -> List[OHLCV]:
        """同步获取 OHLCV 数据"""
        return self._run(self._async_client.get_ohlcv(
            address, interval, start_time, end_time, chain
        ))
    
    def get_ohlcv_dataframe(
        self,
        address: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        chain: str = "solana"
    ) -> OHLCVDataFrame:
        """同步获取 OHLCV DataFrame"""
        return self._run(self._async_client.get_ohlcv_dataframe(
            address, interval, start_time, end_time, chain
        ))
    
    def get_token_price(self, address: str, chain: str = "solana") -> Dict[str, Any]:
        """同步获取代币价格"""
        return self._run(self._async_client.get_token_price(address, chain))
    
    def close(self):
        """关闭客户端"""
        self._run(self._async_client.close())

