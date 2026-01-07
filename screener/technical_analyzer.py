"""
技术面分析模块

通过蜡烛线数据增强交易者分析:
- 入场时机评估
- 趋势顺应能力
- ATR 标准化收益
- 当前持仓健康度
- 波动率择时能力
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from loguru import logger

from .config import TechnicalConfig
from .utils import timestamp_to_pendulum, now_shanghai


@dataclass
class TechnicalMetrics:
    """技术面增强指标"""
    
    # ========== 入场时机指标 ==========
    entry_timing_score: float = 0.0  # 入场时机综合评分 (0-100)
    trend_alignment_rate: float = 0.0  # 趋势顺应率 (0-1)
    ma_entry_quality: float = 0.0  # 均线入场质量 (0-100)
    rsi_entry_quality: float = 0.0  # RSI 入场质量 (0-100)
    
    # ========== 波动率调整指标 ==========
    atr_normalized_pnl: float = 0.0  # ATR 标准化收益
    volatility_timing_score: float = 0.0  # 波动率择时能力 (0-100)
    avg_entry_atr_ratio: float = 0.0  # 平均入场 ATR 比率
    
    # ========== 当前持仓分析 ==========
    position_health_score: float = 0.0  # 持仓健康度 (0-100)
    position_trend_alignment: float = 0.0  # 持仓趋势一致性 (0-1)
    position_atr_distance: float = 0.0  # 入场价距当前价(ATR单位)
    positions_in_profit: int = 0  # 盈利持仓数
    positions_in_loss: int = 0  # 亏损持仓数
    
    # ========== 分类胜率 ==========
    trend_trades: int = 0  # 顺势交易数
    counter_trend_trades: int = 0  # 逆势交易数
    trend_win_rate: float = 0.0  # 顺势交易胜率
    counter_trend_win_rate: float = 0.0  # 逆势交易胜率
    high_vol_trades: int = 0  # 高波动期交易数
    low_vol_trades: int = 0  # 低波动期交易数
    high_vol_win_rate: float = 0.0  # 高波动期胜率
    low_vol_win_rate: float = 0.0  # 低波动期胜率
    
    # ========== 支撑/阻力分析 ==========
    support_resistance_accuracy: float = 0.0  # 支撑/阻力准确率
    breakout_success_rate: float = 0.0  # 突破成功率
    
    # ========== 综合评分 ==========
    overall_technical_score: float = 0.0  # 技术面综合评分 (0-100)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class TechnicalAnalyzer:
    """
    技术面分析器
    
    通过蜡烛线数据分析交易者的技术面能力:
    - 入场时机质量
    - 趋势判断能力
    - 波动率适应能力
    - 当前持仓健康度
    
    使用示例:
        ```python
        from screener.technical_analyzer import TechnicalAnalyzer
        
        analyzer = TechnicalAnalyzer()
        
        # 分析入场时机
        metrics = analyzer.analyze_fills(fills, user_state)
        print(f"入场时机评分: {metrics.entry_timing_score}")
        print(f"趋势顺应率: {metrics.trend_alignment_rate:.1%}")
        ```
    """
    
    def __init__(
        self,
        config: Optional[TechnicalConfig] = None,
        hl_client: Optional[Any] = None
    ):
        """
        初始化技术面分析器
        
        Args:
            config: 技术面分析配置
            hl_client: HyperliquidClient 实例（可选）
        """
        self.config = config or TechnicalConfig()
        self._client = hl_client
        self._candle_cache: Dict[str, pd.DataFrame] = {}
        self._initialized = False
    
    def _ensure_client(self) -> bool:
        """确保客户端已初始化"""
        if self._client is not None:
            return True
        
        try:
            from clients.hyperliquid_client import HyperliquidClient
            self._client = HyperliquidClient()
            self._initialized = True
            return True
        except ImportError:
            logger.warning("无法导入 HyperliquidClient，技术面分析不可用")
            return False
        except Exception as e:
            logger.warning(f"初始化 HyperliquidClient 失败: {e}")
            return False
    
    def analyze_fills(
        self,
        fills: List[Dict],
        user_state: Optional[Dict] = None
    ) -> TechnicalMetrics:
        """
        综合分析成交记录和持仓
        
        Args:
            fills: 成交记录列表
            user_state: 用户状态（可选）
        
        Returns:
            TechnicalMetrics 技术面指标
        """
        metrics = TechnicalMetrics()
        
        if not self._ensure_client():
            return metrics
        
        if not fills:
            return metrics
        
        try:
            # 1. 分析入场时机
            self._analyze_entry_timing(metrics, fills)
            
            # 2. 计算 ATR 标准化收益
            self._analyze_atr_normalized_pnl(metrics, fills)
            
            # 3. 分析波动率择时
            self._analyze_volatility_timing(metrics, fills)
            
            # 4. 分析当前持仓
            if user_state:
                positions = user_state.get('assetPositions', [])
                self._analyze_current_positions(metrics, positions)
            
            # 5. 计算综合评分
            self._calculate_overall_score(metrics)
            
        except Exception as e:
            logger.warning(f"技术面分析失败: {e}")
        
        return metrics
    
    def _analyze_entry_timing(
        self,
        metrics: TechnicalMetrics,
        fills: List[Dict]
    ) -> None:
        """
        分析入场时机质量
        
        评估维度:
        - 趋势一致性：入场方向是否与趋势一致
        - RSI 位置：入场时 RSI 是否在合适区间
        - 均线位置：入场价与均线的相对位置
        """
        trend_aligned = 0
        counter_trend = 0
        trend_wins = 0
        counter_wins = 0
        total_entries = 0
        rsi_quality_sum = 0.0
        ma_quality_sum = 0.0
        
        for fill in fills:
            trade_type = fill.get('trade_type', '')
            if 'open' not in trade_type:
                continue
            
            total_entries += 1
            symbol = fill.get('coin')
            entry_time = datetime.fromtimestamp(fill['time'] / 1000)
            entry_price = float(fill.get('px', 0))
            is_long = 'long' in trade_type
            closed_pnl = float(fill.get('closedPnl', 0))
            
            # 获取入场时的K线数据
            candles = self._get_candles(
                symbol, entry_time, self.config.lookback_bars
            )
            if candles.empty or len(candles) < self.config.min_candles_required:
                continue
            
            # 计算趋势 (SMA 斜率)
            sma_period = self.config.sma_period
            sma = candles['close'].rolling(sma_period).mean()
            if len(sma) >= 5:
                trend_up = sma.iloc[-1] > sma.iloc[-5]
                
                # 趋势一致性判断
                if (is_long and trend_up) or (not is_long and not trend_up):
                    trend_aligned += 1
                    if closed_pnl > 0:
                        trend_wins += 1
                else:
                    counter_trend += 1
                    if closed_pnl > 0:
                        counter_wins += 1
            
            # RSI 质量评估
            rsi = self._calculate_rsi(candles['close'], self.config.rsi_period)
            if len(rsi) > 0 and not np.isnan(rsi.iloc[-1]):
                current_rsi = rsi.iloc[-1]
                rsi_quality = self._evaluate_rsi_quality(current_rsi, is_long)
                rsi_quality_sum += rsi_quality
            
            # MA 位置质量
            if len(sma) > 0 and not np.isnan(sma.iloc[-1]):
                ma_val = sma.iloc[-1]
                ma_quality = self._evaluate_ma_quality(entry_price, ma_val, is_long)
                ma_quality_sum += ma_quality
        
        # 计算汇总指标
        if total_entries > 0:
            metrics.trend_alignment_rate = trend_aligned / total_entries
            metrics.rsi_entry_quality = rsi_quality_sum / total_entries
            metrics.ma_entry_quality = ma_quality_sum / total_entries
            
            # 入场时机综合评分
            metrics.entry_timing_score = (
                metrics.trend_alignment_rate * self.config.trend_weight * 100 +
                metrics.rsi_entry_quality * self.config.rsi_weight +
                metrics.ma_entry_quality * self.config.ma_weight
            )
        
        # 分类胜率
        metrics.trend_trades = trend_aligned
        metrics.counter_trend_trades = counter_trend
        if trend_aligned > 0:
            metrics.trend_win_rate = trend_wins / trend_aligned
        if counter_trend > 0:
            metrics.counter_trend_win_rate = counter_wins / counter_trend
    
    def _analyze_atr_normalized_pnl(
        self,
        metrics: TechnicalMetrics,
        fills: List[Dict]
    ) -> None:
        """
        计算 ATR 标准化的 PnL
        
        消除不同市场波动率的影响，使收益更具可比性
        """
        normalized_pnls = []
        atr_ratios = []
        
        for fill in fills:
            closed_pnl = float(fill.get('closedPnl', 0))
            if closed_pnl == 0:
                continue
            
            symbol = fill.get('coin')
            trade_time = datetime.fromtimestamp(fill['time'] / 1000)
            trade_price = float(fill.get('px', 0))
            
            candles = self._get_candles(
                symbol, trade_time, self.config.atr_lookback_bars
            )
            if candles.empty or len(candles) < self.config.atr_period:
                continue
            
            atr = self._calculate_atr(candles, self.config.atr_period)
            if len(atr) > 0 and atr.iloc[-1] > 0:
                atr_val = atr.iloc[-1]
                
                # ATR 比率
                atr_ratio = atr_val / trade_price if trade_price > 0 else 0
                atr_ratios.append(atr_ratio)
                
                # 标准化 PnL: 实际收益 / (价格 * ATR%)
                if atr_ratio > 0:
                    normalized = closed_pnl / (trade_price * atr_ratio)
                    normalized_pnls.append(normalized)
        
        if normalized_pnls:
            metrics.atr_normalized_pnl = sum(normalized_pnls)
        if atr_ratios:
            metrics.avg_entry_atr_ratio = sum(atr_ratios) / len(atr_ratios)
    
    def _analyze_volatility_timing(
        self,
        metrics: TechnicalMetrics,
        fills: List[Dict]
    ) -> None:
        """
        分析波动率择时能力
        
        评估交易者是否能在高波动/低波动期做出正确决策
        """
        high_vol_trades = 0
        low_vol_trades = 0
        high_vol_wins = 0
        low_vol_wins = 0
        
        # 计算波动率中位数作为高/低分界
        vol_samples = []
        for fill in fills:
            symbol = fill.get('coin')
            trade_time = datetime.fromtimestamp(fill['time'] / 1000)
            
            candles = self._get_candles(symbol, trade_time, 20)
            if candles.empty or len(candles) < 14:
                continue
            
            atr = self._calculate_atr(candles, 14)
            if len(atr) > 0 and atr.iloc[-1] > 0:
                vol_samples.append(atr.iloc[-1] / candles['close'].iloc[-1])
        
        if not vol_samples:
            return
        
        vol_median = np.median(vol_samples)
        
        # 分析每笔交易
        vol_idx = 0
        for fill in fills:
            closed_pnl = float(fill.get('closedPnl', 0))
            if closed_pnl == 0:
                continue
            
            symbol = fill.get('coin')
            trade_time = datetime.fromtimestamp(fill['time'] / 1000)
            
            candles = self._get_candles(symbol, trade_time, 20)
            if candles.empty or len(candles) < 14:
                continue
            
            atr = self._calculate_atr(candles, 14)
            if len(atr) == 0 or atr.iloc[-1] <= 0:
                continue
            
            current_vol = atr.iloc[-1] / candles['close'].iloc[-1]
            
            if current_vol >= vol_median:
                high_vol_trades += 1
                if closed_pnl > 0:
                    high_vol_wins += 1
            else:
                low_vol_trades += 1
                if closed_pnl > 0:
                    low_vol_wins += 1
        
        metrics.high_vol_trades = high_vol_trades
        metrics.low_vol_trades = low_vol_trades
        
        if high_vol_trades > 0:
            metrics.high_vol_win_rate = high_vol_wins / high_vol_trades
        if low_vol_trades > 0:
            metrics.low_vol_win_rate = low_vol_wins / low_vol_trades
        
        # 波动率择时评分
        # 高波动期胜率高且低波动期也稳定 = 好
        if high_vol_trades > 0 and low_vol_trades > 0:
            metrics.volatility_timing_score = (
                metrics.high_vol_win_rate * 50 +
                metrics.low_vol_win_rate * 50
            )
        elif high_vol_trades > 0:
            metrics.volatility_timing_score = metrics.high_vol_win_rate * 100
        elif low_vol_trades > 0:
            metrics.volatility_timing_score = metrics.low_vol_win_rate * 100
    
    def _analyze_current_positions(
        self,
        metrics: TechnicalMetrics,
        positions: List[Dict]
    ) -> None:
        """
        分析当前持仓的技术面健康度
        """
        if not positions:
            return
        
        health_scores = []
        trend_alignments = []
        atr_distances = []
        in_profit = 0
        in_loss = 0
        
        for pos_data in positions:
            pos = pos_data.get('position', {})
            szi = float(pos.get('szi', 0))
            if szi == 0:
                continue
            
            symbol = pos.get('coin')
            entry_price = float(pos.get('entryPx', 0))
            unrealized_pnl = float(pos.get('unrealizedPnl', 0))
            is_long = szi > 0
            
            if unrealized_pnl > 0:
                in_profit += 1
            elif unrealized_pnl < 0:
                in_loss += 1
            
            # 获取当前K线
            candles = self._get_candles(symbol, datetime.now(), 50)
            if candles.empty or len(candles) < 20:
                continue
            
            current_price = candles['close'].iloc[-1]
            health = 50.0  # 基础分
            
            # 计算 ATR 距离
            atr = self._calculate_atr(candles, 14)
            if len(atr) > 0 and atr.iloc[-1] > 0:
                atr_val = atr.iloc[-1]
                distance = abs(current_price - entry_price) / atr_val
                atr_distances.append(distance)
            
            # 趋势判断
            sma = candles['close'].rolling(20).mean()
            if len(sma) >= 5 and not np.isnan(sma.iloc[-1]):
                trend_up = sma.iloc[-1] > sma.iloc[-5]
                
                # 持仓趋势一致性
                if (is_long and trend_up) or (not is_long and not trend_up):
                    health += 25
                    trend_alignments.append(1.0)
                else:
                    health -= 15
                    trend_alignments.append(0.0)
            
            # 浮盈浮亏影响
            if unrealized_pnl > 0:
                health += 20
            elif unrealized_pnl < 0:
                health -= 10
            
            # RSI 位置
            rsi = self._calculate_rsi(candles['close'], 14)
            if len(rsi) > 0 and not np.isnan(rsi.iloc[-1]):
                current_rsi = rsi.iloc[-1]
                # 检查是否在危险区域
                if is_long and current_rsi > 75:
                    health -= 10  # 做多但超买
                elif not is_long and current_rsi < 25:
                    health -= 10  # 做空但超卖
                elif is_long and 40 <= current_rsi <= 60:
                    health += 5  # 健康区间
                elif not is_long and 40 <= current_rsi <= 60:
                    health += 5
            
            health_scores.append(max(0, min(100, health)))
        
        # 汇总指标
        metrics.positions_in_profit = in_profit
        metrics.positions_in_loss = in_loss
        
        if health_scores:
            metrics.position_health_score = sum(health_scores) / len(health_scores)
        if trend_alignments:
            metrics.position_trend_alignment = sum(trend_alignments) / len(trend_alignments)
        if atr_distances:
            metrics.position_atr_distance = sum(atr_distances) / len(atr_distances)
    
    def _calculate_overall_score(self, metrics: TechnicalMetrics) -> None:
        """
        计算技术面综合评分
        """
        score = 0.0
        weights_sum = 0.0
        
        # 入场时机 (权重 40%)
        if metrics.entry_timing_score > 0:
            score += metrics.entry_timing_score * 0.40
            weights_sum += 0.40
        
        # 趋势顺应 (权重 20%)
        if metrics.trend_trades > 0:
            trend_score = metrics.trend_alignment_rate * 100
            score += trend_score * 0.20
            weights_sum += 0.20
        
        # 波动率择时 (权重 20%)
        if metrics.volatility_timing_score > 0:
            score += metrics.volatility_timing_score * 0.20
            weights_sum += 0.20
        
        # 持仓健康 (权重 20%)
        if metrics.position_health_score > 0:
            score += metrics.position_health_score * 0.20
            weights_sum += 0.20
        
        # 归一化
        if weights_sum > 0:
            metrics.overall_technical_score = score / weights_sum
        else:
            metrics.overall_technical_score = 50.0  # 默认中等分数
    
    def _get_candles(
        self,
        symbol: str,
        end_time: datetime,
        bars: int
    ) -> pd.DataFrame:
        """获取K线数据(带缓存)"""
        # 缓存 key: 按小时粒度缓存
        cache_hour = end_time.replace(minute=0, second=0, microsecond=0)
        cache_key = f"{symbol}:{cache_hour.isoformat()}:{bars}"
        
        if cache_key in self._candle_cache:
            return self._candle_cache[cache_key]
        
        try:
            # 计算需要的时间范围
            hours_needed = max(bars, 24)  # 至少获取24小时
            start_time = end_time - timedelta(hours=hours_needed)
            
            ohlcv_df = self._client.get_candles_dataframe(
                symbol,
                self.config.candle_interval,
                start_time,
                end_time
            )
            df = ohlcv_df.to_dataframe()
            
            # 缓存结果
            if len(self._candle_cache) < self.config.max_cache_size:
                self._candle_cache[cache_key] = df
            
            return df
            
        except Exception as e:
            logger.debug(f"获取K线失败 {symbol}: {e}")
            return pd.DataFrame()
    
    def _evaluate_rsi_quality(self, rsi: float, is_long: bool) -> float:
        """评估 RSI 入场质量"""
        if is_long:
            # 做多：RSI 30-50 最佳，20-30/50-60 次之
            if 30 <= rsi <= 50:
                return 100.0
            elif 20 <= rsi < 30:
                return 85.0
            elif 50 < rsi <= 60:
                return 70.0
            elif rsi < 20:
                return 60.0  # 超卖，风险较高但可能反弹
            elif 60 < rsi <= 70:
                return 50.0
            else:  # rsi > 70
                return 30.0  # 超买做多，风险高
        else:
            # 做空：RSI 50-70 最佳
            if 50 <= rsi <= 70:
                return 100.0
            elif 70 < rsi <= 80:
                return 85.0
            elif 40 <= rsi < 50:
                return 70.0
            elif rsi > 80:
                return 60.0  # 超买，风险较高但可能回调
            elif 30 <= rsi < 40:
                return 50.0
            else:  # rsi < 30
                return 30.0  # 超卖做空，风险高
    
    def _evaluate_ma_quality(
        self,
        entry_price: float,
        ma_val: float,
        is_long: bool
    ) -> float:
        """评估均线位置入场质量"""
        if ma_val <= 0:
            return 50.0
        
        distance = (entry_price - ma_val) / ma_val
        
        if is_long:
            # 做多：价格在 MA 附近或略下方较好
            if -0.02 <= distance <= 0.01:
                return 100.0  # 理想位置
            elif -0.05 <= distance < -0.02:
                return 85.0  # 略低于均线
            elif 0.01 < distance <= 0.03:
                return 70.0  # 略高于均线
            elif -0.10 <= distance < -0.05:
                return 60.0  # 较低
            elif 0.03 < distance <= 0.05:
                return 55.0
            else:
                return 40.0  # 距离过远
        else:
            # 做空：价格在 MA 附近或略上方较好
            if -0.01 <= distance <= 0.02:
                return 100.0
            elif 0.02 < distance <= 0.05:
                return 85.0
            elif -0.03 <= distance < -0.01:
                return 70.0
            elif 0.05 < distance <= 0.10:
                return 60.0
            elif -0.05 <= distance < -0.03:
                return 55.0
            else:
                return 40.0
    
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """计算 RSI"""
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        
        rs = gain / loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.rolling(period).mean()
    
    @staticmethod
    def _calculate_bollinger_bands(
        prices: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算布林带"""
        middle = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        return upper, middle, lower
    
    def clear_cache(self) -> None:
        """清空K线缓存"""
        self._candle_cache.clear()
        logger.debug("技术面分析缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            'cached_candles': len(self._candle_cache),
            'max_cache_size': self.config.max_cache_size,
        }


# 便捷函数
def analyze_technical(
    fills: List[Dict],
    user_state: Optional[Dict] = None,
    config: Optional[TechnicalConfig] = None
) -> TechnicalMetrics:
    """
    技术面分析（便捷函数）
    
    Args:
        fills: 成交记录列表
        user_state: 用户状态
        config: 技术面分析配置
    
    Returns:
        TechnicalMetrics 技术面指标
    """
    analyzer = TechnicalAnalyzer(config)
    return analyzer.analyze_fills(fills, user_state)
