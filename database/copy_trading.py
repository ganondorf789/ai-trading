"""
跟单地址和分组管理模块
"""
from typing import List, Dict, Optional
import pendulum
import json
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class CopyTradingOps:
    """跟单地址和分组管理相关操作"""

    # ==================== 跟单分组管理 ====================

    def get_copy_trading_groups(self) -> List[Dict]:
        """
        获取所有跟单分组

        Returns:
            分组列表，包含每个分组的地址数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT g.*, COUNT(a.id) as address_count
                FROM copy_trading_groups g
                LEFT JOIN copy_trading_addresses a ON g.id = a.group_id
                GROUP BY g.id
                ORDER BY g.sort_order, g.id
            """)
            return [dict(row) for row in cursor.fetchall()]

    def save_copy_trading_group(self, data: Dict) -> int:
        """
        保存或更新跟单分组

        Args:
            data: 分组数据 {name, description, color, sort_order}

        Returns:
            分组ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if data.get('id'):
                # 更新
                cursor.execute("""
                    UPDATE copy_trading_groups
                    SET name = ?, description = ?, color = ?, sort_order = ?
                    WHERE id = ?
                """, (
                    data.get('name'),
                    data.get('description', ''),
                    data.get('color', '#3B82F6'),
                    data.get('sort_order', 0),
                    data['id']
                ))
                return data['id']
            else:
                # 插入
                cursor.execute("""
                    INSERT INTO copy_trading_groups (name, description, color, sort_order)
                    VALUES (?, ?, ?, ?)
                """, (
                    data.get('name'),
                    data.get('description', ''),
                    data.get('color', '#3B82F6'),
                    data.get('sort_order', 0)
                ))
                return cursor.lastrowid

    def delete_copy_trading_group(self, group_id: int) -> bool:
        """
        删除跟单分组（不能删除默认分组）

        Args:
            group_id: 分组ID

        Returns:
            是否删除成功
        """
        if group_id == 1:
            return False  # 默认分组不能删除

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 将该分组下的地址移到默认分组
            cursor.execute("""
                UPDATE copy_trading_addresses
                SET group_id = 1
                WHERE group_id = ?
            """, (group_id,))
            # 删除分组
            cursor.execute("DELETE FROM copy_trading_groups WHERE id = ?", (group_id,))
            return cursor.rowcount > 0

    # ==================== 跟单地址管理 ====================

    def get_copy_trading_addresses(
        self,
        group_id: int = None,
        is_enabled: bool = None,
        search: str = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = 'updated_at',
        sort_order: str = 'desc'
    ) -> tuple[List[Dict], int]:
        """
        获取跟单地址列表（带关联的交易者指标）

        Args:
            group_id: 分组ID筛选
            is_enabled: 启用状态筛选
            search: 搜索地址或名称
            limit: 每页数量
            offset: 偏移量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            (地址列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = []
            params = []

            if group_id is not None:
                conditions.append("cta.group_id = ?")
                params.append(group_id)

            if is_enabled is not None:
                conditions.append("cta.is_enabled = ?")
                params.append(is_enabled)

            if search:
                conditions.append("(cta.address LIKE ? OR cta.name LIKE ?)")
                params.extend([f'%{search}%', f'%{search}%'])

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 验证排序字段
            valid_sort_fields = {
                'updated_at', 'created_at', 'name', 'address',
                'copy_ratio', 'is_enabled', 'win_rate', 'total_pnl', 'rating'
            }
            if sort_by not in valid_sort_fields:
                sort_by = 'updated_at'
            order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

            # 处理关联字段排序
            if sort_by in ('win_rate', 'total_pnl', 'rating'):
                sort_column = f'tm.{sort_by}'
            else:
                sort_column = f'cta.{sort_by}'

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) FROM copy_trading_addresses cta
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()[0]

            # 查询数据（关联 trader_metrics 和 groups）
            cursor.execute(f"""
                SELECT
                    cta.*,
                    g.name as group_name,
                    g.color as group_color,
                    tm.win_rate,
                    tm.total_pnl as trader_pnl,
                    tm.rating,
                    tm.overall_score,
                    tm.total_trades,
                    tm.profit_factor,
                    tm.max_drawdown,
                    tm.sharpe_ratio,
                    tm.analyzed_at
                FROM copy_trading_addresses cta
                LEFT JOIN copy_trading_groups g ON cta.group_id = g.id
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE {where_clause}
                ORDER BY {sort_column} {order_direction}
                LIMIT ? OFFSET ?
            """, params + [limit, offset])

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # 解析 JSON 字段
                try:
                    item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
                except:
                    item['symbols_whitelist'] = []
                try:
                    item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
                except:
                    item['symbols_blacklist'] = []
                results.append(item)

            return results, total_count

    def get_copy_trading_address(self, address: str) -> Optional[Dict]:
        """
        获取单个跟单地址详情

        Args:
            address: 交易者地址

        Returns:
            地址详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    cta.*,
                    g.name as group_name,
                    g.color as group_color,
                    tm.win_rate,
                    tm.total_pnl as trader_pnl,
                    tm.rating,
                    tm.overall_score,
                    tm.total_trades,
                    tm.profit_factor,
                    tm.max_drawdown,
                    tm.sharpe_ratio,
                    tm.analyzed_at
                FROM copy_trading_addresses cta
                LEFT JOIN copy_trading_groups g ON cta.group_id = g.id
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE cta.address = ?
            """, (address,))
            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            try:
                item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
            except:
                item['symbols_whitelist'] = []
            try:
                item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
            except:
                item['symbols_blacklist'] = []
            return item

    def save_copy_trading_address(self, data: Dict) -> int:
        """
        保存或更新跟单地址

        Args:
            data: 地址数据

        Returns:
            记录ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 处理 JSON 字段
            whitelist = data.get('symbols_whitelist', [])
            blacklist = data.get('symbols_blacklist', [])
            if isinstance(whitelist, list):
                whitelist = json.dumps(whitelist)
            if isinstance(blacklist, list):
                blacklist = json.dumps(blacklist)

            cursor.execute("""
                INSERT INTO copy_trading_addresses (
                    address, name, group_id, is_enabled,
                    copy_ratio, max_position_size_usd, min_position_size_usd,
                    copy_leverage, max_leverage, default_leverage,
                    max_total_positions, max_daily_trades, slippage,
                    symbols_whitelist, symbols_blacklist,
                    check_interval, dry_run, sync_position, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    name = excluded.name,
                    group_id = excluded.group_id,
                    is_enabled = excluded.is_enabled,
                    copy_ratio = excluded.copy_ratio,
                    max_position_size_usd = excluded.max_position_size_usd,
                    min_position_size_usd = excluded.min_position_size_usd,
                    copy_leverage = excluded.copy_leverage,
                    max_leverage = excluded.max_leverage,
                    default_leverage = excluded.default_leverage,
                    max_total_positions = excluded.max_total_positions,
                    max_daily_trades = excluded.max_daily_trades,
                    slippage = excluded.slippage,
                    symbols_whitelist = excluded.symbols_whitelist,
                    symbols_blacklist = excluded.symbols_blacklist,
                    check_interval = excluded.check_interval,
                    dry_run = excluded.dry_run,
                    sync_position = excluded.sync_position,
                    updated_at = excluded.updated_at
            """, (
                data.get('address'),
                data.get('name', ''),
                data.get('group_id'),
                data.get('is_enabled', True),
                data.get('copy_ratio', 0.1),
                data.get('max_position_size_usd', 500.0),
                data.get('min_position_size_usd', 20.0),
                data.get('copy_leverage', True),
                data.get('max_leverage', 10),
                data.get('default_leverage', 5),
                data.get('max_total_positions', 10),
                data.get('max_daily_trades', 50),
                data.get('slippage', 0.01),
                whitelist,
                blacklist,
                data.get('check_interval', 10.0),
                data.get('dry_run', True),
                data.get('sync_position', True),
                pendulum.now(SHANGHAI_TZ).to_iso8601_string()
            ))

            return cursor.lastrowid

    def delete_copy_trading_address(self, address: str) -> bool:
        """
        删除跟单地址

        Args:
            address: 交易者地址

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM copy_trading_addresses WHERE address = ?",
                (address,)
            )
            return cursor.rowcount > 0

    def toggle_copy_trading_address(self, address: str, is_enabled: bool) -> bool:
        """
        启用/禁用跟单地址

        Args:
            address: 交易者地址
            is_enabled: 是否启用

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE copy_trading_addresses
                SET is_enabled = ?, updated_at = ?
                WHERE address = ?
            """, (is_enabled, pendulum.now(SHANGHAI_TZ).to_iso8601_string(), address))
            return cursor.rowcount > 0

    def toggle_copy_trading_sync_position(self, address: str, sync_position: bool) -> bool:
        """
        切换同步仓位状态

        Args:
            address: 交易者地址
            sync_position: 是否同步仓位

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE copy_trading_addresses
                SET sync_position = ?, updated_at = ?
                WHERE address = ?
            """, (sync_position, pendulum.now(SHANGHAI_TZ).to_iso8601_string(), address))
            return cursor.rowcount > 0

    def batch_update_copy_trading_addresses(
        self,
        addresses: List[str],
        action: str,
        group_id: int = None
    ) -> int:
        """
        批量操作跟单地址

        Args:
            addresses: 地址列表
            action: 操作类型 (enable/disable/delete/move_group)
            group_id: 目标分组ID（仅 move_group 时需要）

        Returns:
            影响的记录数
        """
        if not addresses:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in addresses])

            if action == 'enable':
                cursor.execute(f"""
                    UPDATE copy_trading_addresses
                    SET is_enabled = 1, updated_at = ?
                    WHERE address IN ({placeholders})
                """, [pendulum.now(SHANGHAI_TZ).to_iso8601_string()] + addresses)
            elif action == 'disable':
                cursor.execute(f"""
                    UPDATE copy_trading_addresses
                    SET is_enabled = 0, updated_at = ?
                    WHERE address IN ({placeholders})
                """, [pendulum.now(SHANGHAI_TZ).to_iso8601_string()] + addresses)
            elif action == 'delete':
                cursor.execute(f"""
                    DELETE FROM copy_trading_addresses
                    WHERE address IN ({placeholders})
                """, addresses)
            elif action == 'move_group' and group_id is not None:
                cursor.execute(f"""
                    UPDATE copy_trading_addresses
                    SET group_id = ?, updated_at = ?
                    WHERE address IN ({placeholders})
                """, [group_id, pendulum.now(SHANGHAI_TZ).to_iso8601_string()] + addresses)
            else:
                return 0

            return cursor.rowcount

    def get_enabled_copy_addresses(self) -> List[Dict]:
        """
        获取所有启用的跟单地址及其完整配置（供跟单引擎使用）

        Returns:
            启用的跟单地址配置列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE is_enabled = 1
                ORDER BY updated_at DESC
            """)

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # 解析 JSON 字段
                try:
                    item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
                except:
                    item['symbols_whitelist'] = []
                try:
                    item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
                except:
                    item['symbols_blacklist'] = []
                results.append(item)

            return results

    def get_copy_address_config(self, address: str) -> Optional[Dict]:
        """
        获取单个跟单地址的完整配置

        Args:
            address: 交易者地址

        Returns:
            配置字典，如果不存在则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE address = ?
            """, (address,))

            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            # 解析 JSON 字段
            try:
                item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
            except:
                item['symbols_whitelist'] = []
            try:
                item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
            except:
                item['symbols_blacklist'] = []

            return item
