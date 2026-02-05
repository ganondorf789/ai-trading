"""
用户收藏管理模块 (PostgreSQL)
提供用户维度的交易者收藏功能
"""
from typing import List, Set
from psycopg2 import extras
from loguru import logger


class UserFavoritesOps:
    """用户收藏相关操作"""

    def toggle_user_star(self, user_id: int, address: str, is_starred: bool) -> bool:
        """
        切换用户对交易者的收藏状态

        Args:
            user_id: 用户 ID
            address: 交易者地址
            is_starred: 是否收藏

        Returns:
            是否操作成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if is_starred:
                # 添加收藏（忽略重复）
                cursor.execute("""
                    INSERT INTO user_favorites (user_id, trader_address)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id, trader_address) DO NOTHING
                """, (user_id, address))
                logger.info(f"用户 {user_id} 收藏交易者 {address[:10]}...")
            else:
                # 取消收藏
                cursor.execute("""
                    DELETE FROM user_favorites
                    WHERE user_id = %s AND trader_address = %s
                """, (user_id, address))
                logger.info(f"用户 {user_id} 取消收藏交易者 {address[:10]}...")
            
            return True

    def get_user_starred_addresses(self, user_id: int) -> Set[str]:
        """
        获取用户收藏的所有交易者地址

        Args:
            user_id: 用户 ID

        Returns:
            收藏的交易者地址集合
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT trader_address FROM user_favorites
                WHERE user_id = %s
            """, (user_id,))
            return {row[0] for row in cursor.fetchall()}

    def is_user_starred(self, user_id: int, address: str) -> bool:
        """
        检查用户是否收藏了某个交易者

        Args:
            user_id: 用户 ID
            address: 交易者地址

        Returns:
            是否已收藏
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM user_favorites
                WHERE user_id = %s AND trader_address = %s
                LIMIT 1
            """, (user_id, address))
            return cursor.fetchone() is not None

    def get_user_starred_traders(self, user_id: int, limit: int = 100) -> List[dict]:
        """
        获取用户收藏的交易者详情列表

        Args:
            user_id: 用户 ID
            limit: 返回数量

        Returns:
            收藏的交易者详情列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT tm.*, TRUE as is_starred
                FROM trader_metrics tm
                INNER JOIN user_favorites uf ON tm.address = uf.trader_address
                WHERE uf.user_id = %s
                ORDER BY tm.overall_score DESC
                LIMIT %s
            """, (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_user_favorites_count(self, user_id: int) -> int:
        """
        获取用户收藏的交易者数量

        Args:
            user_id: 用户 ID

        Returns:
            收藏数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM user_favorites
                WHERE user_id = %s
            """, (user_id,))
            return cursor.fetchone()[0]
