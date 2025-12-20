"""策略模块"""
from .base import BaseStrategy, StrategyConfig, StrategyState
from .examples import (
    SMAStrategy,
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    CombinedStrategy,
    # ETH 合约交易优化策略
    SuperTrendStrategy,
    MomentumBreakoutStrategy,
    TrendFollowingEMAStrategy,
    ScalpingStrategy,
    VWAPMomentumStrategy,
    AdaptiveTrendStrategy
)

__all__ = [
    'BaseStrategy', 'StrategyConfig', 'StrategyState',
    'SMAStrategy', 'RSIStrategy', 'MACDStrategy',
    'BollingerBandsStrategy', 'CombinedStrategy',
    # ETH 合约交易优化策略
    'SuperTrendStrategy',
    'MomentumBreakoutStrategy',
    'TrendFollowingEMAStrategy',
    'ScalpingStrategy',
    'VWAPMomentumStrategy',
    'AdaptiveTrendStrategy'
]

