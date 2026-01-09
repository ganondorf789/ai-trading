"""
交易记录管理模块 (PostgreSQL)
"""
from typing import List, Dict, Any
import pendulum
import re
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ
from utils import sanitize_float


class TraderFillsOps:
    """交易记录相关操作"""

    def save_fills(self, address: str, fills: List[Dict]) -> int:
        """
        保存交易者的交易记录

        Args:
            address: 交易者地址
            fills: 交易记录列表

        Returns:
            保存的记录数
        """
        if not fills:
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for fill in fills:
                try:
                    time_ms = fill.get('time', 0)
                    trade_time = pendulum.from_timestamp(time_ms / 1000, tz=SHANGHAI_TZ).to_iso8601_string() if time_ms else None

                    # 计算交易类型
                    dir_val = fill.get('dir', '')
                    start_pos = float(fill.get('startPosition', 0)) if fill.get('startPosition') else 0
                    trade_type = self.calculate_trade_type(dir_val, start_pos)

                    cursor.execute("""
                        INSERT INTO trader_fills (
                            address, coin, side, px, sz, time, trade_time,
                            closed_pnl, hash, start_position, dir, crossed, fee, oid, tid, trade_type
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(address, time, oid) DO UPDATE SET
                            closed_pnl = EXCLUDED.closed_pnl,
                            px = EXCLUDED.px,
                            sz = EXCLUDED.sz,
                            trade_type = EXCLUDED.trade_type
                    """, (
                        address,
                        fill.get('coin'),
                        fill.get('side'),
                        sanitize_float(fill.get('px', 0)),
                        sanitize_float(fill.get('sz', 0)),
                        time_ms,
                        trade_time,
                        sanitize_float(fill.get('closedPnl', 0)),
                        fill.get('hash'),
                        sanitize_float(start_pos) if start_pos else None,
                        dir_val,
                        fill.get('crossed'),
                        sanitize_float(fill.get('fee', 0)),
                        fill.get('oid'),
                        fill.get('tid'),
                        trade_type
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存交易记录失败: {e}")

        return saved_count

    def save_trader_with_fills(
        self,
        metrics,
        fills: List[Dict]
    ) -> tuple[int, int]:
        """
        保存交易者指标和交易记录

        Args:
            metrics: 交易者指标
            fills: 交易记录列表

        Returns:
            (trader_id, fills_count) 元组
        """
        trader_id = self.save_trader(metrics)
        fills_count = self.save_fills(metrics.address, fills)
        return trader_id, fills_count

    def get_trader_fills(
        self,
        address: str,
        limit: int = 100,
        coin: str = None,
        trade_type: str = None,
        pnl_filter: str = None,
        sort_by: str = 'time',
        sort_order: str = 'desc',
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        获取交易者的交易记录

        Args:
            address: 交易者地址
            limit: 返回数量
            coin: 筛选特定币种
            trade_type: 交易类型筛选
            pnl_filter: 盈亏筛选 (profit/loss)
            sort_by: 排序字段
            sort_order: 排序方向 (asc, desc)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            交易记录列表
        """
        # 验证排序字段（防止 SQL 注入）
        valid_sort_columns = {
            'time': 'time',
            'trade_time': 'time',
            'coin': 'coin',
            'side': 'side',
            'px': 'px',
            'sz': 'sz',
            'closed_pnl': 'closed_pnl',
            'fee': 'fee',
            'value': 'px * sz',
            'roi': 'CASE WHEN px * sz > 0 THEN closed_pnl / (px * sz) ELSE 0 END'
        }
        sort_column = valid_sort_columns.get(sort_by, 'time')
        order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建查询条件
            conditions = ["address = %s"]
            params = [address]

            if coin:
                conditions.append("coin = %s")
                params.append(coin)

            # 交易类型筛选
            if trade_type:
                valid_trade_types = {'open_long', 'add_long', 'close_long', 'open_short', 'add_short', 'close_short'}
                if trade_type in valid_trade_types:
                    conditions.append("trade_type = %s")
                    params.append(trade_type)

            # 盈亏筛选
            if pnl_filter == 'profit':
                conditions.append("closed_pnl > 0")
            elif pnl_filter == 'loss':
                conditions.append("closed_pnl < 0")

            # 日期范围筛选
            if start_date:
                start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                start_timestamp_ms = int(start_dt.timestamp() * 1000)
                conditions.append("time >= %s")
                params.append(start_timestamp_ms)

            if end_date:
                end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                end_timestamp_ms = int(end_dt.timestamp() * 1000)
                conditions.append("time <= %s")
                params.append(end_timestamp_ms)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM trader_fills
                WHERE {where_clause}
                ORDER BY {sort_column} {order_direction}
                LIMIT %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_trader_coins(self, address: str) -> List[str]:
        """
        获取交易者交易过的所有币种

        Args:
            address: 交易者地址

        Returns:
            币种列表（按交易次数降序排列）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT coin, COUNT(*) as count
                FROM trader_fills
                WHERE address = %s
                GROUP BY coin
                ORDER BY count DESC
            """, (address,))
            return [row['coin'] for row in cursor.fetchall()]

    def get_fills_summary(
        self,
        address: str,
        exclude_user_perps: bool = True
    ) -> Dict[str, Any]:
        """
        获取交易者交易记录汇总

        Args:
            address: 交易者地址
            exclude_user_perps: 是否排除用户创建的永续合约

        Returns:
            汇总信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 总交易数
            cursor.execute(
                "SELECT COUNT(*) as count FROM trader_fills WHERE address = %s",
                (address,)
            )
            total_fills = cursor.fetchone()['count']

            # 按币种统计
            cursor.execute("""
                SELECT coin, COUNT(*) as count, SUM(closed_pnl) as total_pnl
                FROM trader_fills
                WHERE address = %s
                GROUP BY coin
                ORDER BY count DESC
            """, (address,))

            # 过滤 @数字 格式的用户永续合约
            user_perp_pattern = re.compile(r'^@\d+$')
            by_coin = []
            for row in cursor.fetchall():
                coin = row['coin']
                if exclude_user_perps and coin and user_perp_pattern.match(coin):
                    continue
                by_coin.append(dict(row))

            # 总盈亏
            if exclude_user_perps:
                total_pnl = sum(c['total_pnl'] or 0 for c in by_coin)
            else:
                cursor.execute(
                    "SELECT SUM(closed_pnl) as total FROM trader_fills WHERE address = %s",
                    (address,)
                )
                total_pnl = cursor.fetchone()['total'] or 0

            return {
                'total_fills': total_fills,
                'total_pnl': total_pnl,
                'by_coin': by_coin
            }

    def delete_trader_fills(self, address: str) -> int:
        """
        删除交易者的所有交易记录

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM trader_fills WHERE address = %s",
                (address,)
            )
            return cursor.rowcount

    def get_all_coins(
        self,
        exclude_user_perps: bool = True,
        address: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有币种及其统计信息

        Args:
            exclude_user_perps: 是否排除用户创建的永续合约
            address: 可选，筛选特定交易者的币种

        Returns:
            币种列表，包含交易次数和总盈亏
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if address:
                cursor.execute("""
                    SELECT coin, COUNT(*) as count, SUM(closed_pnl) as total_pnl
                    FROM trader_fills
                    WHERE address = %s
                    GROUP BY coin
                    ORDER BY count DESC
                """, (address,))
            else:
                cursor.execute("""
                    SELECT coin, COUNT(*) as count, SUM(closed_pnl) as total_pnl
                    FROM trader_fills
                    GROUP BY coin
                    ORDER BY count DESC
                """)

            results = []
            user_perp_pattern = re.compile(r'^@\d+$')

            for row in cursor.fetchall():
                coin = row['coin']
                is_user_perp = bool(user_perp_pattern.match(coin)) if coin else False

                if exclude_user_perps and is_user_perp:
                    continue

                results.append({
                    'coin': coin,
                    'count': row['count'],
                    'total_pnl': row['total_pnl'] or 0,
                    'is_user_perp': is_user_perp
                })

            return results
