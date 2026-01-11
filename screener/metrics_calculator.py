"""
指标计算模块

负责从成交记录计算各种交易指标
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pendulum
from loguru import logger

from .models import (
    TraderMetrics,
    PnLMetrics,
    RiskMetrics,
    TradeMetrics,
    ActivityMetrics,
    PositionMetrics,
    ROIMetrics,
    ScoreMetrics,
)
from .utils import (
    SHANGHAI_TZ,
    timestamp_to_pendulum,
    get_time_keys,
    now_shanghai,
    calculate_trade_type,
    safe_divide,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_var,
    calculate_expected_shortfall,
    calculate_consecutive_streaks,
    calculate_holding_time,
)


class MetricsCalculator:
    """
    指标计算器
    
    从成交记录和用户状态计算交易者的各种指标
    """
    
    def __init__(self):
        """初始化计算器"""
        pass
    
    def calculate(
        self,
        address: str,
        fills: List[Dict],
        user_state: Optional[Dict] = None,
        store_fills: bool = True
    ) -> TraderMetrics:
        """
        计算交易者指标
        
        Args:
            address: 交易者地址
            fills: 成交记录列表
            user_state: 用户状态
            store_fills: 是否存储原始交易记录
        
        Returns:
            TraderMetrics 对象
        """
        metrics = TraderMetrics(address=address)
        
        if not fills:
            return metrics
        
        # 预处理成交记录
        processed_fills = self._preprocess_fills(fills)
        
        # 计算各类指标
        self._calculate_pnl_metrics(metrics, processed_fills)
        self._calculate_trade_metrics(metrics, processed_fills)
        self._calculate_risk_metrics(metrics, processed_fills)
        self._calculate_activity_metrics(metrics, processed_fills)
        
        # 从用户状态计算
        if user_state:
            self._calculate_position_metrics(metrics, user_state)
            self._calculate_roi_metrics(metrics, user_state)
        
        # 存储原始数据
        if store_fills:
            metrics.fills = processed_fills
        
        if user_state:
            metrics.asset_positions = user_state.get('assetPositions', [])
        
        # 清理临时属性，避免内存泄漏
        self._cleanup_temp_attributes(metrics)
        
        return metrics
    
    def _preprocess_fills(self, fills: List[Dict]) -> List[Dict]:
        """
        预处理成交记录
        
        Args:
            fills: 原始成交记录
        
        Returns:
            处理后的成交记录
        """
        processed = []
        
        for fill in fills:
            # 复制以避免修改原始数据
            fill_copy = fill.copy()
            
            # 计算交易类型
            dir_val = fill_copy.get('dir', '')
            start_pos = float(fill_copy.get('startPosition', 0)) if fill_copy.get('startPosition') else 0
            fill_copy['trade_type'] = calculate_trade_type(dir_val, start_pos)
            
            processed.append(fill_copy)
        
        # 按时间排序
        processed.sort(key=lambda x: x.get('time', 0))
        
        return processed
    
    def _calculate_pnl_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict]
    ) -> None:
        """
        计算盈亏指标
        
        Args:
            metrics: 指标对象
            fills: 成交记录
        """
        pnl = metrics.pnl
        
        total_profit = 0.0
        total_loss = 0.0
        pnl_list = []
        win_amounts = []
        loss_amounts = []
        
        daily_pnl: Dict[str, float] = {}
        weekly_pnl: Dict[str, float] = {}
        monthly_pnl: Dict[str, float] = {}
        
        recent_7d_start = now_shanghai().subtract(days=7)
        recent_7d_pnl = 0.0
        
        for fill in fills:
            closed_pnl = float(fill.get('closedPnl', 0))
            
            pnl.realized_pnl += closed_pnl
            pnl_list.append(closed_pnl)
            
            # 盈亏分类
            if closed_pnl > 0:
                total_profit += closed_pnl
                win_amounts.append(closed_pnl)
            elif closed_pnl < 0:
                total_loss += abs(closed_pnl)
                loss_amounts.append(abs(closed_pnl))
            
            # 按时间段统计
            trade_time = timestamp_to_pendulum(fill.get('time', 0))
            day_key, week_key, month_key = get_time_keys(trade_time)
            
            daily_pnl[day_key] = daily_pnl.get(day_key, 0) + closed_pnl
            weekly_pnl[week_key] = weekly_pnl.get(week_key, 0) + closed_pnl
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + closed_pnl
            
            # 最近 7 天统计
            if trade_time >= recent_7d_start:
                recent_7d_pnl += closed_pnl
        
        # 计算汇总指标
        pnl.total_pnl = pnl.realized_pnl
        pnl.recent_7d_pnl = recent_7d_pnl
        
        # 时间段均值
        if daily_pnl:
            pnl.daily_pnl = sum(daily_pnl.values()) / len(daily_pnl)
        if weekly_pnl:
            pnl.weekly_pnl = sum(weekly_pnl.values()) / len(weekly_pnl)
        if monthly_pnl:
            pnl.monthly_pnl = sum(monthly_pnl.values()) / len(monthly_pnl)
        
        # 单笔统计
        if pnl_list:
            pnl.max_single_win = max(pnl_list) if max(pnl_list) > 0 else 0
            pnl.max_single_loss = abs(min(pnl_list)) if min(pnl_list) < 0 else 0
        
        if win_amounts:
            pnl.avg_win_amount = sum(win_amounts) / len(win_amounts)
        if loss_amounts:
            pnl.avg_loss_amount = sum(loss_amounts) / len(loss_amounts)
        
        if len(fills) > 0:
            pnl.avg_profit_per_trade = pnl.realized_pnl / len(fills)
        
        # 存储临时数据供其他计算使用
        metrics._pnl_list = pnl_list
        metrics._total_profit = total_profit
        metrics._total_loss = total_loss
        metrics._daily_pnl = daily_pnl
    
    def _calculate_trade_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict]
    ) -> None:
        """
        计算交易统计指标
        
        Args:
            metrics: 指标对象
            fills: 成交记录
        """
        trade = metrics.trade
        
        trade.total_trades = len(fills)
        
        total_price = 0.0
        total_size_usd = 0.0
        symbol_counts: Dict[str, int] = {}
        long_count = 0
        short_count = 0
        
        daily_volume: Dict[str, float] = {}
        weekly_volume: Dict[str, float] = {}
        monthly_volume: Dict[str, float] = {}
        
        recent_7d_start = now_shanghai().subtract(days=7)
        recent_7d_wins = 0
        recent_7d_trades = 0
        
        for fill in fills:
            price = float(fill.get('px', 0))
            size = float(fill.get('sz', 0))
            volume = price * size
            closed_pnl = float(fill.get('closedPnl', 0))
            
            trade.total_volume += volume
            total_price += price
            total_size_usd += volume
            
            # 品种统计
            symbol = fill.get('coin', '')
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
            
            # 多空统计
            side = fill.get('side', '').upper()
            if side in ('B', 'BUY'):
                long_count += 1
            elif side in ('A', 'SELL'):
                short_count += 1
            
            # 盈亏统计
            if closed_pnl > 0:
                trade.winning_trades += 1
            elif closed_pnl < 0:
                trade.losing_trades += 1
            
            # 按时间段统计交易量
            trade_time = timestamp_to_pendulum(fill.get('time', 0))
            day_key, week_key, month_key = get_time_keys(trade_time)
            
            daily_volume[day_key] = daily_volume.get(day_key, 0) + volume
            weekly_volume[week_key] = weekly_volume.get(week_key, 0) + volume
            monthly_volume[month_key] = monthly_volume.get(month_key, 0) + volume
            
            # 最近 7 天统计
            if trade_time >= recent_7d_start:
                recent_7d_trades += 1
                if closed_pnl > 0:
                    recent_7d_wins += 1
        
        # 计算汇总指标
        if trade.total_trades > 0:
            trade.win_rate = trade.winning_trades / trade.total_trades
            trade.avg_trade_price = total_price / trade.total_trades
            trade.avg_trade_size = total_size_usd / trade.total_trades
        
        # 盈亏比
        total_loss = getattr(metrics, '_total_loss', 0)
        total_profit = getattr(metrics, '_total_profit', 0)
        if total_loss > 0:
            trade.profit_factor = total_profit / total_loss
        elif total_profit > 0:
            trade.profit_factor = float('inf')
        
        # 时间段均值
        if daily_volume:
            trade.daily_volume = sum(daily_volume.values()) / len(daily_volume)
        if weekly_volume:
            trade.weekly_volume = sum(weekly_volume.values()) / len(weekly_volume)
        if monthly_volume:
            trade.monthly_volume = sum(monthly_volume.values()) / len(monthly_volume)
        
        # 品种统计
        trade.unique_symbols = len(symbol_counts)
        if symbol_counts:
            trade.favorite_symbol = max(symbol_counts, key=symbol_counts.get)
        
        # 多空比例
        total_sides = long_count + short_count
        if total_sides > 0:
            trade.long_short_ratio = long_count / total_sides
        
        # 最近 7 天胜率
        if recent_7d_trades > 0:
            trade.recent_7d_win_rate = recent_7d_wins / recent_7d_trades
    
    def _calculate_risk_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict]
    ) -> None:
        """
        计算风险指标
        
        Args:
            metrics: 指标对象
            fills: 成交记录
        """
        risk = metrics.risk
        pnl_list = getattr(metrics, '_pnl_list', [])
        
        if len(pnl_list) < 2:
            return
        
        # 最大回撤
        risk.max_drawdown, risk.max_drawdown_abs = calculate_max_drawdown(pnl_list)
        
        # 夏普比率
        risk.sharpe_ratio = calculate_sharpe_ratio(pnl_list)
        
        # 索提诺比率
        risk.sortino_ratio = calculate_sortino_ratio(pnl_list)
        
        # 卡玛比率
        activity = metrics.activity
        if activity.first_trade_time and activity.last_trade_time:
            days = (activity.last_trade_time - activity.first_trade_time).days + 1
            if days > 0 and risk.max_drawdown > 0:
                risk.calmar_ratio = calculate_calmar_ratio(
                    metrics.pnl.total_pnl,
                    risk.max_drawdown,
                    days
                )
        
        # VaR 指标
        risk.var_95 = calculate_var(pnl_list, 0.95)
        risk.var_99 = calculate_var(pnl_list, 0.99)
        risk.cvar_95 = calculate_expected_shortfall(pnl_list, 0.95)
        
        # 连续盈亏
        risk.max_consecutive_wins, risk.max_consecutive_losses = \
            calculate_consecutive_streaks(pnl_list)
    
    def _calculate_activity_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict]
    ) -> None:
        """
        计算活跃度指标
        
        Args:
            metrics: 指标对象
            fills: 成交记录
        """
        activity = metrics.activity
        
        if not fills:
            return
        
        # 时间范围
        activity.first_trade_time = timestamp_to_pendulum(fills[0].get('time', 0))
        activity.last_trade_time = timestamp_to_pendulum(fills[-1].get('time', 0))
        
        # 活跃天数
        daily_pnl = getattr(metrics, '_daily_pnl', {})
        activity.active_days = len(daily_pnl)
        
        # 交易频率
        if activity.first_trade_time and activity.last_trade_time:
            days_active = (activity.last_trade_time - activity.first_trade_time).days + 1
            if days_active > 0:
                activity.trade_frequency_per_day = len(fills) / days_active
        
        # 平均持仓时间
        activity.avg_holding_time_hours = calculate_holding_time(fills)
    
    def _calculate_position_metrics(
        self,
        metrics: TraderMetrics,
        user_state: Dict
    ) -> None:
        """
        计算持仓指标
        
        Args:
            metrics: 指标对象
            user_state: 用户状态
        """
        position = metrics.position
        
        margin = user_state.get('marginSummary', {})
        position.current_equity = float(margin.get('accountValue', 0))
        
        positions = user_state.get('assetPositions', [])
        max_leverage = 1.0
        
        for pos_data in positions:
            pos = pos_data.get('position', {})
            szi = float(pos.get('szi', 0))
            
            if szi != 0:
                position.current_positions += 1
                
                # 未实现盈亏
                metrics.pnl.unrealized_pnl += float(pos.get('unrealizedPnl', 0))
                
                # 杠杆
                leverage = pos.get('leverage', {}).get('value', 1)
                if leverage:
                    max_leverage = max(max_leverage, int(leverage))
        
        position.avg_leverage = max_leverage
        position.max_leverage = max_leverage
    
    def _calculate_roi_metrics(
        self,
        metrics: TraderMetrics,
        user_state: Dict
    ) -> None:
        """
        计算收益率指标
        
        Args:
            metrics: 指标对象
            user_state: 用户状态
        """
        roi = metrics.roi
        equity = metrics.position.current_equity
        
        if equity <= 0:
            return
        
        roi.roi = metrics.pnl.total_pnl / equity
        roi.daily_roi = safe_divide(metrics.pnl.daily_pnl, equity)
        roi.weekly_roi = safe_divide(metrics.pnl.weekly_pnl, equity)
        roi.monthly_roi = safe_divide(metrics.pnl.monthly_pnl, equity)
    
    def _cleanup_temp_attributes(self, metrics: TraderMetrics) -> None:
        """
        清理临时属性，避免内存泄漏
        
        Args:
            metrics: 指标对象
        """
        # 删除计算过程中添加的临时属性
        temp_attrs = ['_pnl_list', '_total_profit', '_total_loss', '_daily_pnl']
        for attr in temp_attrs:
            if hasattr(metrics, attr):
                delattr(metrics, attr)


# 便捷函数
def calculate_metrics(
    address: str,
    fills: List[Dict],
    user_state: Optional[Dict] = None,
    store_fills: bool = True
) -> TraderMetrics:
    """
    计算交易者指标（便捷函数）
    
    Args:
        address: 交易者地址
        fills: 成交记录列表
        user_state: 用户状态
        store_fills: 是否存储原始交易记录
    
    Returns:
        TraderMetrics 对象
    """
    calculator = MetricsCalculator()
    return calculator.calculate(address, fills, user_state, store_fills)
