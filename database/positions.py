"""
持仓管理模块 (PostgreSQL)
"""
from typing import List, Dict, Optional
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ
from utils import sanitize_float
from .cache import cache


PERIOD_INTERVALS = {
    '5m': '5 minutes',
    '30m': '30 minutes',
    '1h': '1 hour',
    '4h': '4 hours',
    '12h': '12 hours',
    '1d': '1 day',
}


class PositionsOps:
    """持仓管理相关操作"""

    def get_position_open_time(self, address: str, coin: str) -> Optional[str]:
        """
        根据历史订单计算某个币种的开仓时间

        逻辑：
        - 从 trader_fills 表中找到该币种最近一次 start_position=0 的开仓记录
        - 开仓类型为 open_long 或 open_short

        Args:
            address: 交易者地址
            coin: 币种

        Returns:
            开仓时间（ISO8601格式字符串），如果找不到则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 找到最近一次从零仓位开始的开仓记录
            # start_position = 0 表示这是一个全新的仓位
            # trade_type: 1=OPEN_LONG, 4=OPEN_SHORT
            cursor.execute("""
                SELECT trade_time, time
                FROM trader_fills
                WHERE address = %s
                  AND coin = %s
                  AND trade_type IN (1, 4)
                ORDER BY time DESC
                LIMIT 1
            """, (address, coin))

            row = cursor.fetchone()
            if row:
                return row['trade_time']

            return None

    def get_positions_open_times(self, address: str, coins: List[str]) -> Dict[str, Optional[str]]:
        """
        批量获取多个币种的开仓时间

        Args:
            address: 交易者地址
            coins: 币种列表

        Returns:
            {coin: open_time} 字典
        """
        if not coins:
            return {}

        result = {coin: None for coin in coins}

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 使用窗口函数一次性获取所有币种最近的开仓时间
            # trade_type: 1=OPEN_LONG, 4=OPEN_SHORT
            cursor.execute("""
                WITH ranked_fills AS (
                    SELECT
                        coin,
                        trade_time,
                        ROW_NUMBER() OVER (PARTITION BY coin ORDER BY time DESC) as rn
                    FROM trader_fills
                    WHERE address = %s
                      AND coin = ANY(%s)
                      AND trade_type IN (1, 4)
                )
                SELECT coin, trade_time
                FROM ranked_fills
                WHERE rn = 1
            """, (address, coins))

            for row in cursor.fetchall():
                result[row['coin']] = row['trade_time']

        return result

    def save_positions(self, address: str, positions: List[Dict]) -> int:
        """
        保存交易者的当前持仓

        Args:
            address: 交易者地址
            positions: 持仓列表

        Returns:
            保存的记录数
        """
        if not positions:
            # 清空该地址的所有持仓
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM asset_positions WHERE address = %s",
                    (address,)
                )
            cache.delete(f"positions:{address}")
            return 0

        # 提取所有非空仓位的币种
        valid_coins = []
        for pos_data in positions:
            pos = pos_data.get('position', {})
            szi = sanitize_float(pos.get('szi', 0))
            if szi != 0:
                valid_coins.append(pos.get('coin'))

        # 批量获取开仓时间
        open_times = self.get_positions_open_times(address, valid_coins)

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 先删除旧持仓
            cursor.execute(
                "DELETE FROM asset_positions WHERE address = %s",
                (address,)
            )

            for pos_data in positions:
                try:
                    pos = pos_data.get('position', {})
                    leverage = pos.get('leverage', {})

                    # 跳过空仓位
                    szi = sanitize_float(pos.get('szi', 0))
                    if szi == 0:
                        continue

                    coin = pos.get('coin')
                    open_time = open_times.get(coin)

                    cursor.execute("""
                        INSERT INTO asset_positions (
                            address, coin, szi, entry_px, position_value,
                            unrealized_pnl, return_on_equity, liquidation_px,
                            margin_used, max_leverage, leverage_type, leverage_value,
                            updated_at, open_time
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        address,
                        coin,
                        szi,
                        sanitize_float(pos.get('entryPx', 0)),
                        sanitize_float(pos.get('positionValue', 0)),
                        sanitize_float(pos.get('unrealizedPnl', 0)),
                        sanitize_float(pos.get('returnOnEquity', 0)),
                        sanitize_float(pos.get('liquidationPx')) if pos.get('liquidationPx') else None,
                        sanitize_float(pos.get('marginUsed', 0)),
                        int(pos.get('maxLeverage', 1)),
                        leverage.get('type'),
                        int(leverage.get('value', 1)),
                        pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
                        open_time
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存持仓记录失败: {e}")

        # 使缓存失效
        cache.delete(f"positions:{address}")
        return saved_count

    def get_positions(self, address: str) -> List[Dict]:
        """
        获取交易者的当前持仓

        Args:
            address: 交易者地址

        Returns:
            持仓列表
        """
        # 尝试从缓存获取
        cached = cache.get_positions(address)
        if cached:
            return cached

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM asset_positions
                WHERE address = %s
                ORDER BY ABS(position_value) DESC
            """, (address,))
            result = [dict(row) for row in cursor.fetchall()]

            # 缓存结果
            if result:
                cache.cache_positions(address, result)

            return result

    def get_liquidation_stats(self, coin: str, period: str = '1d') -> Dict:
        """
        获取清算统计数据（多空人数、清算价值）

        Args:
            coin: 币种 (如 BTC, ETH)
            period: 时间周期 (5m, 30m, 1h, 4h, 12h, 1d)

        Returns:
            清算统计数据
        """
        interval = PERIOD_INTERVALS.get(period, '1 day')

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    CASE WHEN szi > 0 THEN 'long' ELSE 'short' END AS direction,
                    COUNT(*) AS user_count,
                    COALESCE(SUM(ABS(position_value)), 0) AS liquidation_value
                FROM asset_positions
                WHERE coin = %s
                  AND COALESCE(open_time, updated_at) >= NOW() - %s::interval
                GROUP BY CASE WHEN szi > 0 THEN 'long' ELSE 'short' END
            """, (coin, interval))

            rows = cursor.fetchall()

        long_count = 0
        short_count = 0
        long_value = 0.0
        short_value = 0.0

        for row in rows:
            if row['direction'] == 'long':
                long_count = row['user_count']
                long_value = float(row['liquidation_value'])
            else:
                short_count = row['user_count']
                short_value = float(row['liquidation_value'])

        total_count = long_count + short_count
        total_value = long_value + short_value

        return {
            'symbol': coin,
            'period': period,
            'longShortUserCount': {
                'long': {
                    'count': long_count,
                    'ratio': round(long_count / total_count * 100, 2) if total_count > 0 else 0
                },
                'short': {
                    'count': short_count,
                    'ratio': round(short_count / total_count * 100, 2) if total_count > 0 else 0
                }
            },
            'liquidation': {
                'totalValue': round(total_value, 2),
                'currency': 'USD',
                'long': {
                    'value': round(long_value, 2),
                    'ratio': round(long_value / total_value * 100, 2) if total_value > 0 else 0
                },
                'short': {
                    'value': round(short_value, 2),
                    'ratio': round(short_value / total_value * 100, 2) if total_value > 0 else 0
                }
            },
            'timestamp': int(pendulum.now(SHANGHAI_TZ).timestamp())
        }

    def save_position_ratio_snapshot(self) -> int:
        """
        对所有币种拍摄多空比快照，写入 position_ratio_snapshots 表

        Returns:
            保存的快照记录数
        """
        now = pendulum.now(SHANGHAI_TZ)

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 按币种聚合当前持仓数据
            cursor.execute("""
                SELECT
                    coin,
                    COUNT(*) FILTER (WHERE szi > 0) AS long_count,
                    COUNT(*) FILTER (WHERE szi < 0) AS short_count,
                    COALESCE(SUM(ABS(position_value)) FILTER (WHERE szi > 0), 0) AS long_value,
                    COALESCE(SUM(ABS(position_value)) FILTER (WHERE szi < 0), 0) AS short_value
                FROM asset_positions
                GROUP BY coin
            """)
            rows = cursor.fetchall()

            if not rows:
                return 0

            # 批量写入快照
            saved = 0
            for row in rows:
                cursor.execute("""
                    INSERT INTO position_ratio_snapshots
                        (coin, snapshot_time, long_count, short_count, long_value, short_value)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (coin, snapshot_time) DO UPDATE SET
                        long_count = EXCLUDED.long_count,
                        short_count = EXCLUDED.short_count,
                        long_value = EXCLUDED.long_value,
                        short_value = EXCLUDED.short_value
                """, (
                    row['coin'],
                    now.to_iso8601_string(),
                    row['long_count'],
                    row['short_count'],
                    float(row['long_value']),
                    float(row['short_value'])
                ))
                saved += 1

            logger.info(f"多空比快照已保存: {saved} 个币种")
            return saved

    def get_position_ratio_history(self, coin: str, period: str = '1d') -> Dict:
        """
        获取多空比历史数据（Short Ratio 曲线）

        Args:
            coin: 币种
            period: 时间粒度 (1h, 4h, 1d)

        Returns:
            包含 series 数组的时序数据
        """
        # 粒度 → 时间截断精度 + 回看窗口
        period_config = {
            '1h': {'trunc': 'hour', 'lookback': '7 days'},
            '4h': {'trunc': 'hour', 'lookback': '30 days'},
            '1d': {'trunc': 'day', 'lookback': '90 days'},
        }
        cfg = period_config.get(period, period_config['1d'])

        # 4h 需要特殊处理：按4小时分桶
        if period == '4h':
            time_bucket_expr = """
                DATE_TRUNC('day', snapshot_time)
                + INTERVAL '4 hours' * FLOOR(EXTRACT(HOUR FROM snapshot_time) / 4)
            """
        else:
            time_bucket_expr = f"DATE_TRUNC('{cfg['trunc']}', snapshot_time)"

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(f"""
                SELECT
                    {time_bucket_expr} AS bucket,
                    AVG(long_count)  AS long_count,
                    AVG(short_count) AS short_count,
                    AVG(long_value)  AS long_value,
                    AVG(short_value) AS short_value
                FROM position_ratio_snapshots
                WHERE coin = %s
                  AND snapshot_time >= NOW() - %s::interval
                GROUP BY bucket
                ORDER BY bucket ASC
            """, (coin, cfg['lookback']))

            rows = cursor.fetchall()

        series = []
        for row in rows:
            long_c = float(row['long_count'])
            short_c = float(row['short_count'])
            total_c = long_c + short_c
            long_v = float(row['long_value'])
            short_v = float(row['short_value'])

            long_short_ratio = round(short_c / total_c, 4) if total_c > 0 else 0
            value_diff = round(long_v - short_v, 2)

            series.append({
                'timestamp': int(row['bucket'].timestamp()),
                'longShortRatio': long_short_ratio,
                'positionValueDiff': value_diff,
                'longCount': round(long_c),
                'shortCount': round(short_c),
                'longValue': round(long_v, 2),
                'shortValue': round(short_v, 2),
            })

        # 计算均线值
        avg_ratio = 0
        avg_value_diff = 0
        if series:
            avg_ratio = round(sum(s['longShortRatio'] for s in series) / len(series), 4)
            avg_value_diff = round(sum(s['positionValueDiff'] for s in series) / len(series), 2)

        return {
            'symbol': coin,
            'period': period,
            'currentRatio': series[-1]['longShortRatio'] if series else 0,
            'currentValueDiff': series[-1]['positionValueDiff'] if series else 0,
            'avgRatio': avg_ratio,
            'avgValueDiff': avg_value_diff,
            'series': series,
        }
