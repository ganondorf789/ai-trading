"""
交易者仪表盘数据聚合模块 (PostgreSQL)
跨表查询: trader_metrics, trader_fills, position_history, position_calc_state
"""
import json
from typing import Dict, Optional, Any
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
