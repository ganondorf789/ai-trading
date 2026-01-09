"""
筛选会话管理模块 (PostgreSQL)
"""
from typing import List, Dict, Any
from psycopg2 import extras
from loguru import logger


class ScreeningOps:
    """筛选会话相关操作"""

    def save_screening_session(
        self,
        traders,
        config: Dict[str, Any],
        total_analyzed: int
    ) -> int:
        """
        保存筛选会话

        Args:
            traders: 符合条件的交易者列表
            config: 筛选配置
            total_analyzed: 总分析数量

        Returns:
            会话ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 插入会话记录
            cursor.execute("""
                INSERT INTO screening_sessions (
                    lookback_days, min_total_trades, min_win_rate,
                    min_profit_factor, min_total_pnl, max_drawdown,
                    total_analyzed, qualified_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                config.get('lookback_days', 30),
                config.get('min_total_trades', 10),
                config.get('min_win_rate', 0.45),
                config.get('min_profit_factor', 1.0),
                config.get('min_total_pnl', 0.0),
                config.get('max_drawdown', 0.5),
                total_analyzed,
                len(traders)
            ))

            session_id = cursor.fetchone()[0]

            # 保存交易者并关联到会话
            for rank, trader in enumerate(traders, 1):
                # 保存交易者
                trader_id = self.save_trader(trader)

                # 关联到会话
                cursor.execute("""
                    INSERT INTO session_traders (session_id, trader_id, rank)
                    VALUES (%s, %s, %s)
                """, (session_id, trader_id, rank))

            logger.info(f"筛选会话已保存: session_id={session_id}, traders={len(traders)}")
            return session_id

    def get_session_traders(self, session_id: int) -> List[Dict]:
        """
        获取指定会话的交易者

        Args:
            session_id: 会话ID

        Returns:
            交易者记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT tm.*, st.rank
                FROM trader_metrics tm
                JOIN session_traders st ON tm.id = st.trader_id
                WHERE st.session_id = %s
                ORDER BY st.rank
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的筛选会话

        Args:
            limit: 返回数量

        Returns:
            会话记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM screening_sessions
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
