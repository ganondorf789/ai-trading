"""
交易者指标管理模块
"""
from typing import List, Dict, Optional, Any
import pendulum
from loguru import logger

from screener.trader_screener import TraderMetrics, SHANGHAI_TZ


class TraderMetricsOps:
    """交易者指标相关操作"""

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
                    win_rate, profit_factor, max_drawdown, sharpe_ratio, sortino_ratio, calmar_ratio,
                    avg_holding_time_hours, trade_frequency_per_day, avg_leverage,
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
                    daily_volume, weekly_volume, monthly_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    analyzed_at = excluded.analyzed_at,
                    total_trades = excluded.total_trades,
                    winning_trades = excluded.winning_trades,
                    losing_trades = excluded.losing_trades,
                    total_pnl = excluded.total_pnl,
                    realized_pnl = excluded.realized_pnl,
                    unrealized_pnl = excluded.unrealized_pnl,
                    total_volume = excluded.total_volume,
                    roi = excluded.roi,
                    avg_profit_per_trade = excluded.avg_profit_per_trade,
                    win_rate = excluded.win_rate,
                    profit_factor = excluded.profit_factor,
                    max_drawdown = excluded.max_drawdown,
                    sharpe_ratio = excluded.sharpe_ratio,
                    sortino_ratio = excluded.sortino_ratio,
                    calmar_ratio = excluded.calmar_ratio,
                    avg_holding_time_hours = excluded.avg_holding_time_hours,
                    trade_frequency_per_day = excluded.trade_frequency_per_day,
                    avg_leverage = excluded.avg_leverage,
                    active_days = excluded.active_days,
                    last_trade_time = excluded.last_trade_time,
                    first_trade_time = excluded.first_trade_time,
                    current_positions = excluded.current_positions,
                    current_equity = excluded.current_equity,
                    overall_score = excluded.overall_score,
                    rating = excluded.rating,
                    profitability_score = excluded.profitability_score,
                    risk_score = excluded.risk_score,
                    consistency_score = excluded.consistency_score,
                    activity_score = excluded.activity_score,
                    avg_trade_price = excluded.avg_trade_price,
                    avg_trade_size = excluded.avg_trade_size,
                    max_single_win = excluded.max_single_win,
                    max_single_loss = excluded.max_single_loss,
                    max_consecutive_wins = excluded.max_consecutive_wins,
                    max_consecutive_losses = excluded.max_consecutive_losses,
                    avg_win_amount = excluded.avg_win_amount,
                    avg_loss_amount = excluded.avg_loss_amount,
                    unique_symbols = excluded.unique_symbols,
                    favorite_symbol = excluded.favorite_symbol,
                    recent_7d_pnl = excluded.recent_7d_pnl,
                    recent_7d_win_rate = excluded.recent_7d_win_rate,
                    long_short_ratio = excluded.long_short_ratio,
                    daily_pnl = excluded.daily_pnl,
                    weekly_pnl = excluded.weekly_pnl,
                    monthly_pnl = excluded.monthly_pnl,
                    daily_roi = excluded.daily_roi,
                    weekly_roi = excluded.weekly_roi,
                    monthly_roi = excluded.monthly_roi,
                    daily_volume = excluded.daily_volume,
                    weekly_volume = excluded.weekly_volume,
                    monthly_volume = excluded.monthly_volume
            """, (
                metrics.address,
                pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
                metrics.total_trades,
                metrics.winning_trades,
                metrics.losing_trades,
                metrics.total_pnl,
                metrics.realized_pnl,
                metrics.unrealized_pnl,
                metrics.total_volume,
                metrics.roi,
                metrics.avg_profit_per_trade,
                metrics.win_rate,
                metrics.profit_factor if metrics.profit_factor != float('inf') else 999999.0,
                metrics.max_drawdown,
                metrics.sharpe_ratio,
                metrics.sortino_ratio,
                metrics.calmar_ratio,
                metrics.avg_holding_time_hours,
                metrics.trade_frequency_per_day,
                metrics.avg_leverage,
                metrics.active_days,
                metrics.last_trade_time.isoformat() if metrics.last_trade_time else None,
                metrics.first_trade_time.isoformat() if metrics.first_trade_time else None,
                metrics.current_positions,
                metrics.current_equity,
                metrics.overall_score,
                metrics.rating.value,
                metrics.profitability_score,
                metrics.risk_score,
                metrics.consistency_score,
                metrics.activity_score,
                metrics.avg_trade_price,
                metrics.avg_trade_size,
                metrics.max_single_win,
                metrics.max_single_loss,
                metrics.max_consecutive_wins,
                metrics.max_consecutive_losses,
                metrics.avg_win_amount,
                metrics.avg_loss_amount,
                metrics.unique_symbols,
                metrics.favorite_symbol,
                metrics.recent_7d_pnl,
                metrics.recent_7d_win_rate,
                metrics.long_short_ratio,
                metrics.daily_pnl,
                metrics.weekly_pnl,
                metrics.monthly_pnl,
                metrics.daily_roi,
                metrics.weekly_roi,
                metrics.monthly_roi,
                metrics.daily_volume,
                metrics.weekly_volume,
                metrics.monthly_volume
            ))

            return cursor.lastrowid

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
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE address = ?
                ORDER BY analyzed_at DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            return dict(row) if row else None

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
            cursor = conn.cursor()

            query = "SELECT * FROM trader_metrics WHERE 1=1"

            if min_rating:
                rating_order = {'S': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'F': 6}
                min_order = rating_order.get(min_rating, 6)
                valid_ratings = [r for r, o in rating_order.items() if o <= min_order]
                placeholders = ','.join(['?' for _ in valid_ratings])
                query += f" AND rating IN ({placeholders})"
                cursor.execute(
                    query + " ORDER BY overall_score DESC LIMIT ?",
                    valid_ratings + [limit]
                )
            else:
                cursor.execute(query + " ORDER BY overall_score DESC LIMIT ?", (limit,))

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
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE rating = ?
                ORDER BY overall_score DESC
            """, (rating,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trader_history(self, address: str, limit: int = 10) -> List[Dict]:
        """
        获取交易者的分析记录

        注意：由于使用 address 作为唯一键，每个地址只保留最新一条记录

        Args:
            address: 交易者地址
            limit: 返回数量（当前每个地址只有一条记录）

        Returns:
            记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE address = ?
                ORDER BY analyzed_at DESC
                LIMIT ?
            """, (address, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM trader_metrics")
            total_records = cursor.fetchone()[0]

            # 唯一地址数
            cursor.execute("SELECT COUNT(DISTINCT address) FROM trader_metrics")
            unique_addresses = cursor.fetchone()[0]

            # 各评级分布
            cursor.execute("""
                SELECT rating, COUNT(*) as count
                FROM trader_metrics
                GROUP BY rating
            """)
            rating_distribution = {row['rating']: row['count'] for row in cursor.fetchall()}

            # 会话数
            cursor.execute("SELECT COUNT(*) FROM screening_sessions")
            total_sessions = cursor.fetchone()[0]

            return {
                'total_records': total_records,
                'unique_addresses': unique_addresses,
                'rating_distribution': rating_distribution,
                'total_sessions': total_sessions
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
                WHERE analyzed_at < datetime('now', ?)
            """, (f'-{days} days',))
            deleted = cursor.rowcount
            logger.info(f"已删除 {deleted} 条旧记录")
