"""
跟单地址和分组管理模块 (PostgreSQL)
"""
from typing import List, Dict, Optional
import pendulum
import json
from psycopg2 import extras
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
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
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
                    SET name = %s, description = %s, color = %s, sort_order = %s
                    WHERE id = %s
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
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (
                    data.get('name'),
                    data.get('description', ''),
                    data.get('color', '#3B82F6'),
                    data.get('sort_order', 0)
                ))
                return cursor.fetchone()[0]

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
                WHERE group_id = %s
            """, (group_id,))
            # 删除分组
            cursor.execute("DELETE FROM copy_trading_groups WHERE id = %s", (group_id,))
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
        获取跟单地址列表

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
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建查询条件
            conditions = []
            params = []

            if group_id is not None:
                conditions.append("cta.group_id = %s")
                params.append(group_id)

            if is_enabled is not None:
                conditions.append("cta.is_enabled = %s")
                params.append(is_enabled)

            if search:
                conditions.append("(cta.address ILIKE %s OR cta.name ILIKE %s)")
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
                SELECT COUNT(*) as count FROM copy_trading_addresses cta
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()['count']

            # 查询数据
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
                    tm.analyzed_at,
                    tm.is_starred
                FROM copy_trading_addresses cta
                LEFT JOIN copy_trading_groups g ON cta.group_id = g.id
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE {where_clause}
                ORDER BY {sort_column} {order_direction}
                LIMIT %s OFFSET %s
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
                try:
                    item['sync_position_symbols'] = json.loads(item.get('sync_position_symbols') or '[]')
                except:
                    item['sync_position_symbols'] = []
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
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
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
                WHERE cta.address = %s
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
            try:
                item['sync_position_symbols'] = json.loads(item.get('sync_position_symbols') or '[]')
            except:
                item['sync_position_symbols'] = []
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
            sync_position_symbols = data.get('sync_position_symbols', [])
            if isinstance(whitelist, list):
                whitelist = json.dumps(whitelist)
            if isinstance(blacklist, list):
                blacklist = json.dumps(blacklist)
            if isinstance(sync_position_symbols, list):
                sync_position_symbols = json.dumps(sync_position_symbols)

            cursor.execute("""
                INSERT INTO copy_trading_addresses (
                    address, name, group_id, is_enabled,
                    copy_ratio, max_position_size_usd, min_position_size_usd,
                    copy_leverage, max_leverage, default_leverage,
                    max_total_positions, max_daily_trades, slippage,
                    symbols_whitelist, symbols_blacklist,
                    check_interval, dry_run, sync_position, sync_position_symbols, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(address) DO UPDATE SET
                    name = EXCLUDED.name,
                    group_id = EXCLUDED.group_id,
                    is_enabled = EXCLUDED.is_enabled,
                    copy_ratio = EXCLUDED.copy_ratio,
                    max_position_size_usd = EXCLUDED.max_position_size_usd,
                    min_position_size_usd = EXCLUDED.min_position_size_usd,
                    copy_leverage = EXCLUDED.copy_leverage,
                    max_leverage = EXCLUDED.max_leverage,
                    default_leverage = EXCLUDED.default_leverage,
                    max_total_positions = EXCLUDED.max_total_positions,
                    max_daily_trades = EXCLUDED.max_daily_trades,
                    slippage = EXCLUDED.slippage,
                    symbols_whitelist = EXCLUDED.symbols_whitelist,
                    symbols_blacklist = EXCLUDED.symbols_blacklist,
                    check_interval = EXCLUDED.check_interval,
                    dry_run = EXCLUDED.dry_run,
                    sync_position = EXCLUDED.sync_position,
                    sync_position_symbols = EXCLUDED.sync_position_symbols,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
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
                sync_position_symbols,
                pendulum.now(SHANGHAI_TZ).to_iso8601_string()
            ))

            result = cursor.fetchone()
            return result[0] if result else None

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
                "DELETE FROM copy_trading_addresses WHERE address = %s",
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
                SET is_enabled = %s, updated_at = %s
                WHERE address = %s
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
                SET sync_position = %s, updated_at = %s
                WHERE address = %s
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
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            if action == 'enable':
                cursor.execute("""
                    UPDATE copy_trading_addresses
                    SET is_enabled = TRUE, updated_at = %s
                    WHERE address = ANY(%s)
                """, (now, addresses))
            elif action == 'disable':
                cursor.execute("""
                    UPDATE copy_trading_addresses
                    SET is_enabled = FALSE, updated_at = %s
                    WHERE address = ANY(%s)
                """, (now, addresses))
            elif action == 'delete':
                cursor.execute("""
                    DELETE FROM copy_trading_addresses
                    WHERE address = ANY(%s)
                """, (addresses,))
            elif action == 'move_group' and group_id is not None:
                cursor.execute("""
                    UPDATE copy_trading_addresses
                    SET group_id = %s, updated_at = %s
                    WHERE address = ANY(%s)
                """, (group_id, now, addresses))
            else:
                return 0

            return cursor.rowcount

    def get_enabled_copy_addresses(self) -> List[Dict]:
        """
        获取所有启用的跟单地址及其完整配置

        Returns:
            启用的跟单地址配置列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE is_enabled = TRUE
                ORDER BY updated_at DESC
            """)

            results = []
            for row in cursor.fetchall():
                item = dict(row)
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
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE address = %s
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

    # ==================== 风控配置管理 ====================

    def get_risk_control_config(self) -> Dict:
        """
        获取风控配置
        
        Returns:
            风控配置字典，如果不存在则返回默认值
        """
        default_config = {
            'max_total_positions': 10,
            'max_daily_trades': 50,
            'max_single_loss_usd': 100.0,
            'max_daily_loss_usd': 500.0,
            'max_drawdown_pct': 10.0,
            'max_margin_usage_pct': 80.0,
            'pause_on_consecutive_losses': 5,
            'max_order_retries': 3,
            'retry_base_delay': 1.0,
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT config_value FROM system_config WHERE config_key = 'risk_control'
                """)
                row = cursor.fetchone()
                
                if row:
                    config = json.loads(row[0])
                    # 合并默认值，确保所有字段都存在
                    return {**default_config, **config}
                else:
                    return default_config
        except Exception as e:
            logger.warning(f"获取风控配置失败，使用默认值: {e}")
            return default_config

    def save_risk_control_config(self, config: Dict) -> bool:
        """
        保存风控配置
        
        Args:
            config: 风控配置字典
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description, updated_at)
                    VALUES ('risk_control', %s, '跟单风控配置', CURRENT_TIMESTAMP)
                    ON CONFLICT (config_key)
                    DO UPDATE SET config_value = %s, updated_at = CURRENT_TIMESTAMP
                """, (json.dumps(config), json.dumps(config)))
            logger.info(f"风控配置已保存: {config}")
            return True
        except Exception as e:
            logger.error(f"保存风控配置失败: {e}")
            return False

    # ==================== 默认跟单配置管理 ====================

    def get_default_copy_config(self) -> Dict:
        """
        获取默认跟单配置
        
        Returns:
            默认跟单配置字典，如果不存在则返回默认值
        """
        default_config = {
            'copy_ratio': 0.1,
            'max_position_size_usd': 500.0,
            'min_position_size_usd': 20.0,
            'max_leverage': 10,
            'default_leverage': 3,
            'slippage': 0.001,
            'copy_leverage': False,
            'sync_position': False,
            'dry_run': False,
            'symbols_whitelist': [],
            'symbols_blacklist': [],
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT config_value FROM system_config WHERE config_key = 'default_copy_config'
                """)
                row = cursor.fetchone()
                
                if row:
                    config = json.loads(row[0])
                    # 合并默认值，确保所有字段都存在
                    return {**default_config, **config}
                else:
                    return default_config
        except Exception as e:
            logger.warning(f"获取默认跟单配置失败，使用默认值: {e}")
            return default_config

    def save_default_copy_config(self, config: Dict) -> bool:
        """
        保存默认跟单配置
        
        Args:
            config: 默认跟单配置字典
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description, updated_at)
                    VALUES ('default_copy_config', %s, '默认跟单配置', CURRENT_TIMESTAMP)
                    ON CONFLICT (config_key)
                    DO UPDATE SET config_value = %s, updated_at = CURRENT_TIMESTAMP
                """, (json.dumps(config), json.dumps(config)))
            logger.info(f"默认跟单配置已保存: {config}")
            return True
        except Exception as e:
            logger.error(f"保存默认跟单配置失败: {e}")
            return False

    # ==================== 立即跟单配置管理 ====================

    def get_immediate_copy_config(self) -> Dict:
        """
        获取立即跟单配置
        
        Returns:
            立即跟单配置字典，如果不存在则返回默认值
        """
        default_config = {
            # 跟单参数
            'copy_ratio': 0.1,
            'max_position_size_usd': 500.0,
            'min_position_size_usd': 20.0,
            'max_leverage': 10,
            'default_leverage': 3,
            'slippage': 0.001,
            'copy_leverage': False,
            # 跟单条件
            'min_trader_overall_score': 0,  # 最低评分 0-100，0表示不限制
            'min_trader_leverage': 0,  # 目标交易员最小杠杆，>=此值才跟单，0表示不限制
            'symbols_whitelist': [],
            'symbols_blacklist': [],
            'min_position_value_usd': 0,  # 目标仓位最小价值
            'max_position_value_usd': 0,  # 0表示不限制
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT config_value FROM system_config WHERE config_key = 'immediate_copy_config'
                """)
                row = cursor.fetchone()
                
                if row:
                    config = json.loads(row[0])
                    # 合并默认值，确保所有字段都存在
                    return {**default_config, **config}
                else:
                    return default_config
        except Exception as e:
            logger.warning(f"获取立即跟单配置失败，使用默认值: {e}")
            return default_config

    def save_immediate_copy_config(self, config: Dict) -> bool:
        """
        保存立即跟单配置
        
        Args:
            config: 立即跟单配置字典
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description, updated_at)
                    VALUES ('immediate_copy_config', %s, '立即跟单配置', CURRENT_TIMESTAMP)
                    ON CONFLICT (config_key)
                    DO UPDATE SET config_value = %s, updated_at = CURRENT_TIMESTAMP
                """, (json.dumps(config), json.dumps(config)))
            logger.info(f"立即跟单配置已保存: {config}")
            return True
        except Exception as e:
            logger.error(f"保存立即跟单配置失败: {e}")
            return False

    # ==================== 跟单配置规则管理（多配置支持） ====================

    def get_copy_config_rules(self, config_type: str, enabled_only: bool = False) -> List[Dict]:
        """
        获取跟单配置规则列表
        
        Args:
            config_type: 配置类型 ('default' 或 'immediate')
            enabled_only: 是否只返回启用的规则
            
        Returns:
            配置规则列表，按优先级排序
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                sql = """
                    SELECT id, config_type, name, description, 
                           leverage_min, leverage_max, config_data,
                           priority, is_enabled, is_default,
                           created_at, updated_at
                    FROM copy_config_rules
                    WHERE config_type = %s
                """
                params = [config_type]
                
                if enabled_only:
                    sql += " AND is_enabled = TRUE"
                
                sql += " ORDER BY priority ASC, id ASC"
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                result = []
                for row in rows:
                    item = dict(row)
                    # 解析 JSON 数据
                    if item.get('config_data'):
                        if isinstance(item['config_data'], str):
                            item['config_data'] = json.loads(item['config_data'])
                    result.append(item)
                
                return result
        except Exception as e:
            logger.error(f"获取跟单配置规则失败: {e}")
            return []

    def get_copy_config_rule_by_id(self, rule_id: int) -> Optional[Dict]:
        """
        根据ID获取单个配置规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            配置规则字典或 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                cursor.execute("""
                    SELECT id, config_type, name, description,
                           leverage_min, leverage_max, config_data,
                           priority, is_enabled, is_default,
                           created_at, updated_at
                    FROM copy_config_rules
                    WHERE id = %s
                """, (rule_id,))
                
                row = cursor.fetchone()
                if row:
                    item = dict(row)
                    if item.get('config_data') and isinstance(item['config_data'], str):
                        item['config_data'] = json.loads(item['config_data'])
                    return item
                return None
        except Exception as e:
            logger.error(f"获取配置规则失败 (id={rule_id}): {e}")
            return None

    def save_copy_config_rule(self, data: Dict) -> Optional[int]:
        """
        保存或更新跟单配置规则
        
        Args:
            data: 规则数据，包含 config_type, name, leverage_min, leverage_max, config_data 等
            
        Returns:
            规则ID，失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                config_data = data.get('config_data', {})
                if isinstance(config_data, dict):
                    config_data = json.dumps(config_data)
                
                if data.get('id'):
                    # 更新
                    cursor.execute("""
                        UPDATE copy_config_rules
                        SET name = %s, description = %s,
                            leverage_min = %s, leverage_max = %s,
                            config_data = %s, priority = %s,
                            is_enabled = %s, is_default = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        RETURNING id
                    """, (
                        data.get('name', ''),
                        data.get('description', ''),
                        data.get('leverage_min', 0),
                        data.get('leverage_max', 100),
                        config_data,
                        data.get('priority', 0),
                        data.get('is_enabled', True),
                        data.get('is_default', False),
                        data['id']
                    ))
                    result = cursor.fetchone()
                    logger.info(f"更新跟单配置规则: id={data['id']}, name={data.get('name')}")
                    return result[0] if result else None
                else:
                    # 插入
                    cursor.execute("""
                        INSERT INTO copy_config_rules 
                        (config_type, name, description, leverage_min, leverage_max, 
                         config_data, priority, is_enabled, is_default)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        data.get('config_type', 'default'),
                        data.get('name', ''),
                        data.get('description', ''),
                        data.get('leverage_min', 0),
                        data.get('leverage_max', 100),
                        config_data,
                        data.get('priority', 0),
                        data.get('is_enabled', True),
                        data.get('is_default', False)
                    ))
                    rule_id = cursor.fetchone()[0]
                    logger.info(f"创建跟单配置规则: id={rule_id}, name={data.get('name')}")
                    return rule_id
        except Exception as e:
            logger.error(f"保存跟单配置规则失败: {e}")
            return None

    def delete_copy_config_rule(self, rule_id: int) -> bool:
        """
        删除跟单配置规则
        
        Args:
            rule_id: 规则ID
            
        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM copy_config_rules WHERE id = %s", (rule_id,))
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"删除跟单配置规则: id={rule_id}")
                return deleted
        except Exception as e:
            logger.error(f"删除跟单配置规则失败 (id={rule_id}): {e}")
            return False

    def match_copy_config_rule(self, config_type: str, leverage: float) -> Optional[Dict]:
        """
        根据杠杆匹配最合适的配置规则
        
        匹配逻辑：
        1. 按优先级排序，找到第一个杠杆区间匹配的启用规则
        2. 区间判断: leverage_min < leverage <= leverage_max
        3. 如果没有匹配的，返回 is_default=True 的规则
        4. 如果还是没有，返回 None
        
        Args:
            config_type: 配置类型 ('default' 或 'immediate')
            leverage: 杠杆倍数
            
        Returns:
            匹配的配置规则，或 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 先尝试匹配杠杆区间
                cursor.execute("""
                    SELECT id, config_type, name, description,
                           leverage_min, leverage_max, config_data,
                           priority, is_enabled, is_default
                    FROM copy_config_rules
                    WHERE config_type = %s 
                      AND is_enabled = TRUE
                      AND leverage_min < %s 
                      AND leverage_max >= %s
                    ORDER BY priority ASC, id ASC
                    LIMIT 1
                """, (config_type, leverage, leverage))
                
                row = cursor.fetchone()
                
                # 如果没有匹配的，尝试获取默认规则
                if not row:
                    cursor.execute("""
                        SELECT id, config_type, name, description,
                               leverage_min, leverage_max, config_data,
                               priority, is_enabled, is_default
                        FROM copy_config_rules
                        WHERE config_type = %s 
                          AND is_enabled = TRUE
                          AND is_default = TRUE
                        ORDER BY priority ASC
                        LIMIT 1
                    """, (config_type,))
                    row = cursor.fetchone()
                
                if row:
                    item = dict(row)
                    if item.get('config_data') and isinstance(item['config_data'], str):
                        item['config_data'] = json.loads(item['config_data'])
                    return item
                
                return None
        except Exception as e:
            logger.error(f"匹配跟单配置规则失败: {e}")
            return None

    def get_copy_config_by_leverage(self, config_type: str, leverage: float) -> Dict:
        """
        根据杠杆获取跟单配置（整合规则匹配和老配置兼容）
        
        优先使用规则匹配，如果没有规则则回退到老的单一配置
        
        Args:
            config_type: 配置类型 ('default' 或 'immediate')
            leverage: 杠杆倍数
            
        Returns:
            配置字典
        """
        # 先尝试匹配规则
        rule = self.match_copy_config_rule(config_type, leverage)
        
        if rule:
            config = rule.get('config_data', {})
            config['_matched_rule_id'] = rule.get('id')
            config['_matched_rule_name'] = rule.get('name')
            return config
        
        # 回退到老的单一配置
        if config_type == 'default':
            return self.get_default_copy_config()
        else:
            return self.get_immediate_copy_config()
