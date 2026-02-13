"""
交易者标签计算模块

基于交易指标自动为交易者分配标签（英文值存储）
"""
from dataclasses import dataclass
from typing import Optional, List
from loguru import logger

from .models import TraderMetrics, TagMetrics


@dataclass
class TagThresholds:
    """
    标签分类阈值配置
    """
    # 账户总价值阈值 (USD)
    account_small_max: float = 100_000.0
    account_medium_max: float = 500_000.0

    # 交易节奏阈值（小时）
    rhythm_ultra_short_max: float = 1.0
    rhythm_short_max: float = 24.0
    rhythm_swing_max: float = 168.0  # 7天

    # 方向偏好阈值 (long_short_ratio)
    direction_bearish_max: float = 0.3
    direction_bullish_min: float = 0.7

    # 盈利状态阈值
    profit_active_days_min: int = 30
    profit_trades_min: int = 30
    profit_roi_min: float = 0.05
    profit_pf_min: float = 1.3
    break_even_range: float = 0.05


class TraderTagCalculator:
    """
    交易者标签计算器

    根据交易指标自动为交易者分配各类标签
    """

    def __init__(self, thresholds: Optional[TagThresholds] = None):
        self.thresholds = thresholds or TagThresholds()

    def calculate_tags(self, metrics: TraderMetrics) -> TagMetrics:
        """
        计算交易者的所有标签

        Args:
            metrics: 交易者指标

        Returns:
            TagMetrics 对象
        """
        tags = TagMetrics()

        tags.account_value = self._calculate_account_value(metrics)
        tags.trading_rhythm = self._calculate_trading_rhythm(metrics)
        tags.profit_status = self._calculate_profit_status(metrics)
        tags.direction_preference = self._calculate_direction_preference(metrics)
        tags.trading_style = self._calculate_trading_style(metrics)

        return tags

    def _calculate_account_value(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算账户总价值标签

        基于 current_equity:
        - small_capital: < 100K
        - medium_capital: 100K - 500K
        - whale: >= 500K
        """
        equity = metrics.position.current_equity
        if equity <= 0:
            return None

        t = self.thresholds
        if equity < t.account_small_max:
            return "small_capital"
        elif equity < t.account_medium_max:
            return "medium_capital"
        else:
            return "whale"

    def _calculate_trading_rhythm(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算交易节奏标签

        基于 avg_holding_time_hours:
        - ultra_short: < 1h
        - short_term: 1-24h
        - swing: 24-168h
        - long_term: > 168h
        """
        holding_hours = metrics.activity.avg_holding_time_hours
        if holding_hours <= 0:
            return None

        t = self.thresholds
        if holding_hours < t.rhythm_ultra_short_max:
            return "ultra_short"
        elif holding_hours < t.rhythm_short_max:
            return "short_term"
        elif holding_hours < t.rhythm_swing_max:
            return "swing"
        else:
            return "long_term"

    def _calculate_profit_status(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算盈利状态标签

        - consistent_profit: 90d活跃天>=30 AND 90d交易>=30 AND ROI>=5% AND PF>=1.3
                             AND expectancy>0 AND 30d_pnl>0
        - break_even: |ROI| < 5%
        - volatile_profit: total_pnl > 0 (但不满足 consistent_profit)
        """
        if metrics.trade.total_trades == 0:
            return None

        t = self.thresholds
        active_days_90d = metrics.activity.active_days_90d
        trades_90d = metrics.trade.total_trades_90d
        roi = metrics.roi.roi
        pf = metrics.trade.profit_factor
        win_rate = metrics.trade.win_rate
        avg_win = metrics.pnl.avg_win_amount
        avg_loss = metrics.pnl.avg_loss_amount
        pnl_30d = metrics.pnl.recent_30d_pnl

        # 计算 expectancy
        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

        # consistent_profit: 严格标准
        if (active_days_90d >= t.profit_active_days_min and
                trades_90d >= t.profit_trades_min and
                roi >= t.profit_roi_min and
                pf >= t.profit_pf_min and pf != float('inf') and
                expectancy > 0 and
                pnl_30d > 0):
            return "consistent_profit"

        # break_even
        if -t.break_even_range < roi < t.break_even_range:
            return "break_even"

        # volatile_profit
        if metrics.pnl.total_pnl > 0:
            return "volatile_profit"

        return None

    def _calculate_direction_preference(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算方向偏好标签

        基于 long_short_ratio:
        - bearish: < 0.3
        - neutral: 0.3 - 0.7
        - bullish: > 0.7
        """
        if metrics.trade.total_trades == 0:
            return None

        ratio = metrics.trade.long_short_ratio
        t = self.thresholds

        if ratio < t.direction_bearish_max:
            return "bearish"
        elif ratio >= t.direction_bullish_min:
            return "bullish"
        else:
            return "neutral"

    def _calculate_trading_style(self, metrics: TraderMetrics) -> List[str]:
        """
        计算交易风格标签（多标签，每个独立判断）

        - high_freq_stable: 持仓≤24h AND 胜率>0.6 AND 盈亏比≥1.2 AND PF≥1.2 AND 30d交易≥20
        - high_freq_aggressive: 持仓≤24h AND 胜率<0.5 AND 盈亏比≥5 AND PF≥1.5 AND 30d交易≥20
        - low_freq_stable: 持仓>168h AND 胜率>0.6 AND 盈亏比≥1.2 AND PF≥1.2 AND 30d交易≤10
        - stable_profit: 胜率≥0.6 AND 盈亏比≥1.5 AND 回撤≤0.25 AND PF≥1.5 AND Sharpe≥1.0
        - high_risk_high_return: 盈亏比≥3 AND 平均每笔盈利≥10000 AND 回撤≥0.3
        - asymmetric_master: 胜率<0.5 AND 盈亏比≥5 AND PF≥1.5 AND 30d交易≤20
        """
        styles = []

        if metrics.trade.total_trades == 0:
            return styles

        holding = metrics.activity.avg_holding_time_hours
        win_rate = metrics.trade.win_rate
        avg_win = metrics.pnl.avg_win_amount
        avg_loss = metrics.pnl.avg_loss_amount
        pf = metrics.trade.profit_factor
        drawdown = metrics.risk.max_drawdown
        sharpe = metrics.risk.sharpe_ratio
        avg_profit = metrics.pnl.avg_profit_per_trade
        trades_30d = metrics.trade.recent_30d_trades

        # risk_reward = avg_win / avg_loss
        risk_reward = avg_win / avg_loss if avg_loss > 0 else 0.0

        # high_freq_stable
        if (holding <= 24 and win_rate > 0.6 and risk_reward >= 1.2
                and pf >= 1.2 and pf != float('inf') and trades_30d >= 20):
            styles.append("high_freq_stable")

        # high_freq_aggressive
        if (holding <= 24 and win_rate < 0.5 and risk_reward >= 5
                and pf >= 1.5 and pf != float('inf') and trades_30d >= 20):
            styles.append("high_freq_aggressive")

        # low_freq_stable
        if (holding > 168 and win_rate > 0.6 and risk_reward >= 1.2
                and pf >= 1.2 and pf != float('inf') and trades_30d <= 10):
            styles.append("low_freq_stable")

        # stable_profit
        if (win_rate >= 0.6 and risk_reward >= 1.5 and drawdown <= 0.25
                and pf >= 1.5 and pf != float('inf') and sharpe >= 1.0):
            styles.append("stable_profit")

        # high_risk_high_return
        if risk_reward >= 3 and avg_profit >= 10000 and drawdown >= 0.3:
            styles.append("high_risk_high_return")

        # asymmetric_master
        if (win_rate < 0.5 and risk_reward >= 5
                and pf >= 1.5 and pf != float('inf') and trades_30d <= 20):
            styles.append("asymmetric_master")

        return styles


def calculate_tags(
    metrics: TraderMetrics,
    thresholds: Optional[TagThresholds] = None
) -> TraderMetrics:
    """
    计算交易者标签（便捷函数）

    Args:
        metrics: 交易者指标
        thresholds: 分类阈值配置

    Returns:
        更新后的 TraderMetrics
    """
    calculator = TraderTagCalculator(thresholds)
    metrics.tags = calculator.calculate_tags(metrics)
    return metrics
