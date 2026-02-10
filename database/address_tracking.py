"""
地址跟踪管理模块 (PostgreSQL)
用于跟踪特定地址的交易活动并发送通知
"""
from typing import List, Dict, Optional, Tuple
import pendulum
import json
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class AddressTrackingOps:
    """地址跟踪管理相关操作"""

    # ==================== 地址跟踪管理 ====================

    def get_address_trackings(
        self,
        user_id: int,
        is_enabled: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        获取地址跟踪列表

        Args:
            user_id: 用户ID
            is_enabled: 启用状态筛选
            search: 搜索地址或备注
            limit: 每页数量
            offset: 偏移量

        Returns:
            (跟踪列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建查询条件
            conditions = ["user_id = %s"]
            params = [user_id]

            if is_enabled is not None:
                conditions.append("is_enabled = %s")
                params.append(is_enabled)

            if search:
                conditions.append("(tracking_address ILIKE %s OR address_remark ILIKE %s)")
                params.extend([f'%{search}%', f'%{search}%'])

            where_clause = " AND ".join(conditions)

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM address_tracking
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()['count']

            # 查询数据
            cursor.execute(f"""
                SELECT * FROM address_tracking
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # 解析 JSON 字段
                try:
                    item['monitor_events'] = json.loads(item.get('monitor_events') or '[]')
                except:
                    item['monitor_events'] = []
                results.append(item)

            return results, total_count

    def get_address_tracking(self, user_id: int, tracking_id: int) -> Optional[Dict]:
        """
        获取单个地址跟踪详情

        Args:
            user_id: 用户ID
            tracking_id: 跟踪记录ID

        Returns:
            跟踪详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM address_tracking
                WHERE user_id = %s AND id = %s
            """, (user_id, tracking_id,))
            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            try:
                item['monitor_events'] = json.loads(item.get('monitor_events') or '[]')
            except:
                item['monitor_events'] = []
            return item

    def get_address_tracking_by_address(self, user_id: int, tracking_address: str) -> Optional[Dict]:
        """
        按跟踪地址查询跟踪记录

        Args:
            user_id: 用户ID
            tracking_address: 跟踪地址

        Returns:
            跟踪记录
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM address_tracking
                WHERE user_id = %s AND tracking_address = %s
            """, (user_id, tracking_address,))
            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            try:
                item['monitor_events'] = json.loads(item.get('monitor_events') or '[]')
            except:
                item['monitor_events'] = []
            return item

    def save_address_tracking(self, user_id: int, data: Dict) -> Optional[int]:
        """
        保存或更新地址跟踪记录

        Args:
            user_id: 用户ID
            data: 跟踪数据

        Returns:
            记录ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            # 处理 JSON 字段
            monitor_events = data.get('monitor_events', ['open', 'close', 'add', 'reduce'])
            if isinstance(monitor_events, list):
                monitor_events = json.dumps(monitor_events)

            if data.get('id'):
                # 更新现有记录
                cursor.execute("""
                    UPDATE address_tracking
                    SET tracking_address = %s,
                        address_remark = %s,
                        is_enabled = %s,
                        enable_notification = %s,
                        monitor_events = %s,
                        updated_at = %s
                    WHERE user_id = %s AND id = %s
                    RETURNING id
                """, (
                    data.get('tracking_address'),
                    data.get('address_remark', ''),
                    data.get('is_enabled', True),
                    data.get('enable_notification', True),
                    monitor_events,
                    now,
                    user_id,
                    data['id']
                ))
                result = cursor.fetchone()
                return result[0] if result else None
            else:
                # 创建新记录
                cursor.execute("""
                    INSERT INTO address_tracking (
                        user_id, tracking_address, address_remark,
                        is_enabled, enable_notification, monitor_events,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_id,
                    data.get('tracking_address'),
                    data.get('address_remark', ''),
                    data.get('is_enabled', True),
                    data.get('enable_notification', True),
                    monitor_events,
                    now,
                    now
                ))
                result = cursor.fetchone()
                return result[0] if result else None

    def delete_address_tracking(self, user_id: int, tracking_id: int) -> bool:
        """
        删除地址跟踪记录

        Args:
            user_id: 用户ID
            tracking_id: 跟踪记录ID

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM address_tracking WHERE user_id = %s AND id = %s",
                (user_id, tracking_id,)
            )
            return cursor.rowcount > 0

    def toggle_address_tracking(self, user_id: int, tracking_id: int, is_enabled: bool) -> bool:
        """
        启用/禁用地址跟踪

        Args:
            user_id: 用户ID
            tracking_id: 跟踪记录ID
            is_enabled: 是否启用

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            cursor.execute("""
                UPDATE address_tracking
                SET is_enabled = %s, updated_at = %s
                WHERE user_id = %s AND id = %s
            """, (is_enabled, now, user_id, tracking_id))

            return cursor.rowcount > 0

    def toggle_address_tracking_notification(
        self, user_id: int, tracking_id: int, enable_notification: bool
    ) -> bool:
        """
        启用/禁用地址跟踪通知

        Args:
            user_id: 用户ID
            tracking_id: 跟踪记录ID
            enable_notification: 是否启用通知

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            cursor.execute("""
                UPDATE address_tracking
                SET enable_notification = %s, updated_at = %s
                WHERE user_id = %s AND id = %s
            """, (enable_notification, now, user_id, tracking_id))

            return cursor.rowcount > 0

    def get_enabled_address_trackings(self, user_id: Optional[int] = None) -> List[Dict]:
        """
        获取所有启用的地址跟踪配置

        Args:
            user_id: 用户ID（可选，不传则获取所有用户的）

        Returns:
            启用的跟踪配置列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if user_id is not None:
                cursor.execute("""
                    SELECT * FROM address_tracking
                    WHERE user_id = %s AND is_enabled = TRUE
                    ORDER BY updated_at DESC
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT * FROM address_tracking
                    WHERE is_enabled = TRUE
                    ORDER BY user_id, updated_at DESC
                """)

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                try:
                    item['monitor_events'] = json.loads(item.get('monitor_events') or '[]')
                except:
                    item['monitor_events'] = []
                results.append(item)

            return results

    def get_address_tracking_stats(self, user_id: int) -> Dict:
        """
        获取地址跟踪统计信息

        Args:
            user_id: 用户ID

        Returns:
            统计数据
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE is_enabled = TRUE) as enabled_count,
                    COUNT(*) FILTER (WHERE is_enabled = FALSE) as disabled_count,
                    COUNT(*) FILTER (WHERE enable_notification = TRUE) as notification_enabled_count
                FROM address_tracking
                WHERE user_id = %s
            """, (user_id,))

            row = cursor.fetchone()
            return dict(row) if row else {
                'total_count': 0,
                'enabled_count': 0,
                'disabled_count': 0,
                'notification_enabled_count': 0
            }

    def check_address_tracking_exists(self, user_id: int, tracking_address: str) -> bool:
        """
        检查是否已存在该地址的跟踪记录

        Args:
            user_id: 用户ID
            tracking_address: 跟踪地址

        Returns:
            是否存在
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM address_tracking
                WHERE user_id = %s AND tracking_address = %s
                LIMIT 1
            """, (user_id, tracking_address,))
            return cursor.fetchone() is not None

    def batch_delete_address_trackings(self, user_id: int, tracking_ids: List[int]) -> int:
        """
        批量删除地址跟踪记录

        Args:
            user_id: 用户ID
            tracking_ids: 跟踪记录ID列表

        Returns:
            删除的记录数
        """
        if not tracking_ids:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM address_tracking
                WHERE user_id = %s AND id = ANY(%s)
            """, (user_id, tracking_ids,))
            return cursor.rowcount
