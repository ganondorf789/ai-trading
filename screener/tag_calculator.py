"""
交易者标签计算模块

基于交易指标自动为交易者分配标签
"""
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from .models import TraderMetrics, TagMetrics


@dataclass
class TagThresholds:
    """
    标签分类阈值配置
    
    可以根据需要调整这些阈值来优化分类
    """
    # 资金规模阈值 (USD)
    capital_small_max: float = 10000.0
    capital_medium_max: float = 100000.0
    
    # 交易方向阈值 (long_short_ratio)
    direction_bearish_max: float = 0.4
    direction_neutral_max: float = 0.6
    
    # 交易周期阈值 (小时)
    cycle_ultra_short_max: float = 4.0
    cycle_short_max: float = 24.0
    cycle_swing_max: float = 168.0  # 7天
    
    # 频率与风格阈值
    frequency_high_threshold: float = 5.0  # 日均交易频率
    aggressive_drawdown_threshold: float = 0.2  # 回撤阈值
    
    # 收益与风险阈值
    stable_sharpe_min: float = 1.5
    stable_win_rate_min: float = 0.55
    stable_drawdown_max: float = 0.15
    continuous_profit_factor_min: float = 1.5
    continuous_win_rate_min: float = 0.5
    volatile_sharpe_max: float = 0.5
    high_risk_drawdown_min: float = 0.3
    low_drawdown_max: float = 0.1
    break_even_roi_range: float = 0.05
    
    # 策略能力阈值
    volatility_sortino_min: float = 2.0
    volatility_calmar_min: float = 1.0
    asymmetric_ratio_min: float = 2.0


class TraderTagCalculator:
    """
    交易者标签计算器
    
    根据交易指标自动为交易者分配各类标签
    """
    
    def __init__(self, thresholds: Optional[TagThresholds] = None):
        """
        初始化标签计算器
        
        Args:
            thresholds: 分类阈值配置
        """
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
        
        # 计算各类标签
        tags.capital_scale = self._calculate_capital_scale(metrics)
        tags.trading_direction = self._calculate_trading_direction(metrics)
        tags.trading_cycle = self._calculate_trading_cycle(metrics)
        tags.frequency_style = self._calculate_frequency_style(metrics)
        tags.return_risk = self._calculate_return_risk(metrics)
        tags.strategy_capability = self._calculate_strategy_capability(metrics)
        
        return tags
    
    def _calculate_capital_scale(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算资金规模标签
        
        基于 current_equity 判断:
        - 小资金: < $10,000
        - 中等资金: $10,000 - $100,000
        - 大资金: >= $100,000
        """
        equity = metrics.position.current_equity
        
        if equity <= 0:
            return None
        
        t = self.thresholds
        
        if equity < t.capital_small_max:
            return "小资金"
        elif equity < t.capital_medium_max:
            return "中等资金"
        else:
            return "大资金"
    
    def _calculate_trading_direction(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算交易方向标签
        
        基于 long_short_ratio 判断:
        - 偏空头: ratio < 0.4
        - 中性: 0.4 <= ratio <= 0.6
        - 偏多头: ratio > 0.6
        """
        ratio = metrics.trade.long_short_ratio
        
        # 如果没有交易数据，无法判断
        if metrics.trade.total_trades == 0:
            return None
        
        t = self.thresholds
        
        if ratio < t.direction_bearish_max:
            return "偏空头"
        elif ratio <= t.direction_neutral_max:
            return "中性"
        else:
            return "偏多头"
    
    def _calculate_trading_cycle(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算交易周期标签
        
        基于 avg_holding_time_hours 判断:
        - 超短线: < 4 小时
        - 短线: 4-24 小时
        - 波段: 24-168 小时 (1-7天)
        - 长线: > 168 小时
        """
        holding_hours = metrics.activity.avg_holding_time_hours
        
        # 如果没有持仓时间数据，无法判断
        if holding_hours <= 0:
            return None
        
        t = self.thresholds
        
        if holding_hours < t.cycle_ultra_short_max:
            return "超短线"
        elif holding_hours < t.cycle_short_max:
            return "短线"
        elif holding_hours < t.cycle_swing_max:
            return "波段"
        else:
            return "长线"
    
    def _calculate_frequency_style(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算频率与风格标签
        
        结合交易频率和最大回撤判断:
        - 高频激进: 日均交易频率 > 5 且 回撤 > 20%
        - 低频激进: 日均交易频率 <= 5 且 回撤 > 20%
        - 低频稳健: 日均交易频率 <= 5 且 回撤 <= 20%
        """
        freq = metrics.activity.trade_frequency_per_day
        drawdown = metrics.risk.max_drawdown
        
        # 如果没有交易数据，无法判断
        if metrics.trade.total_trades == 0:
            return None
        
        t = self.thresholds
        
        is_high_freq = freq > t.frequency_high_threshold
        is_aggressive = drawdown > t.aggressive_drawdown_threshold
        
        if is_high_freq and is_aggressive:
            return "高频激进"
        elif not is_high_freq and is_aggressive:
            return "低频激进"
        elif not is_high_freq and not is_aggressive:
            return "低频稳健"
        else:
            # 高频但不激进，暂时归类为低频稳健（可以根据需要添加新类别）
            return "低频稳健"
    
    def _calculate_return_risk(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算收益与风险标签
        
        基于多个指标综合判断（按优先级）:
        - 稳定盈利: sharpe > 1.5 且 win_rate > 55% 且 drawdown < 15%
        - 低回撤: drawdown < 10% 且 total_pnl > 0
        - 持续盈利: profit_factor > 1.5 且 win_rate > 50%
        - 高风险高回报: total_pnl > 0 且 drawdown > 30%
        - 波动盈利: total_pnl > 0 且 sharpe < 0.5
        - 盈亏平衡: -5% < roi < 5%
        """
        # 如果没有交易数据，无法判断
        if metrics.trade.total_trades == 0:
            return None
        
        t = self.thresholds
        
        sharpe = metrics.risk.sharpe_ratio
        win_rate = metrics.trade.win_rate
        drawdown = metrics.risk.max_drawdown
        profit_factor = metrics.trade.profit_factor
        total_pnl = metrics.pnl.total_pnl
        roi = metrics.roi.roi
        
        # 按优先级判断（越稳定的标签优先级越高）
        
        # 稳定盈利：最高标准
        if (sharpe > t.stable_sharpe_min and 
            win_rate > t.stable_win_rate_min and 
            drawdown < t.stable_drawdown_max):
            return "稳定盈利"
        
        # 低回撤：风险控制良好
        if drawdown < t.low_drawdown_max and total_pnl > 0:
            return "低回撤"
        
        # 持续盈利：有持续的盈利能力
        if (profit_factor > t.continuous_profit_factor_min and 
            win_rate > t.continuous_win_rate_min and
            profit_factor != float('inf')):
            return "持续盈利"
        
        # 高风险高回报：敢于冒险且有收益
        if total_pnl > 0 and drawdown > t.high_risk_drawdown_min:
            return "高风险高回报"
        
        # 波动盈利：有盈利但不稳定
        if total_pnl > 0 and sharpe < t.volatile_sharpe_max:
            return "波动盈利"
        
        # 盈亏平衡：基本没赚没亏
        if -t.break_even_roi_range < roi < t.break_even_roi_range:
            return "盈亏平衡"
        
        return None
    
    def _calculate_strategy_capability(self, metrics: TraderMetrics) -> Optional[str]:
        """
        计算策略能力标签
        
        - 波动策略: sortino_ratio > 2 或 calmar_ratio > 1（善于利用波动）
        - 非对称高手: avg_win_amount / avg_loss_amount > 2（盈亏不对称优势）
        """
        # 如果没有交易数据，无法判断
        if metrics.trade.total_trades == 0:
            return None
        
        t = self.thresholds
        
        sortino = metrics.risk.sortino_ratio
        calmar = metrics.risk.calmar_ratio
        avg_win = metrics.pnl.avg_win_amount
        avg_loss = metrics.pnl.avg_loss_amount
        
        # 检查非对称高手：平均盈利远大于平均亏损
        if avg_loss > 0 and avg_win / avg_loss > t.asymmetric_ratio_min:
            return "非对称高手"
        
        # 检查波动策略：善于在波动中获利
        if (sortino > t.volatility_sortino_min or 
            (calmar > t.volatility_calmar_min and calmar != float('inf'))):
            return "波动策略"
        
        return None


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
