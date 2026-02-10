"""
历史委托管理模块 (PostgreSQL)

存储和查询用户的历史委托记录
"""
from typing import List, Dict, Any, Optional
from psycopg2 import extras
from loguru import logger

from utils import sanitize_float


class TraderOrdersOps:
    """历史委托相关操作"""

    def save_historical_orders(self, address: str, orders: List[Dict]) -> int:
        """
        保存用户的历史委托记录

        Args:
            address: 交易者地址
            orders: 历史委托列表（API 原始格式）

        Returns:
            保存的记录数
        """
        if not orders:
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for record in orders:
                try:
                    order = record.get('order', {})
                    status = record.get('status', '')
                    status_timestamp = record.get('statusTimestamp', 0)

                    oid = order.get('oid')
                    if oid is None:
                        continue

                    cursor.execute("""
                        INSERT INTO trader_historical_orders (
                            address, coin, side, limit_px, sz, orig_sz,
                            oid, order_type, is_trigger, trigger_condition,
                            trigger_px, is_position_tpsl, reduce_only,
                            order_timestamp, status, status_timestamp, cloid
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(address, oid) DO UPDATE SET
                            status = EXCLUDED.status,
                            status_timestamp = EXCLUDED.status_timestamp,
                            sz = EXCLUDED.sz
                    """, (
                        address,
                        order.get('coin', ''),
                        order.get('side', ''),
                        order.get('limitPx', ''),
                        order.get('sz', ''),
                        order.get('origSz', order.get('sz', '')),
                        oid,
                        order.get('orderType', 'Limit'),
                        order.get('isTrigger', False),
                        order.get('triggerCondition', ''),
                        order.get('triggerPx', ''),
                        order.get('isPositionTpsl', False),
                        order.get('reduceOnly', False),
                        order.get('timestamp', 0),
                        status,
                        status_timestamp,
                        order.get('cloid', ''),
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存历史委托记录失败: {e}")

        return saved_count

    def get_historical_orders(
        self,
        address: str,
        limit: int = 100,
        coin: str = None,
        status: str = None,
        side: str = None,
        sort_order: str = 'desc'
    ) -> List[Dict]:
        """
        获取用户的历史委托记录

        Args:
            address: 交易者地址
            limit: 返回数量
            coin: 筛选特定币种
            status: 筛选状态 (open, canceled, filled, triggered, rejected, marginCanceled)
            side: 筛选方向 (B=买入, A=卖出)
            sort_order: 排序方向 (asc, desc)

        Returns:
            历史委托记录列表
        """
        order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = ["address = %s"]
            params = [address]

            if coin:
                conditions.append("coin = %s")
                params.append(coin)

            if status:
                conditions.append("status = %s")
                params.append(status)

            if side:
                conditions.append("side = %s")
                params.append(side)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM trader_historical_orders
                WHERE {where_clause}
                ORDER BY status_timestamp {order_direction}
                LIMIT %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_latest_order(self, address: str) -> Optional[Dict]:
        """
        获取用户最新的一条委托记录

        Args:
            address: 交易者地址

        Returns:
            最新的委托记录字典，如果没有记录则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_historical_orders
                WHERE address = %s
                ORDER BY status_timestamp DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_orders_stats(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取用户历史委托的聚合统计

        Args:
            address: 交易者地址

        Returns:
            聚合统计字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled_count,
                    SUM(CASE WHEN status = 'canceled' THEN 1 ELSE 0 END) as canceled_count,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count,
                    SUM(CASE WHEN status = 'triggered' THEN 1 ELSE 0 END) as triggered_count,
                    SUM(CASE WHEN status = 'marginCanceled' THEN 1 ELSE 0 END) as margin_canceled_count,
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
                    SUM(CASE WHEN side = 'B' THEN 1 ELSE 0 END) as buy_count,
                    SUM(CASE WHEN side = 'A' THEN 1 ELSE 0 END) as sell_count,
                    COUNT(DISTINCT coin) as unique_coins,
                    MIN(order_timestamp) as first_order_time,
                    MAX(order_timestamp) as last_order_time
                FROM trader_historical_orders
                WHERE address = %s
            """, (address,))

            row = cursor.fetchone()
            if not row or row['total_orders'] == 0:
                return None

            return {
                'total_orders': row['total_orders'],
                'filled_count': row['filled_count'] or 0,
                'canceled_count': row['canceled_count'] or 0,
                'rejected_count': row['rejected_count'] or 0,
                'triggered_count': row['triggered_count'] or 0,
                'margin_canceled_count': row['margin_canceled_count'] or 0,
                'open_count': row['open_count'] or 0,
                'buy_count': row['buy_count'] or 0,
                'sell_count': row['sell_count'] or 0,
                'unique_coins': row['unique_coins'],
                'first_order_time': row['first_order_time'],
                'last_order_time': row['last_order_time'],
            }

    def get_orders_by_coin(self, address: str) -> Dict[str, int]:
        """
        按币种统计委托数量

        Args:
            address: 交易者地址

        Returns:
            {币种: 委托数} 字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT 
                    coin,
                    COUNT(*) as count
                FROM trader_historical_orders
                WHERE address = %s
                GROUP BY coin
                ORDER BY count DESC
            """, (address,))

            result = {}
            for row in cursor.fetchall():
                if row['coin']:
                    result[row['coin']] = row['count']

            return result

    def get_orders_count(self, address: str) -> int:
        """获取用户历史委托记录总数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM trader_historical_orders WHERE address = %s",
                (address,)
            )
            return cursor.fetchone()[0]

    def delete_historical_orders(self, address: str) -> int:
        """
        删除用户的所有历史委托记录

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM trader_historical_orders WHERE address = %s",
                (address,)
            )
            return cursor.rowcount
