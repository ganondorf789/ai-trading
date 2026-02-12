"""
交易者仪表盘数据聚合模块 (PostgreSQL)
跨表查询: trader_metrics, trader_fills, position_history, position_calc_state
"""
import json
from typing import Dict, List, Optional, Any
import pendulum
from psycopg2 import extras

from screener import SHANGHAI_TZ


class TraderDashboardOps:
    """交易者仪表盘相关操作"""

    def get_trader_dashboard(self, address: str, start_date: str = None, end_date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取交易者仪表盘汇总数据

        Args:
            address: 交易者地址
            start_date: 开始日期 (YYYY-MM-DD)，可选
            end_date: 结束日期 (YYYY-MM-DD)，可选

        Returns:
            仪表盘数据字典，如果交易者不存在则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 1. trader_metrics - 账户概览和盈亏数据
            cursor.execute("""
                SELECT current_equity, max_drawdown, roi, unrealized_pnl
                FROM trader_metrics
                WHERE address = %s
            """, (address,))
            metrics_row = cursor.fetchone()

            if not metrics_row:
                return None

            current_equity = float(metrics_row['current_equity'] or 0)
            max_drawdown = float(metrics_row['max_drawdown'] or 0)
            roi = float(metrics_row['roi'] or 0)
            unrealized_pnl = float(metrics_row['unrealized_pnl'] or 0)

            # 2. trader_fills - 成交笔数（日期范围筛选）
            fills_conditions = ["address = %s"]
            fills_params = [address]

            if start_date:
                start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                fills_conditions.append("time >= %s")
                fills_params.append(int(start_dt.timestamp() * 1000))

            if end_date:
                end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                fills_conditions.append("time <= %s")
                fills_params.append(int(end_dt.timestamp() * 1000))

            fills_where = " AND ".join(fills_conditions)
            cursor.execute(f"SELECT COUNT(*) as cnt FROM trader_fills WHERE {fills_where}", fills_params)
            filled_orders = cursor.fetchone()['cnt']

            # 3. position_history - 已平仓仓位统计（日期范围筛选）
            pos_conditions = ["address = %s", "status = 'closed'"]
            pos_params = [address]

            if start_date:
                start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                pos_conditions.append("close_time >= %s")
                pos_params.append(start_dt.to_iso8601_string())

            if end_date:
                end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                pos_conditions.append("close_time <= %s")
                pos_params.append(end_dt.to_iso8601_string())

            pos_where = " AND ".join(pos_conditions)
            cursor.execute(f"""
                SELECT
                    COUNT(*) as closed_positions,
                    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as winning_positions
                FROM position_history
                WHERE {pos_where}
            """, pos_params)
            pos_row = cursor.fetchone()
            closed_positions = pos_row['closed_positions']
            winning_positions = pos_row['winning_positions']
            win_rate = round(winning_positions / closed_positions * 100, 2) if closed_positions > 0 else 0.0

            # 4. position_calc_state - 当前持仓数据
            cursor.execute("""
                SELECT open_positions_snapshot
                FROM position_calc_state
                WHERE address = %s
            """, (address,))
            calc_row = cursor.fetchone()

            total_position_value = 0.0
            long_value = 0.0
            short_value = 0.0

            if calc_row and calc_row['open_positions_snapshot']:
                snapshot = calc_row['open_positions_snapshot']
                if isinstance(snapshot, str):
                    snapshot = json.loads(snapshot)

                for pos in snapshot.values():
                    pos_value = abs(float(pos.get('current_size', 0)) * float(pos.get('avg_entry_price', 0)))
                    total_position_value += pos_value
                    if pos.get('direction') == 'long':
                        long_value += pos_value
                    else:
                        short_value += pos_value

            margin_usage_rate = round(total_position_value / current_equity * 100, 2) if current_equity > 0 else 0.0
            total_dir = long_value + short_value
            long_ratio = round(long_value / total_dir * 100, 2) if total_dir > 0 else 0.0
            short_ratio = round(short_value / total_dir * 100, 2) if total_dir > 0 else 0.0

            if long_value > short_value:
                direction_preference = 'long'
            elif short_value > long_value:
                direction_preference = 'short'
            else:
                direction_preference = 'neutral'

            # 计算 available_margin（近似值）
            available_margin = max(0.0, current_equity - total_position_value)

            return {
                'account_overview': {
                    'account_value': round(current_equity, 2),
                    'available_margin': round(available_margin, 2),
                },
                'trading_performance': {
                    'win_rate': win_rate,
                    'max_drawdown': round(max_drawdown, 2),
                    'filled_orders': filled_orders,
                    'closed_positions': closed_positions,
                },
                'current_positions': {
                    'total_position_value': round(total_position_value, 2),
                    'margin_usage_rate': margin_usage_rate,
                    'direction_preference': direction_preference,
                    'long_ratio': long_ratio,
                    'short_ratio': short_ratio,
                    'long_value': round(long_value, 2),
                    'short_value': round(short_value, 2),
                },
                'profit_loss': {
                    'roi': round(roi, 2),
                    'unrealized_pnl': round(unrealized_pnl, 2),
                },
            }

    def get_trader_closed_performance(self, address: str, start_date: str = None, end_date: str = None) -> Optional[Dict[str, Any]]:
        """
        获取交易者平仓表现统计（基于 position_history 已平仓仓位）

        Args:
            address: 交易者地址
            start_date: 开始日期 (YYYY-MM-DD)，可选
            end_date: 结束日期 (YYYY-MM-DD)，可选

        Returns:
            平仓表现数据字典，如果无数据则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建日期范围条件
            conditions = ["address = %s", "status = 'closed'"]
            params: List[Any] = [address]

            if start_date:
                start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                conditions.append("close_time >= %s")
                params.append(start_dt.to_iso8601_string())

            if end_date:
                end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                conditions.append("close_time <= %s")
                params.append(end_dt.to_iso8601_string())

            where_clause = " AND ".join(conditions)

            # 单条查询聚合所有需要的统计
            cursor.execute(f"""
                SELECT
                    COUNT(*) as closed_count,
                    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as winning_count,
                    COUNT(CASE WHEN realized_pnl < 0 THEN 1 END) as losing_count,
                    COALESCE(SUM(realized_pnl), 0) as total_realized_pnl,
                    COALESCE(SUM(total_fee), 0) as total_fee,
                    COALESCE(SUM(realized_pnl) FILTER (WHERE direction = 'long'), 0) as long_pnl,
                    COALESCE(SUM(realized_pnl) FILTER (WHERE direction = 'short'), 0) as short_pnl,
                    COALESCE(SUM(holding_hours), 0) as total_holding_hours,
                    MIN(holding_hours) as min_holding_hours,
                    MAX(holding_hours) as max_holding_hours,
                    AVG(holding_hours) as avg_holding_hours
                FROM position_history
                WHERE {where_clause}
            """, params)

            row = cursor.fetchone()

            if not row or row['closed_count'] == 0:
                return None

            closed_count = row['closed_count']
            winning_count = row['winning_count']
            losing_count = row['losing_count']
            total_realized_pnl = float(row['total_realized_pnl'])
            total_fee = float(row['total_fee'])
            long_pnl = float(row['long_pnl'])
            short_pnl = float(row['short_pnl'])

            win_rate = round(winning_count / closed_count * 100, 2)
            net_pnl = total_realized_pnl - total_fee

            # 持仓时间
            total_holding_hours = float(row['total_holding_hours'] or 0)
            min_holding_hours = float(row['min_holding_hours'] or 0)
            max_holding_hours = float(row['max_holding_hours'] or 0)
            avg_holding_hours = float(row['avg_holding_hours'] or 0)

            return {
                'overview': {
                    'win_rate': win_rate,
                    'realized_pnl': round(total_realized_pnl, 2),
                    'total_fee': round(total_fee, 2),
                },
                'closed_stats': {
                    'closed_count': closed_count,
                    'winning_count': winning_count,
                    'losing_count': losing_count,
                },
                'pnl_summary': {
                    'net_pnl': round(net_pnl, 2),
                    'long_pnl': round(long_pnl, 2),
                    'short_pnl': round(short_pnl, 2),
                },
                'holding_time': {
                    'total_hours': round(total_holding_hours, 4),
                    'min_hours': round(min_holding_hours, 4),
                    'max_hours': round(max_holding_hours, 4),
                    'avg_hours': round(avg_holding_hours, 4),
                },
            }

    def get_trader_pnl_curve(self, address: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
        """
        获取交易者总盈亏曲线（合并交易盈亏 + 资金费 + 存取款）

        数据源：
        - trader_fills: closed_pnl（交易盈亏）
        - trader_funding_history: usdc（资金费收支）
        - trader_ledger_updates: usdc（存取款/转账）

        不传日期范围时默认返回最近24小时。

        Args:
            address: 交易者地址
            start_date: 开始日期 (YYYY-MM-DD)，可选
            end_date: 结束日期 (YYYY-MM-DD)，可选

        Returns:
            包含曲线数据点和基准值的字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建时间范围
            time_lower = None
            time_upper = None

            if start_date or end_date:
                if start_date:
                    start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                    time_lower = int(start_dt.timestamp() * 1000)
                if end_date:
                    end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                    time_upper = int(end_dt.timestamp() * 1000)
            else:
                since = pendulum.now(SHANGHAI_TZ).subtract(hours=24)
                time_lower = int(since.timestamp() * 1000)

            # --- 基准值：时间范围之前的各项累计 ---
            base_pnl = 0.0
            base_funding = 0.0
            base_deposit = 0.0

            if time_lower:
                cursor.execute(
                    "SELECT COALESCE(SUM(closed_pnl), 0) as v FROM trader_fills WHERE address = %s AND time < %s",
                    (address, time_lower)
                )
                base_pnl = float(cursor.fetchone()['v'])

                cursor.execute(
                    "SELECT COALESCE(SUM(usdc), 0) as v FROM trader_funding_history WHERE address = %s AND time < %s",
                    (address, time_lower)
                )
                base_funding = float(cursor.fetchone()['v'])

                cursor.execute(
                    "SELECT COALESCE(SUM(usdc), 0) as v FROM trader_ledger_updates WHERE address = %s AND time < %s",
                    (address, time_lower)
                )
                base_deposit = float(cursor.fetchone()['v'])

            # --- UNION ALL 查询范围内的事件 ---
            time_conds = ""
            union_params: List[Any] = []

            if time_lower and time_upper:
                time_conds = "AND time >= %s AND time <= %s"
                union_params = [time_lower, time_upper]
            elif time_lower:
                time_conds = "AND time >= %s"
                union_params = [time_lower]
            elif time_upper:
                time_conds = "AND time <= %s"
                union_params = [time_upper]

            query = f"""
                SELECT time, amount, fee, type, coin FROM (
                    SELECT time, closed_pnl as amount, fee, 'trade' as type, coin
                    FROM trader_fills
                    WHERE address = %s {time_conds}

                    UNION ALL

                    SELECT time, usdc as amount, 0 as fee, 'funding' as type, coin
                    FROM trader_funding_history
                    WHERE address = %s {time_conds}

                    UNION ALL

                    SELECT time, usdc as amount, fee, delta_type as type, '' as coin
                    FROM trader_ledger_updates
                    WHERE address = %s {time_conds}
                ) combined
                ORDER BY time ASC
            """
            # 每个子查询都需要 address + 时间参数
            all_params: List[Any] = []
            for _ in range(3):
                all_params.append(address)
                all_params.extend(union_params)

            cursor.execute(query, all_params)
            rows = cursor.fetchall()

            # --- 构建曲线 ---
            cum_pnl = base_pnl
            cum_funding = base_funding
            cum_deposit = base_deposit
            cum_total = cum_pnl + cum_funding + cum_deposit

            points = []
            for row in rows:
                amount = float(row['amount'] or 0)
                event_type = row['type']

                if event_type == 'trade':
                    cum_pnl += amount
                elif event_type == 'funding':
                    cum_funding += amount
                else:
                    # deposit / withdraw / internalTransfer 等
                    cum_deposit += amount

                cum_total = cum_pnl + cum_funding + cum_deposit

                points.append({
                    'time': row['time'],
                    'amount': round(amount, 2),
                    'fee': round(float(row['fee'] or 0), 4),
                    'type': event_type,
                    'coin': row['coin'] or '',
                    'cumulative_pnl': round(cum_pnl, 2),
                    'cumulative_funding': round(cum_funding, 2),
                    'cumulative_deposit': round(cum_deposit, 2),
                    'cumulative_total': round(cum_total, 2),
                })

            return {
                'base': {
                    'pnl': round(base_pnl, 2),
                    'funding': round(base_funding, 2),
                    'deposit': round(base_deposit, 2),
                    'total': round(base_pnl + base_funding + base_deposit, 2),
                },
                'points': points,
            }

    def get_trader_best_trades(self, address: str, start_date: str = None, end_date: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取交易者盈利最高的 Top N 交易（基于 position_history 已平仓仓位）

        Args:
            address: 交易者地址
            start_date: 开始日期 (YYYY-MM-DD)，可选
            end_date: 结束日期 (YYYY-MM-DD)，可选
            limit: 返回数量，默认 10

        Returns:
            按 realized_pnl 降序排列的仓位列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = ["address = %s", "status = 'closed'"]
            params: List[Any] = [address]

            if start_date:
                start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                conditions.append("close_time >= %s")
                params.append(start_dt.to_iso8601_string())

            if end_date:
                end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                conditions.append("close_time <= %s")
                params.append(end_dt.to_iso8601_string())

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT
                    coin, direction, open_time, close_time,
                    max_size, avg_entry_price, avg_close_price,
                    realized_pnl, total_fee, holding_hours,
                    open_trades, close_trades, total_volume
                FROM position_history
                WHERE {where_clause}
                ORDER BY realized_pnl DESC
                LIMIT %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]
