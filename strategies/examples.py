"""
示例交易策略
包含几种常见的交易策略实现
"""
from typing import Dict, Optional
import pandas as pd
import numpy as np
from loguru import logger

from core.models import OHLCVDataFrame, Signal, SignalType, Position, PositionSide
from strategies.base import BaseStrategy, StrategyConfig


class SMAStrategy(BaseStrategy):
    """
    简单移动平均线交叉策略
    
    当快线上穿慢线时做多，下穿时做空
    """
    
    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 30,
        config: Optional[StrategyConfig] = None
    ):
        """
        初始化
        
        Args:
            fast_period: 快线周期
            slow_period: 慢线周期
            config: 策略配置
        """
        config = config or StrategyConfig(name="SMA_CrossOver")
        config.params.update({
            "fast_period": fast_period,
            "slow_period": slow_period
        })
        super().__init__(config)
        
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """计算 SMA 指标"""
        df = data.df
        
        sma_fast = df['close'].rolling(window=self.fast_period).mean()
        sma_slow = df['close'].rolling(window=self.slow_period).mean()
        
        return {
            "sma_fast": sma_fast,
            "sma_slow": sma_slow
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        """生成交易信号"""
        sma_fast = indicators["sma_fast"]
        sma_slow = indicators["sma_slow"]
        
        if len(sma_fast) < 2:
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        # 当前和前一根 K 线的指标值
        fast_current = sma_fast.iloc[-1]
        fast_prev = sma_fast.iloc[-2]
        slow_current = sma_slow.iloc[-1]
        slow_prev = sma_slow.iloc[-2]
        
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        
        # 金叉 - 做多信号
        if fast_prev <= slow_prev and fast_current > slow_current:
            if current_position is None or current_position.side == PositionSide.SHORT:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1.0,
                    stop_loss=self.calculate_stop_loss(current_price, True),
                    take_profit=self.calculate_take_profit(current_price, True),
                    metadata={"reason": "SMA golden cross"}
                )
        
        # 死叉 - 做空信号
        elif fast_prev >= slow_prev and fast_current < slow_current:
            if current_position is None or current_position.side == PositionSide.LONG:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1.0,
                    stop_loss=self.calculate_stop_loss(current_price, False),
                    take_profit=self.calculate_take_profit(current_price, False),
                    metadata={"reason": "SMA death cross"}
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class RSIStrategy(BaseStrategy):
    """
    RSI 超买超卖策略
    
    RSI 低于超卖线时做多，高于超买线时做空
    """
    
    def __init__(
        self,
        period: int = 14,
        overbought: float = 70,
        oversold: float = 30,
        config: Optional[StrategyConfig] = None
    ):
        """
        初始化
        
        Args:
            period: RSI 周期
            overbought: 超买阈值
            oversold: 超卖阈值
            config: 策略配置
        """
        config = config or StrategyConfig(name="RSI_Strategy")
        config.params.update({
            "period": period,
            "overbought": overbought,
            "oversold": oversold
        })
        super().__init__(config)
        
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """计算 RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """计算 RSI 指标"""
        df = data.df
        rsi = self.calculate_rsi(df['close'], self.period)
        
        return {
            "rsi": rsi
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        """生成交易信号"""
        rsi = indicators["rsi"]
        
        if len(rsi) < 2 or pd.isna(rsi.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        
        # RSI 从超卖区反弹 - 做多
        if prev_rsi < self.oversold and current_rsi >= self.oversold:
            if current_position is None:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=(self.oversold - prev_rsi) / self.oversold,
                    stop_loss=self.calculate_stop_loss(current_price, True),
                    take_profit=self.calculate_take_profit(current_price, True),
                    metadata={"reason": f"RSI oversold bounce", "rsi": current_rsi}
                )
        
        # RSI 从超买区回落 - 做空
        elif prev_rsi > self.overbought and current_rsi <= self.overbought:
            if current_position is None:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=(prev_rsi - self.overbought) / (100 - self.overbought),
                    stop_loss=self.calculate_stop_loss(current_price, False),
                    take_profit=self.calculate_take_profit(current_price, False),
                    metadata={"reason": f"RSI overbought pullback", "rsi": current_rsi}
                )
        
        # 如果持有多仓且 RSI 超买，平仓
        if current_position and current_position.side == PositionSide.LONG:
            if current_rsi > self.overbought:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "RSI overbought, close long"}
                )
        
        # 如果持有空仓且 RSI 超卖，平仓
        if current_position and current_position.side == PositionSide.SHORT:
            if current_rsi < self.oversold:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "RSI oversold, close short"}
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class MACDStrategy(BaseStrategy):
    """
    MACD 策略
    
    MACD 线上穿信号线时做多，下穿时做空
    """
    
    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        config: Optional[StrategyConfig] = None
    ):
        """
        初始化
        
        Args:
            fast_period: 快线 EMA 周期
            slow_period: 慢线 EMA 周期
            signal_period: 信号线周期
            config: 策略配置
        """
        config = config or StrategyConfig(name="MACD_Strategy")
        config.params.update({
            "fast_period": fast_period,
            "slow_period": slow_period,
            "signal_period": signal_period
        })
        super().__init__(config)
        
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """计算 MACD 指标"""
        df = data.df
        
        ema_fast = df['close'].ewm(span=self.fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow_period, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        """生成交易信号"""
        macd = indicators["macd"]
        signal = indicators["signal"]
        histogram = indicators["histogram"]
        
        if len(macd) < 2:
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        
        # MACD 上穿信号线 - 做多
        if macd.iloc[-2] <= signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]:
            if current_position is None or current_position.side == PositionSide.SHORT:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(abs(histogram.iloc[-1]) / current_price * 100, 1.0),
                    stop_loss=self.calculate_stop_loss(current_price, True),
                    take_profit=self.calculate_take_profit(current_price, True),
                    metadata={"reason": "MACD bullish cross", "histogram": histogram.iloc[-1]}
                )
        
        # MACD 下穿信号线 - 做空
        elif macd.iloc[-2] >= signal.iloc[-2] and macd.iloc[-1] < signal.iloc[-1]:
            if current_position is None or current_position.side == PositionSide.LONG:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(abs(histogram.iloc[-1]) / current_price * 100, 1.0),
                    stop_loss=self.calculate_stop_loss(current_price, False),
                    take_profit=self.calculate_take_profit(current_price, False),
                    metadata={"reason": "MACD bearish cross", "histogram": histogram.iloc[-1]}
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class BollingerBandsStrategy(BaseStrategy):
    """
    布林带策略
    
    价格触及下轨时做多，触及上轨时做空
    """
    
    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        config: Optional[StrategyConfig] = None
    ):
        """
        初始化
        
        Args:
            period: 布林带周期
            std_dev: 标准差倍数
            config: 策略配置
        """
        config = config or StrategyConfig(name="BollingerBands_Strategy")
        config.params.update({
            "period": period,
            "std_dev": std_dev
        })
        super().__init__(config)
        
        self.period = period
        self.std_dev = std_dev
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """计算布林带指标"""
        df = data.df
        
        middle = df['close'].rolling(window=self.period).mean()
        std = df['close'].rolling(window=self.period).std()
        
        upper = middle + (std * self.std_dev)
        lower = middle - (std * self.std_dev)
        
        # 计算 %B 指标
        percent_b = (df['close'] - lower) / (upper - lower)
        
        return {
            "middle": middle,
            "upper": upper,
            "lower": lower,
            "percent_b": percent_b
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        """生成交易信号"""
        upper = indicators["upper"]
        lower = indicators["lower"]
        percent_b = indicators["percent_b"]
        
        if pd.isna(upper.iloc[-1]) or pd.isna(lower.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        
        # 价格跌破下轨 - 做多（超卖反弹）
        if current_price <= lower.iloc[-1]:
            if current_position is None:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1 - percent_b.iloc[-1] if percent_b.iloc[-1] < 0 else 0.5,
                    stop_loss=self.calculate_stop_loss(current_price, True),
                    take_profit=self.calculate_take_profit(current_price, True),
                    metadata={"reason": "Price touched lower band", "percent_b": percent_b.iloc[-1]}
                )
        
        # 价格突破上轨 - 做空（超买回调）
        elif current_price >= upper.iloc[-1]:
            if current_position is None:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=percent_b.iloc[-1] - 1 if percent_b.iloc[-1] > 1 else 0.5,
                    stop_loss=self.calculate_stop_loss(current_price, False),
                    take_profit=self.calculate_take_profit(current_price, False),
                    metadata={"reason": "Price touched upper band", "percent_b": percent_b.iloc[-1]}
                )
        
        # 持有多仓，价格回到中轨，平仓
        if current_position and current_position.side == PositionSide.LONG:
            if current_price >= indicators["middle"].iloc[-1]:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Price returned to middle band"}
                )
        
        # 持有空仓，价格回到中轨，平仓
        if current_position and current_position.side == PositionSide.SHORT:
            if current_price <= indicators["middle"].iloc[-1]:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Price returned to middle band"}
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class CombinedStrategy(BaseStrategy):
    """
    组合策略
    
    结合多个策略信号进行决策
    """
    
    def __init__(
        self,
        strategies: list,
        min_agreement: int = 2,
        config: Optional[StrategyConfig] = None
    ):
        """
        初始化
        
        Args:
            strategies: 子策略列表
            min_agreement: 最小一致信号数量
            config: 策略配置
        """
        config = config or StrategyConfig(name="Combined_Strategy")
        super().__init__(config)
        
        self.strategies = strategies
        self.min_agreement = min_agreement
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """计算所有子策略的指标"""
        all_indicators = {}
        
        for i, strategy in enumerate(self.strategies):
            indicators = strategy.calculate_indicators(data)
            for name, series in indicators.items():
                all_indicators[f"{strategy.name}_{name}"] = series
        
        return all_indicators
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        """生成组合信号"""
        buy_count = 0
        sell_count = 0
        close_count = 0
        
        for strategy in self.strategies:
            strategy_indicators = strategy.calculate_indicators(data)
            signal = strategy.generate_signal(data, strategy_indicators, current_position)
            
            if signal.signal_type == SignalType.BUY:
                buy_count += 1
            elif signal.signal_type == SignalType.SELL:
                sell_count += 1
            elif signal.signal_type == SignalType.CLOSE:
                close_count += 1
        
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        
        # 如果足够多的策略同意平仓
        if close_count >= self.min_agreement:
            return Signal(
                signal_type=SignalType.CLOSE,
                symbol=self.config.symbols[0],
                price=current_price,
                timestamp=timestamp,
                metadata={"close_votes": close_count}
            )
        
        # 如果足够多的策略同意做多
        if buy_count >= self.min_agreement:
            return Signal(
                signal_type=SignalType.BUY,
                symbol=self.config.symbols[0],
                price=current_price,
                timestamp=timestamp,
                strength=buy_count / len(self.strategies),
                stop_loss=self.calculate_stop_loss(current_price, True),
                take_profit=self.calculate_take_profit(current_price, True),
                metadata={"buy_votes": buy_count}
            )
        
        # 如果足够多的策略同意做空
        if sell_count >= self.min_agreement:
            return Signal(
                signal_type=SignalType.SELL,
                symbol=self.config.symbols[0],
                price=current_price,
                timestamp=timestamp,
                strength=sell_count / len(self.strategies),
                stop_loss=self.calculate_stop_loss(current_price, False),
                take_profit=self.calculate_take_profit(current_price, False),
                metadata={"sell_votes": sell_count}
            )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )

