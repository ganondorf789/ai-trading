"""
交易记录管理模块 (PostgreSQL)
"""
from typing import List, Dict, Any, Optional
import pendulum
import re
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ
from screener.utils import calculate_trade_type
from utils import sanitize_float


class TraderFillsOps:
    """交易记录相关操作"""

    def _ensure_partition_exists(self, cursor, time_ms: int):
        """
        确保指定时间戳对应的分区存在（仅对分区表有效）
        
        Args:
            cursor: 数据库游标
            time_ms: 毫秒时间戳
        """
        try:
            # 检查是否是分区表
            cursor.execute("""
                SELECT 1 FROM pg_partitioned_table pt
                JOIN pg_class c ON pt.partrelid = c.oid
                WHERE c.relname = 'trader_fills'
            """)
            if not cursor.fetchone():
                return  # 不是分区表，无需创建分区
            
            # 计算分区名
            dt = pendulum.from_timestamp(time_ms / 1000, tz=SHANGHAI_TZ)
            partition_name = f"trader_fills_{dt.format('YYYY_MM')}"
            
            # 检查分区是否存在
            cursor.execute("""
                SELECT 1 FROM pg_class WHERE relname = %s
            """, (partition_name,))
            
            if not cursor.fetchone():
                # 创建分区
                start_ts = int(dt.start_of('month').timestamp() * 1000)
                end_ts = int(dt.add(months=1).start_of('month').timestamp() * 1000)
                
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {partition_name}
                    PARTITION OF trader_fills
                    FOR VALUES FROM ({start_ts}) TO ({end_ts})
                """)
                logger.info(f"自动创建分区: {partition_name}")
        except Exception as e:
            logger.debug(f"检查/创建分区失败（可能不是分区表）: {e}")

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
            
            # 检查是否是分区表，决定使用哪种 ON CONFLICT 语法
            cursor.execute("""
                SELECT 1 FROM pg_partitioned_table pt
                JOIN pg_class c ON pt.partrelid = c.oid
                WHERE c.relname = 'trader_fills'
            """)
            is_partitioned = cursor.fetchone() is not None

            for fill in fills:
                try:
                    time_ms = fill.get('time', 0)
                    trade_time = pendulum.from_timestamp(time_ms / 1000, tz=SHANGHAI_TZ).to_iso8601_string() if time_ms else None

                    # 计算交易类型
                    dir_val = fill.get('dir', '')
                    start_pos = float(fill.get('startPosition', 0)) if fill.get('startPosition') else 0
                    trade_type = calculate_trade_type(dir_val, start_pos)

                    # 确保分区存在
                    if is_partitioned and time_ms:
                        self._ensure_partition_exists(cursor, time_ms)

                    # 根据表类型选择 ON CONFLICT 语法
                    if is_partitioned:
                        # 分区表：唯一约束包含 time
                        cursor.execute("""
                            INSERT INTO trader_fills (
                                address, coin, side, px, sz, time, trade_time,
                                closed_pnl, hash, start_position, dir, crossed, fee, oid, tid, trade_type
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT(address, tid, time) DO UPDATE SET
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
                    else:
                        # 普通表：原有语法
                        cursor.execute("""
                            INSERT INTO trader_fills (
                                address, coin, side, px, sz, time, trade_time,
                                closed_pnl, hash, start_position, dir, crossed, fee, oid, tid, trade_type
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT(address, tid) DO UPDATE SET
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
            # trade_type: 1=OPEN_LONG, 2=ADD_LONG, 3=CLOSE_LONG, 4=OPEN_SHORT, 5=ADD_SHORT, 6=CLOSE_SHORT
            if trade_type:
                # 支持整数或字符串格式
                trade_type_map = {
                    'open_long': 1, 'add_long': 2, 'close_long': 3,
                    'open_short': 4, 'add_short': 5, 'close_short': 6
                }
                if isinstance(trade_type, str) and trade_type in trade_type_map:
                    conditions.append("trade_type = %s")
                    params.append(trade_type_map[trade_type])
                elif isinstance(trade_type, int) and 1 <= trade_type <= 6:
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

    def get_latest_fill(self, address: str) -> Optional[Dict]:
        """
        获取交易者最新的一条交易记录
        
        Args:
            address: 交易者地址
        
        Returns:
            最新的交易记录字典，如果没有记录则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_fills
                WHERE address = %s
                ORDER BY time DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            return dict(row) if row else None

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

    def get_fills_for_metrics(
        self,
        address: str,
        lookback_days: int = 0
    ) -> List[Dict[str, Any]]:
        """
        获取用于指标计算的交易记录（转换为 API 格式）

        Args:
            address: 交易者地址
            lookback_days: 回溯天数，0 表示获取所有记录

        Returns:
            API 格式的交易记录列表（按时间升序）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建查询条件
            conditions = ["address = %s"]
            params = [address]

            # 时间范围筛选
            if lookback_days > 0:
                start_dt = pendulum.now(SHANGHAI_TZ).subtract(days=lookback_days).start_of('day')
                start_timestamp_ms = int(start_dt.timestamp() * 1000)
                conditions.append("time >= %s")
                params.append(start_timestamp_ms)

            where_clause = " AND ".join(conditions)

            cursor.execute(f"""
                SELECT * FROM trader_fills
                WHERE {where_clause}
                ORDER BY time ASC
            """, params)

            rows = cursor.fetchall()

            # 转换为 API 格式（camelCase）
            api_fills = []
            for row in rows:
                api_fill = {
                    'time': row['time'],
                    'coin': row['coin'],
                    'px': row['px'],
                    'sz': row['sz'],
                    'side': row['side'],
                    'closedPnl': row['closed_pnl'] or 0,
                    'dir': row['dir'],
                    'startPosition': row['start_position'],
                    'hash': row['hash'],
                    'crossed': row['crossed'],
                    'fee': row['fee'] or 0,
                    'oid': row['oid'],
                    'tid': row['tid'],
                }
                api_fills.append(api_fill)

            return api_fills

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

    def get_high_frequency_windows(
        self,
        address: str = None,
        window_minutes: int = 2,
        threshold: int = 2000,
        lookback_days: int = 0
    ) -> List[Dict[str, Any]]:
        """
        查找高频时间段（指定时间窗口内 >= threshold 条记录）
        
        用于发现可能因 API 返回上限（2000条）而丢失数据的时间段。
        
        Args:
            address: 可选，指定交易者地址
            window_minutes: 时间窗口大小（分钟），默认 2
            threshold: 阈值，默认 2000
            lookback_days: 回溯天数，0 表示查询所有记录
        
        Returns:
            高频时间段列表，每项包含：
            - address: 交易者地址
            - window_start: 时间窗口开始时间（毫秒）
            - window_end: 时间窗口结束时间（毫秒）
            - fill_count: 记录数
        """
        window_ms = window_minutes * 60 * 1000  # 转换为毫秒
        
        # 构建时间条件
        time_condition = ""
        params = []
        
        if lookback_days > 0:
            start_dt = pendulum.now(SHANGHAI_TZ).subtract(days=lookback_days).start_of('day')
            start_timestamp_ms = int(start_dt.timestamp() * 1000)
            time_condition = " AND time >= %s"
            params.append(start_timestamp_ms)
        
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            if address:
                query = f"""
                    SELECT 
                        address,
                        (time / %s) * %s as window_start,
                        COUNT(*) as fill_count
                    FROM trader_fills
                    WHERE address = %s{time_condition}
                    GROUP BY address, (time / %s) * %s
                    HAVING COUNT(*) >= %s
                    ORDER BY fill_count DESC
                """
                query_params = [window_ms, window_ms, address] + params + [window_ms, window_ms, threshold]
                cursor.execute(query, query_params)
            else:
                if time_condition:
                    query = f"""
                        SELECT 
                            address,
                            (time / %s) * %s as window_start,
                            COUNT(*) as fill_count
                        FROM trader_fills
                        WHERE 1=1{time_condition}
                        GROUP BY address, (time / %s) * %s
                        HAVING COUNT(*) >= %s
                        ORDER BY fill_count DESC
                    """
                    query_params = [window_ms, window_ms] + params + [window_ms, window_ms, threshold]
                else:
                    query = """
                        SELECT 
                            address,
                            (time / %s) * %s as window_start,
                            COUNT(*) as fill_count
                        FROM trader_fills
                        GROUP BY address, (time / %s) * %s
                        HAVING COUNT(*) >= %s
                        ORDER BY fill_count DESC
                    """
                    query_params = [window_ms, window_ms, window_ms, window_ms, threshold]
                cursor.execute(query, query_params)
            
            results = []
            for row in cursor.fetchall():
                window_start = int(row['window_start'])
                results.append({
                    'address': row['address'],
                    'window_start': window_start,
                    'window_end': window_start + window_ms,
                    'fill_count': row['fill_count']
                })
            
            return results

    # ============= 数据库聚合下推方法 =============
    # 这些方法将计算下推到数据库，减少内存中的数据处理

    def get_fills_stats_aggregated(self, address: str) -> Optional[Dict[str, Any]]:
        """
        从数据库获取交易记录的聚合统计信息
        
        将统计计算下推到数据库，避免在内存中遍历大量数据。
        
        Args:
            address: 交易者地址
        
        Returns:
            聚合统计字典，包含：
            - fills_count: 总交易记录数
            - total_volume: 总交易量 (px * sz)
            - total_size_usd: 总交易规模
            - total_closed_pnl: 总已实现盈亏
            - total_fee: 总手续费
            - first_trade_time: 首次交易时间（毫秒）
            - last_trade_time: 最后交易时间（毫秒）
            - long_count: 做多交易数
            - short_count: 做空交易数
            - avg_price: 平均价格
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as fills_count,
                    COALESCE(SUM(px * sz), 0) as total_volume,
                    COALESCE(SUM(sz), 0) as total_size_usd,
                    COALESCE(SUM(closed_pnl), 0) as total_closed_pnl,
                    COALESCE(SUM(fee), 0) as total_fee,
                    MIN(time) as first_trade_time,
                    MAX(time) as last_trade_time,
                    SUM(CASE WHEN side = 'B' THEN 1 ELSE 0 END) as long_count,
                    SUM(CASE WHEN side = 'A' THEN 1 ELSE 0 END) as short_count,
                    COALESCE(AVG(px), 0) as avg_price
                FROM trader_fills
                WHERE address = %s
            """, (address,))
            
            row = cursor.fetchone()
            if not row or row['fills_count'] == 0:
                return None
            
            return {
                'fills_count': row['fills_count'],
                'total_volume': float(row['total_volume']),
                'total_size_usd': float(row['total_size_usd']),
                'total_closed_pnl': float(row['total_closed_pnl']),
                'total_fee': float(row['total_fee']),
                'first_trade_time': row['first_trade_time'],
                'last_trade_time': row['last_trade_time'],
                'long_count': row['long_count'],
                'short_count': row['short_count'],
                'avg_price': float(row['avg_price']),
            }

    def get_pnl_by_period(
        self,
        address: str,
        period: str = 'daily'
    ) -> Dict[str, float]:
        """
        按时间段聚合盈亏数据
        
        Args:
            address: 交易者地址
            period: 时间段类型 ('daily', 'weekly', 'monthly')
        
        Returns:
            {时间段键: 盈亏值} 字典
            - daily: 'YYYY-MM-DD' -> pnl
            - weekly: 'YYYY-WW' -> pnl
            - monthly: 'YYYY-MM' -> pnl
        """
        # 根据时间段类型选择 SQL 的日期截断方式
        if period == 'daily':
            date_format = "TO_CHAR(TO_TIMESTAMP(time / 1000) AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM-DD')"
        elif period == 'weekly':
            # ISO 周格式: YYYY-WW
            date_format = "TO_CHAR(TO_TIMESTAMP(time / 1000) AT TIME ZONE 'Asia/Shanghai', 'IYYY-IW')"
        elif period == 'monthly':
            date_format = "TO_CHAR(TO_TIMESTAMP(time / 1000) AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM')"
        else:
            raise ValueError(f"Unsupported period: {period}")
        
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            cursor.execute(f"""
                SELECT 
                    {date_format} as period_key,
                    COALESCE(SUM(closed_pnl), 0) as pnl
                FROM trader_fills
                WHERE address = %s
                GROUP BY {date_format}
                ORDER BY period_key
            """, (address,))
            
            result = {}
            for row in cursor.fetchall():
                if row['period_key']:
                    result[row['period_key']] = float(row['pnl'])
            
            return result

    def get_volume_by_period(
        self,
        address: str,
        period: str = 'daily'
    ) -> Dict[str, float]:
        """
        按时间段聚合交易量数据
        
        Args:
            address: 交易者地址
            period: 时间段类型 ('daily', 'weekly', 'monthly')
        
        Returns:
            {时间段键: 交易量} 字典
        """
        if period == 'daily':
            date_format = "TO_CHAR(TO_TIMESTAMP(time / 1000) AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM-DD')"
        elif period == 'weekly':
            date_format = "TO_CHAR(TO_TIMESTAMP(time / 1000) AT TIME ZONE 'Asia/Shanghai', 'IYYY-IW')"
        elif period == 'monthly':
            date_format = "TO_CHAR(TO_TIMESTAMP(time / 1000) AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM')"
        else:
            raise ValueError(f"Unsupported period: {period}")
        
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            cursor.execute(f"""
                SELECT 
                    {date_format} as period_key,
                    COALESCE(SUM(px * sz), 0) as volume
                FROM trader_fills
                WHERE address = %s
                GROUP BY {date_format}
                ORDER BY period_key
            """, (address,))
            
            result = {}
            for row in cursor.fetchall():
                if row['period_key']:
                    result[row['period_key']] = float(row['volume'])
            
            return result

    def get_symbol_stats(self, address: str) -> Dict[str, int]:
        """
        获取按币种统计的交易次数
        
        Args:
            address: 交易者地址
        
        Returns:
            {币种: 交易次数} 字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    coin,
                    COUNT(*) as count
                FROM trader_fills
                WHERE address = %s
                GROUP BY coin
                ORDER BY count DESC
            """, (address,))
            
            result = {}
            for row in cursor.fetchall():
                if row['coin']:
                    result[row['coin']] = row['count']
            
            return result

    def get_aggregated_fills_metrics(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取完整的数据库聚合指标，用于替代内存中的 fills 遍历
        
        这是一个综合方法，一次性获取所有需要的聚合数据。
        
        Args:
            address: 交易者地址
        
        Returns:
            完整的聚合指标字典，包含：
            - basic_stats: 基础统计（fills_count, volume, pnl 等）
            - daily_pnl: 按日聚合的盈亏
            - weekly_pnl: 按周聚合的盈亏
            - monthly_pnl: 按月聚合的盈亏
            - daily_volume: 按日聚合的交易量
            - weekly_volume: 按周聚合的交易量
            - monthly_volume: 按月聚合的交易量
            - symbol_counts: 按币种统计的交易次数
        """
        # 获取基础统计
        basic_stats = self.get_fills_stats_aggregated(address)
        if not basic_stats:
            return None
        
        # 获取时间段聚合数据
        daily_pnl = self.get_pnl_by_period(address, 'daily')
        weekly_pnl = self.get_pnl_by_period(address, 'weekly')
        monthly_pnl = self.get_pnl_by_period(address, 'monthly')
        
        daily_volume = self.get_volume_by_period(address, 'daily')
        weekly_volume = self.get_volume_by_period(address, 'weekly')
        monthly_volume = self.get_volume_by_period(address, 'monthly')
        
        # 获取币种统计
        symbol_counts = self.get_symbol_stats(address)
        
        return {
            'basic_stats': basic_stats,
            'daily_pnl': daily_pnl,
            'weekly_pnl': weekly_pnl,
            'monthly_pnl': monthly_pnl,
            'daily_volume': daily_volume,
            'weekly_volume': weekly_volume,
            'monthly_volume': monthly_volume,
            'symbol_counts': symbol_counts,
        }
