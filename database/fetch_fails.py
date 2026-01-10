"""
交易记录获取失败记录管理模块 (PostgreSQL)
"""
from typing import List, Dict, Any, Optional
from psycopg2 import extras
from loguru import logger


class FetchFailsOps:
    """交易记录获取失败记录相关操作"""

    def record_fetch_fail(
        self,
        address: str,
        fail_type: str,
        error_message: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> int:
        """
        记录一条获取失败的记录

        Args:
            address: 交易者地址
            fail_type: 失败类型 ('recent' | 'month' | 'week' | 'day' | 'hour')
            error_message: 错误信息
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）

        Returns:
            记录ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fetch_fails (
                    address, fail_type, error_message, start_time, end_time, status
                ) VALUES (%s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (address, fail_type, error_message, start_time, end_time))
            record_id = cursor.fetchone()[0]
            logger.debug(f"记录获取失败: {address[:10]}... [{fail_type}] - {error_message[:50]}")
            return record_id

    def get_pending_fails(
        self,
        address: Optional[str] = None,
        fail_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取待处理的失败记录

        Args:
            address: 筛选特定地址
            fail_type: 筛选特定失败类型
            limit: 返回数量

        Returns:
            失败记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = ["status IN ('pending', 'retrying')"]
            params = []

            if address:
                conditions.append("address = %s")
                params.append(address)

            if fail_type:
                conditions.append("fail_type = %s")
                params.append(fail_type)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM fetch_fails
                WHERE {where_clause}
                ORDER BY created_at ASC
                LIMIT %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_fails_by_address(self, address: str) -> List[Dict[str, Any]]:
        """
        获取某个地址的所有失败记录

        Args:
            address: 交易者地址

        Returns:
            失败记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM fetch_fails
                WHERE address = %s
                ORDER BY created_at DESC
            """, (address,))
            return [dict(row) for row in cursor.fetchall()]

    def get_fails_summary(self) -> Dict[str, Any]:
        """
        获取失败记录汇总统计

        Returns:
            汇总统计字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 按状态统计
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM fetch_fails
                GROUP BY status
            """)
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # 按类型统计
            cursor.execute("""
                SELECT fail_type, COUNT(*) as count
                FROM fetch_fails
                WHERE status IN ('pending', 'retrying')
                GROUP BY fail_type
            """)
            by_type = {row['fail_type']: row['count'] for row in cursor.fetchall()}

            # 按地址统计（待处理）
            cursor.execute("""
                SELECT address, COUNT(*) as count
                FROM fetch_fails
                WHERE status IN ('pending', 'retrying')
                GROUP BY address
                ORDER BY count DESC
                LIMIT 20
            """)
            by_address = [dict(row) for row in cursor.fetchall()]

            return {
                'by_status': by_status,
                'by_type': by_type,
                'by_address': by_address,
                'total_pending': by_status.get('pending', 0) + by_status.get('retrying', 0),
                'total_resolved': by_status.get('resolved', 0),
                'total_failed': by_status.get('failed', 0)
            }

    def update_fail_status(
        self,
        fail_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        更新失败记录状态

        Args:
            fail_id: 记录ID
            status: 新状态 ('pending' | 'retrying' | 'resolved' | 'failed')
            error_message: 可选的错误信息更新

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status == 'resolved':
                cursor.execute("""
                    UPDATE fetch_fails
                    SET status = %s, updated_at = CURRENT_TIMESTAMP, resolved_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (status, fail_id))
            elif error_message:
                cursor.execute("""
                    UPDATE fetch_fails
                    SET status = %s, error_message = %s, retry_count = retry_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (status, error_message, fail_id))
            else:
                cursor.execute("""
                    UPDATE fetch_fails
                    SET status = %s, retry_count = retry_count + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (status, fail_id))

            return cursor.rowcount > 0

    def mark_as_resolved(self, fail_id: int) -> bool:
        """
        标记记录为已解决

        Args:
            fail_id: 记录ID

        Returns:
            是否更新成功
        """
        return self.update_fail_status(fail_id, 'resolved')

    def mark_as_failed(self, fail_id: int, error_message: str) -> bool:
        """
        标记记录为永久失败

        Args:
            fail_id: 记录ID
            error_message: 最终错误信息

        Returns:
            是否更新成功
        """
        return self.update_fail_status(fail_id, 'failed', error_message)

    def increment_retry_count(self, fail_id: int) -> bool:
        """
        增加重试次数

        Args:
            fail_id: 记录ID

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE fetch_fails
                SET retry_count = retry_count + 1, status = 'retrying',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (fail_id,))
            return cursor.rowcount > 0

    def delete_resolved_fails(self, days_old: int = 30) -> int:
        """
        删除已解决的旧记录

        Args:
            days_old: 删除多少天前的记录

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM fetch_fails
                WHERE status = 'resolved'
                AND resolved_at < CURRENT_TIMESTAMP - INTERVAL '%s days'
            """, (days_old,))
            return cursor.rowcount

    def clear_fails_for_address(self, address: str) -> int:
        """
        清除某个地址的所有失败记录

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM fetch_fails WHERE address = %s",
                (address,)
            )
            return cursor.rowcount

    def get_addresses_with_pending_fails(self) -> List[str]:
        """
        获取有待处理失败记录的所有地址

        Returns:
            地址列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT address
                FROM fetch_fails
                WHERE status IN ('pending', 'retrying')
                ORDER BY address
            """)
            return [row[0] for row in cursor.fetchall()]
