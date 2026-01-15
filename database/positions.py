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

    def save_copied_positions(self, target_address: str, positions: Dict[str, Dict]) -> int:
        """
        保存目标交易者的已跟单仓位状态

        Args:
            target_address: 目标地址
            positions: 已跟单仓位 {symbol: position_data}

        Returns:
            保存的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 先删除该目标的旧状态
            cursor.execute(
                "DELETE FROM copy_position_states WHERE target_address = %s",
                (target_address,)
            )

            saved_count = 0
            for symbol, pos in positions.items():
                try:
                    cursor.execute("""
                        INSERT INTO copy_position_states (
                            target_address, symbol, size, side, entry_price,
                            leverage, notional, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        target_address,
                        symbol,
                        pos.get('size', 0),
                        pos.get('side', ''),
                        pos.get('entry_price', 0),
                        pos.get('leverage', 1),
                        pos.get('notional', 0),
                        pendulum.now(SHANGHAI_TZ).to_iso8601_string()
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存跟单状态失败: {e}")

            return saved_count

    def get_copied_positions(self, target_address: str) -> Dict[str, Dict]:
        """
        获取目标交易者的已跟单仓位状态

        Args:
            target_address: 目标地址

        Returns:
            已跟单仓位 {symbol: position_data}
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM copy_position_states
                WHERE target_address = %s
            """, (target_address,))

            positions = {}
            for row in cursor.fetchall():
                positions[row['symbol']] = {
                    'symbol': row['symbol'],
                    'size': row['size'],
                    'side': row['side'],
                    'entry_price': row['entry_price'],
                    'leverage': row['leverage'],
                    'notional': row['notional']
                }
            return positions

    def delete_copied_position(self, target_address: str, symbol: str) -> bool:
        """
        删除单个已跟单仓位状态

        Args:
            target_address: 目标地址
            symbol: 币种

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM copy_position_states
                WHERE target_address = %s AND symbol = %s
            """, (target_address, symbol))
            return cursor.rowcount > 0

    def clear_copied_positions(self, target_address: str) -> int:
        """
        清空目标交易者的所有已跟单仓位状态

        Args:
            target_address: 目标地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM copy_position_states WHERE target_address = %s",
                (target_address,)
            )
            return cursor.rowcount
