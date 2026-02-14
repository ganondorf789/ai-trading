"""
交易者 PnL 历史模块 (PostgreSQL)

存储从 Hyperliquid portfolio API 获取的 perp PnL 时间序列数据
周期: perpDay, perpWeek, perpAllTime
"""
from typing import List, Dict, Any, Optional
from psycopg2 import extras
from loguru import logger


class TraderPnlHistoryOps:
    """交易者 PnL 历史相关操作"""

    def save_pnl_history(self, address: str, portfolio_data: List) -> int:
        """
        保存交易者的 perp PnL 历史数据

        Args:
            address: 交易者地址
            portfolio_data: portfolio API 返回的原始数据 [[period, data], ...]

        Returns:
            保存的记录数
        """
        # 只保留 perp 相关周期
        perp_periods = {'perpDay', 'perpWeek', 'perpAllTime'}

        rows = []
        for period, data in portfolio_data:
            if period not in perp_periods:
                continue

            pnl_history = data.get('pnlHistory', [])
            account_value_history = data.get('accountValueHistory', [])
            vlm = data.get('vlm', '0')

            # 构建 account_value 的时间戳映射
            av_map = {ts: val for ts, val in account_value_history}

            for ts, pnl_val in pnl_history:
                rows.append((
                    address,
                    period,
                    ts,
                    float(pnl_val),
                    float(av_map.get(ts, 0)),
                    float(vlm),
                ))

        if not rows:
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for row in rows:
                try:
                    cursor.execute("""
                        INSERT INTO trader_pnl_history (
                            address, period, time, pnl, account_value, vlm
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT(address, period, time) DO UPDATE SET
                            pnl = EXCLUDED.pnl,
                            account_value = EXCLUDED.account_value,
                            vlm = EXCLUDED.vlm
                    """, row)
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存 PnL 历史记录失败: {e}")

        return saved_count

    def get_pnl_history(
        self,
        address: str,
        period: str = 'perpAllTime',
        limit: int = 0,
    ) -> List[Dict]:
        """
        获取交易者指定周期的 PnL 历史

        Args:
            address: 交易者地址
            period: 周期 (perpDay, perpWeek, perpAllTime)
            limit: 返回数量，0 表示不限制

        Returns:
            PnL 历史记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            sql = """
                SELECT time, pnl, account_value, vlm
                FROM trader_pnl_history
                WHERE address = %s AND period = %s
                ORDER BY time ASC
            """
            params: list = [address, period]

            if limit > 0:
                sql += " LIMIT %s"
                params.append(limit)

            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_pnl_history_all_periods(self, address: str) -> Dict[str, List[Dict]]:
        """
        获取交易者所有 perp 周期的 PnL 历史

        Args:
            address: 交易者地址

        Returns:
            {period: [记录列表]} 字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT period, time, pnl, account_value, vlm
                FROM trader_pnl_history
                WHERE address = %s
                ORDER BY period, time ASC
            """, (address,))

            result: Dict[str, List[Dict]] = {}
            for row in cursor.fetchall():
                period = row['period']
                if period not in result:
                    result[period] = []
                result[period].append({
                    'time': row['time'],
                    'pnl': float(row['pnl']),
                    'account_value': float(row['account_value']),
                    'vlm': float(row['vlm']),
                })
            return result

    def delete_pnl_history(self, address: str, period: Optional[str] = None) -> int:
        """
        删除交易者的 PnL 历史记录

        Args:
            address: 交易者地址
            period: 指定周期，None 则删除所有周期

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if period:
                cursor.execute(
                    "DELETE FROM trader_pnl_history WHERE address = %s AND period = %s",
                    (address, period)
                )
            else:
                cursor.execute(
                    "DELETE FROM trader_pnl_history WHERE address = %s",
                    (address,)
                )
            return cursor.rowcount
