"""
秘钥管理模块 (PostgreSQL)
用于存储和管理注册秘钥
"""
from typing import Optional, Dict, List
import secrets
from datetime import datetime, timedelta
from psycopg2 import extras
from loguru import logger


class SecretKeysOps:
    """秘钥相关数据库操作"""

    # ==================== 用户身份常量 ====================
    
    ROLE_USER = 'user'          # 普通用户
    ROLE_MEMBER = 'member'      # 会员
    ROLE_ADMIN = 'admin'        # 超级管理员
    
    VALID_ROLES = [ROLE_USER, ROLE_MEMBER, ROLE_ADMIN]

    # ==================== 秘钥生成 ====================

    def generate_secret_key(self, length: int = 32) -> str:
        """
        生成随机秘钥
        
        Args:
            length: 秘钥长度（字符数）
            
        Returns:
            随机秘钥字符串
        """
        return secrets.token_urlsafe(length)[:length]

    # ==================== 秘钥管理 ====================

    def create_secret_key(
        self,
        key_name: str = '',
        user_role: str = 'user',
        expires_days: int = 30,
        expires_at: Optional[datetime] = None,
        created_by: Optional[int] = None,
        key_value: Optional[str] = None
    ) -> Optional[Dict]:
        """
        创建新秘钥（每个秘钥只能使用一次）

        Args:
            key_name: 秘钥名称/备注
            user_role: 使用此秘钥注册的用户身份 (user/member/admin)
            expires_days: 注册用户的有效天数（0表示永不过期）
            expires_at: 秘钥过期时间（None表示永不过期）
            created_by: 创建者用户ID
            key_value: 指定秘钥值（可选，不指定则自动生成）

        Returns:
            创建成功返回秘钥信息，失败返回 None
        """
        try:
            # 验证用户身份
            if user_role not in self.VALID_ROLES:
                logger.warning(f"创建秘钥失败: 无效的用户身份 - {user_role}")
                return None
            
            # 生成秘钥值
            if not key_value:
                key_value = self.generate_secret_key()
            
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 检查秘钥是否已存在
                cursor.execute(
                    "SELECT id FROM secret_keys WHERE key_value = %s",
                    (key_value,)
                )
                if cursor.fetchone():
                    logger.warning(f"创建秘钥失败: 秘钥已存在")
                    return None
                
                # 插入秘钥
                cursor.execute("""
                    INSERT INTO secret_keys (
                        key_value, key_name, user_role,
                        expires_days, is_used, used_by_user_id,
                        is_active, expires_at, created_by,
                        created_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, FALSE, NULL,
                        TRUE, %s, %s,
                        CURRENT_TIMESTAMP
                    )
                    RETURNING id, key_value, key_name, user_role,
                              expires_days, is_used, used_by_user_id,
                              is_active, expires_at, created_by, created_at
                """, (
                    key_value, key_name, user_role,
                    expires_days,
                    expires_at, created_by
                ))
                
                key = cursor.fetchone()
                if key:
                    logger.info(f"秘钥创建成功: {key_name or key_value[:8]}...")
                    return dict(key)
                return None
                
        except Exception as e:
            logger.error(f"创建秘钥失败: {e}")
            return None

    def validate_secret_key(self, key_value: str) -> Optional[Dict]:
        """
        验证秘钥是否有效（用于注册，每个秘钥只能使用一次）

        Args:
            key_value: 秘钥值

        Returns:
            有效返回秘钥信息，无效返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, key_value, key_name, user_role,
                           expires_days, is_used, used_by_user_id,
                           is_active, expires_at, created_by, created_at
                    FROM secret_keys
                    WHERE key_value = %s
                """, (key_value,))
                
                key = cursor.fetchone()
                if not key:
                    logger.warning(f"秘钥验证失败: 秘钥不存在")
                    return None
                
                key = dict(key)
                
                # 检查是否启用
                if not key['is_active']:
                    logger.warning(f"秘钥验证失败: 秘钥已禁用")
                    return None
                
                # 检查是否过期
                if key['expires_at'] and key['expires_at'] < datetime.now():
                    logger.warning(f"秘钥验证失败: 秘钥已过期")
                    return None
                
                # 检查是否已使用
                if key['is_used']:
                    logger.warning(f"秘钥验证失败: 秘钥已被使用")
                    return None
                
                return key
                
        except Exception as e:
            logger.error(f"验证秘钥失败: {e}")
            return None

    def use_secret_key(self, key_id: int, user_id: int) -> bool:
        """
        使用秘钥（标记为已使用并记录用户ID）

        Args:
            key_id: 秘钥ID
            user_id: 使用秘钥的用户ID

        Returns:
            是否成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 更新秘钥为已使用状态
                cursor.execute("""
                    UPDATE secret_keys
                    SET is_used = TRUE,
                        used_by_user_id = %s
                    WHERE id = %s AND is_used = FALSE
                """, (user_id, key_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"秘钥已使用: key_id={key_id}, user_id={user_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"使用秘钥失败: {e}")
            return False

    def get_secret_key(self, key_id: int) -> Optional[Dict]:
        """
        获取秘钥信息

        Args:
            key_id: 秘钥ID

        Returns:
            秘钥信息
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, key_value, key_name, user_role,
                           expires_days, is_used, used_by_user_id,
                           is_active, expires_at, created_by, created_at
                    FROM secret_keys
                    WHERE id = %s
                """, (key_id,))
                
                key = cursor.fetchone()
                return dict(key) if key else None
                
        except Exception as e:
            logger.error(f"获取秘钥失败: {e}")
            return None

    def get_secret_keys(
        self,
        is_active: Optional[bool] = None,
        is_used: Optional[bool] = None,
        user_role: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        获取秘钥列表

        Args:
            is_active: 是否启用筛选
            is_used: 是否已使用筛选
            user_role: 用户身份筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            秘钥列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 构建查询条件
                conditions = []
                params = []
                
                if is_active is not None:
                    conditions.append("is_active = %s")
                    params.append(is_active)
                
                if is_used is not None:
                    conditions.append("is_used = %s")
                    params.append(is_used)
                
                if user_role:
                    conditions.append("user_role = %s")
                    params.append(user_role)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                cursor.execute(f"""
                    SELECT id, key_value, key_name, user_role,
                           expires_days, is_used, used_by_user_id,
                           is_active, expires_at, created_by, created_at
                    FROM secret_keys
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"获取秘钥列表失败: {e}")
            return []

    def update_secret_key(
        self,
        key_id: int,
        key_name: Optional[str] = None,
        user_role: Optional[str] = None,
        expires_days: Optional[int] = None,
        is_active: Optional[bool] = None,
        expires_at: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        更新秘钥信息

        Args:
            key_id: 秘钥ID
            key_name: 秘钥名称
            user_role: 用户身份
            expires_days: 有效天数
            is_active: 是否启用
            expires_at: 过期时间

        Returns:
            更新后的秘钥信息
        """
        try:
            # 验证用户身份
            if user_role and user_role not in self.VALID_ROLES:
                logger.warning(f"更新秘钥失败: 无效的用户身份 - {user_role}")
                return None
            
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 构建更新语句
                updates = []
                params = []
                
                if key_name is not None:
                    updates.append("key_name = %s")
                    params.append(key_name)
                
                if user_role is not None:
                    updates.append("user_role = %s")
                    params.append(user_role)
                
                if expires_days is not None:
                    updates.append("expires_days = %s")
                    params.append(expires_days)
                
                if is_active is not None:
                    updates.append("is_active = %s")
                    params.append(is_active)
                
                if expires_at is not None:
                    updates.append("expires_at = %s")
                    params.append(expires_at)
                
                if not updates:
                    return self.get_secret_key(key_id)
                
                params.append(key_id)
                
                cursor.execute(f"""
                    UPDATE secret_keys
                    SET {', '.join(updates)}
                    WHERE id = %s
                    RETURNING id, key_value, key_name, user_role,
                              expires_days, is_used, used_by_user_id,
                              is_active, expires_at, created_by, created_at
                """, params)
                
                key = cursor.fetchone()
                if key:
                    logger.info(f"秘钥更新成功: id={key_id}")
                    return dict(key)
                return None
                
        except Exception as e:
            logger.error(f"更新秘钥失败: {e}")
            return None

    def delete_secret_key(self, key_id: int) -> bool:
        """
        删除秘钥

        Args:
            key_id: 秘钥ID

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "DELETE FROM secret_keys WHERE id = %s",
                    (key_id,)
                )
                
                if cursor.rowcount > 0:
                    logger.info(f"秘钥删除成功: id={key_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"删除秘钥失败: {e}")
            return False

    def get_secret_key_stats(self) -> Dict:
        """
        获取秘钥统计信息

        Returns:
            统计数据
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_count,
                        COUNT(*) FILTER (WHERE is_active = TRUE) as active_count,
                        COUNT(*) FILTER (WHERE is_active = FALSE) as inactive_count,
                        COUNT(*) FILTER (WHERE is_used = TRUE) as used_count,
                        COUNT(*) FILTER (WHERE is_used = FALSE AND is_active = TRUE) as available_count,
                        COUNT(*) FILTER (WHERE user_role = 'user') as user_role_count,
                        COUNT(*) FILTER (WHERE user_role = 'member') as member_role_count,
                        COUNT(*) FILTER (WHERE user_role = 'admin') as admin_role_count
                    FROM secret_keys
                """)
                
                row = cursor.fetchone()
                return dict(row) if row else {
                    'total_count': 0,
                    'active_count': 0,
                    'inactive_count': 0,
                    'used_count': 0,
                    'available_count': 0,
                    'user_role_count': 0,
                    'member_role_count': 0,
                    'admin_role_count': 0
                }
                
        except Exception as e:
            logger.error(f"获取秘钥统计失败: {e}")
            return {}

    def batch_create_secret_keys(
        self,
        count: int,
        key_name_prefix: str = '',
        user_role: str = 'user',
        expires_days: int = 30,
        expires_at: Optional[datetime] = None,
        created_by: Optional[int] = None
    ) -> List[Dict]:
        """
        批量创建秘钥（每个秘钥只能使用一次）

        Args:
            count: 创建数量
            key_name_prefix: 名称前缀
            user_role: 用户身份
            expires_days: 有效天数
            expires_at: 过期时间
            created_by: 创建者用户ID

        Returns:
            创建的秘钥列表
        """
        created_keys = []
        for i in range(count):
            key_name = f"{key_name_prefix}_{i+1}" if key_name_prefix else ''
            key = self.create_secret_key(
                key_name=key_name,
                user_role=user_role,
                expires_days=expires_days,
                expires_at=expires_at,
                created_by=created_by
            )
            if key:
                created_keys.append(key)
        
        logger.info(f"批量创建秘钥完成: 成功 {len(created_keys)}/{count}")
        return created_keys
