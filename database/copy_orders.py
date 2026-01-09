"""
跟单订单管理模块 (PostgreSQL)
"""
from typing import List, Dict
import pendulum
from psycopg2 import extras

from screener.trader_screener import SHANGHAI_TZ


class CopyOrdersOps:
    """跟单订单管理相关操作"""

    def save_copy_order(self, order: Dict) -> int:
        """
        保存跟单订单记录

        Args:
            order: 订单数据

        Returns:
            订单ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO copy_trading_orders (
                    target_address, symbol, side, action, size, price,
                    leverage, copy_ratio, target_size, target_entry_price,
                    status, error_message, pnl, is_dry_run, created_at, executed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                order.get('target_address'),
                order.get('symbol'),
                order.get('side'),
                order.get('action'),
                order.get('size', 0),
                order.get('price'),
                order.get('leverage', 1),
                order.get('copy_ratio'),
                order.get('target_size'),
                order.get('target_entry_price'),
                order.get('status', 'pending'),
                order.get('error_message'),
                order.get('pnl', 0),
                order.get('is_dry_run', True),
                order.get('created_at', pendulum.now(SHANGHAI_TZ).to_iso8601_string()),
                order.get('executed_at')
            ))
            return cursor.fetchone()[0]

    def update_copy_order(self, order_id: int, updates: Dict) -> bool:
        """
        更新跟单订单状态

        Args:
            order_id: 订单ID
            updates: 更新数据

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            set_clauses = []
            params = []

            for key, value in updates.items():
                if key in ('status', 'error_message', 'pnl', 'executed_at', 'price'):
                    set_clauses.append(f"{key} = %s")
                    params.append(value)

            if not set_clauses:
                return False

            params.append(order_id)
            cursor.execute(f"""
                UPDATE copy_trading_orders
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """, params)

            return cursor.rowcount > 0

    def get_copy_orders(
        self,
        target_address: str = None,
        symbol: str = None,
        status: str = None,
        action: str = None,
        is_dry_run: bool = None,
        days: int = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[Dict], int]:
        """
        获取跟单订单列表

        Args:
            target_address: 目标地址筛选
            symbol: 币种筛选
            status: 状态筛选
            action: 操作类型筛选
            is_dry_run: 是否模拟模式筛选
            days: 最近N天
            start_date: 开始日期
            end_date: 结束日期
            limit: 每页数量
            offset: 偏移量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            (订单列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = []
            params = []

            if target_address:
                conditions.append("o.target_address = %s")
                params.append(target_address)

            if symbol:
                conditions.append("o.symbol = %s")
                params.append(symbol)

            if status:
                conditions.append("o.status = %s")
                params.append(status)

            if action:
                conditions.append("o.action = %s")
                params.append(action)

            if is_dry_run is not None:
                conditions.append("o.is_dry_run = %s")
                params.append(is_dry_run)

            if days is not None and days > 0:
                conditions.append("o.created_at >= NOW() - INTERVAL '%s days'")
                params.append(days)

            if start_date:
                conditions.append("o.created_at >= %s")
                params.append(start_date)

            if end_date:
                conditions.append("o.created_at <= %s")
                params.append(end_date)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 验证排序字段
            valid_sort_fields = {'created_at', 'executed_at', 'symbol', 'side', 'action', 'size', 'price', 'pnl', 'status'}
            if sort_by not in valid_sort_fields:
                sort_by = 'created_at'
            order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM copy_trading_orders o
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()['count']

            # 查询数据
            cursor.execute(f"""
                SELECT
                    o.*,
                    cta.name as target_name
                FROM copy_trading_orders o
                LEFT JOIN copy_trading_addresses cta ON o.target_address = cta.address
                WHERE {where_clause}
                ORDER BY o.{sort_by} {order_direction}
                LIMIT %s OFFSET %s
            """, params + [limit, offset])

            return [dict(row) for row in cursor.fetchall()], total_count

    def get_copy_order_stats(
        self,
        target_address: str = None,
        days: int = 7
    ) -> Dict:
        """
        获取跟单订单统计

        Args:
            target_address: 目标地址筛选
            days: 统计天数

        Returns:
            统计数据
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = [f"created_at >= NOW() - INTERVAL '{days} days'"]
            params = []

            if target_address:
                conditions.append("target_address = %s")
                params.append(target_address)

            where_clause = " AND ".join(conditions)

            # 总体统计
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN action = 'open' THEN 1 ELSE 0 END) as opens,
                    SUM(CASE WHEN action = 'close' THEN 1 ELSE 0 END) as closes,
                    SUM(pnl) as total_pnl,
                    SUM(CASE WHEN is_dry_run = FALSE THEN 1 ELSE 0 END) as real_orders
                FROM copy_trading_orders
                WHERE {where_clause}
            """, params)

            row = cursor.fetchone()
            stats = dict(row) if row else {}

            # 按币种统计
            cursor.execute(f"""
                SELECT
                    symbol,
                    COUNT(*) as count,
                    SUM(pnl) as pnl
                FROM copy_trading_orders
                WHERE {where_clause}
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT 10
            """, params)

            stats['by_symbol'] = [dict(r) for r in cursor.fetchall()]

            # 按目标地址统计
            cursor.execute(f"""
                SELECT
                    o.target_address,
                    cta.name as target_name,
                    COUNT(*) as count,
                    SUM(o.pnl) as pnl
                FROM copy_trading_orders o
                LEFT JOIN copy_trading_addresses cta ON o.target_address = cta.address
                WHERE {where_clause.replace('target_address', 'o.target_address').replace('created_at', 'o.created_at')}
                GROUP BY o.target_address, cta.name
                ORDER BY count DESC
            """, params)

            stats['by_target'] = [dict(r) for r in cursor.fetchall()]

            return stats

    def delete_old_copy_orders(self, days: int = 30) -> int:
        """
        删除旧的跟单订单记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM copy_trading_orders
                WHERE created_at < NOW() - INTERVAL '%s days'
            """, (days,))
            return cursor.rowcount
