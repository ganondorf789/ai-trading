"""
交易者指标管理模块 (PostgreSQL)
"""
from typing import List, Dict, Optional, Any
import pendulum
from psycopg2 import extras
from loguru import logger

from screener import TraderMetrics, SHANGHAI_TZ
from utils import sanitize_value
from .cache import cache


class TraderMetricsOps:
    """交易者指标相关操作"""

    def _get_metric_value(self, metrics: TraderMetrics, attr_path: str, default=0.0):
        """
        安全获取指标值，支持嵌套属性
        
        Args:
            metrics: TraderMetrics 对象
            attr_path: 属性路径，如 'risk.var_95' 或 'total_pnl'
            default: 默认值
        
        Returns:
            属性值或默认值
        """
        try:
            parts = attr_path.split('.')
            value = metrics
            for part in parts:
                value = getattr(value, part)
            return value if value is not None else default
        except (AttributeError, TypeError):
            return default

    def _prepare_metrics_values(self, metrics: TraderMetrics) -> tuple:
        """
        准备用于数据库插入的指标值元组
        
        Args:
            metrics: TraderMetrics 对象
        
        Returns:
            值元组
        """
        # 获取 ROI 值（兼容新旧结构）
        roi_value = sanitize_value(self._get_metric_value(metrics, 'roi.roi', 0.0))
        
        # 获取新增风险指标
        max_drawdown_abs = sanitize_value(self._get_metric_value(metrics, 'risk.max_drawdown_abs', 0.0))
        var_95 = sanitize_value(self._get_metric_value(metrics, 'risk.var_95', 0.0))
        var_99 = sanitize_value(self._get_metric_value(metrics, 'risk.var_99', 0.0))
        cvar_95 = sanitize_value(self._get_metric_value(metrics, 'risk.cvar_95', 0.0))
        
        # 获取 max_leverage（兼容新旧结构）
        max_leverage = sanitize_value(self._get_metric_value(metrics, 'position.max_leverage', metrics.avg_leverage))
        
        return (
            metrics.address,
            pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
            sanitize_value(metrics.total_trades, 0),
            sanitize_value(metrics.winning_trades, 0),
            sanitize_value(metrics.losing_trades, 0),
            sanitize_value(metrics.total_pnl),
            sanitize_value(metrics.realized_pnl),
            sanitize_value(metrics.unrealized_pnl),
            sanitize_value(metrics.total_volume),
            roi_value,
            sanitize_value(metrics.avg_profit_per_trade),
            sanitize_value(metrics.win_rate),
            sanitize_value(metrics.profit_factor),
            sanitize_value(metrics.max_drawdown),
            max_drawdown_abs,
            sanitize_value(metrics.sharpe_ratio),
            sanitize_value(metrics.sortino_ratio),
            sanitize_value(metrics.calmar_ratio),
            var_95,
            var_99,
            cvar_95,
            sanitize_value(metrics.avg_holding_time_hours),
            sanitize_value(metrics.trade_frequency_per_day),
            sanitize_value(metrics.avg_leverage),
            max_leverage,
            sanitize_value(metrics.active_days, 0),
            metrics.last_trade_time.isoformat() if metrics.last_trade_time else None,
            metrics.first_trade_time.isoformat() if metrics.first_trade_time else None,
            sanitize_value(metrics.current_positions, 0),
            sanitize_value(metrics.current_equity),
            sanitize_value(metrics.overall_score),
            metrics.rating.value,
            sanitize_value(metrics.profitability_score),
            sanitize_value(metrics.risk_score),
            sanitize_value(metrics.consistency_score),
            sanitize_value(metrics.activity_score),
            sanitize_value(metrics.avg_trade_price),
            sanitize_value(metrics.avg_trade_size),
            sanitize_value(metrics.max_single_win),
            sanitize_value(metrics.max_single_loss),
            sanitize_value(metrics.max_consecutive_wins, 0),
            sanitize_value(metrics.max_consecutive_losses, 0),
            sanitize_value(metrics.avg_win_amount),
            sanitize_value(metrics.avg_loss_amount),
            sanitize_value(metrics.unique_symbols, 0),
            metrics.favorite_symbol or '',
            sanitize_value(metrics.recent_7d_pnl),
            sanitize_value(metrics.recent_7d_win_rate),
            sanitize_value(metrics.long_short_ratio),
            sanitize_value(metrics.daily_pnl),
            sanitize_value(metrics.weekly_pnl),
            sanitize_value(metrics.monthly_pnl),
            sanitize_value(metrics.daily_roi),
            sanitize_value(metrics.weekly_roi),
            sanitize_value(metrics.monthly_roi),
            sanitize_value(metrics.daily_volume),
            sanitize_value(metrics.weekly_volume),
            sanitize_value(metrics.monthly_volume),
            # Tags
            metrics.tag_capital_scale,
            metrics.tag_trading_direction,
            metrics.tag_trading_cycle,
            metrics.tag_frequency_style,
            metrics.tag_return_risk,
            metrics.tag_strategy_capability,
        )

    def save_trader(self, metrics: TraderMetrics) -> int:
        """
        保存或更新交易者指标（使用 address 作为唯一键）

        Args:
            metrics: 交易者指标对象

        Returns:
            记录ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO trader_metrics (
                    address, analyzed_at,
                    total_trades, winning_trades, losing_trades,
                    total_pnl, realized_pnl, unrealized_pnl, total_volume,
                    roi, avg_profit_per_trade,
                    win_rate, profit_factor, max_drawdown, max_drawdown_abs,
                    sharpe_ratio, sortino_ratio, calmar_ratio,
                    var_95, var_99, cvar_95,
                    avg_holding_time_hours, trade_frequency_per_day, avg_leverage, max_leverage,
                    active_days, last_trade_time, first_trade_time,
                    current_positions, current_equity,
                    overall_score, rating,
                    profitability_score, risk_score, consistency_score, activity_score,
                    avg_trade_price, avg_trade_size, max_single_win, max_single_loss,
                    max_consecutive_wins, max_consecutive_losses,
                    avg_win_amount, avg_loss_amount,
                    unique_symbols, favorite_symbol,
                    recent_7d_pnl, recent_7d_win_rate, long_short_ratio,
                    daily_pnl, weekly_pnl, monthly_pnl,
                    daily_roi, weekly_roi, monthly_roi,
                    daily_volume, weekly_volume, monthly_volume,
                    tag_capital_scale, tag_trading_direction, tag_trading_cycle,
                    tag_frequency_style, tag_return_risk, tag_strategy_capability
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(address) DO UPDATE SET
                    analyzed_at = EXCLUDED.analyzed_at,
                    total_trades = EXCLUDED.total_trades,
                    winning_trades = EXCLUDED.winning_trades,
                    losing_trades = EXCLUDED.losing_trades,
                    total_pnl = EXCLUDED.total_pnl,
                    realized_pnl = EXCLUDED.realized_pnl,
                    unrealized_pnl = EXCLUDED.unrealized_pnl,
                    total_volume = EXCLUDED.total_volume,
                    roi = EXCLUDED.roi,
                    avg_profit_per_trade = EXCLUDED.avg_profit_per_trade,
                    win_rate = EXCLUDED.win_rate,
                    profit_factor = EXCLUDED.profit_factor,
                    max_drawdown = EXCLUDED.max_drawdown,
                    max_drawdown_abs = EXCLUDED.max_drawdown_abs,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    sortino_ratio = EXCLUDED.sortino_ratio,
                    calmar_ratio = EXCLUDED.calmar_ratio,
                    var_95 = EXCLUDED.var_95,
                    var_99 = EXCLUDED.var_99,
                    cvar_95 = EXCLUDED.cvar_95,
                    avg_holding_time_hours = EXCLUDED.avg_holding_time_hours,
                    trade_frequency_per_day = EXCLUDED.trade_frequency_per_day,
                    avg_leverage = EXCLUDED.avg_leverage,
                    max_leverage = EXCLUDED.max_leverage,
                    active_days = EXCLUDED.active_days,
                    last_trade_time = EXCLUDED.last_trade_time,
                    first_trade_time = EXCLUDED.first_trade_time,
                    current_positions = EXCLUDED.current_positions,
                    current_equity = EXCLUDED.current_equity,
                    overall_score = EXCLUDED.overall_score,
                    rating = EXCLUDED.rating,
                    profitability_score = EXCLUDED.profitability_score,
                    risk_score = EXCLUDED.risk_score,
                    consistency_score = EXCLUDED.consistency_score,
                    activity_score = EXCLUDED.activity_score,
                    avg_trade_price = EXCLUDED.avg_trade_price,
                    avg_trade_size = EXCLUDED.avg_trade_size,
                    max_single_win = EXCLUDED.max_single_win,
                    max_single_loss = EXCLUDED.max_single_loss,
                    max_consecutive_wins = EXCLUDED.max_consecutive_wins,
                    max_consecutive_losses = EXCLUDED.max_consecutive_losses,
                    avg_win_amount = EXCLUDED.avg_win_amount,
                    avg_loss_amount = EXCLUDED.avg_loss_amount,
                    unique_symbols = EXCLUDED.unique_symbols,
                    favorite_symbol = EXCLUDED.favorite_symbol,
                    recent_7d_pnl = EXCLUDED.recent_7d_pnl,
                    recent_7d_win_rate = EXCLUDED.recent_7d_win_rate,
                    long_short_ratio = EXCLUDED.long_short_ratio,
                    daily_pnl = EXCLUDED.daily_pnl,
                    weekly_pnl = EXCLUDED.weekly_pnl,
                    monthly_pnl = EXCLUDED.monthly_pnl,
                    daily_roi = EXCLUDED.daily_roi,
                    weekly_roi = EXCLUDED.weekly_roi,
                    monthly_roi = EXCLUDED.monthly_roi,
                    daily_volume = EXCLUDED.daily_volume,
                    weekly_volume = EXCLUDED.weekly_volume,
                    monthly_volume = EXCLUDED.monthly_volume,
                    tag_capital_scale = EXCLUDED.tag_capital_scale,
                    tag_trading_direction = EXCLUDED.tag_trading_direction,
                    tag_trading_cycle = EXCLUDED.tag_trading_cycle,
                    tag_frequency_style = EXCLUDED.tag_frequency_style,
                    tag_return_risk = EXCLUDED.tag_return_risk,
                    tag_strategy_capability = EXCLUDED.tag_strategy_capability
                RETURNING id
            """, self._prepare_metrics_values(metrics))

            result = cursor.fetchone()
            trader_id = result[0] if result else None

            # 使缓存失效
            cache.invalidate_trader(metrics.address)

            return trader_id

    def save_traders(self, traders: List[TraderMetrics]) -> List[int]:
        """
        批量保存交易者指标

        Args:
            traders: 交易者指标列表

        Returns:
            插入的记录ID列表
        """
        ids = []
        for trader in traders:
            trader_id = self.save_trader(trader)
            ids.append(trader_id)
        logger.info(f"已保存 {len(ids)} 个交易者到数据库")
        return ids

    def get_trader_by_address(self, address: str) -> Optional[Dict]:
        """
        根据地址获取最新的交易者记录

        Args:
            address: 交易者地址

        Returns:
            交易者记录字典
        """
        # 尝试从缓存获取
        cached = cache.get_trader(address)
        if cached:
            return cached

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE address = %s
                ORDER BY analyzed_at DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            result = dict(row) if row else None

            # 缓存结果
            if result:
                cache.cache_trader(address, result)

            return result

    def get_top_traders(
        self,
        limit: int = 20,
        min_rating: str = None
    ) -> List[Dict]:
        """
        获取评分最高的交易者

        Args:
            limit: 返回数量
            min_rating: 最低评级

        Returns:
            交易者记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if min_rating:
                rating_order = {'S': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'F': 6}
                min_order = rating_order.get(min_rating, 6)
                valid_ratings = [r for r, o in rating_order.items() if o <= min_order]
                
                cursor.execute("""
                    SELECT * FROM trader_metrics
                    WHERE rating = ANY(%s)
                    ORDER BY overall_score DESC
                    LIMIT %s
                """, (valid_ratings, limit))
            else:
                cursor.execute("""
                    SELECT * FROM trader_metrics
                    ORDER BY overall_score DESC
                    LIMIT %s
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_traders_by_rating(self, rating: str) -> List[Dict]:
        """
        根据评级获取交易者

        Args:
            rating: 评级 (S/A/B/C/D/F)

        Returns:
            交易者记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE rating = %s
                ORDER BY overall_score DESC
            """, (rating,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trader_history(self, address: str, limit: int = 10) -> List[Dict]:
        """
        获取交易者的分析记录

        Args:
            address: 交易者地址
            limit: 返回数量

        Returns:
            记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE address = %s
                ORDER BY analyzed_at DESC
                LIMIT %s
            """, (address, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 总记录数
            cursor.execute("SELECT COUNT(*) as count FROM trader_metrics")
            total_records = cursor.fetchone()['count']

            # 唯一地址数
            cursor.execute("SELECT COUNT(DISTINCT address) as count FROM trader_metrics")
            unique_addresses = cursor.fetchone()['count']

            # 各评级分布
            cursor.execute("""
                SELECT rating, COUNT(*) as count
                FROM trader_metrics
                GROUP BY rating
            """)
            rating_distribution = {row['rating']: row['count'] for row in cursor.fetchall()}

            return {
                'total_records': total_records,
                'unique_addresses': unique_addresses,
                'rating_distribution': rating_distribution
            }

    def delete_old_records(self, days: int = 90):
        """
        删除旧记录

        Args:
            days: 保留最近多少天的记录
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM trader_metrics
                WHERE analyzed_at < NOW() - INTERVAL '%s days'
            """, (days,))
            deleted = cursor.rowcount
            logger.info(f"已删除 {deleted} 条旧记录")

    def toggle_star(self, address: str, is_starred: bool) -> bool:
        """
        切换交易者收藏状态

        Args:
            address: 交易者地址
            is_starred: 是否收藏

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trader_metrics
                SET is_starred = %s
                WHERE address = %s
            """, (is_starred, address))
            updated = cursor.rowcount > 0
            
            # 使缓存失效
            if updated:
                cache.invalidate_trader(address)
                logger.info(f"交易者 {address[:10]}... 收藏状态: {is_starred}")
            
            return updated

    def get_starred_traders(self, limit: int = 100) -> List[Dict]:
        """
        获取所有收藏的交易者

        Args:
            limit: 返回数量

        Returns:
            收藏的交易者列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE is_starred = TRUE
                ORDER BY overall_score DESC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_total_trades(self, address: str, total_trades: int) -> bool:
        """
        更新交易者的总交易数

        Args:
            address: 交易者地址
            total_trades: 新的总交易数

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trader_metrics
                SET total_trades = %s, analyzed_at = NOW()
                WHERE address = %s
            """, (total_trades, address))
            updated = cursor.rowcount > 0
            
            # 使缓存失效
            if updated:
                cache.invalidate_trader(address)
                logger.info(f"交易者 {address[:10]}... total_trades 更新为: {total_trades}")
            
            return updated

    def get_position_analysis_for_trader(self, address: str) -> Dict[str, Any]:
        """
        获取交易员的仓位分析详情
        
        Args:
            address: 交易者地址
            
        Returns:
            仓位分析详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # 基础统计
            cursor.execute("""
                SELECT
                    COUNT(*) as total_positions,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as winning_positions,
                    COUNT(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN 1 END) as losing_positions,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(AVG(realized_pnl) FILTER (WHERE status = 'closed'), 0) as avg_pnl,
                    COALESCE(AVG(realized_pnl) FILTER (WHERE realized_pnl > 0 AND status = 'closed'), 0) as avg_win_pnl,
                    COALESCE(AVG(ABS(realized_pnl)) FILTER (WHERE realized_pnl < 0 AND status = 'closed'), 0) as avg_loss_pnl,
                    MAX(realized_pnl) as best_position,
                    MIN(realized_pnl) as worst_position,
                    COALESCE(AVG(holding_hours) FILTER (WHERE status = 'closed'), 0) as avg_holding_hours,
                    COALESCE(AVG(open_trades), 1) as avg_build_trades,
                    COALESCE(SUM(total_fee), 0) as total_fees,
                    COUNT(DISTINCT coin) as unique_coins
                FROM position_history
                WHERE address = %s
            """, (address,))
            
            stats = dict(cursor.fetchone())
            
            # 计算胜率和盈亏比
            closed = stats.get('closed_positions', 0)
            winning = stats.get('winning_positions', 0)
            stats['position_win_rate'] = round(winning / closed * 100, 1) if closed > 0 else 0
            
            avg_win = stats.get('avg_win_pnl', 0)
            avg_loss = stats.get('avg_loss_pnl', 0)
            stats['position_profit_factor'] = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0
            
            # 按币种统计
            cursor.execute("""
                SELECT
                    coin,
                    COUNT(*) as positions,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as wins,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(AVG(holding_hours) FILTER (WHERE status = 'closed'), 0) as avg_holding
                FROM position_history
                WHERE address = %s AND status = 'closed'
                GROUP BY coin
                ORDER BY total_pnl DESC
                LIMIT 10
            """, (address,))
            
            stats['by_coin'] = [dict(row) for row in cursor.fetchall()]
            
            # 近期表现（30天）
            cursor.execute("""
                SELECT
                    COUNT(*) as positions,
                    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as wins,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl
                FROM position_history
                WHERE address = %s 
                  AND status = 'closed'
                  AND close_time > NOW() - INTERVAL '30 days'
            """, (address,))
            
            recent = cursor.fetchone()
            stats['recent_30d'] = {
                'positions': recent['positions'],
                'wins': recent['wins'],
                'total_pnl': recent['total_pnl'],
                'win_rate': round(recent['wins'] / recent['positions'] * 100, 1) if recent['positions'] > 0 else 0
            }
            
            return stats