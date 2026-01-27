"""
新仓位记录模块 (PostgreSQL)
记录监控脚本检测到的新仓位
"""
from typing import List, Dict, Optional
from datetime import datetime
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class NewPositionsOps:
    """新仓位记录相关操作"""

    def save_new_position(
        self,
        trader_address: str,
        position: Dict,
        trader_name: Optional[str] = None,
        trader_rating: Optional[str] = None,
        trader_score: Optional[float] = None,
        notified: bool = False,
        target_is_starred: bool = False
    ) -> Optional[int]:
        """
        保存检测到的新仓位记录

        Args:
            trader_address: 交易员地址
            position: 仓位数据（包含 coin, szi, entry_px, leverage 等）
            trader_name: 交易员名称
            trader_rating: 交易员评级
            trader_score: 交易员评分
            notified: 是否已发送通知
            target_is_starred: 目标交易员是否被标记

        Returns:
            新记录的 ID，失败返回 None
        """
        try:
            coin = position.get('coin', '')
            szi = float(position.get('szi', 0) or 0)
            entry_px = float(position.get('entry_px', 0) or 0)
            position_value = abs(szi) * entry_px
            leverage = position.get('leverage', 1)
            if isinstance(leverage, dict):
                leverage = leverage.get('value', 1)
            leverage = int(leverage or 1)
            
            # 判断方向
            direction = 'long' if szi > 0 else 'short'
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO detected_new_positions (
                        trader_address, trader_name, trader_rating, trader_score,
                        coin, direction, szi, entry_px, position_value, leverage,
                        detected_at, notified, target_is_starred
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    trader_address,
                    trader_name or '',
                    trader_rating,
                    trader_score,
                    coin,
                    direction,
                    abs(szi),
                    entry_px,
                    position_value,
                    leverage,
                    pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
                    notified,
                    target_is_starred
                ))
                
                row = cursor.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"保存新仓位记录失败: {e}")
            return None

    def save_new_positions_batch(
        self,
        trader: Dict,
        positions: List[Dict],
        notified: bool = False,
        target_is_starred: bool = False
    ) -> int:
        """
        批量保存检测到的新仓位记录

        Args:
            trader: 交易员信息（包含 address, name, rating, overall_score）
            positions: 仓位列表
            notified: 是否已发送通知
            target_is_starred: 目标交易员是否被标记

        Returns:
            保存成功的记录数
        """
        if not positions:
            return 0

        trader_address = trader.get('address', '')
        trader_name = trader.get('name', '')
        trader_rating = trader.get('rating')
        trader_score = trader.get('overall_score')
        
        saved_count = 0
        for position in positions:
            result = self.save_new_position(
                trader_address=trader_address,
                position=position,
                trader_name=trader_name,
                trader_rating=trader_rating,
                trader_score=trader_score,
                notified=notified,
                target_is_starred=target_is_starred
            )
            if result:
                saved_count += 1
        
        return saved_count

    def get_new_positions(
        self,
        limit: int = 100,
        offset: int = 0,
        trader_address: Optional[str] = None,
        coin: Optional[str] = None,
        direction: Optional[str] = None,
        rating: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        查询新仓位记录

        Args:
            limit: 返回数量限制
            offset: 偏移量
            trader_address: 按交易员地址过滤
            coin: 按币种过滤
            direction: 按方向过滤 ('long' 或 'short')
            rating: 按评级过滤
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            新仓位记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # 构建查询条件
            conditions = []
            params = []
            
            if trader_address:
                conditions.append("trader_address = %s")
                params.append(trader_address)
            
            if coin:
                conditions.append("coin = %s")
                params.append(coin)
            
            if direction:
                conditions.append("direction = %s")
                params.append(direction)
            
            if rating:
                conditions.append("trader_rating = %s")
                params.append(rating)
            
            if start_time:
                conditions.append("detected_at >= %s")
                params.append(start_time)
            
            if end_time:
                conditions.append("detected_at <= %s")
                params.append(end_time)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT * FROM detected_new_positions
                WHERE {where_clause}
                ORDER BY detected_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_new_positions_cursor(
        self,
        limit: int = 50,
        before: Optional[int] = None,
        after: Optional[int] = None,
        trader_address: Optional[str] = None,
        coin: Optional[str] = None,
        direction: Optional[str] = None,
        rating: Optional[str] = None,
        min_position_value: Optional[float] = None,
        max_position_value: Optional[float] = None,
        min_leverage: Optional[int] = None,
        max_leverage: Optional[int] = None
    ) -> List[Dict]:
        """
        使用游标分页查询新仓位记录

        Args:
            limit: 返回数量限制
            before: 游标ID，获取此ID之前的记录（不包含此ID），为空则从最新记录开始
            after: 游标ID，获取此ID之后的记录（不包含此ID），用于获取更新的数据
            trader_address: 按交易员地址过滤
            coin: 按币种过滤
            direction: 按方向过滤 ('long' 或 'short')
            rating: 按评级过滤
            min_position_value: 最小仓位价值 (USD)
            max_position_value: 最大仓位价值 (USD)
            min_leverage: 最小杠杆
            max_leverage: 最大杠杆

        Returns:
            新仓位记录列表（按 id 降序排列）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # 构建查询条件
            conditions = []
            params = []
            
            # before 游标条件
            if before is not None:
                conditions.append("id < %s")
                params.append(before)
            
            # after 游标条件
            if after is not None:
                conditions.append("id > %s")
                params.append(after)
            
            if trader_address:
                conditions.append("trader_address = %s")
                params.append(trader_address)
            
            if coin:
                conditions.append("coin = %s")
                params.append(coin)
            
            if direction:
                conditions.append("direction = %s")
                params.append(direction)
            
            if rating:
                conditions.append("trader_rating = %s")
                params.append(rating)
            
            # 仓位价值筛选
            if min_position_value is not None:
                conditions.append("position_value >= %s")
                params.append(min_position_value)
            
            if max_position_value is not None:
                conditions.append("position_value <= %s")
                params.append(max_position_value)
            
            # 杠杆筛选
            if min_leverage is not None:
                conditions.append("leverage >= %s")
                params.append(min_leverage)
            
            if max_leverage is not None:
                conditions.append("leverage <= %s")
                params.append(max_leverage)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 使用 after 时，先按 ASC 排序取最早的 N 条，然后反转为 DESC
            if after is not None and before is None:
                query = f"""
                    SELECT * FROM (
                        SELECT * FROM detected_new_positions
                        WHERE {where_clause}
                        ORDER BY id ASC
                        LIMIT %s
                    ) sub ORDER BY id DESC
                """
            else:
                query = f"""
                    SELECT * FROM detected_new_positions
                    WHERE {where_clause}
                    ORDER BY id DESC
                    LIMIT %s
                """
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_new_positions_count(
        self,
        trader_address: Optional[str] = None,
        coin: Optional[str] = None,
        direction: Optional[str] = None,
        rating: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        查询新仓位记录数量

        Args:
            trader_address: 按交易员地址过滤
            coin: 按币种过滤
            direction: 按方向过滤
            rating: 按评级过滤
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            记录数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if trader_address:
                conditions.append("trader_address = %s")
                params.append(trader_address)
            
            if coin:
                conditions.append("coin = %s")
                params.append(coin)
            
            if direction:
                conditions.append("direction = %s")
                params.append(direction)
            
            if rating:
                conditions.append("trader_rating = %s")
                params.append(rating)
            
            if start_time:
                conditions.append("detected_at >= %s")
                params.append(start_time)
            
            if end_time:
                conditions.append("detected_at <= %s")
                params.append(end_time)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT COUNT(*) FROM detected_new_positions
                WHERE {where_clause}
            """
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row[0] if row else 0

    def get_recent_new_positions_by_coin(
        self,
        minutes: int = 60,
        min_count: int = 1
    ) -> List[Dict]:
        """
        获取最近一段时间内各币种的新仓位统计

        Args:
            minutes: 时间范围（分钟）
            min_count: 最小数量过滤

        Returns:
            币种统计列表 [{coin, count, long_count, short_count, avg_score, traders}]
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    coin,
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE direction = 'long') as long_count,
                    COUNT(*) FILTER (WHERE direction = 'short') as short_count,
                    AVG(trader_score) as avg_score,
                    ARRAY_AGG(DISTINCT trader_address) as traders
                FROM detected_new_positions
                WHERE detected_at >= NOW() - INTERVAL '%s minutes'
                GROUP BY coin
                HAVING COUNT(*) >= %s
                ORDER BY total_count DESC
            """, (minutes, min_count))
            
            return [dict(row) for row in cursor.fetchall()]

    def get_new_positions_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        获取新仓位统计信息

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # 构建时间条件
            time_conditions = []
            params = []
            
            if start_time:
                time_conditions.append("detected_at >= %s")
                params.append(start_time)
            
            if end_time:
                time_conditions.append("detected_at <= %s")
                params.append(end_time)
            
            where_clause = " AND ".join(time_conditions) if time_conditions else "1=1"
            
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE direction = 'long') as long_count,
                    COUNT(*) FILTER (WHERE direction = 'short') as short_count,
                    COUNT(DISTINCT trader_address) as unique_traders,
                    COUNT(DISTINCT coin) as unique_coins,
                    AVG(position_value) as avg_position_value,
                    SUM(position_value) as total_position_value,
                    AVG(trader_score) as avg_trader_score,
                    MIN(detected_at) as first_detected_at,
                    MAX(detected_at) as last_detected_at
                FROM detected_new_positions
                WHERE {where_clause}
            """, params)
            
            row = cursor.fetchone()
            return dict(row) if row else {}

    def delete_old_new_positions(self, days: int = 30) -> int:
        """
        删除超过指定天数的旧记录

        Args:
            days: 保留的天数

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM detected_new_positions
                WHERE detected_at < NOW() - INTERVAL '%s days'
            """, (days,))
            return cursor.rowcount
