"""
跟单仓位状态管理模块 (PostgreSQL)
"""
from typing import List, Dict
from psycopg2 import extras


class CopyOrdersOps:
    """跟单仓位状态管理相关操作"""

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
        获取交易员持仓（带筛选条件）
        
        注意：此函数获取所有符合筛选条件的交易员持仓，而不仅仅是跟单交易员

        Args:
            enabled_only: 已弃用，保留是为了兼容性（默认显示所有交易员）
            group_id: 分组ID筛选（仅对跟单交易员有效）
            metric_filters: 指标筛选条件

        Returns:
            (持仓列表, 统计数据)
        """
        metric_filters = metric_filters or {}

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建交易员筛选条件
            conditions = ["1=1"]
            params = []

            # 如果指定了分组，只查找该分组的跟单交易员
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

            # 获取符合条件的交易员地址（从所有交易员中筛选）
            if group_id is not None:
                # 如果指定了分组，只从跟单地址中筛选
                cursor.execute(f"""
                    SELECT DISTINCT tm.address
                    FROM trader_metrics tm
                    INNER JOIN copy_trading_addresses cta ON tm.address = cta.address
                    WHERE {where_clause}
                """, params)
            else:
                # 否则从所有交易员中筛选
                cursor.execute(f"""
                    SELECT DISTINCT tm.address
                    FROM trader_metrics tm
                    LEFT JOIN copy_trading_addresses cta ON tm.address = cta.address
                    WHERE {where_clause}
                """, params)
            
            trader_addresses = {row['address'] for row in cursor.fetchall()}

            if not trader_addresses:
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
            address_list = list(trader_addresses)
            cursor.execute("""
                SELECT ap.*, 
                       cta.name as trader_name, 
                       cta.group_id, 
                       ctg.name as group_name, 
                       ctg.color as group_color,
                       tm.is_starred,
                       tm.overall_score,
                       tm.rating,
                       tm.total_pnl as trader_pnl
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

    def get_trader_positions_recent(self, minutes: int = 10) -> list:
        """
        获取最近N分钟内更新的所有交易员持仓
        
        纯数据获取，不做后端筛选和统计计算（由前端实现）

        Args:
            minutes: 获取最近N分钟内更新的数据，默认10分钟

        Returns:
            持仓列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT ap.*, 
                       cta.name as trader_name, 
                       cta.group_id, 
                       ctg.name as group_name, 
                       ctg.color as group_color,
                       tm.is_starred,
                       tm.overall_score,
                       tm.rating,
                       tm.total_pnl as trader_pnl
                FROM asset_positions ap
                LEFT JOIN copy_trading_addresses cta ON ap.address = cta.address
                LEFT JOIN copy_trading_groups ctg ON cta.group_id = ctg.id
                LEFT JOIN trader_metrics tm ON ap.address = tm.address
                WHERE ap.updated_at >= NOW() - INTERVAL '%s minutes'
                ORDER BY ABS(ap.position_value) DESC
            """, (minutes,))

            positions = [dict(row) for row in cursor.fetchall()]
            return positions
