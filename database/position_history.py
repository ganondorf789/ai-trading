"""
仓位历史管理模块 (PostgreSQL)
记录交易员完整的开仓→平仓周期
"""
from typing import List, Dict, Any, Optional, Tuple
import json
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class PositionHistoryOps:
    """仓位历史相关操作"""

    # ==================== 增量计算状态管理 ====================

    def get_position_calc_state(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取仓位计算状态
        
        Args:
            address: 交易者地址
        
        Returns:
            计算状态字典，包含：
            - last_processed_fill_time: 最后处理的 fill 时间戳
            - open_positions_snapshot: 未平仓仓位的 JSON 快照
            - total_fills_processed: 已处理的 fills 总数
            - total_positions_generated: 生成的仓位总数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM position_calc_state
                WHERE address = %s
            """, (address,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # 解析 JSON 快照
                if result.get('open_positions_snapshot'):
                    if isinstance(result['open_positions_snapshot'], str):
                        result['open_positions_snapshot'] = json.loads(result['open_positions_snapshot'])
                return result
            return None

    def save_position_calc_state(
        self,
        address: str,
        last_processed_fill_time: int,
        open_positions_snapshot: Dict[str, Dict],
        total_fills_processed: int,
        total_positions_generated: int
    ) -> None:
        """
        保存仓位计算状态
        
        Args:
            address: 交易者地址
            last_processed_fill_time: 最后处理的 fill 时间戳
            open_positions_snapshot: 未平仓仓位的 JSON 快照
            total_fills_processed: 已处理的 fills 总数
            total_positions_generated: 生成的仓位总数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO position_calc_state (
                    address, last_processed_fill_time, open_positions_snapshot,
                    total_fills_processed, total_positions_generated, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (address) DO UPDATE SET
                    last_processed_fill_time = EXCLUDED.last_processed_fill_time,
                    open_positions_snapshot = EXCLUDED.open_positions_snapshot,
                    total_fills_processed = EXCLUDED.total_fills_processed,
                    total_positions_generated = EXCLUDED.total_positions_generated,
                    updated_at = EXCLUDED.updated_at
            """, (
                address,
                last_processed_fill_time,
                json.dumps(open_positions_snapshot, default=str),
                total_fills_processed,
                total_positions_generated,
                pendulum.now(SHANGHAI_TZ).to_iso8601_string()
            ))

    def delete_position_calc_state(self, address: str) -> None:
        """删除仓位计算状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM position_calc_state WHERE address = %s",
                (address,)
            )

    # ==================== 增量计算核心方法 ====================

    def calculate_position_history_incremental(
        self,
        address: str,
        coin: str = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        增量计算仓位历史
        
        只处理上次计算后新增的 fills，大幅减少计算量。
        
        Args:
            address: 交易者地址
            coin: 可选，只计算特定币种
        
        Returns:
            (新产生的已平仓位列表, 处理的 fills 数量)
        """
        # 获取上次计算状态
        calc_state = self.get_position_calc_state(address)
        
        last_processed_time = 0
        positions_by_coin: Dict[str, Dict] = {}
        total_fills_processed = 0
        total_positions_generated = 0
        
        if calc_state:
            last_processed_time = calc_state.get('last_processed_fill_time', 0)
            positions_by_coin = calc_state.get('open_positions_snapshot', {})
            total_fills_processed = calc_state.get('total_fills_processed', 0)
            total_positions_generated = calc_state.get('total_positions_generated', 0)
        
        with self._get_connection(statement_timeout='300s') as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 只获取新增的交易记录
            if coin:
                cursor.execute("""
                    SELECT coin, trade_time, time, trade_type, px, sz, closed_pnl, fee, start_position
                    FROM trader_fills
                    WHERE address = %s AND coin = %s AND time > %s
                    ORDER BY time ASC
                """, (address, coin, last_processed_time))
            else:
                cursor.execute("""
                    SELECT coin, trade_time, time, trade_type, px, sz, closed_pnl, fee, start_position
                    FROM trader_fills
                    WHERE address = %s AND time > %s
                    ORDER BY time ASC
                """, (address, last_processed_time))

            fills = cursor.fetchall()

        if not fills:
            return [], 0

        # 处理新增的 fills
        new_closed_positions: List[Dict] = []
        new_last_processed_time = last_processed_time

        for fill in fills:
            fill_coin = fill['coin']
            trade_type = fill.get('trade_type', '')
            trade_time = fill['trade_time']
            time_ms = fill['time']
            px = float(fill.get('px', 0) or 0)
            sz = float(fill.get('sz', 0) or 0)
            closed_pnl = float(fill.get('closed_pnl', 0) or 0)
            fee = float(fill.get('fee', 0) or 0)

            if not trade_type:
                continue

            new_last_processed_time = max(new_last_processed_time, time_ms)
            total_fills_processed += 1

            # 开仓（从零仓位）
            if trade_type in (1, 4):
                # 如果有旧的未平仓仓位，先关闭它
                if fill_coin in positions_by_coin:
                    old_pos = positions_by_coin[fill_coin]
                    old_pos['status'] = 'closed'
                    old_pos['close_time'] = trade_time
                    if old_pos.get('open_time_ms') and time_ms:
                        old_pos['holding_hours'] = (time_ms - old_pos['open_time_ms']) / (1000 * 3600)
                    new_closed_positions.append(old_pos)
                    total_positions_generated += 1

                # 创建新仓位
                direction = 'long' if trade_type in (1, 2, 3) else 'short'
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
            elif trade_type in (2, 5):
                if fill_coin not in positions_by_coin:
                    direction = 'long' if trade_type in (1, 2, 3) else 'short'
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
            elif trade_type in (3, 6):
                if fill_coin not in positions_by_coin:
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

                # 检查是否完全平仓
                if abs(pos['current_size']) < 0.0001:
                    pos['status'] = 'closed'
                    pos['close_time'] = trade_time
                    if pos.get('open_time_ms') and time_ms:
                        pos['holding_hours'] = (time_ms - pos['open_time_ms']) / (1000 * 3600)
                    new_closed_positions.append(pos)
                    total_positions_generated += 1
                    del positions_by_coin[fill_coin]

        # 保存计算状态
        self.save_position_calc_state(
            address=address,
            last_processed_fill_time=new_last_processed_time,
            open_positions_snapshot=positions_by_coin,
            total_fills_processed=total_fills_processed,
            total_positions_generated=total_positions_generated
        )

        return new_closed_positions, len(fills)

    def rebuild_position_history_incremental(self, address: str) -> int:
        """
        增量重建交易员的仓位历史
        
        只处理新增的 fills，大幅提升性能。
        
        Args:
            address: 交易者地址
        
        Returns:
            新保存的记录数
        """
        new_positions, fills_processed = self.calculate_position_history_incremental(address)
        
        if not new_positions:
            logger.debug(f"增量计算: {address} 无新仓位记录, 处理 {fills_processed} 条 fills")
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for pos in new_positions:
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

        logger.info(f"增量重建仓位历史: {address}, 处理 {fills_processed} 条 fills, 新增 {saved_count} 条仓位记录")
        return saved_count

    def get_open_positions_from_state(self, address: str) -> List[Dict[str, Any]]:
        """
        从计算状态获取未平仓仓位
        
        Args:
            address: 交易者地址
        
        Returns:
            未平仓仓位列表
        """
        calc_state = self.get_position_calc_state(address)
        if not calc_state:
            return []
        
        open_positions = calc_state.get('open_positions_snapshot', {})
        return list(open_positions.values())

    # ==================== 原有方法（全量计算）====================

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
            # trade_type: 1=OPEN_LONG, 4=OPEN_SHORT
            if trade_type in (1, 4):
                # 如果有旧的未平仓仓位，先关闭它（异常情况）
                if fill_coin in positions_by_coin:
                    old_pos = positions_by_coin[fill_coin]
                    old_pos['status'] = 'closed'
                    old_pos['close_time'] = trade_time
                    if old_pos['open_time_ms'] and time_ms:
                        old_pos['holding_hours'] = (time_ms - old_pos['open_time_ms']) / (1000 * 3600)
                    position_history.append(old_pos)

                # 创建新仓位
                # trade_type 1, 2, 3 是多头相关，4, 5, 6 是空头相关
                direction = 'long' if trade_type in (1, 2, 3) else 'short'
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
            # trade_type: 2=ADD_LONG, 5=ADD_SHORT
            elif trade_type in (2, 5):
                if fill_coin not in positions_by_coin:
                    # 没有开仓记录，创建一个（可能是历史数据不完整）
                    direction = 'long' if trade_type in (1, 2, 3) else 'short'
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
            # trade_type: 3=CLOSE_LONG, 6=CLOSE_SHORT
            elif trade_type in (3, 6):
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

    def rebuild_position_history(self, address: str, force_full: bool = False) -> int:
        """
        重建交易员的仓位历史（从 fills 重新计算并保存）
        
        默认使用增量计算，只处理新增的 fills。
        设置 force_full=True 可强制全量重建。

        Args:
            address: 交易者地址
            force_full: 是否强制全量重建（默认使用增量计算）

        Returns:
            保存的记录数
        """
        # 默认使用增量计算
        if not force_full:
            return self.rebuild_position_history_incremental(address)
        
        # 全量重建：先删除计算状态
        self.delete_position_calc_state(address)
        
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

        logger.info(f"全量重建仓位历史完成: {address}, 共 {saved_count} 条记录")
        return saved_count

    def get_position_history(
        self,
        address: str,
        coin: str = None,
        status: str = None,
        direction: str = None,
        start_time: str = None,
        end_time: str = None,
        pnl_filter: str = None,
        sort_by: str = 'open_time',
        sort_order: str = 'desc',
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取交易员的仓位历史

        Args:
            address: 交易者地址
            coin: 可选，筛选特定币种
            status: 可选，筛选状态（'open', 'closed'）
            direction: 可选，筛选方向（'long', 'short'）
            start_time: 可选，开始时间（ISO格式）
            end_time: 可选，结束时间（ISO格式）
            pnl_filter: 可选，盈亏筛选（'profit', 'loss'）
            sort_by: 排序字段，默认 open_time
            sort_order: 排序方向，默认 desc
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

            if direction:
                conditions.append("direction = %s")
                params.append(direction)

            if start_time:
                conditions.append("open_time >= %s")
                params.append(start_time)

            if end_time:
                conditions.append("open_time <= %s")
                params.append(end_time)

            if pnl_filter == 'profit':
                conditions.append("realized_pnl > 0")
            elif pnl_filter == 'loss':
                conditions.append("realized_pnl < 0")

            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])

            # 映射前端字段名到数据库字段名
            sort_field_map = {
                'coin': 'coin',
                'direction': 'direction',
                'open_time': 'open_time',
                'close_time': 'close_time',
                'max_size': 'max_size',
                'entry_price': 'avg_entry_price',
                'close_price': 'avg_close_price',
                'position_value': '(max_size * avg_entry_price)',
                'holding': 'holding_hours',
                'pnl': 'realized_pnl',
                'status': 'status',
            }
            db_sort_field = sort_field_map.get(sort_by, 'open_time')
            order_direction = 'ASC' if sort_order == 'asc' else 'DESC'

            cursor.execute(f"""
                SELECT *,
                    (max_size * avg_entry_price) as position_value
                FROM position_history
                WHERE {where_clause}
                ORDER BY {db_sort_field} {order_direction}
                LIMIT %s OFFSET %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_position_history_count(
        self,
        address: str,
        coin: str = None,
        status: str = None,
        direction: str = None,
        start_time: str = None,
        end_time: str = None,
        pnl_filter: str = None
    ) -> int:
        """
        获取仓位历史记录总数

        Args:
            address: 交易者地址
            coin: 可选，筛选特定币种
            status: 可选，筛选状态
            direction: 可选，筛选方向（'long', 'short'）
            start_time: 可选，开始时间（ISO格式）
            end_time: 可选，结束时间（ISO格式）
            pnl_filter: 可选，盈亏筛选（'profit', 'loss'）

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

            if direction:
                conditions.append("direction = %s")
                params.append(direction)

            if start_time:
                conditions.append("open_time >= %s")
                params.append(start_time)

            if end_time:
                conditions.append("open_time <= %s")
                params.append(end_time)

            if pnl_filter == 'profit':
                conditions.append("realized_pnl > 0")
            elif pnl_filter == 'loss':
                conditions.append("realized_pnl < 0")

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

    def get_position_metrics_from_db(self, address: str) -> Optional[Dict[str, Any]]:
        """
        从数据库获取仓位指标（与 calculate_position_based_metrics 格式兼容）
        
        用于大数据量优化：直接从数据库读取仓位统计，而不是在内存中重建。
        
        Args:
            address: 交易者地址
        
        Returns:
            与 calculate_position_based_metrics 返回格式兼容的字典：
            - winning_positions: 盈利仓位数
            - losing_positions: 亏损仓位数
            - total_closed_positions: 已平仓位数
            - total_open_positions: 未平仓位数
            - win_rate: 胜率
            - total_pnl: 总盈亏
            - total_profit: 总盈利
            - total_loss: 总亏损
            - avg_win: 平均盈利
            - avg_loss: 平均亏损
            - profit_factor: 盈亏比
            - pnl_list: 已平仓位盈亏列表（用于风险指标计算）
            - avg_holding_hours: 平均持仓时长
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 获取统计数据
            cursor.execute("""
                SELECT
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_positions,
                    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_positions,
                    COUNT(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN 1 END) as winning_positions,
                    COUNT(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN 1 END) as losing_positions,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl,
                    COALESCE(SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END), 0) as total_profit,
                    COALESCE(ABS(SUM(CASE WHEN realized_pnl < 0 THEN realized_pnl ELSE 0 END)), 0) as total_loss,
                    COALESCE(AVG(CASE WHEN realized_pnl > 0 AND status = 'closed' THEN realized_pnl END), 0) as avg_win,
                    COALESCE(AVG(CASE WHEN realized_pnl < 0 AND status = 'closed' THEN ABS(realized_pnl) END), 0) as avg_loss,
                    COALESCE(AVG(CASE WHEN status = 'closed' THEN holding_hours END), 0) as avg_holding_hours
                FROM position_history
                WHERE address = %s
            """, (address,))

            row = cursor.fetchone()
            
            if not row or row['closed_positions'] == 0:
                return None

            stats = dict(row)
            
            # 计算胜率和盈亏比
            total_closed = stats['closed_positions']
            winning = stats['winning_positions']
            total_profit = float(stats['total_profit'])
            total_loss = float(stats['total_loss'])
            
            win_rate = winning / total_closed if total_closed > 0 else 0.0
            profit_factor = total_profit / total_loss if total_loss > 0 else (
                float('inf') if total_profit > 0 else 0.0
            )

            # 获取 pnl_list（用于风险指标计算）
            cursor.execute("""
                SELECT realized_pnl
                FROM position_history
                WHERE address = %s AND status = 'closed'
                ORDER BY close_time ASC
            """, (address,))
            
            pnl_list = [float(row['realized_pnl'] or 0) for row in cursor.fetchall()]

            return {
                'winning_positions': stats['winning_positions'],
                'losing_positions': stats['losing_positions'],
                'total_closed_positions': stats['closed_positions'],
                'total_open_positions': stats['open_positions'],
                'win_rate': float(win_rate),
                'total_pnl': float(stats['total_pnl']),
                'total_profit': float(total_profit),
                'total_loss': float(total_loss),
                'avg_win': float(stats['avg_win']),
                'avg_loss': float(stats['avg_loss']),
                'profit_factor': float(profit_factor) if profit_factor != float('inf') else float('inf'),
                'pnl_list': pnl_list,
                'avg_holding_hours': float(stats['avg_holding_hours']),
            }

    def has_position_history(self, address: str) -> bool:
        """
        检查交易员是否有仓位历史记录
        
        Args:
            address: 交易者地址
        
        Returns:
            是否有仓位历史记录
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM position_history WHERE address = %s LIMIT 1
                )
            """, (address,))
            return cursor.fetchone()[0]

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
                    (ph.max_size * ph.avg_entry_price) as position_value,
                    tm.rating,
                    tm.overall_score,
                    tm.win_rate as trader_win_rate,
                    tm.total_pnl as trader_pnl,
                    tm.is_starred,
                    tm.display_name as trader_name
                FROM position_history ph
                LEFT JOIN trader_metrics tm ON ph.address = tm.address
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
                    tm.display_name as trader_name,
                    COUNT(*) as total_positions,
                    COALESCE(SUM(ph.realized_pnl), 0) as total_pnl,
                    COALESCE(SUM(ph.total_volume), 0) as total_volume
                FROM position_history ph
                LEFT JOIN trader_metrics tm ON ph.address = tm.address
                GROUP BY ph.address, tm.display_name
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
