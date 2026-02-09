"""
通知管理模块 (PostgreSQL)
用于存储和管理跟单交易通知
"""
from typing import List, Dict, Optional, Tuple
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


# SQL CASE 表达式：将通知 type 映射到分类 category
# 与 services/routes/notifications.py 中的 NOTIFICATION_CATEGORIES 保持一致
TYPE_TO_CATEGORY_SQL = """
    CASE
        WHEN n.type = 'announcement' THEN 'announcement'
        WHEN n.type IN ('market', 'price_alert') THEN 'market'
        WHEN n.type IN ('open', 'close', 'adjust') THEN 'trading'
        ELSE 'error'
    END
"""


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
                - user_id: 用户ID（可选，用于定向发送通知）

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
                        user_id, is_read, created_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, FALSE, CURRENT_TIMESTAMP
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
                    data.get('pnl'),
                    data.get('user_id')
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
        user_id: Optional[int] = None,
        notification_type: Optional[str] = None,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        获取通知列表

        Args:
            user_id: 用户ID筛选
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

            if user_id is not None:
                conditions.append("user_id = %s")
                params.append(user_id)

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

    def get_unread_count(self, user_id: Optional[int] = None) -> int:
        """
        获取未读通知数量

        Args:
            user_id: 用户ID（可选）

        Returns:
            未读通知数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id is not None:
                cursor.execute("""
                    SELECT COUNT(*) FROM notifications
                    WHERE is_read = FALSE AND user_id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT COUNT(*) FROM notifications
                    WHERE is_read = FALSE
                """)
            result = cursor.fetchone()
            return result[0] if result else 0

    def get_unread_count_by_type(self, user_id: int) -> Dict[str, int]:
        """
        按 type 分组统计用户未读通知数量（基于 notification_read_marks 水位线）

        Args:
            user_id: 用户ID

        Returns:
            字典 {type: unread_count}，例如 {'open': 3, 'error': 1, 'announcement': 2}
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute(f"""
                SELECT n.type, COUNT(*) as count
                FROM notifications n
                LEFT JOIN notification_read_marks rm_all
                    ON rm_all.user_id = %s AND rm_all.category = 'all'
                LEFT JOIN notification_read_marks rm_cat
                    ON rm_cat.user_id = %s AND rm_cat.category = ({TYPE_TO_CATEGORY_SQL})
                WHERE n.id > COALESCE(rm_all.read_before_id, 0)
                  AND n.id > COALESCE(rm_cat.read_before_id, 0)
                GROUP BY n.type
            """, (user_id, user_id))

            return {row['type']: row['count'] for row in cursor.fetchall()}

    # ==================== 已读标记管理 ====================

    def get_user_read_marks(self, user_id: int) -> Dict[str, int]:
        """
        获取用户的所有已读水位线

        Args:
            user_id: 用户ID

        Returns:
            字典 {category: read_before_id}，例如 {'all': 100, 'trading': 150}
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT category, read_before_id
                FROM notification_read_marks
                WHERE user_id = %s
            """, (user_id,))
            return {row['category']: row['read_before_id'] for row in cursor.fetchall()}

    def mark_category_read(self, user_id: int, category: str, types: List[str]) -> int:
        """
        标记某个分类的所有通知为已读（水位线方式）

        将 read_before_id 设为该分类下当前最大的 notification.id，
        之后查询时 id <= read_before_id 的通知即视为已读。

        Args:
            user_id: 用户ID
            category: 分类名 ('announcement' | 'market' | 'trading' | 'error')
            types: 该分类包含的通知 type 列表

        Returns:
            新的 read_before_id 值
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 获取该分类下最大的通知 ID
            placeholders = ", ".join(["%s"] * len(types))
            cursor.execute(f"""
                SELECT COALESCE(MAX(id), 0) FROM notifications
                WHERE type IN ({placeholders})
            """, types)
            max_id = cursor.fetchone()[0]

            if max_id == 0:
                return 0

            # UPSERT: 用 GREATEST 确保水位线只升不降
            cursor.execute("""
                INSERT INTO notification_read_marks (user_id, category, read_before_id, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, category) DO UPDATE SET
                    read_before_id = GREATEST(notification_read_marks.read_before_id, EXCLUDED.read_before_id),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING read_before_id
            """, (user_id, category, max_id))

            result = cursor.fetchone()
            logger.debug(f"用户 {user_id} 标记分类 {category} 已读, read_before_id={result[0]}")
            return result[0]

    def mark_all_read_for_user(self, user_id: int) -> int:
        """
        标记所有通知为已读（水位线方式）

        Args:
            user_id: 用户ID

        Returns:
            新的 read_before_id 值
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 获取所有通知中最大的 ID
            cursor.execute("SELECT COALESCE(MAX(id), 0) FROM notifications")
            max_id = cursor.fetchone()[0]

            if max_id == 0:
                return 0

            cursor.execute("""
                INSERT INTO notification_read_marks (user_id, category, read_before_id, updated_at)
                VALUES (%s, 'all', %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, category) DO UPDATE SET
                    read_before_id = GREATEST(notification_read_marks.read_before_id, EXCLUDED.read_before_id),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING read_before_id
            """, (user_id, max_id))

            result = cursor.fetchone()
            logger.debug(f"用户 {user_id} 标记全部已读, read_before_id={result[0]}")
            return result[0]

    def update_notification(
        self,
        notification_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> bool:
        """
        更新通知

        Args:
            notification_id: 通知 ID
            title: 新标题（可选）
            content: 新内容（可选）

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建更新字段
                updates = []
                params = []
                
                if title is not None:
                    updates.append("title = %s")
                    params.append(title)
                
                if content is not None:
                    updates.append("content = %s")
                    params.append(content)
                
                if not updates:
                    return True  # 没有需要更新的字段
                
                params.append(notification_id)
                
                cursor.execute(f"""
                    UPDATE notifications
                    SET {", ".join(updates)}
                    WHERE id = %s
                """, params)
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"更新通知失败: {e}")
            return False

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
        user_id: Optional[int] = None,
        limit: int = 50,
        before: Optional[int] = None,
        after: Optional[int] = None,
        notification_type: Optional[str] = None,
        notification_types: Optional[List[str]] = None,
        is_read: Optional[bool] = None,
        symbol: Optional[str] = None,
        target_address: Optional[str] = None
    ) -> List[Dict]:
        """
        使用游标分页查询通知记录

        Args:
            user_id: 用户ID（用于计算每用户已读状态）
            limit: 返回数量限制
            before: 游标ID，获取此ID之前的记录（不包含此ID），为空则从最新记录开始
            after: 游标ID，获取此ID之后的记录（不包含此ID），用于获取更新的数据
            notification_type: 按单个通知类型过滤 ('open' | 'close' | 'adjust' | 'error' 等)
            notification_types: 按多个通知类型过滤（用于大类查询，如 ['open', 'close', 'adjust']）
            is_read: 按已读状态过滤（基于 notification_read_marks 水位线）
            symbol: 按交易对过滤
            target_address: 按目标交易员地址过滤

        Returns:
            通知记录列表（按 id 降序排列），包含计算后的 is_read 字段
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            
            # 构建查询
            params = []
            conditions = []
            join_clauses = ""
            
            # 根据是否有 user_id 决定 is_read 的计算方式
            if user_id is not None:
                # 使用 notification_read_marks 水位线计算 is_read
                select_cols = f"""n.*,
                    CASE
                        WHEN n.id <= COALESCE(rm_all.read_before_id, 0) THEN TRUE
                        WHEN n.id <= COALESCE(rm_cat.read_before_id, 0) THEN TRUE
                        ELSE FALSE
                    END as is_read"""
                join_clauses = f"""
                    LEFT JOIN notification_read_marks rm_all
                        ON rm_all.user_id = %s AND rm_all.category = 'all'
                    LEFT JOIN notification_read_marks rm_cat
                        ON rm_cat.user_id = %s AND rm_cat.category = ({TYPE_TO_CATEGORY_SQL})
                """
                params.extend([user_id, user_id])
                
                # is_read 过滤（基于水位线）
                if is_read is True:
                    conditions.append(
                        "(n.id <= COALESCE(rm_all.read_before_id, 0) OR n.id <= COALESCE(rm_cat.read_before_id, 0))"
                    )
                elif is_read is False:
                    conditions.append(
                        "n.id > COALESCE(rm_all.read_before_id, 0) AND n.id > COALESCE(rm_cat.read_before_id, 0)"
                    )
            else:
                # 无用户上下文，使用表上的 is_read 列（兼容旧逻辑）
                select_cols = "n.*"
                if is_read is not None:
                    conditions.append("n.is_read = %s")
                    params.append(is_read)
            
            # before 游标条件
            if before is not None:
                conditions.append("n.id < %s")
                params.append(before)
            
            # after 游标条件
            if after is not None:
                conditions.append("n.id > %s")
                params.append(after)
            
            # notification_types 优先于 notification_type
            if notification_types:
                placeholders = ", ".join(["%s"] * len(notification_types))
                conditions.append(f"n.type IN ({placeholders})")
                params.extend(notification_types)
            elif notification_type:
                conditions.append("n.type = %s")
                params.append(notification_type)
            
            if symbol:
                conditions.append("n.symbol = %s")
                params.append(symbol)
            
            if target_address:
                conditions.append("n.target_address = %s")
                params.append(target_address)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 使用 after 时，先按 ASC 排序取最早的 N 条，然后反转为 DESC
            if after is not None and before is None:
                query = f"""
                    SELECT * FROM (
                        SELECT {select_cols} FROM notifications n
                        {join_clauses}
                        WHERE {where_clause}
                        ORDER BY n.id ASC
                        LIMIT %s
                    ) sub ORDER BY id DESC
                """
            else:
                query = f"""
                    SELECT {select_cols} FROM notifications n
                    {join_clauses}
                    WHERE {where_clause}
                    ORDER BY n.id DESC
                    LIMIT %s
                """
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
