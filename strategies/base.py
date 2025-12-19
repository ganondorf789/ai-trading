"""
策略基类
定义策略的基本接口和生命周期
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
from loguru import logger

from core.models import (
    OHLCV, OHLCVDataFrame, Signal, SignalType, Position,
    Order, OrderSide, OrderType
)


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str = "BaseStrategy"
    symbols: List[str] = field(default_factory=lambda: ["ETH"])
    timeframe: str = "1h"
    max_positions: int = 1
    position_size_pct: float = 0.1  # 仓位占账户比例
    stop_loss_pct: float = 0.02  # 止损百分比
    take_profit_pct: float = 0.04  # 止盈百分比
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyState:
    """策略状态"""
    is_running: bool = False
    current_positions: List[Position] = field(default_factory=list)
    pending_orders: List[Order] = field(default_factory=list)
    last_signal: Optional[Signal] = None
    last_update: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)


class BaseStrategy(ABC):
    """
    策略基类
    
    所有交易策略都应该继承此类并实现抽象方法
    """
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        初始化策略
        
        Args:
            config: 策略配置
        """
        self.config = config or StrategyConfig()
        self.state = StrategyState()
        self._data: Dict[str, OHLCVDataFrame] = {}
        self._indicators: Dict[str, pd.DataFrame] = {}
        
        logger.info(f"策略初始化: {self.config.name}")
    
    @property
    def name(self) -> str:
        """策略名称"""
        return self.config.name
    
    @abstractmethod
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """
        计算技术指标
        
        Args:
            data: OHLCV 数据
        
        Returns:
            指标字典 {指标名: 指标值Series}
        """
        pass
    
    @abstractmethod
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        """
        生成交易信号
        
        Args:
            data: OHLCV 数据
            indicators: 技术指标
            current_position: 当前持仓
        
        Returns:
            交易信号
        """
        pass
    
    def on_init(self):
        """
        策略初始化回调
        在策略开始运行前调用
        """
        logger.info(f"策略 {self.name} 初始化")
    
    def on_start(self):
        """
        策略启动回调
        """
        self.state.is_running = True
        logger.info(f"策略 {self.name} 启动")
    
    def on_stop(self):
        """
        策略停止回调
        """
        self.state.is_running = False
        logger.info(f"策略 {self.name} 停止")
    
    def on_data(self, symbol: str, data: OHLCVDataFrame):
        """
        新数据回调
        
        Args:
            symbol: 交易对符号
            data: 新的 OHLCV 数据
        """
        self._data[symbol] = data
        self.state.last_update = datetime.now()
    
    def on_order_filled(self, order: Order):
        """
        订单成交回调
        
        Args:
            order: 成交的订单
        """
        logger.info(f"订单成交: {order}")
    
    def on_position_opened(self, position: Position):
        """
        开仓回调
        
        Args:
            position: 新开的仓位
        """
        self.state.current_positions.append(position)
        logger.info(f"开仓: {position}")
    
    def on_position_closed(self, position: Position, pnl: float):
        """
        平仓回调
        
        Args:
            position: 平掉的仓位
            pnl: 盈亏
        """
        if position in self.state.current_positions:
            self.state.current_positions.remove(position)
        logger.info(f"平仓: {position}, PnL: {pnl}")
    
    def update(
        self,
        symbol: str,
        data: OHLCVDataFrame,
        current_position: Optional[Position] = None
    ) -> Signal:
        """
        策略更新
        
        Args:
            symbol: 交易对符号
            data: OHLCV 数据
            current_position: 当前持仓
        
        Returns:
            交易信号
        """
        # 更新数据
        self.on_data(symbol, data)
        
        # 计算指标
        indicators = self.calculate_indicators(data)
        self._indicators[symbol] = pd.DataFrame(indicators)
        
        # 生成信号
        signal = self.generate_signal(data, indicators, current_position)
        self.state.last_signal = signal
        
        return signal
    
    def calculate_position_size(
        self,
        account_value: float,
        price: float,
        risk_per_trade: Optional[float] = None
    ) -> float:
        """
        计算仓位大小
        
        Args:
            account_value: 账户价值
            price: 当前价格
            risk_per_trade: 单笔风险（可选）
        
        Returns:
            仓位大小
        """
        risk = risk_per_trade or self.config.position_size_pct
        position_value = account_value * risk
        size = position_value / price
        return size
    
    def calculate_stop_loss(
        self,
        entry_price: float,
        is_long: bool,
        atr: Optional[float] = None
    ) -> float:
        """
        计算止损价格
        
        Args:
            entry_price: 入场价格
            is_long: 是否做多
            atr: ATR 值（可选，用于动态止损）
        
        Returns:
            止损价格
        """
        if atr:
            stop_distance = atr * 2  # 2倍 ATR
        else:
            stop_distance = entry_price * self.config.stop_loss_pct
        
        if is_long:
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
    
    def calculate_take_profit(
        self,
        entry_price: float,
        is_long: bool,
        risk_reward_ratio: float = 2.0
    ) -> float:
        """
        计算止盈价格
        
        Args:
            entry_price: 入场价格
            is_long: 是否做多
            risk_reward_ratio: 风险回报比
        
        Returns:
            止盈价格
        """
        profit_distance = entry_price * self.config.stop_loss_pct * risk_reward_ratio
        
        if is_long:
            return entry_price + profit_distance
        else:
            return entry_price - profit_distance
    
    def get_indicators(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        获取指标数据
        
        Args:
            symbol: 交易对符号
        
        Returns:
            指标 DataFrame
        """
        return self._indicators.get(symbol)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于序列化）
        """
        return {
            "name": self.name,
            "config": {
                "symbols": self.config.symbols,
                "timeframe": self.config.timeframe,
                "max_positions": self.config.max_positions,
                "position_size_pct": self.config.position_size_pct,
                "stop_loss_pct": self.config.stop_loss_pct,
                "take_profit_pct": self.config.take_profit_pct,
                "params": self.config.params
            },
            "state": {
                "is_running": self.state.is_running,
                "last_update": self.state.last_update.isoformat() if self.state.last_update else None,
                "metrics": self.state.metrics
            }
        }

