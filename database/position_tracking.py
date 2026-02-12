"""
仓位级别跟单管理模块 (PostgreSQL)
第二种跟单模式：跟单特定交易员的特定仓位
"""
from typing import List, Dict, Optional, Tuple
import pendulum
import json
from ulid import ULID
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class PositionTrackingOps:
    """仓位级别跟单相关操作"""

    # ==================== 仓位跟单管理 ====================

    def get_position_trackings(
        self,
        status: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        target_address: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        获取仓位跟单列表

        Args:
            status: 状态筛选 (pending/active/closed/stopped)
            is_enabled: 启用状态筛选
            target_address: 目标交易员筛选
            symbol: 币种筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            (跟单列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建查询条件
            conditions = []
            params = []

            if status is not None:
                conditions.append("status = %s")
                params.append(status)

            if is_enabled is not None:
                conditions.append("is_enabled = %s")
                params.append(is_enabled)

            if target_address is not None:
                conditions.append("target_address = %s")
                params.append(target_address)

            if symbol is not None:
                conditions.append("symbol = %s")
                params.append(symbol)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM copy_position_tracking
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()['count']

            # 查询数据
            cursor.execute(f"""
                SELECT cpt.*,
                       tm.display_name as target_display_name
                FROM copy_position_tracking cpt
                LEFT JOIN trader_metrics tm ON cpt.target_address = tm.address
                WHERE {where_clause}
                ORDER BY cpt.updated_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])

            results = [dict(row) for row in cursor.fetchall()]
            return results, total_count

    def get_active_position_trackings(self) -> List[Dict]:
        """
        获取所有启用且活跃的仓位跟单配置

        Returns:
            启用的跟单配置列表（status 为 pending 或 active），包含交易员评分信息
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT cpt.*,
                       COALESCE(cpt.target_score, tm.overall_score) AS target_score,
                       COALESCE(cpt.target_rating, tm.rating) AS target_rating
                FROM copy_position_tracking cpt
                LEFT JOIN trader_metrics tm ON cpt.target_address = tm.address
                WHERE cpt.is_enabled = TRUE AND cpt.status IN ('pending', 'active')
                ORDER BY cpt.updated_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_position_tracking(self, tracking_id: str) -> Optional[Dict]:
        """
        获取单个仓位跟单详情

        Args:
            tracking_id: 跟单记录ID（ULID字符串）

        Returns:
            跟单详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM copy_position_tracking
                WHERE id = %s
            """, (tracking_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_position_tracking_by_target(
        self,
        target_address: str,
        symbol: str,
        active_only: bool = True
    ) -> Optional[Dict]:
        """
        按目标地址和币种查询跟单记录

        Args:
            target_address: 目标交易员地址
            symbol: 币种
            active_only: 是否只查询活跃记录

        Returns:
            跟单记录
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if active_only:
                cursor.execute("""
                    SELECT * FROM copy_position_tracking
                    WHERE target_address = %s AND symbol = %s
                    AND status IN ('pending', 'active')
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (target_address, symbol))
            else:
                cursor.execute("""
                    SELECT * FROM copy_position_tracking
                    WHERE target_address = %s AND symbol = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (target_address, symbol))

            row = cursor.fetchone()
            return dict(row) if row else None

    def save_position_tracking(self, data: Dict) -> str:
        """
        创建或更新仓位跟单记录

        Args:
            data: 跟单数据

        Returns:
            记录ID（ULID字符串）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            if data.get('id'):
                # 更新现有记录
                cursor.execute("""
                    UPDATE copy_position_tracking
                    SET target_name = %s,
                        is_enabled = %s,
                        copy_ratio = %s,
                        max_position_size_usd = %s,
                        min_position_size_usd = %s,
                        copy_leverage = %s,
                        max_leverage = %s,
                        default_leverage = %s,
                        slippage = %s,
                        auto_replenish = %s,
                        replenish_ratio = %s,
                        replenish_min_value_usd = %s,
                        replenish_max_value_usd = %s,
                        target_initial_size = %s,
                        target_initial_side = %s,
                        target_initial_entry_price = %s,
                        target_initial_leverage = %s,
                        my_size = %s,
                        my_side = %s,
                        my_entry_price = %s,
                        status = %s,
                        closed_pnl = %s,
                        close_reason = %s,
                        started_at = %s,
                        closed_at = %s,
                        target_is_starred = %s,
                        target_score = %s,
                        target_rating = %s,
                        position_mode = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING id
                """, (
                    data.get('target_name', ''),
                    data.get('is_enabled', True),
                    data.get('copy_ratio', 0.1),
                    data.get('max_position_size_usd', 500.0),
                    data.get('min_position_size_usd', 20.0),
                    data.get('copy_leverage', True),
                    data.get('max_leverage', 10),
                    data.get('default_leverage', 5),
                    data.get('slippage', 0.01),
                    data.get('auto_replenish', False),
                    data.get('replenish_ratio', 0.5),
                    data.get('replenish_min_value_usd', 10.0),
                    data.get('replenish_max_value_usd', 100.0),
                    data.get('target_initial_size'),
                    data.get('target_initial_side'),
                    data.get('target_initial_entry_price'),
                    data.get('target_initial_leverage'),
                    data.get('my_size', 0.0),
                    data.get('my_side'),
                    data.get('my_entry_price'),
                    data.get('status', 'pending'),
                    data.get('closed_pnl'),
                    data.get('close_reason'),
                    data.get('started_at'),
                    data.get('closed_at'),
                    data.get('target_is_starred', False),
                    data.get('target_score'),
                    data.get('target_rating'),
                    data.get('position_mode', 'cross'),
                    now,
                    data['id']
                ))
                return data['id']
            else:
                # 生成 ULID 作为主键
                tracking_id = str(ULID())
                
                # 创建新记录
                cursor.execute("""
                    INSERT INTO copy_position_tracking (
                        id,
                        target_address, target_name, symbol,
                        is_enabled, copy_ratio, max_position_size_usd, min_position_size_usd,
                        copy_leverage, max_leverage, default_leverage, slippage,
                        auto_replenish, replenish_ratio, replenish_min_value_usd, replenish_max_value_usd,
                        target_initial_size, target_initial_side, target_initial_entry_price, target_initial_leverage,
                        my_size, my_side, my_entry_price,
                        status, closed_pnl, close_reason,
                        target_is_starred, target_score, target_rating,
                        position_mode,
                        created_at, started_at, closed_at, updated_at
                    ) VALUES (
                        %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s,
                        %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    tracking_id,
                    data.get('target_address'),
                    data.get('target_name', ''),
                    data.get('symbol'),
                    data.get('is_enabled', True),
                    data.get('copy_ratio', 0.1),
                    data.get('max_position_size_usd', 500.0),
                    data.get('min_position_size_usd', 20.0),
                    data.get('copy_leverage', True),
                    data.get('max_leverage', 10),
                    data.get('default_leverage', 5),
                    data.get('slippage', 0.01),
                    data.get('auto_replenish', False),
                    data.get('replenish_ratio', 0.5),
                    data.get('replenish_min_value_usd', 10.0),
                    data.get('replenish_max_value_usd', 100.0),
                    data.get('target_initial_size'),
                    data.get('target_initial_side'),
                    data.get('target_initial_entry_price'),
                    data.get('target_initial_leverage'),
                    data.get('my_size', 0.0),
                    data.get('my_side'),
                    data.get('my_entry_price'),
                    data.get('status', 'pending'),
                    data.get('closed_pnl'),
                    data.get('close_reason'),
                    data.get('target_is_starred', False),
                    data.get('target_score'),
                    data.get('target_rating'),
                    data.get('position_mode', 'cross'),
                    now,
                    data.get('started_at'),
                    data.get('closed_at'),
                    now
                ))
                result = cursor.fetchone()
                return result[0] if result else None

    def update_tracking_status(
        self,
        tracking_id: str,
        status: str,
        close_reason: Optional[str] = None,
        closed_pnl: Optional[float] = None
    ) -> bool:
        """
        更新跟单状态

        Args:
            tracking_id: 跟单记录ID（ULID字符串）
            status: 新状态 (pending/active/closed/stopped)
            close_reason: 关闭原因
            closed_pnl: 平仓盈亏

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            # 根据状态设置时间字段
            if status == 'active':
                cursor.execute("""
                    UPDATE copy_position_tracking
                    SET status = %s, started_at = %s, updated_at = %s
                    WHERE id = %s
                """, (status, now, now, tracking_id))
            elif status in ('closed', 'stopped'):
                cursor.execute("""
                    UPDATE copy_position_tracking
                    SET status = %s, close_reason = %s, closed_pnl = %s,
                        closed_at = %s, updated_at = %s
                    WHERE id = %s
                """, (status, close_reason, closed_pnl, now, now, tracking_id))
            else:
                cursor.execute("""
                    UPDATE copy_position_tracking
                    SET status = %s, updated_at = %s
                    WHERE id = %s
                """, (status, now, tracking_id))

            return cursor.rowcount > 0

    def update_tracking_position(
        self,
        tracking_id: str,
        my_size: float,
        my_side: str,
        my_entry_price: Optional[float] = None
    ) -> bool:
        """
        更新跟单仓位信息

        Args:
            tracking_id: 跟单记录ID（ULID字符串）
            my_size: 我方仓位大小
            my_side: 我方仓位方向
            my_entry_price: 我方入场价

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            cursor.execute("""
                UPDATE copy_position_tracking
                SET my_size = %s, my_side = %s, my_entry_price = %s, updated_at = %s
                WHERE id = %s
            """, (my_size, my_side, my_entry_price, now, tracking_id))

            return cursor.rowcount > 0

    def toggle_position_tracking(self, tracking_id: str, is_enabled: bool) -> bool:
        """
        启用/禁用仓位跟单

        Args:
            tracking_id: 跟单记录ID
            is_enabled: 是否启用

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            cursor.execute("""
                UPDATE copy_position_tracking
                SET is_enabled = %s, updated_at = %s
                WHERE id = %s
            """, (is_enabled, now, tracking_id))

            return cursor.rowcount > 0

    def delete_position_tracking(self, tracking_id: str) -> bool:
        """
        删除仓位跟单记录

        Args:
            tracking_id: 跟单记录ID

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM copy_position_tracking WHERE id = %s",
                (tracking_id,)
            )
            return cursor.rowcount > 0

    def get_position_tracking_stats(self) -> Dict:
        """
        获取仓位跟单统计信息

        Returns:
            统计数据
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                    COUNT(*) FILTER (WHERE status = 'active') as active_count,
                    COUNT(*) FILTER (WHERE status = 'closed') as closed_count,
                    COUNT(*) FILTER (WHERE status = 'stopped') as stopped_count,
                    COUNT(*) FILTER (WHERE is_enabled = TRUE AND status IN ('pending', 'active')) as enabled_count,
                    COUNT(DISTINCT target_address) as unique_traders,
                    COUNT(DISTINCT symbol) as unique_symbols,
                    COALESCE(SUM(closed_pnl) FILTER (WHERE status = 'closed'), 0) as total_closed_pnl
                FROM copy_position_tracking
            """)

            row = cursor.fetchone()
            return dict(row) if row else {
                'total_count': 0,
                'pending_count': 0,
                'active_count': 0,
                'closed_count': 0,
                'stopped_count': 0,
                'enabled_count': 0,
                'unique_traders': 0,
                'unique_symbols': 0,
                'total_closed_pnl': 0
            }

    def check_position_tracking_exists(
        self,
        target_address: str,
        symbol: str
    ) -> bool:
        """
        检查是否已存在活跃的仓位跟单

        Args:
            target_address: 目标交易员地址
            symbol: 币种

        Returns:
            是否存在
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM copy_position_tracking
                WHERE target_address = %s AND symbol = %s
                AND status IN ('pending', 'active')
                LIMIT 1
            """, (target_address, symbol))
            return cursor.fetchone() is not None
