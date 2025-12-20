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


# ============================================================
# 以下是针对 ETH 合约交易优化的高收益策略
# ============================================================


class SuperTrendStrategy(BaseStrategy):
    """
    SuperTrend 策略 - 适合 ETH 等高波动加密货币

    使用 ATR 动态计算趋势线，价格突破趋势线时产生信号
    特点：趋势跟踪能力强，能捕捉大行情
    推荐时间周期：1h, 4h
    """

    def __init__(
        self,
        atr_period: int = 10,
        multiplier: float = 3.0,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(name="SuperTrend_Strategy")
        config.params.update({
            "atr_period": atr_period,
            "multiplier": multiplier
        })
        # 针对高波动市场调整止损止盈
        config.stop_loss_pct = 0.03  # 3% 止损
        config.take_profit_pct = 0.09  # 9% 止盈 (3:1 盈亏比)
        super().__init__(config)

        self.atr_period = atr_period
        self.multiplier = multiplier

    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算 ATR"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        """计算 SuperTrend 指标 (NumPy 向量化优化版)"""
        df = data.df
        n = len(df)

        atr = self.calculate_atr(df, self.atr_period)
        hl2 = (df['high'].values + df['low'].values) / 2
        close = df['close'].values
        atr_values = atr.values

        # 初始化数组
        upper_band = hl2 + (self.multiplier * atr_values)
        lower_band = hl2 - (self.multiplier * atr_values)
        direction = np.ones(n, dtype=np.int32)
        supertrend = np.empty(n)
        supertrend[:] = np.nan

        # 使用 NumPy 循环 (比 pandas iloc 快 10-100 倍)
        for i in range(self.atr_period, n):
            # 调整上下轨
            if close[i-1] <= upper_band[i-1]:
                upper_band[i] = min(upper_band[i], upper_band[i-1])
            if close[i-1] >= lower_band[i-1]:
                lower_band[i] = max(lower_band[i], lower_band[i-1])

            # 判断方向
            if i == self.atr_period:
                direction[i] = 1
                supertrend[i] = lower_band[i]
            elif direction[i-1] == 1:
                if close[i] < lower_band[i]:
                    direction[i] = -1
                    supertrend[i] = upper_band[i]
                else:
                    direction[i] = 1
                    supertrend[i] = lower_band[i]
            else:
                if close[i] > upper_band[i]:
                    direction[i] = 1
                    supertrend[i] = lower_band[i]
                else:
                    direction[i] = -1
                    supertrend[i] = upper_band[i]

        return {
            "supertrend": pd.Series(supertrend, index=df.index),
            "direction": pd.Series(direction, index=df.index),
            "atr": atr,
            "upper_band": pd.Series(upper_band, index=df.index),
            "lower_band": pd.Series(lower_band, index=df.index)
        }

    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        direction = indicators["direction"]
        atr = indicators["atr"]

        if len(direction) < 3 or pd.isna(direction.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )

        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]

        # 方向从 -1 变为 1 - 做多
        if direction.iloc[-2] == -1 and direction.iloc[-1] == 1:
            if current_position is None or current_position.side == PositionSide.SHORT:
                stop_loss = current_price - (current_atr * 2)
                take_profit = current_price + (current_atr * 6)
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1.0,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={"reason": "SuperTrend bullish flip", "atr": current_atr}
                )

        # 方向从 1 变为 -1 - 做空
        elif direction.iloc[-2] == 1 and direction.iloc[-1] == -1:
            if current_position is None or current_position.side == PositionSide.LONG:
                stop_loss = current_price + (current_atr * 2)
                take_profit = current_price - (current_atr * 6)
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1.0,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={"reason": "SuperTrend bearish flip", "atr": current_atr}
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class MomentumBreakoutStrategy(BaseStrategy):
    """
    动量突破策略 - 适合捕捉 ETH 大行情

    结合成交量突破和 RSI 动量确认，在突破关键价位时入场
    特点：胜率较低但盈亏比高，适合趋势行情
    推荐时间周期：4h, 1d
    """

    def __init__(
        self,
        breakout_period: int = 20,
        volume_multiplier: float = 2.0,
        rsi_period: int = 14,
        rsi_threshold: float = 50,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(name="MomentumBreakout_Strategy")
        config.params.update({
            "breakout_period": breakout_period,
            "volume_multiplier": volume_multiplier,
            "rsi_period": rsi_period,
            "rsi_threshold": rsi_threshold
        })
        config.stop_loss_pct = 0.025
        config.take_profit_pct = 0.075  # 3:1 盈亏比
        super().__init__(config)

        self.breakout_period = breakout_period
        self.volume_multiplier = volume_multiplier
        self.rsi_period = rsi_period
        self.rsi_threshold = rsi_threshold

    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df

        # 计算突破通道
        highest_high = df['high'].rolling(window=self.breakout_period).max()
        lowest_low = df['low'].rolling(window=self.breakout_period).min()

        # 成交量分析
        volume_ma = df['volume'].rolling(window=self.breakout_period).mean()
        volume_ratio = df['volume'] / volume_ma

        # RSI
        rsi = self.calculate_rsi(df['close'], self.rsi_period)

        # 计算价格动量
        momentum = df['close'].pct_change(periods=5) * 100

        return {
            "highest_high": highest_high,
            "lowest_low": lowest_low,
            "volume_ratio": volume_ratio,
            "rsi": rsi,
            "momentum": momentum
        }

    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        highest_high = indicators["highest_high"]
        lowest_low = indicators["lowest_low"]
        volume_ratio = indicators["volume_ratio"]
        rsi = indicators["rsi"]
        momentum = indicators["momentum"]

        if pd.isna(highest_high.iloc[-2]) or pd.isna(rsi.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )

        current_price = data.latest_close
        prev_high = highest_high.iloc[-2]
        prev_low = lowest_low.iloc[-2]
        current_volume_ratio = volume_ratio.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_momentum = momentum.iloc[-1]
        timestamp = data.latest.timestamp

        # 向上突破条件：价格突破前高 + 放量 + RSI > 50 + 正动量
        if (current_price > prev_high and
            current_volume_ratio > self.volume_multiplier and
            current_rsi > self.rsi_threshold and
            current_momentum > 0):
            if current_position is None or current_position.side == PositionSide.SHORT:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume_ratio / 3, 1.0),
                    stop_loss=prev_low,  # 止损设在突破前的低点
                    take_profit=current_price + (current_price - prev_low) * 3,
                    metadata={
                        "reason": "Bullish breakout with volume",
                        "volume_ratio": current_volume_ratio,
                        "rsi": current_rsi
                    }
                )

        # 向下突破条件：价格突破前低 + 放量 + RSI < 50 + 负动量
        elif (current_price < prev_low and
              current_volume_ratio > self.volume_multiplier and
              current_rsi < self.rsi_threshold and
              current_momentum < 0):
            if current_position is None or current_position.side == PositionSide.LONG:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume_ratio / 3, 1.0),
                    stop_loss=prev_high,
                    take_profit=current_price - (prev_high - current_price) * 3,
                    metadata={
                        "reason": "Bearish breakout with volume",
                        "volume_ratio": current_volume_ratio,
                        "rsi": current_rsi
                    }
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class TrendFollowingEMAStrategy(BaseStrategy):
    """
    趋势跟踪 EMA 策略 - 适合 ETH 中长期趋势

    使用多条 EMA 确认趋势方向，配合 ADX 确认趋势强度
    特点：过滤震荡行情，只在强趋势中交易
    推荐时间周期：4h, 1d
    """

    def __init__(
        self,
        fast_ema: int = 8,
        medium_ema: int = 21,
        slow_ema: int = 55,
        adx_period: int = 14,
        adx_threshold: float = 25,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(name="TrendFollowingEMA_Strategy")
        config.params.update({
            "fast_ema": fast_ema,
            "medium_ema": medium_ema,
            "slow_ema": slow_ema,
            "adx_period": adx_period,
            "adx_threshold": adx_threshold
        })
        config.stop_loss_pct = 0.035
        config.take_profit_pct = 0.105  # 3:1 盈亏比
        super().__init__(config)

        self.fast_ema = fast_ema
        self.medium_ema = medium_ema
        self.slow_ema = slow_ema
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold

    def calculate_adx(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算 ADX 指标"""
        high = df['high']
        low = df['low']
        close = df['close']

        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1

        plus_dm = plus_dm.where((plus_dm > minus_dm.abs()) & (plus_dm > 0), 0)
        minus_dm = minus_dm.abs().where((minus_dm.abs() > plus_dm) & (minus_dm < 0), 0)

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()

        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df

        ema_fast = df['close'].ewm(span=self.fast_ema, adjust=False).mean()
        ema_medium = df['close'].ewm(span=self.medium_ema, adjust=False).mean()
        ema_slow = df['close'].ewm(span=self.slow_ema, adjust=False).mean()

        adx = self.calculate_adx(df, self.adx_period)

        # EMA 排列状态
        bullish_alignment = (ema_fast > ema_medium) & (ema_medium > ema_slow)
        bearish_alignment = (ema_fast < ema_medium) & (ema_medium < ema_slow)

        return {
            "ema_fast": ema_fast,
            "ema_medium": ema_medium,
            "ema_slow": ema_slow,
            "adx": adx,
            "bullish_alignment": bullish_alignment,
            "bearish_alignment": bearish_alignment
        }

    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        ema_fast = indicators["ema_fast"]
        ema_medium = indicators["ema_medium"]
        adx = indicators["adx"]
        bullish = indicators["bullish_alignment"]
        bearish = indicators["bearish_alignment"]

        if pd.isna(adx.iloc[-1]) or len(adx) < 3:
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )

        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_adx = adx.iloc[-1]

        # 趋势强度足够
        strong_trend = current_adx > self.adx_threshold

        # 多头排列刚形成 + 趋势强 + 价格在快线上方
        if (bullish.iloc[-1] and not bullish.iloc[-2] and
            strong_trend and current_price > ema_fast.iloc[-1]):
            if current_position is None or current_position.side == PositionSide.SHORT:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_adx / 50, 1.0),
                    stop_loss=ema_medium.iloc[-1] * 0.98,
                    take_profit=current_price * (1 + self.config.take_profit_pct),
                    metadata={"reason": "EMA bullish alignment", "adx": current_adx}
                )

        # 空头排列刚形成 + 趋势强 + 价格在快线下方
        elif (bearish.iloc[-1] and not bearish.iloc[-2] and
              strong_trend and current_price < ema_fast.iloc[-1]):
            if current_position is None or current_position.side == PositionSide.LONG:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_adx / 50, 1.0),
                    stop_loss=ema_medium.iloc[-1] * 1.02,
                    take_profit=current_price * (1 - self.config.take_profit_pct),
                    metadata={"reason": "EMA bearish alignment", "adx": current_adx}
                )

        # 趋势反转平仓
        if current_position:
            if current_position.side == PositionSide.LONG and bearish.iloc[-1]:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Trend reversed to bearish"}
                )
            elif current_position.side == PositionSide.SHORT and bullish.iloc[-1]:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Trend reversed to bullish"}
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class ScalpingStrategy(BaseStrategy):
    """
    高频剥头皮策略 - 适合 ETH 短线交易

    使用快速指标捕捉小幅波动，高频交易积累利润
    特点：交易频繁，单笔利润小但积少成多
    建议配合较低杠杆使用
    推荐时间周期：5m, 15m
    """

    def __init__(
        self,
        ema_period: int = 9,
        rsi_period: int = 7,
        bb_period: int = 14,
        bb_std: float = 2.0,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(name="Scalping_Strategy")
        config.params.update({
            "ema_period": ema_period,
            "rsi_period": rsi_period,
            "bb_period": bb_period,
            "bb_std": bb_std
        })
        # 剥头皮策略使用更小的止损止盈
        config.stop_loss_pct = 0.008  # 0.8% 止损
        config.take_profit_pct = 0.012  # 1.2% 止盈 (1.5:1 盈亏比)
        super().__init__(config)

        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df

        # 快速 EMA
        ema = df['close'].ewm(span=self.ema_period, adjust=False).mean()

        # 快速 RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # 布林带
        bb_middle = df['close'].rolling(window=self.bb_period).mean()
        bb_std = df['close'].rolling(window=self.bb_period).std()
        bb_upper = bb_middle + (bb_std * self.bb_std)
        bb_lower = bb_middle - (bb_std * self.bb_std)

        # 计算价格相对于布林带的位置
        bb_position = (df['close'] - bb_lower) / (bb_upper - bb_lower)

        # 成交量变化
        volume_change = df['volume'].pct_change()

        return {
            "ema": ema,
            "rsi": rsi,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "bb_position": bb_position,
            "volume_change": volume_change
        }

    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        ema = indicators["ema"]
        rsi = indicators["rsi"]
        bb_lower = indicators["bb_lower"]
        bb_upper = indicators["bb_upper"]
        bb_position = indicators["bb_position"]

        if pd.isna(rsi.iloc[-1]) or pd.isna(bb_lower.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )

        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_rsi = rsi.iloc[-1]
        current_bb_pos = bb_position.iloc[-1]

        # 做多条件：价格触及布林下轨 + RSI 超卖 + 价格在 EMA 附近
        if (current_bb_pos < 0.1 and  # 接近下轨
            current_rsi < 35 and  # RSI 超卖
            abs(current_price - ema.iloc[-1]) / current_price < 0.02):  # 接近 EMA
            if current_position is None:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=0.7,
                    stop_loss=bb_lower.iloc[-1] * 0.995,
                    take_profit=indicators["bb_middle"].iloc[-1],
                    metadata={"reason": "Scalp buy - BB lower + RSI oversold", "rsi": current_rsi}
                )

        # 做空条件：价格触及布林上轨 + RSI 超买
        elif (current_bb_pos > 0.9 and  # 接近上轨
              current_rsi > 65 and  # RSI 超买
              abs(current_price - ema.iloc[-1]) / current_price < 0.02):
            if current_position is None:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=0.7,
                    stop_loss=bb_upper.iloc[-1] * 1.005,
                    take_profit=indicators["bb_middle"].iloc[-1],
                    metadata={"reason": "Scalp sell - BB upper + RSI overbought", "rsi": current_rsi}
                )

        # 快速平仓：回到中轨
        if current_position:
            bb_mid = indicators["bb_middle"].iloc[-1]
            if current_position.side == PositionSide.LONG and current_price >= bb_mid:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Take profit at BB middle"}
                )
            elif current_position.side == PositionSide.SHORT and current_price <= bb_mid:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Take profit at BB middle"}
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class VWAPMomentumStrategy(BaseStrategy):
    """
    VWAP 动量策略 - 适合 ETH 日内交易

    基于成交量加权平均价格(VWAP)判断多空，配合动量确认
    特点：跟随主力资金方向，适合日内波段
    推荐时间周期：15m, 1h
    """

    def __init__(
        self,
        vwap_period: int = 20,
        momentum_period: int = 10,
        volume_ma_period: int = 20,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(name="VWAPMomentum_Strategy")
        config.params.update({
            "vwap_period": vwap_period,
            "momentum_period": momentum_period,
            "volume_ma_period": volume_ma_period
        })
        config.stop_loss_pct = 0.02
        config.take_profit_pct = 0.05
        super().__init__(config)

        self.vwap_period = vwap_period
        self.momentum_period = momentum_period
        self.volume_ma_period = volume_ma_period

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df

        # 计算 VWAP
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).rolling(window=self.vwap_period).sum() / \
               df['volume'].rolling(window=self.vwap_period).sum()

        # 价格相对 VWAP 的偏离度
        vwap_deviation = (df['close'] - vwap) / vwap * 100

        # 动量指标
        momentum = df['close'].pct_change(periods=self.momentum_period) * 100

        # 成交量分析
        volume_ma = df['volume'].rolling(window=self.volume_ma_period).mean()
        volume_ratio = df['volume'] / volume_ma

        # 累积成交量力量 (OBV)
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = 0
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]

        obv_ema = obv.ewm(span=10, adjust=False).mean()

        return {
            "vwap": vwap,
            "vwap_deviation": vwap_deviation,
            "momentum": momentum,
            "volume_ratio": volume_ratio,
            "obv": obv,
            "obv_ema": obv_ema
        }

    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        vwap = indicators["vwap"]
        vwap_deviation = indicators["vwap_deviation"]
        momentum = indicators["momentum"]
        volume_ratio = indicators["volume_ratio"]
        obv = indicators["obv"]
        obv_ema = indicators["obv_ema"]

        if pd.isna(vwap.iloc[-1]) or pd.isna(momentum.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )

        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_vwap = vwap.iloc[-1]
        current_deviation = vwap_deviation.iloc[-1]
        current_momentum = momentum.iloc[-1]
        current_volume_ratio = volume_ratio.iloc[-1]

        # OBV 趋势
        obv_bullish = obv.iloc[-1] > obv_ema.iloc[-1]
        obv_bearish = obv.iloc[-1] < obv_ema.iloc[-1]

        # 做多条件：
        # 1. 价格刚突破 VWAP
        # 2. 动量为正
        # 3. 成交量放大
        # 4. OBV 趋势向上
        if (current_price > current_vwap and
            data.df['close'].iloc[-2] <= vwap.iloc[-2] and  # 刚突破
            current_momentum > 1 and
            current_volume_ratio > 1.2 and
            obv_bullish):
            if current_position is None or current_position.side == PositionSide.SHORT:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume_ratio / 2, 1.0),
                    stop_loss=current_vwap * 0.99,
                    take_profit=current_price * 1.05,
                    metadata={
                        "reason": "VWAP breakout with momentum",
                        "vwap_deviation": current_deviation,
                        "momentum": current_momentum
                    }
                )

        # 做空条件
        elif (current_price < current_vwap and
              data.df['close'].iloc[-2] >= vwap.iloc[-2] and  # 刚跌破
              current_momentum < -1 and
              current_volume_ratio > 1.2 and
              obv_bearish):
            if current_position is None or current_position.side == PositionSide.LONG:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume_ratio / 2, 1.0),
                    stop_loss=current_vwap * 1.01,
                    take_profit=current_price * 0.95,
                    metadata={
                        "reason": "VWAP breakdown with momentum",
                        "vwap_deviation": current_deviation,
                        "momentum": current_momentum
                    }
                )

        # 偏离过大时平仓
        if current_position:
            if abs(current_deviation) > 3:  # 偏离 VWAP 超过 3%
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": f"VWAP deviation too large: {current_deviation:.2f}%"}
                )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class AdaptiveTrendStrategy(BaseStrategy):
    """
    自适应趋势策略 - 适合 ETH 各种市场环境

    根据市场波动率自动调整参数，在趋势和震荡市场都能适应
    特点：智能适应市场环境，降低假信号
    推荐时间周期：1h, 4h
    """

    def __init__(
        self,
        base_period: int = 20,
        atr_period: int = 14,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(name="AdaptiveTrend_Strategy")
        config.params.update({
            "base_period": base_period,
            "atr_period": atr_period
        })
        config.stop_loss_pct = 0.03
        config.take_profit_pct = 0.09
        super().__init__(config)

        self.base_period = base_period
        self.atr_period = atr_period

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df

        # ATR 用于判断波动率
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()

        # 波动率百分比
        volatility = atr / close * 100

        # 根据波动率调整 EMA 周期
        # 高波动用短周期，低波动用长周期
        avg_volatility = volatility.rolling(window=50).mean()

        # 自适应 EMA
        adaptive_ema = pd.Series(index=df.index, dtype=float)
        for i in range(self.base_period, len(df)):
            if pd.isna(volatility.iloc[i]) or pd.isna(avg_volatility.iloc[i]):
                continue

            # 波动率比率调整周期
            vol_ratio = volatility.iloc[i] / avg_volatility.iloc[i] if avg_volatility.iloc[i] > 0 else 1
            adjusted_period = max(5, min(50, int(self.base_period / vol_ratio)))

            # 计算自适应 EMA
            alpha = 2 / (adjusted_period + 1)
            if pd.isna(adaptive_ema.iloc[i-1]):
                adaptive_ema.iloc[i] = close.iloc[i]
            else:
                adaptive_ema.iloc[i] = alpha * close.iloc[i] + (1 - alpha) * adaptive_ema.iloc[i-1]

        # 趋势方向
        trend = pd.Series(index=df.index, dtype=int)
        trend[close > adaptive_ema] = 1
        trend[close < adaptive_ema] = -1
        trend = trend.fillna(0)

        # 趋势强度
        trend_strength = abs(close - adaptive_ema) / atr

        # Keltner 通道
        keltner_upper = adaptive_ema + (atr * 2)
        keltner_lower = adaptive_ema - (atr * 2)

        return {
            "adaptive_ema": adaptive_ema,
            "atr": atr,
            "volatility": volatility,
            "trend": trend,
            "trend_strength": trend_strength,
            "keltner_upper": keltner_upper,
            "keltner_lower": keltner_lower
        }

    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        adaptive_ema = indicators["adaptive_ema"]
        atr = indicators["atr"]
        trend = indicators["trend"]
        trend_strength = indicators["trend_strength"]
        keltner_upper = indicators["keltner_upper"]
        keltner_lower = indicators["keltner_lower"]

        if pd.isna(adaptive_ema.iloc[-1]) or pd.isna(atr.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )

        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]
        current_trend = trend.iloc[-1]
        prev_trend = trend.iloc[-2] if len(trend) > 1 else 0
        current_strength = trend_strength.iloc[-1]

        # 趋势反转且强度足够
        if prev_trend == -1 and current_trend == 1 and current_strength > 1:
            if current_position is None or current_position.side == PositionSide.SHORT:
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_strength / 2, 1.0),
                    stop_loss=keltner_lower.iloc[-1],
                    take_profit=current_price + (current_atr * 4),
                    metadata={
                        "reason": "Adaptive trend reversal to bullish",
                        "trend_strength": current_strength
                    }
                )

        elif prev_trend == 1 and current_trend == -1 and current_strength > 1:
            if current_position is None or current_position.side == PositionSide.LONG:
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_strength / 2, 1.0),
                    stop_loss=keltner_upper.iloc[-1],
                    take_profit=current_price - (current_atr * 4),
                    metadata={
                        "reason": "Adaptive trend reversal to bearish",
                        "trend_strength": current_strength
                    }
                )

        # 趋势衰弱平仓
        if current_position and current_strength < 0.5:
            return Signal(
                signal_type=SignalType.CLOSE,
                symbol=self.config.symbols[0],
                price=current_price,
                timestamp=timestamp,
                metadata={"reason": "Trend strength weakening"}
            )

        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )
