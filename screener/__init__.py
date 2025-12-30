"""
Hyperliquid 交易者筛选模块
自动发现和筛选优质交易者地址

使用示例:
    from screener import TraderScreener, ScreenerConfig
    
    # 创建筛选器
    config = ScreenerConfig(min_win_rate=0.5, min_profit_factor=1.5)
    screener = TraderScreener(config)
    
    # 分析交易者
    metrics = screener.analyze_trader("0x...")
    
    # 批量筛选
    qualified = screener.screen_traders(["0x...", "0x..."])
"""

from screener.trader_screener import (
    TraderScreener,
    TraderMetrics,
    ScreenerConfig,
    QualityRating,
    discover_active_traders
)
from screener.address_sources import AddressSource

__all__ = [
    'TraderScreener',
    'TraderMetrics', 
    'ScreenerConfig',
    'QualityRating',
    'AddressSource',
    'discover_active_traders'
]

