"""
交易者地址数据源
从多个来源获取候选交易者地址
"""
import json
import requests
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

from hyperliquid.info import Info
from hyperliquid.utils import constants


class AddressSource:
    """
    交易者地址数据源管理器
    
    支持多种获取候选地址的方式：
    - 从文件加载
    - 从 Hyperliquid API 获取
    - 手动添加
    """
    
    def __init__(
        self,
        api_url: str = constants.MAINNET_API_URL,
        testnet: bool = False
    ):
        """
        初始化地址源
        
        Args:
            api_url: Hyperliquid API URL
            testnet: 是否使用测试网
        """
        self.api_url = constants.TESTNET_API_URL if testnet else api_url
        self.info = Info(self.api_url, skip_ws=True)
        
        self._addresses: List[str] = []
        self._address_info: Dict[str, Dict] = {}
    
    def add_address(self, address: str, info: Optional[Dict] = None):
        """
        添加单个地址
        
        Args:
            address: 交易者地址
            info: 附加信息
        """
        if address and address not in self._addresses:
            self._addresses.append(address)
            if info:
                self._address_info[address] = info
    
    def add_addresses(self, addresses: List[str]):
        """
        添加多个地址
        
        Args:
            addresses: 地址列表
        """
        for addr in addresses:
            self.add_address(addr)
    
    def load_from_file(self, filepath: str) -> int:
        """
        从文件加载地址
        
        支持格式：
        - JSON 文件 (列表或带 addresses 键的对象)
        - 文本文件 (每行一个地址)
        
        Args:
            filepath: 文件路径
        
        Returns:
            加载的地址数量
        """
        path = Path(filepath)
        
        if not path.exists():
            logger.warning(f"文件不存在: {filepath}")
            return 0
        
        count_before = len(self._addresses)
        
        if path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if isinstance(data, list):
                # 直接是地址列表
                for item in data:
                    if isinstance(item, str):
                        self.add_address(item)
                    elif isinstance(item, dict) and 'address' in item:
                        self.add_address(item['address'], item)
            elif isinstance(data, dict):
                # 包含 addresses 键
                addresses = data.get('addresses', data.get('traders', []))
                for item in addresses:
                    if isinstance(item, str):
                        self.add_address(item)
                    elif isinstance(item, dict) and 'address' in item:
                        self.add_address(item['address'], item)
        else:
            # 文本文件，每行一个地址
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    addr = line.strip()
                    if addr and addr.startswith('0x'):
                        self.add_address(addr)
        
        count_added = len(self._addresses) - count_before
        logger.info(f"从 {filepath} 加载了 {count_added} 个地址")
        
        return count_added
    
    def save_to_file(self, filepath: str):
        """
        保存地址到文件
        
        Args:
            filepath: 文件路径
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        output = {
            "timestamp": datetime.now().isoformat(),
            "count": len(self._addresses),
            "addresses": [
                {
                    "address": addr,
                    **(self._address_info.get(addr, {}))
                }
                for addr in self._addresses
            ]
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"已保存 {len(self._addresses)} 个地址到 {filepath}")
    
    def discover_from_fills(
        self,
        symbols: List[str] = None,
        limit: int = 100
    ) -> int:
        """
        从公开交易数据发现活跃交易者
        
        注意：此功能需要 Hyperliquid 支持公开交易流 API
        
        Args:
            symbols: 要监控的交易对
            limit: 每个交易对获取的交易数
        
        Returns:
            发现的地址数量
        """
        # Hyperliquid 目前没有公开的全局交易流 API
        # 这里预留接口，可以通过其他方式实现
        logger.info("发现活跃交易者功能暂未实现，请手动添加地址")
        return 0
    
    def discover_from_positions(
        self,
        min_position_value: float = 10000.0
    ) -> int:
        """
        从大持仓发现交易者
        
        注意：需要遍历大量地址，可能需要其他数据源
        
        Args:
            min_position_value: 最小持仓价值（美元）
        
        Returns:
            发现的地址数量
        """
        logger.info("从持仓发现交易者功能暂未实现，请手动添加地址")
        return 0
    
    def get_well_known_traders(self) -> List[str]:
        """
        获取知名交易者地址
        
        这些是社区公认的优质交易者
        需要定期更新
        
        Returns:
            知名交易者地址列表
        """
        # 这里可以维护一个知名交易者列表
        # 数据来源：Hyperliquid Discord、Twitter、排行榜等
        well_known = []
        
        # 添加到地址列表
        for addr in well_known:
            self.add_address(addr, {"source": "well_known"})
        
        return well_known
    
    def filter_by_activity(
        self,
        min_trades: int = 10,
        lookback_days: int = 30
    ) -> List[str]:
        """
        按活跃度过滤地址
        
        Args:
            min_trades: 最小交易次数
            lookback_days: 回溯天数
        
        Returns:
            活跃地址列表
        """
        active_addresses = []
        start_time = datetime.now() - timedelta(days=lookback_days)
        start_ms = int(start_time.timestamp() * 1000)
        
        for addr in self._addresses:
            try:
                fills = self.info.user_fills_by_time(
                    addr,
                    start_ms,
                    int(datetime.now().timestamp() * 1000)
                )
                
                if len(fills) >= min_trades:
                    active_addresses.append(addr)
                    
            except Exception as e:
                logger.debug(f"检查地址活跃度失败: {addr[:10]}...: {e}")
        
        logger.info(f"活跃地址: {len(active_addresses)}/{len(self._addresses)}")
        
        return active_addresses
    
    def get_addresses(self) -> List[str]:
        """
        获取所有地址
        
        Returns:
            地址列表
        """
        return self._addresses.copy()
    
    def clear(self):
        """清空所有地址"""
        self._addresses.clear()
        self._address_info.clear()
    
    def __len__(self) -> int:
        return len(self._addresses)
    
    def __iter__(self):
        return iter(self._addresses)


# 预定义的一些公开地址（来自公开信息，仅供参考）
# 实际使用时建议自己收集和验证
SAMPLE_ADDRESSES = [
    # 这里可以添加一些公开的交易者地址作为示例
    # 注意：不要添加私人信息
]

