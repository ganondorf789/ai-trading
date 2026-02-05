"""
指标计算模块

负责从成交记录计算各种交易指标

注意：盈利笔数、亏损笔数、胜率、总盈亏、已实现盈亏、7天盈亏、最大回撤、Sharpe Ratio
这些指标是基于完整的仓位历史（开仓→平仓周期）计算的，而不是单笔成交记录。
这样更能准确反映交易者的真实表现。
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
    TagMetrics,
)
from .tag_calculator import TraderTagCalculator
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
    rebuild_positions_from_fills,
    calculate_position_based_metrics,
    calculate_position_pnl_by_time,
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
        store_fills: bool = True,
        db_total_trades: Optional[int] = None
    ) -> TraderMetrics:
        """
        计算交易者指标
        
        注意：盈利笔数、亏损笔数、胜率、总盈亏、已实现盈亏、7天盈亏、
        最大回撤、Sharpe Ratio 等指标是基于完整的仓位历史计算的，
        而不是单笔成交记录。
        
        Args:
            address: 交易者地址
            fills: 成交记录列表
            user_state: 用户状态
            store_fills: 是否存储原始交易记录
            db_total_trades: 从数据库获取的总交易数（如果提供则使用此值）
        
        Returns:
            TraderMetrics 对象
        """
        metrics = TraderMetrics(address=address)
        
        if not fills:
            return metrics
        
        # 预处理成交记录
        processed_fills = self._preprocess_fills(fills)
        
        # 从 fills 重建仓位历史
        # 这样可以更准确地计算胜率、盈亏笔数等指标
        positions = rebuild_positions_from_fills(processed_fills)
        position_metrics = calculate_position_based_metrics(positions)
        
        # 计算各类指标（使用仓位历史）
        self._calculate_pnl_metrics(metrics, processed_fills, positions, position_metrics, db_total_trades)
        self._calculate_trade_metrics(metrics, processed_fills, positions, position_metrics, db_total_trades)
        self._calculate_risk_metrics(metrics, processed_fills, positions, position_metrics)
        self._calculate_activity_metrics(metrics, processed_fills, positions, position_metrics, db_total_trades)
        
        # 从用户状态计算
        if user_state:
            self._calculate_position_metrics(metrics, user_state)
            self._calculate_roi_metrics(metrics, user_state)
        
        # 存储原始数据
        if store_fills:
            metrics.fills = processed_fills
        
        if user_state:
            metrics.asset_positions = user_state.get('assetPositions', [])
        
        # 计算交易者标签
        self._calculate_tags(metrics)
        
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
        fills: List[Dict],
        positions: List[Dict],
        position_metrics: Dict[str, Any],
        db_total_trades: Optional[int] = None
    ) -> None:
        """
        计算盈亏指标
        
        注意：总盈亏、已实现盈亏、7天盈亏等指标基于完整仓位历史计算
        
        Args:
            metrics: 指标对象
            fills: 成交记录
            positions: 仓位历史
            position_metrics: 基于仓位计算的指标
            db_total_trades: 从数据库获取的总交易数
        """
        pnl = metrics.pnl
        
        # ===== 基于仓位历史计算的核心指标 =====
        # 使用仓位历史计算总盈亏、已实现盈亏
        pnl.total_pnl = position_metrics.get('total_pnl', 0.0)
        pnl.realized_pnl = position_metrics.get('total_pnl', 0.0)
        
        # 7天盈亏：基于7天内平仓的仓位
        pnl.recent_7d_pnl = calculate_position_pnl_by_time(positions, days=7)
        
        # 平均每笔盈亏（基于已平仓位数）
        total_closed = position_metrics.get('total_closed_positions', 0)
        if total_closed > 0:
            pnl.avg_profit_per_trade = pnl.total_pnl / total_closed
        
        # 平均盈利/亏损金额（基于仓位）
        pnl.avg_win_amount = position_metrics.get('avg_win', 0.0)
        pnl.avg_loss_amount = position_metrics.get('avg_loss', 0.0)
        
        # ===== 基于 fills 计算的辅助指标（按时间段统计）=====
        daily_pnl: Dict[str, float] = {}
        weekly_pnl: Dict[str, float] = {}
        monthly_pnl: Dict[str, float] = {}
        
        # 仍然使用 fills 来计算时间段统计（因为需要精确的时间信息）
        for fill in fills:
            closed_pnl = float(fill.get('closedPnl', 0))
            trade_time = timestamp_to_pendulum(fill.get('time', 0))
            day_key, week_key, month_key = get_time_keys(trade_time)
            
            daily_pnl[day_key] = daily_pnl.get(day_key, 0) + closed_pnl
            weekly_pnl[week_key] = weekly_pnl.get(week_key, 0) + closed_pnl
            monthly_pnl[month_key] = monthly_pnl.get(month_key, 0) + closed_pnl
        
        # 时间段均值
        if daily_pnl:
            pnl.daily_pnl = sum(daily_pnl.values()) / len(daily_pnl)
        if weekly_pnl:
            pnl.weekly_pnl = sum(weekly_pnl.values()) / len(weekly_pnl)
        if monthly_pnl:
            pnl.monthly_pnl = sum(monthly_pnl.values()) / len(monthly_pnl)
        
        # 单仓最大盈亏（基于仓位）
        position_pnl_list = position_metrics.get('pnl_list', [])
        if position_pnl_list:
            pnl.max_single_win = max(position_pnl_list) if max(position_pnl_list) > 0 else 0
            pnl.max_single_loss = abs(min(position_pnl_list)) if min(position_pnl_list) < 0 else 0
        
        # 存储临时数据供其他计算使用
        metrics._pnl_list = position_pnl_list  # 使用仓位盈亏列表
        metrics._total_profit = position_metrics.get('total_profit', 0.0)
        metrics._total_loss = position_metrics.get('total_loss', 0.0)
        metrics._daily_pnl = daily_pnl
    
    def _calculate_trade_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict],
        positions: List[Dict],
        position_metrics: Dict[str, Any],
        db_total_trades: Optional[int] = None
    ) -> None:
        """
        计算交易统计指标
        
        注意：盈利笔数、亏损笔数、胜率等指标基于完整仓位历史计算
        
        Args:
            metrics: 指标对象
            fills: 成交记录
            positions: 仓位历史
            position_metrics: 基于仓位计算的指标
            db_total_trades: 从数据库获取的总交易数（如果提供则使用此值）
        """
        trade = metrics.trade
        
        # ===== 基于仓位历史计算的核心指标 =====
        # 盈利/亏损笔数（基于已平仓位）
        trade.winning_trades = position_metrics.get('winning_positions', 0)
        trade.losing_trades = position_metrics.get('losing_positions', 0)
        
        # 总交易数：已平仓位数 + 未平仓位数
        total_closed = position_metrics.get('total_closed_positions', 0)
        total_open = position_metrics.get('total_open_positions', 0)
        trade.total_trades = db_total_trades if db_total_trades is not None else (total_closed + total_open)
        
        # 胜率（基于已平仓位）
        trade.win_rate = position_metrics.get('win_rate', 0.0)
        
        # 盈亏比（基于仓位历史）
        pf = position_metrics.get('profit_factor', 0.0)
        trade.profit_factor = pf if pf != float('inf') else float('inf')
        
        # ===== 基于 fills 计算的辅助指标 =====
        total_price = 0.0
        total_size_usd = 0.0
        symbol_counts: Dict[str, int] = {}
        long_count = 0
        short_count = 0
        
        daily_volume: Dict[str, float] = {}
        weekly_volume: Dict[str, float] = {}
        monthly_volume: Dict[str, float] = {}
        
        for fill in fills:
            price = float(fill.get('px', 0))
            size = float(fill.get('sz', 0))
            volume = price * size
            
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
            
            # 按时间段统计交易量
            trade_time = timestamp_to_pendulum(fill.get('time', 0))
            day_key, week_key, month_key = get_time_keys(trade_time)
            
            daily_volume[day_key] = daily_volume.get(day_key, 0) + volume
            weekly_volume[week_key] = weekly_volume.get(week_key, 0) + volume
            monthly_volume[month_key] = monthly_volume.get(month_key, 0) + volume
        
        # 计算平均值
        num_fills = len(fills)
        if num_fills > 0:
            trade.avg_trade_price = total_price / num_fills
            trade.avg_trade_size = total_size_usd / num_fills
        
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
        
        # 最近 7 天胜率（基于仓位历史）
        recent_7d_positions = [
            p for p in positions 
            if p.get('status') == 'closed' and 
               (p.get('close_time', 0) or 0) >= (now_shanghai().subtract(days=7).timestamp() * 1000)
        ]
        if recent_7d_positions:
            recent_7d_wins = sum(1 for p in recent_7d_positions if (p.get('realized_pnl', 0) or 0) > 0)
            trade.recent_7d_win_rate = recent_7d_wins / len(recent_7d_positions)
    
    def _calculate_risk_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict],
        positions: List[Dict],
        position_metrics: Dict[str, Any]
    ) -> None:
        """
        计算风险指标
        
        注意：最大回撤、Sharpe Ratio 等指标基于仓位盈亏序列计算，
        而不是单笔成交记录的盈亏。这样更能反映真实的风险特征。
        
        Args:
            metrics: 指标对象
            fills: 成交记录
            positions: 仓位历史
            position_metrics: 基于仓位计算的指标
        """
        risk = metrics.risk
        
        # 使用仓位盈亏列表（已平仓位的盈亏序列）
        pnl_list = position_metrics.get('pnl_list', [])
        
        if len(pnl_list) < 2:
            return
        
        # 按仓位平仓时间排序盈亏列表
        closed_positions = [p for p in positions if p.get('status') == 'closed']
        closed_positions.sort(key=lambda x: x.get('close_time', 0) or 0)
        sorted_pnl_list = [p.get('realized_pnl', 0) or 0 for p in closed_positions]
        
        if len(sorted_pnl_list) < 2:
            sorted_pnl_list = pnl_list
        
        # 最大回撤（基于仓位累计盈亏）
        risk.max_drawdown, risk.max_drawdown_abs = calculate_max_drawdown(sorted_pnl_list)
        
        # 夏普比率（基于仓位盈亏）
        risk.sharpe_ratio = calculate_sharpe_ratio(sorted_pnl_list)
        
        # 索提诺比率
        risk.sortino_ratio = calculate_sortino_ratio(sorted_pnl_list)
        
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
        
        # VaR 指标（基于仓位盈亏）
        risk.var_95 = calculate_var(sorted_pnl_list, 0.95)
        risk.var_99 = calculate_var(sorted_pnl_list, 0.99)
        risk.cvar_95 = calculate_expected_shortfall(sorted_pnl_list, 0.95)
        
        # 连续盈亏（基于仓位盈亏序列）
        risk.max_consecutive_wins, risk.max_consecutive_losses = \
            calculate_consecutive_streaks(sorted_pnl_list)
    
    def _calculate_activity_metrics(
        self,
        metrics: TraderMetrics,
        fills: List[Dict],
        positions: List[Dict],
        position_metrics: Dict[str, Any],
        db_total_trades: Optional[int] = None
    ) -> None:
        """
        计算活跃度指标
        
        Args:
            metrics: 指标对象
            fills: 成交记录
            positions: 仓位历史
            position_metrics: 基于仓位计算的指标
            db_total_trades: 从数据库获取的总交易数
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
        
        # 交易频率（基于仓位数）
        if activity.first_trade_time and activity.last_trade_time:
            days_active = (activity.last_trade_time - activity.first_trade_time).days + 1
            if days_active > 0:
                # 使用仓位数而不是 fills 数
                total_positions = (
                    position_metrics.get('total_closed_positions', 0) + 
                    position_metrics.get('total_open_positions', 0)
                )
                total_trades = db_total_trades if db_total_trades is not None else total_positions
                activity.trade_frequency_per_day = total_trades / days_active
        
        # 平均持仓时间（基于仓位历史）
        activity.avg_holding_time_hours = position_metrics.get('avg_holding_hours', 0.0)
    
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
    
    def _calculate_tags(self, metrics: TraderMetrics) -> None:
        """
        计算交易者标签
        
        Args:
            metrics: 指标对象
        """
        tag_calculator = TraderTagCalculator()
        metrics.tags = tag_calculator.calculate_tags(metrics)
    
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
    store_fills: bool = True,
    db_total_trades: Optional[int] = None
) -> TraderMetrics:
    """
    计算交易者指标（便捷函数）
    
    Args:
        address: 交易者地址
        fills: 成交记录列表
        user_state: 用户状态
        store_fills: 是否存储原始交易记录
        db_total_trades: 从数据库获取的总交易数（如果提供则使用此值）
    
    Returns:
        TraderMetrics 对象
    """
    calculator = MetricsCalculator()
    return calculator.calculate(address, fills, user_state, store_fills, db_total_trades)
