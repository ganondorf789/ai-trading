"""
通知管理模块 (PostgreSQL)
用于存储和管理跟单交易通知
"""
from typing import List, Dict, Optional, Tuple
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class NotificationsOps:
    """通知相关数据库操作"""

    # ==================== 通知管理 ====================

    def save_notification(self, data: Dict) -> Optional[int]:
        """
        保存通知到数据库

        Args:
            data: 通知数据，包含:
                - type: 通知类型 ('open' | 'close' | 'adjust' | 'error')
                - title: 通知标题
                - content: Markdown 格式内容
                - target_address: 目标交易员地址（可选）
                - symbol: 交易对（可选）
                - side: 方向 'long' | 'short'（可选）
                - size: 仓位大小（可选）
                - pnl: 盈亏（可选）

        Returns:
            通知记录 ID，失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO notifications (
                        type, title, content,
                        target_address, symbol, side, size, pnl,
                        is_read, created_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        FALSE, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                """, (
                    data.get('type', 'info'),
                    data.get('title', ''),
                    data.get('content', ''),
                    data.get('target_address'),
                    data.get('symbol'),
                    data.get('side'),
                    data.get('size'),
                    data.get('pnl')
                ))
                
                result = cursor.fetchone()
                notification_id = result[0] if result else None
                
                if notification_id:
                    logger.debug(f"通知已保存: id={notification_id}, type={data.get('type')}")
                
                return notification_id
                
        except Exception as e:
            logger.error(f"保存通知失败: {e}")
            return None

    def get_notifications(
        self,
        notification_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        获取通知列表

        Args:
            notification_type: 通知类型筛选
            is_read: 已读状态筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            (通知列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 构建查询条件
            conditions = []
            params = []

            if notification_type is not None:
                conditions.append("type = %s")
                params.append(notification_type)

            if is_read is not None:
                conditions.append("is_read = %s")
                params.append(is_read)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM notifications
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()['count']

            # 查询数据
            cursor.execute(f"""
                SELECT * FROM notifications
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params + [limit, offset])

            results = [dict(row) for row in cursor.fetchall()]
            return results, total_count

    def get_notification(self, notification_id: int) -> Optional[Dict]:
        """
        获取单个通知详情

        Args:
            notification_id: 通知 ID

        Returns:
            通知详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM notifications
                WHERE id = %s
            """, (notification_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def mark_notification_read(self, notification_id: int) -> bool:
        """
        标记通知为已读

        Args:
            notification_id: 通知 ID

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications
                SET is_read = TRUE
                WHERE id = %s
            """, (notification_id,))
            return cursor.rowcount > 0

    def mark_all_notifications_read(self) -> int:
        """
        标记所有通知为已读

        Returns:
            更新的通知数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications
                SET is_read = TRUE
                WHERE is_read = FALSE
            """)
            return cursor.rowcount

    def get_unread_count(self) -> int:
        """
        获取未读通知数量

        Returns:
            未读通知数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM notifications
                WHERE is_read = FALSE
            """)
            result = cursor.fetchone()
            return result[0] if result else 0

    def delete_notification(self, notification_id: int) -> bool:
        """
        删除通知

        Args:
            notification_id: 通知 ID

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM notifications WHERE id = %s",
                (notification_id,)
            )
            return cursor.rowcount > 0

    def delete_old_notifications(self, days: int = 30) -> int:
        """
        删除指定天数之前的旧通知

        Args:
            days: 保留最近多少天的通知

        Returns:
            删除的通知数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM notifications
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            """, (days,))
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"已删除 {deleted_count} 条旧通知（{days} 天前）")
            return deleted_count

    def get_notification_stats(self) -> Dict:
        """
        获取通知统计信息

        Returns:
            统计数据
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT
                    COUNT(*) as total_count,
                    COUNT(*) FILTER (WHERE is_read = FALSE) as unread_count,
                    COUNT(*) FILTER (WHERE type = 'open') as open_count,
                    COUNT(*) FILTER (WHERE type = 'close') as close_count,
                    COUNT(*) FILTER (WHERE type = 'adjust') as adjust_count,
                    COUNT(*) FILTER (WHERE type = 'error') as error_count,
                    MAX(created_at) as latest_notification_at
                FROM notifications
            """)

            row = cursor.fetchone()
            return dict(row) if row else {
                'total_count': 0,
                'unread_count': 0,
                'open_count': 0,
                'close_count': 0,
                'adjust_count': 0,
                'error_count': 0,
                'latest_notification_at': None
            }

    def get_notifications_cursor(
        self,
        limit: int = 50,
        before: Optional[int] = None,
        after: Optional[int] = None,
        notification_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        symbol: Optional[str] = None,
        target_address: Optional[str] = None
    ) -> List[Dict]:
        """
        使用游标分页查询通知记录

        Args:
            limit: 返回数量限制
            before: 游标ID，获取此ID之前的记录（不包含此ID），为空则从最新记录开始
            after: 游标ID，获取此ID之后的记录（不包含此ID），用于获取更新的数据
            notification_type: 按通知类型过滤 ('open' | 'close' | 'adjust' | 'error')
            is_read: 按已读状态过滤
            symbol: 按交易对过滤
            target_address: 按目标交易员地址过滤

        Returns:
            通知记录列表（按 id 降序排列）
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
            
            if notification_type:
                conditions.append("type = %s")
                params.append(notification_type)
            
            if is_read is not None:
                conditions.append("is_read = %s")
                params.append(is_read)
            
            if symbol:
                conditions.append("symbol = %s")
                params.append(symbol)
            
            if target_address:
                conditions.append("target_address = %s")
                params.append(target_address)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 使用 after 时，先按 ASC 排序取最早的 N 条，然后反转为 DESC
            if after is not None and before is None:
                query = f"""
                    SELECT * FROM (
                        SELECT * FROM notifications
                        WHERE {where_clause}
                        ORDER BY id ASC
                        LIMIT %s
                    ) sub ORDER BY id DESC
                """
            else:
                query = f"""
                    SELECT * FROM notifications
                    WHERE {where_clause}
                    ORDER BY id DESC
                    LIMIT %s
                """
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
