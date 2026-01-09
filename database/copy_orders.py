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
        sort_order: str = "desc",
        metric_filters: Dict = None
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
            metric_filters: 交易员指标筛选条件

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

            # 处理指标筛选
            need_trader_metrics_join = False
            if metric_filters:
                if metric_filters.get('min_win_rate') is not None:
                    conditions.append("COALESCE(tm.win_rate, 0) >= %s")
                    params.append(metric_filters['min_win_rate'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_win_rate') is not None:
                    conditions.append("COALESCE(tm.win_rate, 100) <= %s")
                    params.append(metric_filters['max_win_rate'])
                    need_trader_metrics_join = True
                if metric_filters.get('min_profit_factor') is not None:
                    conditions.append("COALESCE(tm.profit_factor, 0) >= %s")
                    params.append(metric_filters['min_profit_factor'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_profit_factor') is not None:
                    conditions.append("COALESCE(tm.profit_factor, 999) <= %s")
                    params.append(metric_filters['max_profit_factor'])
                    need_trader_metrics_join = True
                if metric_filters.get('min_pnl') is not None:
                    conditions.append("COALESCE(tm.total_pnl, 0) >= %s")
                    params.append(metric_filters['min_pnl'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_pnl') is not None:
                    conditions.append("COALESCE(tm.total_pnl, 0) <= %s")
                    params.append(metric_filters['max_pnl'])
                    need_trader_metrics_join = True
                if metric_filters.get('min_drawdown') is not None:
                    conditions.append("COALESCE(tm.max_drawdown, 0) >= %s")
                    params.append(metric_filters['min_drawdown'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_drawdown') is not None:
                    conditions.append("COALESCE(tm.max_drawdown, 100) <= %s")
                    params.append(metric_filters['max_drawdown'])
                    need_trader_metrics_join = True
                if metric_filters.get('min_sharpe') is not None:
                    conditions.append("COALESCE(tm.sharpe_ratio, -999) >= %s")
                    params.append(metric_filters['min_sharpe'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_sharpe') is not None:
                    conditions.append("COALESCE(tm.sharpe_ratio, 999) <= %s")
                    params.append(metric_filters['max_sharpe'])
                    need_trader_metrics_join = True
                if metric_filters.get('min_trades') is not None:
                    conditions.append("COALESCE(tm.total_trades, 0) >= %s")
                    params.append(metric_filters['min_trades'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_trades') is not None:
                    conditions.append("COALESCE(tm.total_trades, 0) <= %s")
                    params.append(metric_filters['max_trades'])
                    need_trader_metrics_join = True
                if metric_filters.get('min_score') is not None:
                    conditions.append("COALESCE(tm.overall_score, 0) >= %s")
                    params.append(metric_filters['min_score'])
                    need_trader_metrics_join = True
                if metric_filters.get('max_score') is not None:
                    conditions.append("COALESCE(tm.overall_score, 100) <= %s")
                    params.append(metric_filters['max_score'])
                    need_trader_metrics_join = True

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 验证排序字段
            valid_sort_fields = {'created_at', 'executed_at', 'symbol', 'side', 'action', 'size', 'price', 'pnl', 'status'}
            if sort_by not in valid_sort_fields:
                sort_by = 'created_at'
            order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

            # 构建 JOIN 子句
            trader_metrics_join = "LEFT JOIN trader_metrics tm ON o.target_address = tm.address" if need_trader_metrics_join else ""

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM copy_trading_orders o
                LEFT JOIN copy_trading_addresses cta ON o.target_address = cta.address
                {trader_metrics_join}
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
                {trader_metrics_join}
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

    # ==================== 跟单仓位状态管理 ====================

    def get_copy_position_states(self, target_address: str = None) -> List[Dict]:
        """
        获取跟单仓位状态列表

        Args:
            target_address: 可选，筛选目标地址

        Returns:
            仓位状态列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if target_address:
                cursor.execute("""
                    SELECT cps.*, cta.name as target_name
                    FROM copy_position_states cps
                    LEFT JOIN copy_trading_addresses cta ON cps.target_address = cta.address
                    WHERE cps.target_address = %s
                    ORDER BY cps.updated_at DESC
                """, (target_address,))
            else:
                cursor.execute("""
                    SELECT cps.*, cta.name as target_name
                    FROM copy_position_states cps
                    LEFT JOIN copy_trading_addresses cta ON cps.target_address = cta.address
                    ORDER BY cps.updated_at DESC
                """)

            return [dict(row) for row in cursor.fetchall()]

    def get_copy_position_stats(self) -> Dict:
        """
        获取跟单仓位统计

        Returns:
            统计数据字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 总仓位数
            cursor.execute("SELECT COUNT(*) as count FROM copy_position_states")
            total_positions = cursor.fetchone()['count']

            # 按目标地址分组统计
            cursor.execute("""
                SELECT
                    cps.target_address,
                    cta.name as target_name,
                    COUNT(*) as position_count,
                    SUM(cps.notional) as total_notional
                FROM copy_position_states cps
                LEFT JOIN copy_trading_addresses cta ON cps.target_address = cta.address
                GROUP BY cps.target_address, cta.name
                ORDER BY position_count DESC
            """)
            by_target = [dict(row) for row in cursor.fetchall()]

            # 按币种统计
            cursor.execute("""
                SELECT
                    symbol,
                    side,
                    COUNT(*) as count,
                    SUM(ABS(size)) as total_size,
                    SUM(notional) as total_notional
                FROM copy_position_states
                GROUP BY symbol, side
                ORDER BY total_notional DESC
            """)
            by_symbol = [dict(row) for row in cursor.fetchall()]

            # 多空统计
            cursor.execute("""
                SELECT
                    side,
                    COUNT(*) as count,
                    SUM(notional) as total_notional
                FROM copy_position_states
                GROUP BY side
            """)
            by_side = {row['side']: {'count': row['count'], 'notional': row['total_notional']} for row in cursor.fetchall()}

            return {
                'total_positions': total_positions,
                'by_target': by_target,
                'by_symbol': by_symbol,
                'by_side': by_side
            }

    def clear_all_copy_position_states(self) -> int:
        """
        清空所有跟单仓位状态

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM copy_position_states")
            return cursor.rowcount

    def get_copy_trading_addresses_list(self, enabled_only: bool = True) -> List[Dict]:
        """
        获取跟单地址列表（简化版，用于刷新持仓）

        Args:
            enabled_only: 是否只返回已启用的地址

        Returns:
            地址列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if enabled_only:
                cursor.execute("SELECT address, name FROM copy_trading_addresses WHERE is_enabled = TRUE")
            else:
                cursor.execute("SELECT address, name FROM copy_trading_addresses")

            return [dict(row) for row in cursor.fetchall()]

    def get_trader_positions_with_filters(
        self,
        enabled_only: bool = True,
        group_id: int = None,
        metric_filters: Dict = None
    ) -> tuple:
        """
        获取跟单交易员持仓（带筛选条件）

        Args:
            enabled_only: 是否只显示已启用的地址
            group_id: 分组ID筛选
            metric_filters: 指标筛选条件

        Returns:
            (持仓列表, 统计数据)
        """
        metric_filters = metric_filters or {}

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建跟单地址查询条件
            conditions = ["1=1"]
            params = []

            if enabled_only:
                conditions.append("cta.is_enabled = TRUE")

            if group_id is not None:
                conditions.append("cta.group_id = %s")
                params.append(group_id)

            # 指标筛选条件
            filter_mappings = {
                'min_win_rate': ("COALESCE(tm.win_rate, 0) >= %s", lambda v: v),
                'max_win_rate': ("COALESCE(tm.win_rate, 100) <= %s", lambda v: v),
                'min_profit_factor': ("COALESCE(tm.profit_factor, 0) >= %s", lambda v: v),
                'max_profit_factor': ("COALESCE(tm.profit_factor, 999) <= %s", lambda v: v),
                'min_pnl': ("COALESCE(tm.total_pnl, 0) >= %s", lambda v: v),
                'max_pnl': ("COALESCE(tm.total_pnl, 0) <= %s", lambda v: v),
                'min_drawdown': ("COALESCE(tm.max_drawdown, 0) >= %s", lambda v: v),
                'max_drawdown': ("COALESCE(tm.max_drawdown, 100) <= %s", lambda v: v),
                'min_sharpe': ("COALESCE(tm.sharpe_ratio, -999) >= %s", lambda v: v),
                'max_sharpe': ("COALESCE(tm.sharpe_ratio, 999) <= %s", lambda v: v),
                'min_sortino': ("COALESCE(tm.sortino_ratio, -999) >= %s", lambda v: v),
                'max_sortino': ("COALESCE(tm.sortino_ratio, 999) <= %s", lambda v: v),
                'min_trades': ("COALESCE(tm.total_trades, 0) >= %s", lambda v: v),
                'max_trades': ("COALESCE(tm.total_trades, 0) <= %s", lambda v: v),
                'min_score': ("COALESCE(tm.overall_score, 0) >= %s", lambda v: v),
                'max_score': ("COALESCE(tm.overall_score, 100) <= %s", lambda v: v),
            }

            for key, (condition, transform) in filter_mappings.items():
                if metric_filters.get(key) is not None:
                    conditions.append(condition)
                    params.append(transform(metric_filters[key]))

            where_clause = " AND ".join(conditions)

            # 获取符合条件的跟单地址
            cursor.execute(f"""
                SELECT cta.address, cta.name, cta.group_id, cta.is_enabled
                FROM copy_trading_addresses cta
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE {where_clause}
            """, params)
            copy_addresses = {row['address']: dict(row) for row in cursor.fetchall()}

            if not copy_addresses:
                return [], {
                    'total_positions': 0,
                    'total_traders': 0,
                    'total_notional': 0,
                    'long_count': 0,
                    'short_count': 0,
                    'long_notional': 0,
                    'short_notional': 0,
                    'by_coin': [],
                    'by_trader': []
                }

            # 获取这些地址的持仓
            address_list = list(copy_addresses.keys())
            cursor.execute("""
                SELECT ap.*, cta.name as trader_name, cta.group_id, ctg.name as group_name, ctg.color as group_color,
                       tm.is_starred
                FROM asset_positions ap
                LEFT JOIN copy_trading_addresses cta ON ap.address = cta.address
                LEFT JOIN copy_trading_groups ctg ON cta.group_id = ctg.id
                LEFT JOIN trader_metrics tm ON ap.address = tm.address
                WHERE ap.address = ANY(%s)
                ORDER BY ABS(ap.position_value) DESC
            """, (address_list,))

            positions = []
            stats = {
                'total_positions': 0,
                'total_traders': set(),
                'total_notional': 0,
                'long_count': 0,
                'short_count': 0,
                'long_notional': 0,
                'short_notional': 0,
                'by_coin': {},
                'by_trader': {}
            }

            for row in cursor.fetchall():
                pos = dict(row)
                positions.append(pos)

                stats['total_positions'] += 1
                stats['total_traders'].add(pos['address'])

                position_value = abs(float(pos.get('position_value', 0)))
                stats['total_notional'] += position_value

                szi = float(pos.get('szi', 0))
                if szi > 0:
                    stats['long_count'] += 1
                    stats['long_notional'] += position_value
                else:
                    stats['short_count'] += 1
                    stats['short_notional'] += position_value

                coin = pos.get('coin', 'Unknown')
                if coin not in stats['by_coin']:
                    stats['by_coin'][coin] = {'count': 0, 'notional': 0, 'long': 0, 'short': 0}
                stats['by_coin'][coin]['count'] += 1
                stats['by_coin'][coin]['notional'] += position_value
                if szi > 0:
                    stats['by_coin'][coin]['long'] += 1
                else:
                    stats['by_coin'][coin]['short'] += 1

                address = pos.get('address')
                if address not in stats['by_trader']:
                    stats['by_trader'][address] = {
                        'name': pos.get('trader_name'),
                        'count': 0,
                        'notional': 0
                    }
                stats['by_trader'][address]['count'] += 1
                stats['by_trader'][address]['notional'] += position_value

            # 转换统计数据
            stats['total_traders'] = len(stats['total_traders'])
            stats['by_coin'] = [
                {'coin': k, **v}
                for k, v in sorted(stats['by_coin'].items(), key=lambda x: -x[1]['notional'])
            ]
            stats['by_trader'] = [
                {'address': k, **v}
                for k, v in sorted(stats['by_trader'].items(), key=lambda x: -x[1]['notional'])
            ]

            return positions, stats
