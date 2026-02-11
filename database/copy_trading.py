"""
跟单地址管理模块 (PostgreSQL)
"""
from typing import List, Dict, Optional
import pendulum
import json
from ulid import ULID
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class CopyTradingOps:
    """跟单地址管理相关操作"""

    # ==================== 跟单地址管理 ====================

    def get_copy_trading_addresses(
        self,
        user_id: str,
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
            user_id: 用户ID
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
            conditions = ["cta.user_id = %s"]
            params = [user_id]

            if is_enabled is not None:
                conditions.append("cta.is_enabled = %s")
                params.append(is_enabled)

            if search:
                conditions.append("(cta.address ILIKE %s OR cta.name ILIKE %s)")
                params.extend([f'%{search}%', f'%{search}%'])

            where_clause = " AND ".join(conditions)

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
                    tm.display_name,
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
                results.append(item)

            return results, total_count

    def get_copy_trading_address(self, user_id: str, address: str) -> Optional[Dict]:
        """
        获取单个跟单地址详情

        Args:
            user_id: 用户ID
            address: 交易者地址

        Returns:
            地址详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT
                    cta.*,
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
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE cta.user_id = %s AND cta.address = %s
            """, (user_id, address,))
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

    def save_copy_trading_address(self, user_id: str, data: Dict) -> str:
        """
        保存或更新跟单地址

        Args:
            user_id: 用户ID
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

            # 生成 ULID 作为主键（仅用于新记录，ON CONFLICT 更新时不会修改）
            address_id = str(ULID())
            
            cursor.execute("""
                INSERT INTO copy_trading_addresses (
                    id, user_id, address, name, is_enabled,
                    copy_ratio, max_position_size_usd, min_position_size_usd,
                    copy_leverage, max_leverage, default_leverage,
                    max_total_positions, max_daily_trades, slippage,
                    symbols_whitelist, symbols_blacklist,
                    check_interval, dry_run,
                    copy_once,
                    auto_replenish, replenish_ratio, replenish_min_value_usd, replenish_max_value_usd,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(user_id, address) DO UPDATE SET
                    name = EXCLUDED.name,
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
                    copy_once = EXCLUDED.copy_once,
                    auto_replenish = EXCLUDED.auto_replenish,
                    replenish_ratio = EXCLUDED.replenish_ratio,
                    replenish_min_value_usd = EXCLUDED.replenish_min_value_usd,
                    replenish_max_value_usd = EXCLUDED.replenish_max_value_usd,
                    updated_at = EXCLUDED.updated_at
                RETURNING id
            """, (
                address_id,
                user_id,
                data.get('address'),
                data.get('name', ''),
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
                data.get('copy_once', False),
                data.get('auto_replenish', False),
                data.get('replenish_ratio', 0.5),
                data.get('replenish_min_value_usd', 10.0),
                data.get('replenish_max_value_usd', 100.0),
                pendulum.now(SHANGHAI_TZ).to_iso8601_string()
            ))

            result = cursor.fetchone()
            return result[0] if result else None

    def delete_copy_trading_address(self, user_id: str, address: str) -> bool:
        """
        删除跟单地址

        Args:
            user_id: 用户ID
            address: 交易者地址

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM copy_trading_addresses WHERE user_id = %s AND address = %s",
                (user_id, address,)
            )
            return cursor.rowcount > 0

    def toggle_copy_trading_address(self, user_id: str, address: str, is_enabled: bool) -> bool:
        """
        启用/禁用跟单地址

        Args:
            user_id: 用户ID
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
                WHERE user_id = %s AND address = %s
            """, (is_enabled, pendulum.now(SHANGHAI_TZ).to_iso8601_string(), user_id, address))
            return cursor.rowcount > 0

    def batch_update_copy_trading_addresses(
        self,
        user_id: str,
        addresses: List[str],
        action: str
    ) -> int:
        """
        批量操作跟单地址

        Args:
            user_id: 用户ID
            addresses: 地址列表
            action: 操作类型 (enable/disable/delete)

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
                    WHERE user_id = %s AND address = ANY(%s)
                """, (now, user_id, addresses))
            elif action == 'disable':
                cursor.execute("""
                    UPDATE copy_trading_addresses
                    SET is_enabled = FALSE, updated_at = %s
                    WHERE user_id = %s AND address = ANY(%s)
                """, (now, user_id, addresses))
            elif action == 'delete':
                cursor.execute("""
                    DELETE FROM copy_trading_addresses
                    WHERE user_id = %s AND address = ANY(%s)
                """, (user_id, addresses,))
            else:
                return 0

            return cursor.rowcount

    def get_enabled_copy_addresses(self, user_id: str) -> List[Dict]:
        """
        获取所有启用的跟单地址及其完整配置

        Args:
            user_id: 用户ID

        Returns:
            启用的跟单地址配置列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE user_id = %s AND is_enabled = TRUE
                ORDER BY updated_at DESC
            """, (user_id,))

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

    def get_copy_address_config(self, user_id: str, address: str) -> Optional[Dict]:
        """
        获取单个跟单地址的完整配置

        Args:
            user_id: 用户ID
            address: 交易者地址

        Returns:
            配置字典，如果不存在则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE user_id = %s AND address = %s
            """, (user_id, address,))

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

    # ==================== 默认跟单配置管理 ====================

    def get_default_copy_config(self, user_id: str) -> Dict:
        """
        获取默认跟单配置
        
        Args:
            user_id: 用户ID
        
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
            'dry_run': False,
            'copy_once': False,
            'symbols_whitelist': [],
            'symbols_blacklist': [],
            'auto_replenish': False,
            'replenish_ratio': 0.5,
            'replenish_min_value_usd': 10.0,
            'replenish_max_value_usd': 100.0,
        }
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                config_key = f'default_copy_config:{user_id}'
                cursor.execute("""
                    SELECT config_value FROM system_config WHERE config_key = %s
                """, (config_key,))
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

    def save_default_copy_config(self, user_id: str, config: Dict) -> bool:
        """
        保存默认跟单配置
        
        Args:
            user_id: 用户ID
            config: 默认跟单配置字典
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                config_key = f'default_copy_config:{user_id}'
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description, updated_at)
                    VALUES (%s, %s, '默认跟单配置', CURRENT_TIMESTAMP)
                    ON CONFLICT (config_key)
                    DO UPDATE SET config_value = %s, updated_at = CURRENT_TIMESTAMP
                """, (config_key, json.dumps(config), json.dumps(config)))
            logger.info(f"用户 {user_id} 默认跟单配置已保存: {config}")
            return True
        except Exception as e:
            logger.error(f"保存默认跟单配置失败: {e}")
            return False

    # ==================== 立即跟单配置管理 ====================

    def get_immediate_copy_config(self, user_id: str) -> Dict:
        """
        获取立即跟单配置
        
        Args:
            user_id: 用户ID
        
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
                config_key = f'immediate_copy_config:{user_id}'
                cursor.execute("""
                    SELECT config_value FROM system_config WHERE config_key = %s
                """, (config_key,))
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

    def save_immediate_copy_config(self, user_id: str, config: Dict) -> bool:
        """
        保存立即跟单配置
        
        Args:
            user_id: 用户ID
            config: 立即跟单配置字典
            
        Returns:
            是否保存成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                config_key = f'immediate_copy_config:{user_id}'
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value, description, updated_at)
                    VALUES (%s, %s, '立即跟单配置', CURRENT_TIMESTAMP)
                    ON CONFLICT (config_key)
                    DO UPDATE SET config_value = %s, updated_at = CURRENT_TIMESTAMP
                """, (config_key, json.dumps(config), json.dumps(config)))
            logger.info(f"用户 {user_id} 立即跟单配置已保存: {config}")
            return True
        except Exception as e:
            logger.error(f"保存立即跟单配置失败: {e}")
            return False

    # ==================== 跟单配置规则管理（多配置支持） ====================

    def get_copy_config_rules(self, user_id: str, config_type: str, enabled_only: bool = False) -> List[Dict]:
        """
        获取跟单配置规则列表
        
        Args:
            user_id: 用户ID
            config_type: 配置类型 ('default' 或 'immediate')
            enabled_only: 是否只返回启用的规则
            
        Returns:
            配置规则列表，按优先级/币种排序
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                sql = """
                    SELECT id, config_type, name, description, 
                           leverage_min, leverage_max, config_data,
                           priority, is_enabled, is_default, symbol,
                           created_at, updated_at
                    FROM copy_config_rules
                    WHERE user_id = %s AND config_type = %s
                """
                params = [user_id, config_type]
                
                if enabled_only:
                    sql += " AND is_enabled = TRUE"
                
                # 立即跟单按币种排序，默认跟单按优先级排序
                if config_type == 'immediate':
                    sql += " ORDER BY symbol ASC, id ASC"
                else:
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

    def get_copy_config_rule_by_id(self, user_id: str, rule_id: str) -> Optional[Dict]:
        """
        根据ID获取单个配置规则
        
        Args:
            user_id: 用户ID
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
                           priority, is_enabled, is_default, symbol,
                           created_at, updated_at
                    FROM copy_config_rules
                    WHERE user_id = %s AND id = %s
                """, (user_id, rule_id,))
                
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

    def get_immediate_config_rule_by_symbol(self, user_id: str, symbol: str) -> Optional[Dict]:
        """
        根据币种获取立即跟单配置规则（每个币种最多一个配置）
        
        Args:
            user_id: 用户ID
            symbol: 币种名称
            
        Returns:
            配置规则字典或 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                cursor.execute("""
                    SELECT id, config_type, name, description,
                           leverage_min, leverage_max, config_data,
                           priority, is_enabled, is_default, symbol,
                           created_at, updated_at
                    FROM copy_config_rules
                    WHERE user_id = %s AND config_type = 'immediate' AND symbol = %s
                    LIMIT 1
                """, (user_id, symbol.upper(),))
                
                row = cursor.fetchone()
                if row:
                    item = dict(row)
                    if item.get('config_data') and isinstance(item['config_data'], str):
                        item['config_data'] = json.loads(item['config_data'])
                    return item
                return None
        except Exception as e:
            logger.error(f"获取立即跟单配置规则失败 (symbol={symbol}): {e}")
            return None

    def save_copy_config_rule(self, user_id: str, data: Dict) -> Optional[str]:
        """
        保存或更新跟单配置规则
        
        Args:
            user_id: 用户ULID
            data: 规则数据，包含 config_type, name, leverage_min, leverage_max, config_data, symbol 等
            
        Returns:
            规则ID (ULID)，失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                config_data = data.get('config_data', {})
                if isinstance(config_data, dict):
                    config_data = json.dumps(config_data)
                
                if data.get('id'):
                    # 更新（只能更新自己的规则）
                    cursor.execute("""
                        UPDATE copy_config_rules
                        SET name = %s, description = %s,
                            leverage_min = %s, leverage_max = %s,
                            config_data = %s, priority = %s,
                            is_enabled = %s, is_default = %s, symbol = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND id = %s
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
                        data.get('symbol'),
                        user_id,
                        data['id']
                    ))
                    result = cursor.fetchone()
                    logger.info(f"用户 {user_id} 更新跟单配置规则: id={data['id']}, name={data.get('name')}, symbol={data.get('symbol')}")
                    return result[0] if result else None
                else:
                    # 插入
                    rule_id = str(ULID())
                    cursor.execute("""
                        INSERT INTO copy_config_rules 
                        (id, user_id, config_type, name, description, leverage_min, leverage_max, 
                         config_data, priority, is_enabled, is_default, symbol)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        rule_id,
                        user_id,
                        data.get('config_type', 'default'),
                        data.get('name', ''),
                        data.get('description', ''),
                        data.get('leverage_min', 0),
                        data.get('leverage_max', 100),
                        config_data,
                        data.get('priority', 0),
                        data.get('is_enabled', True),
                        data.get('is_default', False),
                        data.get('symbol')
                    ))
                    rule_id = cursor.fetchone()[0]
                    logger.info(f"用户 {user_id} 创建跟单配置规则: id={rule_id}, name={data.get('name')}, symbol={data.get('symbol')}")
                    return rule_id
        except Exception as e:
            logger.error(f"保存跟单配置规则失败: {e}")
            return None

    def toggle_config_rule_enabled(self, rule_id: str, is_enabled: bool) -> bool:
        """
        启用/禁用跟单配置规则

        Args:
            rule_id: 规则ID
            is_enabled: 是否启用

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE copy_config_rules
                    SET is_enabled = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                """, (is_enabled, rule_id))
                row = cursor.fetchone()
                if row:
                    logger.info(f"跟单配置规则 id={rule_id} is_enabled -> {is_enabled}")
                    return True
                return False
        except Exception as e:
            logger.error(f"切换跟单配置规则状态失败 (id={rule_id}): {e}")
            return False

    def delete_copy_config_rule(self, user_id: str, rule_id: str) -> bool:
        """
        删除跟单配置规则
        
        Args:
            user_id: 用户ID
            rule_id: 规则ID
            
        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM copy_config_rules WHERE user_id = %s AND id = %s", (user_id, rule_id,))
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.info(f"用户 {user_id} 删除跟单配置规则: id={rule_id}")
                return deleted
        except Exception as e:
            logger.error(f"删除跟单配置规则失败 (id={rule_id}): {e}")
            return False

    def match_copy_config_rule(self, user_id: str, config_type: str, leverage: float) -> Optional[Dict]:
        """
        根据杠杆匹配最合适的配置规则
        
        匹配逻辑：
        1. 按优先级排序，找到第一个杠杆区间匹配的启用规则
        2. 区间判断: leverage_min < leverage <= leverage_max
        3. 如果没有匹配的，返回 is_default=True 的规则
        4. 如果还是没有，返回 None
        
        Args:
            user_id: 用户ID
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
                    WHERE user_id = %s AND config_type = %s 
                      AND is_enabled = TRUE
                      AND leverage_min < %s 
                      AND leverage_max >= %s
                    ORDER BY priority ASC, id ASC
                    LIMIT 1
                """, (user_id, config_type, leverage, leverage))
                
                row = cursor.fetchone()
                
                # 如果没有匹配的，尝试获取默认规则
                if not row:
                    cursor.execute("""
                        SELECT id, config_type, name, description,
                               leverage_min, leverage_max, config_data,
                               priority, is_enabled, is_default
                        FROM copy_config_rules
                        WHERE user_id = %s AND config_type = %s 
                          AND is_enabled = TRUE
                          AND is_default = TRUE
                        ORDER BY priority ASC
                        LIMIT 1
                    """, (user_id, config_type,))
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

    def get_all_immediate_configs_for_symbol(self, symbol: str) -> List[Dict]:
        """
        获取所有用户中匹配指定币种的立即跟单配置
        
        用于监控脚本：遍历所有用户的立即跟单规则，返回匹配的配置列表。
        
        Args:
            symbol: 币种名称
            
        Returns:
            匹配的配置列表，每条包含 _user_id 和配置参数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                cursor.execute("""
                    SELECT id, user_id, config_type, name, description,
                           leverage_min, leverage_max, config_data,
                           priority, is_enabled, is_default, symbol,
                           created_at, updated_at
                    FROM copy_config_rules
                    WHERE config_type = 'immediate'
                      AND symbol = %s
                      AND is_enabled = TRUE
                      AND user_id IS NOT NULL
                    ORDER BY user_id, priority ASC
                """, (symbol.upper(),))
                
                results = []
                for row in cursor.fetchall():
                    item = dict(row)
                    # 解析 JSON 数据
                    if item.get('config_data'):
                        if isinstance(item['config_data'], str):
                            item['config_data'] = json.loads(item['config_data'])
                    # 展开 config_data 为顶层字段，方便使用
                    config = item.get('config_data', {})
                    config['_matched_rule_name'] = item.get('name')
                    config['_matched_rule_id'] = item.get('id')
                    config['_matched_symbol'] = item.get('symbol')
                    config['_user_id'] = item.get('user_id')
                    results.append(config)
                
                return results
        except Exception as e:
            logger.error(f"获取所有用户立即跟单配置失败 (symbol={symbol}): {e}")
            return []

    def get_immediate_config_by_symbol(self, user_id: str, symbol: str) -> Dict:
        """
        根据币种获取立即跟单配置
        
        Args:
            user_id: 用户ID
            symbol: 币种名称
            
        Returns:
            配置字典，如果没有匹配规则则返回空字典
        """
        rule = self.get_immediate_config_rule_by_symbol(user_id, symbol)
        
        if rule and rule.get('is_enabled'):
            config = rule.get('config_data', {})
            config['_matched_rule_name'] = rule.get('name')
            config['_matched_rule_id'] = rule.get('id')
            config['_matched_symbol'] = rule.get('symbol')
            return config
        
        return {}

    def get_copy_config_by_leverage(self, user_id: str, config_type: str, leverage: float) -> Dict:
        """
        根据杠杆获取跟单配置（仅用于默认跟单）
        
        Args:
            user_id: 用户ID
            config_type: 配置类型 ('default' 或 'immediate')
            leverage: 杠杆倍数
            
        Returns:
            配置字典，如果没有匹配规则则返回空字典
        """
        rule = self.match_copy_config_rule(user_id, config_type, leverage)
        
        if rule:
            config = rule.get('config_data', {})
            config['_matched_rule_id'] = rule.get('id')
            config['_matched_rule_name'] = rule.get('name')
            return config
        
        return {}
