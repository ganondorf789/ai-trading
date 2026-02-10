"""
资金费历史管理模块 (PostgreSQL)

存储和查询用户的资金费支付记录
"""
from typing import List, Dict, Any, Optional
import pendulum
from psycopg2 import extras
from loguru import logger

from utils import sanitize_float


class TraderFundingOps:
    """资金费历史相关操作"""

    def save_funding_records(self, address: str, records: List[Dict]) -> int:
        """
        保存用户的资金费历史记录

        Args:
            address: 交易者地址
            records: 资金费记录列表（API 原始格式）

        Returns:
            保存的记录数
        """
        if not records:
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for record in records:
                try:
                    delta = record.get('delta', {})
                    time_ms = record.get('time', 0)

                    cursor.execute("""
                        INSERT INTO trader_funding_history (
                            address, coin, funding_rate, szi, usdc, 
                            n_samples, hash, time
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(address, time, coin) DO UPDATE SET
                            funding_rate = EXCLUDED.funding_rate,
                            usdc = EXCLUDED.usdc,
                            szi = EXCLUDED.szi
                    """, (
                        address,
                        delta.get('coin', ''),
                        delta.get('fundingRate', '0'),
                        sanitize_float(delta.get('szi', 0)),
                        sanitize_float(delta.get('usdc', 0)),
                        delta.get('nSamples'),
                        record.get('hash', ''),
                        time_ms,
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存资金费记录失败: {e}")

        return saved_count

    def get_funding_records(
        self,
        address: str,
        limit: int = 100,
        coin: str = None,
        start_time: int = None,
        end_time: int = None,
        sort_order: str = 'desc'
    ) -> List[Dict]:
        """
        获取用户的资金费历史记录

        Args:
            address: 交易者地址
            limit: 返回数量
            coin: 筛选特定币种
            start_time: 开始时间（毫秒时间戳）
            end_time: 结束时间（毫秒时间戳）
            sort_order: 排序方向 (asc, desc)

        Returns:
            资金费记录列表
        """
        order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = ["address = %s"]
            params = [address]

            if coin:
                conditions.append("coin = %s")
                params.append(coin)

            if start_time:
                conditions.append("time >= %s")
                params.append(start_time)

            if end_time:
                conditions.append("time <= %s")
                params.append(end_time)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM trader_funding_history
                WHERE {where_clause}
                ORDER BY time {order_direction}
                LIMIT %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_latest_funding_record(self, address: str) -> Optional[Dict]:
        """
        获取用户最新的一条资金费记录

        Args:
            address: 交易者地址

        Returns:
            最新的资金费记录字典，如果没有记录则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_funding_history
                WHERE address = %s
                ORDER BY time DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_funding_stats(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取用户资金费的聚合统计

        Args:
            address: 交易者地址

        Returns:
            聚合统计字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COALESCE(SUM(usdc), 0) as total_funding_usdc,
                    COALESCE(SUM(CASE WHEN usdc > 0 THEN usdc ELSE 0 END), 0) as total_received,
                    COALESCE(SUM(CASE WHEN usdc < 0 THEN usdc ELSE 0 END), 0) as total_paid,
                    MIN(time) as first_funding_time,
                    MAX(time) as last_funding_time,
                    COUNT(DISTINCT coin) as unique_coins
                FROM trader_funding_history
                WHERE address = %s
            """, (address,))

            row = cursor.fetchone()
            if not row or row['total_records'] == 0:
                return None

            return {
                'total_records': row['total_records'],
                'total_funding_usdc': float(row['total_funding_usdc']),
                'total_received': float(row['total_received']),
                'total_paid': float(row['total_paid']),
                'first_funding_time': row['first_funding_time'],
                'last_funding_time': row['last_funding_time'],
                'unique_coins': row['unique_coins'],
            }

    def get_funding_by_coin(self, address: str) -> Dict[str, float]:
        """
        按币种统计资金费

        Args:
            address: 交易者地址

        Returns:
            {币种: 资金费总额} 字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT 
                    coin,
                    COALESCE(SUM(usdc), 0) as total_usdc,
                    COUNT(*) as record_count
                FROM trader_funding_history
                WHERE address = %s
                GROUP BY coin
                ORDER BY total_usdc DESC
            """, (address,))

            result = {}
            for row in cursor.fetchall():
                if row['coin']:
                    result[row['coin']] = float(row['total_usdc'])

            return result

    def get_funding_count(self, address: str) -> int:
        """获取用户资金费记录总数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM trader_funding_history WHERE address = %s",
                (address,)
            )
            return cursor.fetchone()[0]

    def delete_funding_records(self, address: str) -> int:
        """
        删除用户的所有资金费记录

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM trader_funding_history WHERE address = %s",
                (address,)
            )
            return cursor.rowcount
