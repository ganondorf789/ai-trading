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


# ==================== 高级优化策略 ====================


class SuperTrendStrategy(BaseStrategy):
    """
    超级趋势策略 (SuperTrend)
    
    基于ATR的趋势跟踪策略，在加密货币市场表现优异
    - 使用ATR动态计算支撑/阻力带
    - 趋势明确时跟随趋势
    - 趋势反转时及时止损
    """
    
    def __init__(
        self,
        atr_period: int = 10,
        atr_multiplier: float = 3.0,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(
            name="SuperTrend",
            stop_loss_pct=0.03,
            take_profit_pct=0.09
        )
        config.params.update({
            "atr_period": atr_period,
            "atr_multiplier": atr_multiplier
        })
        super().__init__(config)
        
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算ATR"""
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
        """计算SuperTrend指标"""
        df = data.df.copy()
        
        atr = self.calculate_atr(df, self.atr_period)
        hl2 = (df['high'] + df['low']) / 2
        
        # 上轨和下轨
        upper_band = hl2 + (self.atr_multiplier * atr)
        lower_band = hl2 - (self.atr_multiplier * atr)
        
        # SuperTrend计算
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        final_upper = upper_band.copy()
        final_lower = lower_band.copy()
        
        for i in range(1, len(df)):
            # 调整上轨
            if upper_band.iloc[i] < final_upper.iloc[i-1] or df['close'].iloc[i-1] > final_upper.iloc[i-1]:
                final_upper.iloc[i] = upper_band.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i-1]
            
            # 调整下轨
            if lower_band.iloc[i] > final_lower.iloc[i-1] or df['close'].iloc[i-1] < final_lower.iloc[i-1]:
                final_lower.iloc[i] = lower_band.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i-1]
        
        # 确定趋势方向
        for i in range(1, len(df)):
            if i == 1:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                if supertrend.iloc[i-1] == final_upper.iloc[i-1]:
                    if df['close'].iloc[i] > final_upper.iloc[i]:
                        direction.iloc[i] = 1
                        supertrend.iloc[i] = final_lower.iloc[i]
                    else:
                        direction.iloc[i] = -1
                        supertrend.iloc[i] = final_upper.iloc[i]
                else:
                    if df['close'].iloc[i] < final_lower.iloc[i]:
                        direction.iloc[i] = -1
                        supertrend.iloc[i] = final_upper.iloc[i]
                    else:
                        direction.iloc[i] = 1
                        supertrend.iloc[i] = final_lower.iloc[i]
        
        return {
            "supertrend": supertrend,
            "direction": direction,
            "atr": atr,
            "upper": final_upper,
            "lower": final_lower
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
        
        current_dir = direction.iloc[-1]
        prev_dir = direction.iloc[-2]
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]
        
        # 趋势翻转做多
        if prev_dir == -1 and current_dir == 1:
            if current_position is None or current_position.side == PositionSide.SHORT:
                stop_loss = current_price - (2.0 * current_atr)
                take_profit = current_price + (4.0 * current_atr)
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
        
        # 趋势翻转做空
        elif prev_dir == 1 and current_dir == -1:
            if current_position is None or current_position.side == PositionSide.LONG:
                stop_loss = current_price + (2.0 * current_atr)
                take_profit = current_price - (4.0 * current_atr)
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


class VolumeBreakoutStrategy(BaseStrategy):
    """
    成交量确认突破策略
    
    只在成交量放大时确认突破，过滤虚假突破
    - 价格突破关键位置
    - 成交量必须超过平均成交量的倍数
    - 使用ATR设置动态止损
    """
    
    def __init__(
        self,
        lookback_period: int = 20,
        volume_multiplier: float = 1.5,
        atr_period: int = 14,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(
            name="VolumeBreakout",
            stop_loss_pct=0.025,
            take_profit_pct=0.075
        )
        config.params.update({
            "lookback_period": lookback_period,
            "volume_multiplier": volume_multiplier,
            "atr_period": atr_period
        })
        super().__init__(config)
        
        self.lookback_period = lookback_period
        self.volume_multiplier = volume_multiplier
        self.atr_period = atr_period
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df
        
        # 计算关键价位
        highest_high = df['high'].rolling(window=self.lookback_period).max()
        lowest_low = df['low'].rolling(window=self.lookback_period).min()
        
        # 成交量指标
        avg_volume = df['volume'].rolling(window=self.lookback_period).mean()
        volume_ratio = df['volume'] / avg_volume
        
        # ATR
        atr = self.calculate_atr(df, self.atr_period)
        
        # 价格位置
        price_position = (df['close'] - lowest_low) / (highest_high - lowest_low)
        
        return {
            "highest_high": highest_high,
            "lowest_low": lowest_low,
            "avg_volume": avg_volume,
            "volume_ratio": volume_ratio,
            "atr": atr,
            "price_position": price_position
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        df = data.df
        highest = indicators["highest_high"]
        lowest = indicators["lowest_low"]
        volume_ratio = indicators["volume_ratio"]
        atr = indicators["atr"]
        
        if len(df) < self.lookback_period + 2:
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        prev_close = df['close'].iloc[-2]
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]
        current_volume_ratio = volume_ratio.iloc[-1]
        prev_high = highest.iloc[-2]  # 使用前一根K线的最高点
        prev_low = lowest.iloc[-2]
        
        # 向上突破 + 成交量确认
        if (current_price > prev_high and 
            prev_close <= prev_high and 
            current_volume_ratio >= self.volume_multiplier):
            
            if current_position is None:
                stop_loss = current_price - (2.5 * current_atr)
                take_profit = current_price + (5.0 * current_atr)
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume_ratio / 3.0, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Volume confirmed breakout UP",
                        "volume_ratio": current_volume_ratio
                    }
                )
        
        # 向下突破 + 成交量确认
        if (current_price < prev_low and 
            prev_close >= prev_low and 
            current_volume_ratio >= self.volume_multiplier):
            
            if current_position is None:
                stop_loss = current_price + (2.5 * current_atr)
                take_profit = current_price - (5.0 * current_atr)
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume_ratio / 3.0, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Volume confirmed breakout DOWN",
                        "volume_ratio": current_volume_ratio
                    }
                )
        
        # 移动止损逻辑
        if current_position:
            if current_position.side == PositionSide.LONG:
                trailing_stop = current_price - (2.0 * current_atr)
                if trailing_stop > current_position.entry_price:
                    # 已经盈利，可以考虑移动止损
                    pass
            
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class MomentumTrendStrategy(BaseStrategy):
    """
    动量趋势策略
    
    结合趋势方向和动量强度，只在趋势明确且动量充足时入场
    - EMA判断趋势方向
    - RSI判断动量
    - ADX过滤震荡市场
    """
    
    def __init__(
        self,
        ema_fast: int = 8,
        ema_slow: int = 21,
        ema_trend: int = 50,
        rsi_period: int = 14,
        adx_period: int = 14,
        adx_threshold: float = 25,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(
            name="MomentumTrend",
            stop_loss_pct=0.02,
            take_profit_pct=0.06
        )
        config.params.update({
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_trend": ema_trend,
            "rsi_period": rsi_period,
            "adx_period": adx_period,
            "adx_threshold": adx_threshold
        })
        super().__init__(config)
        
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.ema_trend = ema_trend
        self.rsi_period = rsi_period
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_adx(self, df: pd.DataFrame, period: int) -> pd.Series:
        """计算ADX指标"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # +DM 和 -DM
        plus_dm = high.diff()
        minus_dm = low.diff().abs() * -1
        
        plus_dm = plus_dm.where((plus_dm > minus_dm.abs()) & (plus_dm > 0), 0)
        minus_dm = minus_dm.abs().where((minus_dm.abs() > plus_dm) & (minus_dm < 0), 0)
        
        # TR
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # 平滑
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # DX 和 ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df
        close = df['close']
        
        # EMA
        ema_fast = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow, adjust=False).mean()
        ema_trend = close.ewm(span=self.ema_trend, adjust=False).mean()
        
        # RSI
        rsi = self.calculate_rsi(close, self.rsi_period)
        
        # ADX
        adx = self.calculate_adx(df, self.adx_period)
        
        # ATR
        atr = self.calculate_atr(df, 14)
        
        return {
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_trend": ema_trend,
            "rsi": rsi,
            "adx": adx,
            "atr": atr
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        ema_fast = indicators["ema_fast"]
        ema_slow = indicators["ema_slow"]
        ema_trend = indicators["ema_trend"]
        rsi = indicators["rsi"]
        adx = indicators["adx"]
        atr = indicators["atr"]
        
        if len(ema_fast) < 3 or pd.isna(adx.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]
        current_adx = adx.iloc[-1]
        current_rsi = rsi.iloc[-1]
        
        # 趋势条件
        uptrend = (ema_fast.iloc[-1] > ema_slow.iloc[-1] and 
                   ema_slow.iloc[-1] > ema_trend.iloc[-1] and
                   current_price > ema_trend.iloc[-1])
        
        downtrend = (ema_fast.iloc[-1] < ema_slow.iloc[-1] and 
                     ema_slow.iloc[-1] < ema_trend.iloc[-1] and
                     current_price < ema_trend.iloc[-1])
        
        # EMA交叉
        fast_cross_up = (ema_fast.iloc[-2] <= ema_slow.iloc[-2] and 
                         ema_fast.iloc[-1] > ema_slow.iloc[-1])
        fast_cross_down = (ema_fast.iloc[-2] >= ema_slow.iloc[-2] and 
                           ema_fast.iloc[-1] < ema_slow.iloc[-1])
        
        # ADX过滤 - 只在趋势市场交易
        trending = current_adx >= self.adx_threshold
        
        # 做多条件：上升趋势 + 快线上穿慢线 + ADX确认趋势 + RSI不超买
        if uptrend and fast_cross_up and trending and current_rsi < 70:
            if current_position is None or current_position.side == PositionSide.SHORT:
                stop_loss = current_price - (2.0 * current_atr)
                take_profit = current_price + (4.0 * current_atr)
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_adx / 50, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Momentum trend BUY",
                        "adx": current_adx,
                        "rsi": current_rsi
                    }
                )
        
        # 做空条件：下降趋势 + 快线下穿慢线 + ADX确认趋势 + RSI不超卖
        if downtrend and fast_cross_down and trending and current_rsi > 30:
            if current_position is None or current_position.side == PositionSide.LONG:
                stop_loss = current_price + (2.0 * current_atr)
                take_profit = current_price - (4.0 * current_atr)
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_adx / 50, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Momentum trend SELL",
                        "adx": current_adx,
                        "rsi": current_rsi
                    }
                )
        
        # 平仓条件
        if current_position:
            if current_position.side == PositionSide.LONG:
                # 多头平仓：趋势转弱或RSI超买
                if not uptrend or current_rsi > 80 or current_adx < 20:
                    return Signal(
                        signal_type=SignalType.CLOSE,
                        symbol=self.config.symbols[0],
                        price=current_price,
                        timestamp=timestamp,
                        metadata={"reason": "Trend weakening or overbought"}
                    )
            elif current_position.side == PositionSide.SHORT:
                # 空头平仓：趋势转弱或RSI超卖
                if not downtrend or current_rsi < 20 or current_adx < 20:
                    return Signal(
                        signal_type=SignalType.CLOSE,
                        symbol=self.config.symbols[0],
                        price=current_price,
                        timestamp=timestamp,
                        metadata={"reason": "Trend weakening or oversold"}
                    )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class MeanReversionATRStrategy(BaseStrategy):
    """
    改进版均值回归策略
    
    在价格极度偏离均值时入场，使用ATR控制风险
    - 使用z-score衡量价格偏离程度
    - RSI确认超买超卖
    - ATR动态止损
    - 等待反转信号确认后入场
    """
    
    def __init__(
        self,
        lookback: int = 20,
        z_threshold: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 25,
        rsi_overbought: float = 75,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(
            name="MeanReversionATR",
            stop_loss_pct=0.025,
            take_profit_pct=0.05
        )
        config.params.update({
            "lookback": lookback,
            "z_threshold": z_threshold,
            "rsi_period": rsi_period,
            "rsi_oversold": rsi_oversold,
            "rsi_overbought": rsi_overbought
        })
        super().__init__(config)
        
        self.lookback = lookback
        self.z_threshold = z_threshold
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df
        close = df['close']
        
        # 均值和标准差
        sma = close.rolling(window=self.lookback).mean()
        std = close.rolling(window=self.lookback).std()
        
        # Z-Score
        z_score = (close - sma) / std
        
        # RSI
        rsi = self.calculate_rsi(close, self.rsi_period)
        
        # ATR
        atr = self.calculate_atr(df, 14)
        
        # 价格变化率（用于确认反转）
        price_change = close.pct_change()
        
        return {
            "sma": sma,
            "z_score": z_score,
            "rsi": rsi,
            "atr": atr,
            "price_change": price_change
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        z_score = indicators["z_score"]
        rsi = indicators["rsi"]
        atr = indicators["atr"]
        sma = indicators["sma"]
        price_change = indicators["price_change"]
        
        if len(z_score) < 3 or pd.isna(z_score.iloc[-1]):
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        timestamp = data.latest.timestamp
        current_z = z_score.iloc[-1]
        prev_z = z_score.iloc[-2]
        current_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        current_atr = atr.iloc[-1]
        current_change = price_change.iloc[-1]
        
        # 做多条件：
        # 1. Z-Score低于阈值（价格远低于均值）
        # 2. RSI从超卖区反弹
        # 3. 价格开始上涨（确认反转）
        oversold_condition = (
            prev_z < -self.z_threshold and
            current_z > prev_z and  # Z-Score开始回升
            prev_rsi < self.rsi_oversold and
            current_rsi > prev_rsi and  # RSI开始回升
            current_change > 0  # 价格在上涨
        )
        
        if oversold_condition:
            if current_position is None:
                stop_loss = current_price - (2.0 * current_atr)
                take_profit = sma.iloc[-1]  # 目标是回归均值
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(abs(current_z) / 3.0, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Mean reversion BUY",
                        "z_score": current_z,
                        "rsi": current_rsi
                    }
                )
        
        # 做空条件：
        # 1. Z-Score高于阈值（价格远高于均值）
        # 2. RSI从超买区回落
        # 3. 价格开始下跌（确认反转）
        overbought_condition = (
            prev_z > self.z_threshold and
            current_z < prev_z and  # Z-Score开始回落
            prev_rsi > self.rsi_overbought and
            current_rsi < prev_rsi and  # RSI开始回落
            current_change < 0  # 价格在下跌
        )
        
        if overbought_condition:
            if current_position is None:
                stop_loss = current_price + (2.0 * current_atr)
                take_profit = sma.iloc[-1]  # 目标是回归均值
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(abs(current_z) / 3.0, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Mean reversion SELL",
                        "z_score": current_z,
                        "rsi": current_rsi
                    }
                )
        
        # 平仓：价格回归均值
        if current_position:
            if current_position.side == PositionSide.LONG and current_z >= 0:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Price returned to mean (long)"}
                )
            elif current_position.side == PositionSide.SHORT and current_z <= 0:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Price returned to mean (short)"}
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class TripleScreenStrategy(BaseStrategy):
    """
    三重滤网策略 (Triple Screen)
    
    亚历山大·埃尔德的经典策略改进版
    - 第一屏：周期趋势（使用大周期EMA判断趋势方向）
    - 第二屏：震荡指标（使用MACD柱状图判断动量）
    - 第三屏：精确入场（使用价格突破入场）
    
    只顺着大趋势方向交易，过滤逆势信号
    """
    
    def __init__(
        self,
        trend_ema: int = 50,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        breakout_period: int = 5,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(
            name="TripleScreen",
            stop_loss_pct=0.02,
            take_profit_pct=0.06
        )
        config.params.update({
            "trend_ema": trend_ema,
            "macd_fast": macd_fast,
            "macd_slow": macd_slow,
            "macd_signal": macd_signal,
            "breakout_period": breakout_period
        })
        super().__init__(config)
        
        self.trend_ema = trend_ema
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.breakout_period = breakout_period
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df
        close = df['close']
        
        # 第一屏：趋势EMA
        ema_trend = close.ewm(span=self.trend_ema, adjust=False).mean()
        trend_direction = (close > ema_trend).astype(int) - (close < ema_trend).astype(int)
        
        # 第二屏：MACD
        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        # MACD柱状图方向
        hist_rising = histogram > histogram.shift(1)
        
        # 第三屏：突破
        highest = df['high'].rolling(window=self.breakout_period).max()
        lowest = df['low'].rolling(window=self.breakout_period).min()
        
        # ATR
        atr = self.calculate_atr(df, 14)
        
        return {
            "ema_trend": ema_trend,
            "trend_direction": trend_direction,
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
            "hist_rising": hist_rising,
            "highest": highest,
            "lowest": lowest,
            "atr": atr
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        df = data.df
        trend_dir = indicators["trend_direction"]
        histogram = indicators["histogram"]
        hist_rising = indicators["hist_rising"]
        highest = indicators["highest"]
        lowest = indicators["lowest"]
        atr = indicators["atr"]
        ema_trend = indicators["ema_trend"]
        
        if len(df) < self.trend_ema + 5:
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        prev_close = df['close'].iloc[-2]
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]
        
        # 第一屏：确定趋势方向
        is_uptrend = trend_dir.iloc[-1] > 0
        is_downtrend = trend_dir.iloc[-1] < 0
        
        # 第二屏：MACD柱状图条件
        # 做多：柱状图在零轴下方但开始上升
        macd_buy_signal = histogram.iloc[-1] < 0 and hist_rising.iloc[-1]
        # 做空：柱状图在零轴上方但开始下降
        macd_sell_signal = histogram.iloc[-1] > 0 and not hist_rising.iloc[-1]
        
        # 第三屏：突破入场
        prev_highest = highest.iloc[-2]
        prev_lowest = lowest.iloc[-2]
        
        breakout_up = current_price > prev_highest and prev_close <= prev_highest
        breakout_down = current_price < prev_lowest and prev_close >= prev_lowest
        
        # 做多：上升趋势 + MACD回调后反弹 + 价格突破
        if is_uptrend and macd_buy_signal and breakout_up:
            if current_position is None or current_position.side == PositionSide.SHORT:
                stop_loss = current_price - (2.0 * current_atr)
                take_profit = current_price + (4.0 * current_atr)
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1.0,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Triple Screen BUY",
                        "trend": "up",
                        "histogram": histogram.iloc[-1]
                    }
                )
        
        # 做空：下降趋势 + MACD反弹后回落 + 价格突破
        if is_downtrend and macd_sell_signal and breakout_down:
            if current_position is None or current_position.side == PositionSide.LONG:
                stop_loss = current_price + (2.0 * current_atr)
                take_profit = current_price - (4.0 * current_atr)
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=1.0,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Triple Screen SELL",
                        "trend": "down",
                        "histogram": histogram.iloc[-1]
                    }
                )
        
        # 平仓：趋势反转
        if current_position:
            if current_position.side == PositionSide.LONG and is_downtrend:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Trend reversed to down"}
                )
            elif current_position.side == PositionSide.SHORT and is_uptrend:
                return Signal(
                    signal_type=SignalType.CLOSE,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    metadata={"reason": "Trend reversed to up"}
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )


class SmartMoneyStrategy(BaseStrategy):
    """
    聪明资金策略 (Smart Money Concepts)
    
    基于市场结构和流动性的策略
    - 识别市场结构（Higher Highs, Lower Lows）
    - 寻找流动性扫荡后的反转
    - 在订单块区域入场
    """
    
    def __init__(
        self,
        structure_lookback: int = 10,
        liquidity_threshold: float = 0.005,
        atr_period: int = 14,
        config: Optional[StrategyConfig] = None
    ):
        config = config or StrategyConfig(
            name="SmartMoney",
            stop_loss_pct=0.015,
            take_profit_pct=0.045
        )
        config.params.update({
            "structure_lookback": structure_lookback,
            "liquidity_threshold": liquidity_threshold,
            "atr_period": atr_period
        })
        super().__init__(config)
        
        self.structure_lookback = structure_lookback
        self.liquidity_threshold = liquidity_threshold
        self.atr_period = atr_period
    
    def calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def find_swing_points(self, df: pd.DataFrame, lookback: int) -> tuple:
        """找到摆动高点和低点"""
        highs = df['high']
        lows = df['low']
        
        swing_highs = pd.Series(index=df.index, dtype=float)
        swing_lows = pd.Series(index=df.index, dtype=float)
        
        for i in range(lookback, len(df) - lookback):
            # 检查是否是摆动高点
            is_swing_high = True
            for j in range(1, lookback + 1):
                if highs.iloc[i] <= highs.iloc[i-j] or highs.iloc[i] <= highs.iloc[i+j]:
                    is_swing_high = False
                    break
            if is_swing_high:
                swing_highs.iloc[i] = highs.iloc[i]
            
            # 检查是否是摆动低点
            is_swing_low = True
            for j in range(1, lookback + 1):
                if lows.iloc[i] >= lows.iloc[i-j] or lows.iloc[i] >= lows.iloc[i+j]:
                    is_swing_low = False
                    break
            if is_swing_low:
                swing_lows.iloc[i] = lows.iloc[i]
        
        return swing_highs, swing_lows
    
    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df
        
        # ATR
        atr = self.calculate_atr(df, self.atr_period)
        
        # 摆动点
        swing_highs, swing_lows = self.find_swing_points(df, 3)
        
        # 近期高低点
        recent_high = df['high'].rolling(window=self.structure_lookback).max()
        recent_low = df['low'].rolling(window=self.structure_lookback).min()
        
        # 成交量
        avg_volume = df['volume'].rolling(window=20).mean()
        volume_ratio = df['volume'] / avg_volume
        
        # 价格动量
        momentum = df['close'].pct_change(5)
        
        return {
            "atr": atr,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "volume_ratio": volume_ratio,
            "momentum": momentum
        }
    
    def generate_signal(
        self,
        data: OHLCVDataFrame,
        indicators: Dict[str, pd.Series],
        current_position: Optional[Position] = None
    ) -> Signal:
        df = data.df
        atr = indicators["atr"]
        recent_high = indicators["recent_high"]
        recent_low = indicators["recent_low"]
        volume_ratio = indicators["volume_ratio"]
        momentum = indicators["momentum"]
        
        if len(df) < self.structure_lookback + 10:
            return Signal(
                signal_type=SignalType.HOLD,
                symbol=self.config.symbols[0],
                price=data.latest_close,
                timestamp=data.latest.timestamp
            )
        
        current_price = data.latest_close
        prev_price = df['close'].iloc[-2]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        timestamp = data.latest.timestamp
        current_atr = atr.iloc[-1]
        current_volume = volume_ratio.iloc[-1]
        
        # 前一根K线的高低点
        prev_recent_high = recent_high.iloc[-2]
        prev_recent_low = recent_low.iloc[-2]
        
        # 流动性扫荡后做多：
        # 1. 价格突破近期低点（扫荡卖方流动性）
        # 2. 然后强力反弹回来
        # 3. 成交量放大
        liquidity_sweep_low = (
            current_low < prev_recent_low and  # 突破了前期低点
            current_price > prev_recent_low and  # 收盘回到低点上方
            current_price > prev_price and  # 价格在上涨
            current_volume > 1.2  # 成交量放大
        )
        
        if liquidity_sweep_low:
            if current_position is None:
                stop_loss = current_low - (0.5 * current_atr)
                take_profit = current_price + (3.0 * current_atr)
                return Signal(
                    signal_type=SignalType.BUY,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume / 2.0, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Smart Money BUY - Liquidity sweep",
                        "swept_level": prev_recent_low,
                        "volume": current_volume
                    }
                )
        
        # 流动性扫荡后做空：
        # 1. 价格突破近期高点（扫荡买方流动性）
        # 2. 然后强力回落
        # 3. 成交量放大
        liquidity_sweep_high = (
            current_high > prev_recent_high and  # 突破了前期高点
            current_price < prev_recent_high and  # 收盘回到高点下方
            current_price < prev_price and  # 价格在下跌
            current_volume > 1.2  # 成交量放大
        )
        
        if liquidity_sweep_high:
            if current_position is None:
                stop_loss = current_high + (0.5 * current_atr)
                take_profit = current_price - (3.0 * current_atr)
                return Signal(
                    signal_type=SignalType.SELL,
                    symbol=self.config.symbols[0],
                    price=current_price,
                    timestamp=timestamp,
                    strength=min(current_volume / 2.0, 1.0),
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    metadata={
                        "reason": "Smart Money SELL - Liquidity sweep",
                        "swept_level": prev_recent_high,
                        "volume": current_volume
                    }
                )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=current_price,
            timestamp=timestamp
        )