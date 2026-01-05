"""
持仓管理模块
"""
from typing import List, Dict
import pendulum
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class PositionsOps:
    """持仓管理相关操作"""

    def save_positions(self, address: str, positions: List[Dict]) -> int:
        """
        保存交易者的当前持仓（来自 assetPositions）

        Args:
            address: 交易者地址
            positions: 持仓列表（从 user_state['assetPositions'] 获取）

        Returns:
            保存的记录数
        """
        if not positions:
            # 清空该地址的所有持仓
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM asset_positions WHERE address = ?",
                    (address,)
                )
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 先删除旧持仓
            cursor.execute(
                "DELETE FROM asset_positions WHERE address = ?",
                (address,)
            )

            for pos_data in positions:
                try:
                    pos = pos_data.get('position', {})
                    leverage = pos.get('leverage', {})

                    # 跳过空仓位
                    szi = float(pos.get('szi', 0))
                    if szi == 0:
                        continue

                    cursor.execute("""
                        INSERT INTO asset_positions (
                            address, coin, szi, entry_px, position_value,
                            unrealized_pnl, return_on_equity, liquidation_px,
                            margin_used, max_leverage, leverage_type, leverage_value,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        address,
                        pos.get('coin'),
                        szi,
                        float(pos.get('entryPx', 0)),
                        float(pos.get('positionValue', 0)),
                        float(pos.get('unrealizedPnl', 0)),
                        float(pos.get('returnOnEquity', 0)),
                        float(pos.get('liquidationPx')) if pos.get('liquidationPx') else None,
                        float(pos.get('marginUsed', 0)),
                        int(pos.get('maxLeverage', 1)),
                        leverage.get('type'),
                        int(leverage.get('value', 1)),
                        pendulum.now(SHANGHAI_TZ).to_iso8601_string()
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存持仓记录失败: {e}")

        return saved_count

    def get_positions(self, address: str) -> List[Dict]:
        """
        获取交易者的当前持仓

        Args:
            address: 交易者地址

        Returns:
            持仓列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM asset_positions
                WHERE address = ?
                ORDER BY ABS(position_value) DESC
            """, (address,))
            return [dict(row) for row in cursor.fetchall()]

    def save_copied_positions(self, target_address: str, positions: Dict[str, Dict]) -> int:
        """
        保存目标交易者的已跟单仓位状态（用于重启后恢复）

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
                "DELETE FROM copy_position_states WHERE target_address = ?",
                (target_address,)
            )

            saved_count = 0
            for symbol, pos in positions.items():
                try:
                    cursor.execute("""
                        INSERT INTO copy_position_states (
                            target_address, symbol, size, side, entry_price,
                            leverage, notional, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        获取目标交易者的已跟单仓位状态（用于重启后恢复）

        Args:
            target_address: 目标地址

        Returns:
            已跟单仓位 {symbol: position_data}
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM copy_position_states
                WHERE target_address = ?
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
                WHERE target_address = ? AND symbol = ?
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
                "DELETE FROM copy_position_states WHERE target_address = ?",
                (target_address,)
            )
            return cursor.rowcount
