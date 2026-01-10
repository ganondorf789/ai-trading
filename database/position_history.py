"""
仓位历史管理模块 (PostgreSQL)
记录交易员完整的开仓→平仓周期
"""
from typing import List, Dict, Any, Optional
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class PositionHistoryOps:
    """仓位历史相关操作"""

    def calculate_position_history_from_fills(
        self,
        address: str,
        coin: str = None
    ) -> List[Dict[str, Any]]:
        """
        从 trader_fills 计算仓位历史

        算法：
        - 按时间顺序遍历 fills
        - 遇到 open_long/open_short 时开始新仓位
        - 遇到 add_long/add_short 时更新仓位信息
        - 遇到 close_long/close_short 时更新平仓信息
        - 当仓位完全平仓时（通过 closed_pnl 判断），标记为已完成

        Args:
            address: 交易者地址
            coin: 可选，只计算特定币种

        Returns:
            仓位历史列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 获取该地址的所有交易记录
            if coin:
                cursor.execute("""
                    SELECT coin, trade_time, time, trade_type, px, sz, closed_pnl, fee, start_position
                    FROM trader_fills
                    WHERE address = %s AND coin = %s
                    ORDER BY time ASC
                """, (address, coin))
            else:
                cursor.execute("""
                    SELECT coin, trade_time, time, trade_type, px, sz, closed_pnl, fee, start_position
                    FROM trader_fills
                    WHERE address = %s
                    ORDER BY time ASC
                """, (address,))

            fills = cursor.fetchall()

        if not fills:
            return []

        # 按币种分组处理
        positions_by_coin: Dict[str, Dict] = {}  # 当前持仓状态
        position_history: List[Dict] = []

        for fill in fills:
            fill_coin = fill['coin']
            trade_type = fill.get('trade_type', '')
            trade_time = fill['trade_time']
            time_ms = fill['time']
            px = float(fill.get('px', 0) or 0)
            sz = float(fill.get('sz', 0) or 0)
            closed_pnl = float(fill.get('closed_pnl', 0) or 0)
            fee = float(fill.get('fee', 0) or 0)
            start_position = float(fill.get('start_position', 0) or 0)

            if not trade_type:
                continue

            # 开仓（从零仓位）
            if trade_type in ('open_long', 'open_short'):
                # 如果有旧的未平仓仓位，先关闭它（异常情况）
                if fill_coin in positions_by_coin:
                    old_pos = positions_by_coin[fill_coin]
                    old_pos['status'] = 'closed'
                    old_pos['close_time'] = trade_time
                    if old_pos['open_time_ms'] and time_ms:
                        old_pos['holding_hours'] = (time_ms - old_pos['open_time_ms']) / (1000 * 3600)
                    position_history.append(old_pos)

                # 创建新仓位
                direction = 'long' if 'long' in trade_type else 'short'
                positions_by_coin[fill_coin] = {
                    'address': address,
                    'coin': fill_coin,
                    'direction': direction,
                    'open_time': trade_time,
                    'open_time_ms': time_ms,
                    'close_time': None,
                    'max_size': sz,
                    'current_size': sz,
                    'avg_entry_price': px,
                    'total_entry_value': px * sz,
                    'total_entry_size': sz,
                    'avg_close_price': None,
                    'total_close_value': 0,
                    'total_close_size': 0,
                    'total_volume': px * sz,
                    'realized_pnl': closed_pnl,
                    'total_fee': fee,
                    'open_trades': 1,
                    'close_trades': 0,
                    'holding_hours': None,
                    'status': 'open'
                }

            # 加仓
            elif trade_type in ('add_long', 'add_short'):
                if fill_coin not in positions_by_coin:
                    # 没有开仓记录，创建一个（可能是历史数据不完整）
                    direction = 'long' if 'long' in trade_type else 'short'
                    positions_by_coin[fill_coin] = {
                        'address': address,
                        'coin': fill_coin,
                        'direction': direction,
                        'open_time': trade_time,
                        'open_time_ms': time_ms,
                        'close_time': None,
                        'max_size': sz,
                        'current_size': sz,
                        'avg_entry_price': px,
                        'total_entry_value': px * sz,
                        'total_entry_size': sz,
                        'avg_close_price': None,
                        'total_close_value': 0,
                        'total_close_size': 0,
                        'total_volume': px * sz,
                        'realized_pnl': closed_pnl,
                        'total_fee': fee,
                        'open_trades': 1,
                        'close_trades': 0,
                        'holding_hours': None,
                        'status': 'open'
                    }
                else:
                    pos = positions_by_coin[fill_coin]
                    pos['current_size'] += sz
                    pos['max_size'] = max(pos['max_size'], pos['current_size'])
                    pos['total_entry_value'] += px * sz
                    pos['total_entry_size'] += sz
                    pos['avg_entry_price'] = pos['total_entry_value'] / pos['total_entry_size'] if pos['total_entry_size'] > 0 else 0
                    pos['total_volume'] += px * sz
                    pos['realized_pnl'] += closed_pnl
                    pos['total_fee'] += fee
                    pos['open_trades'] += 1

            # 平仓
            elif trade_type in ('close_long', 'close_short'):
                if fill_coin not in positions_by_coin:
                    # 没有开仓记录，跳过（可能是历史数据不完整）
                    continue

                pos = positions_by_coin[fill_coin]
                pos['current_size'] -= sz
                pos['total_close_value'] += px * sz
                pos['total_close_size'] += sz
                pos['avg_close_price'] = pos['total_close_value'] / pos['total_close_size'] if pos['total_close_size'] > 0 else None
                pos['total_volume'] += px * sz
                pos['realized_pnl'] += closed_pnl
                pos['total_fee'] += fee
                pos['close_trades'] += 1

                # 检查是否完全平仓（仓位接近0）
                if abs(pos['current_size']) < 0.0001:
                    pos['status'] = 'closed'
                    pos['close_time'] = trade_time
                    if pos['open_time_ms'] and time_ms:
                        pos['holding_hours'] = (time_ms - pos['open_time_ms']) / (1000 * 3600)
                    position_history.append(pos)
                    del positions_by_coin[fill_coin]

        # 添加未平仓的仓位
        for coin, pos in positions_by_coin.items():
            pos['status'] = 'open'
            position_history.append(pos)

        # 按开仓时间降序排列
        position_history.sort(key=lambda x: x.get('open_time_ms', 0) or 0, reverse=True)

        return position_history

    def rebuild_position_history(self, address: str) -> int:
        """
        重建交易员的仓位历史（从 fills 重新计算并保存）

        Args:
            address: 交易者地址

        Returns:
            保存的记录数
        """
        # 计算仓位历史
        positions = self.calculate_position_history_from_fills(address)

        if not positions:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 先删除该地址的旧记录
            cursor.execute(
                "DELETE FROM position_history WHERE address = %s",
                (address,)
            )

            saved_count = 0
            for pos in positions:
                try:
                    cursor.execute("""
                        INSERT INTO position_history (
                            address, coin, direction, open_time, close_time,
                            max_size, avg_entry_price, avg_close_price, total_volume,
                            realized_pnl, total_fee, open_trades, close_trades,
                            holding_hours, status, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        address,
                        pos['coin'],
                        pos['direction'],
                        pos['open_time'],
                        pos['close_time'],
                        pos['max_size'],
                        pos['avg_entry_price'],
                        pos['avg_close_price'],
                        pos['total_volume'],
                        pos['realized_pnl'],
                        pos['total_fee'],
                        pos['open_trades'],
                        pos['close_trades'],
                        pos['holding_hours'],
                        pos['status'],
                        pendulum.now(SHANGHAI_TZ).to_iso8601_string()
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存仓位历史失败: {e}")

        logger.info(f"重建仓位历史完成: {address}, 共 {saved_count} 条记录")
        return saved_count

    def get_position_history(
        self,
        address: str,
        coin: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取交易员的仓位历史

        Args:
            address: 交易者地址
            coin: 可选，筛选特定币种
            status: 可选，筛选状态（'open', 'closed'）
            limit: 返回数量
            offset: 偏移量

        Returns:
            仓位历史列表
        """
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

            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])

            cursor.execute(f"""
                SELECT * FROM position_history
                WHERE {where_clause}
                ORDER BY open_time DESC
                LIMIT %s OFFSET %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_position_history_count(
        self,
        address: str,
        coin: str = None,
        status: str = None
    ) -> int:
        """
        获取仓位历史记录总数

        Args:
            address: 交易者地址
            coin: 可选，筛选特定币种
            status: 可选，筛选状态

        Returns:
            记录总数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["address = %s"]
            params = [address]

            if coin:
                conditions.append("coin = %s")
                params.append(coin)

            if status:
                conditions.append("status = %s")
                params.append(status)

            where_clause = " AND ".join(conditions)

            cursor.execute(f"""
                SELECT COUNT(*) FROM position_history
                WHERE {where_clause}
            """, params)

            return cursor.fetchone()[0]

    def get_position_history_stats(self, address: str) -> Dict[str, Any]:
        """
        获取仓位历史统计信息

        Args:
            address: 交易者地址

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    COUNT(*) as total_positions,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as winning_positions,
                    COUNT(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN 1 END) as losing_positions,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END), 0) as total_profit,
                    COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl ELSE 0 END), 0) as total_loss,
                    COALESCE(AVG(CASE WHEN status = 'closed' THEN holding_hours END), 0) as avg_holding_hours,
                    COALESCE(AVG(realized_pnl), 0) as avg_pnl,
                    COALESCE(SUM(total_fee), 0) as total_fees,
                    COUNT(DISTINCT coin) as unique_coins
                FROM position_history
                WHERE address = %s
            """, (address,))

            row = cursor.fetchone()

            if not row:
                return {
                    'total_positions': 0,
                    'closed_positions': 0,
                    'open_positions': 0,
                    'winning_positions': 0,
                    'losing_positions': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'total_profit': 0,
                    'total_loss': 0,
                    'avg_holding_hours': 0,
                    'avg_pnl': 0,
                    'total_fees': 0,
                    'unique_coins': 0
                }

            stats = dict(row)

            # 计算胜率
            closed = stats.get('closed_positions', 0)
            winning = stats.get('winning_positions', 0)
            stats['win_rate'] = winning / closed if closed > 0 else 0

            return stats

    def get_position_history_by_coin(self, address: str) -> List[Dict[str, Any]]:
        """
        按币种汇总仓位历史

        Args:
            address: 交易者地址

        Returns:
            按币种汇总的列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    coin,
                    COUNT(*) as total_positions,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as winning_positions,
                    COUNT(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN 1 END) as losing_positions,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(AVG(CASE WHEN status = 'closed' THEN holding_hours END), 0) as avg_holding_hours,
                    COALESCE(SUM(total_volume), 0) as total_volume
                FROM position_history
                WHERE address = %s
                GROUP BY coin
                ORDER BY total_pnl DESC
            """, (address,))

            results = []
            for row in cursor.fetchall():
                stats = dict(row)
                closed = stats.get('closed_positions', 0)
                winning = stats.get('winning_positions', 0)
                stats['win_rate'] = winning / closed if closed > 0 else 0
                results.append(stats)

            return results

    def delete_position_history(self, address: str) -> int:
        """
        删除交易员的仓位历史

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM position_history WHERE address = %s",
                (address,)
            )
            return cursor.rowcount

    # ==================== 全局统计方法 ====================

    def get_all_position_history(
        self,
        coin: str = None,
        status: str = None,
        direction: str = None,
        min_pnl: float = None,
        max_pnl: float = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取所有交易员的仓位历史

        Args:
            coin: 可选，筛选特定币种
            status: 可选，筛选状态（'open', 'closed'）
            direction: 可选，筛选方向（'long', 'short'）
            min_pnl: 可选，最小盈亏
            max_pnl: 可选，最大盈亏
            limit: 返回数量
            offset: 偏移量

        Returns:
            仓位历史列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = ["1=1"]
            params = []

            if coin:
                conditions.append("ph.coin = %s")
                params.append(coin)

            if status:
                conditions.append("ph.status = %s")
                params.append(status)

            if direction:
                conditions.append("ph.direction = %s")
                params.append(direction)

            if min_pnl is not None:
                conditions.append("ph.realized_pnl >= %s")
                params.append(min_pnl)

            if max_pnl is not None:
                conditions.append("ph.realized_pnl <= %s")
                params.append(max_pnl)

            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])

            # 关联查询获取交易员信息
            cursor.execute(f"""
                SELECT 
                    ph.*,
                    tm.rating,
                    tm.overall_score,
                    tm.win_rate as trader_win_rate,
                    tm.total_pnl as trader_pnl,
                    tm.is_starred,
                    ca.name as trader_name,
                    ca.group_id,
                    cg.name as group_name,
                    cg.color as group_color
                FROM position_history ph
                LEFT JOIN trader_metrics tm ON ph.address = tm.address
                LEFT JOIN copy_trading_addresses ca ON ph.address = ca.address
                LEFT JOIN copy_trading_groups cg ON ca.group_id = cg.id
                WHERE {where_clause}
                ORDER BY ph.open_time DESC
                LIMIT %s OFFSET %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_all_position_history_count(
        self,
        coin: str = None,
        status: str = None,
        direction: str = None,
        min_pnl: float = None,
        max_pnl: float = None
    ) -> int:
        """
        获取所有仓位历史记录总数

        Returns:
            记录总数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = ["1=1"]
            params = []

            if coin:
                conditions.append("coin = %s")
                params.append(coin)

            if status:
                conditions.append("status = %s")
                params.append(status)

            if direction:
                conditions.append("direction = %s")
                params.append(direction)

            if min_pnl is not None:
                conditions.append("realized_pnl >= %s")
                params.append(min_pnl)

            if max_pnl is not None:
                conditions.append("realized_pnl <= %s")
                params.append(max_pnl)

            where_clause = " AND ".join(conditions)

            cursor.execute(f"""
                SELECT COUNT(*) FROM position_history
                WHERE {where_clause}
            """, params)

            return cursor.fetchone()[0]

    def get_all_position_history_stats(self) -> Dict[str, Any]:
        """
        获取所有交易员的仓位历史统计信息

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    COUNT(*) as total_positions,
                    COUNT(DISTINCT address) as total_traders,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN direction = 'long' THEN 1 END) as long_count,
                    COUNT(CASE WHEN direction = 'short' THEN 1 END) as short_count,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as winning_positions,
                    COUNT(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN 1 END) as losing_positions,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END), 0) as total_profit,
                    COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl ELSE 0 END), 0) as total_loss,
                    COALESCE(AVG(CASE WHEN status = 'closed' THEN holding_hours END), 0) as avg_holding_hours,
                    COALESCE(AVG(realized_pnl), 0) as avg_pnl,
                    COALESCE(SUM(total_fee), 0) as total_fees,
                    COALESCE(SUM(total_volume), 0) as total_volume,
                    COUNT(DISTINCT coin) as unique_coins
                FROM position_history
            """)

            row = cursor.fetchone()

            if not row:
                return {
                    'total_positions': 0,
                    'total_traders': 0,
                    'closed_positions': 0,
                    'open_positions': 0,
                    'long_count': 0,
                    'short_count': 0,
                    'winning_positions': 0,
                    'losing_positions': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'total_profit': 0,
                    'total_loss': 0,
                    'avg_holding_hours': 0,
                    'avg_pnl': 0,
                    'total_fees': 0,
                    'total_volume': 0,
                    'unique_coins': 0,
                    'by_coin': [],
                    'by_trader': []
                }

            stats = dict(row)

            # 计算胜率
            closed = stats.get('closed_positions', 0)
            winning = stats.get('winning_positions', 0)
            stats['win_rate'] = winning / closed if closed > 0 else 0

            # 获取币种统计
            cursor.execute("""
                SELECT
                    coin,
                    COUNT(*) as total_positions,
                    COUNT(CASE WHEN direction = 'long' THEN 1 END) as long_count,
                    COUNT(CASE WHEN direction = 'short' THEN 1 END) as short_count,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(SUM(total_volume), 0) as total_volume
                FROM position_history
                GROUP BY coin
                ORDER BY total_pnl DESC
                LIMIT 20
            """)
            stats['by_coin'] = [dict(row) for row in cursor.fetchall()]

            # 获取交易员统计
            cursor.execute("""
                SELECT
                    ph.address,
                    ca.name as trader_name,
                    COUNT(*) as total_positions,
                    COALESCE(SUM(ph.realized_pnl), 0) as total_pnl,
                    COALESCE(SUM(ph.total_volume), 0) as total_volume
                FROM position_history ph
                LEFT JOIN copy_trading_addresses ca ON ph.address = ca.address
                GROUP BY ph.address, ca.name
                ORDER BY total_pnl DESC
                LIMIT 20
            """)
            stats['by_trader'] = [dict(row) for row in cursor.fetchall()]

            return stats

    def get_all_position_history_by_coin(self) -> List[Dict[str, Any]]:
        """
        获取所有交易员按币种汇总的仓位历史

        Returns:
            按币种汇总的列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    coin,
                    COUNT(*) as total_positions,
                    COUNT(DISTINCT address) as trader_count,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN direction = 'long' THEN 1 END) as long_count,
                    COUNT(CASE WHEN direction = 'short' THEN 1 END) as short_count,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as winning_positions,
                    COUNT(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN 1 END) as losing_positions,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(AVG(CASE WHEN status = 'closed' THEN holding_hours END), 0) as avg_holding_hours,
                    COALESCE(SUM(total_volume), 0) as total_volume
                FROM position_history
                GROUP BY coin
                ORDER BY total_pnl DESC
            """)

            results = []
            for row in cursor.fetchall():
                stats = dict(row)
                closed = stats.get('closed_positions', 0)
                winning = stats.get('winning_positions', 0)
                stats['win_rate'] = winning / closed if closed > 0 else 0
                results.append(stats)

            return results
