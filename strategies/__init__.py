"""策略模块"""
from .base import BaseStrategy, StrategyConfig, StrategyState
from .examples import (
    # 原有基础策略
    SMAStrategy,
    RSIStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    CombinedStrategy,
    # 新增高级策略
    SuperTrendStrategy,
    VolumeBreakoutStrategy,
    MomentumTrendStrategy,
    MeanReversionATRStrategy,
    TripleScreenStrategy,
    SmartMoneyStrategy
)

__all__ = [
    # 基类
    'BaseStrategy', 'StrategyConfig', 'StrategyState',
    # 原有策略
    'SMAStrategy', 'RSIStrategy', 'MACDStrategy',
    'BollingerBandsStrategy', 'CombinedStrategy',
    # 新增高级策略
    'SuperTrendStrategy',
    'VolumeBreakoutStrategy',
    'MomentumTrendStrategy',
    'MeanReversionATRStrategy',
    'TripleScreenStrategy',
    'SmartMoneyStrategy'
]

