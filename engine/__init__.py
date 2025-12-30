"""交易引擎模块"""
from .backtest import BacktestEngine, BacktestConfig, BacktestResult
from .live import LiveEngine, LiveEngineConfig, LiveEngineState, LiveEngineWithWebSocket
from .copy_trading import (
    CopyTradingConfig,
    MultiTargetCopyTradingBot,
    MultiTargetCopyTradingBotWithWebSocket,
    TargetSubscriptionManager
)

__all__ = [
    'BacktestEngine', 'BacktestConfig', 'BacktestResult',
    'LiveEngine', 'LiveEngineConfig', 'LiveEngineState', 'LiveEngineWithWebSocket',
    'CopyTradingConfig',
    'MultiTargetCopyTradingBot', 'MultiTargetCopyTradingBotWithWebSocket',
    'TargetSubscriptionManager'
]

