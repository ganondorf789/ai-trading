"""
用户管理模块 (PostgreSQL)
用于存储和管理用户账户信息
"""
from typing import Optional, Dict, List
import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from ulid import ULID
from psycopg2 import extras
from loguru import logger
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class UsersOps:
    """用户相关数据库操作"""

    # ==================== 用户身份常量 ====================
    
    ROLE_USER = 'user'          # 普通用户
    ROLE_MEMBER = 'member'      # 会员
    ROLE_ADMIN = 'admin'        # 超级管理员
    
    VALID_ROLES = [ROLE_USER, ROLE_MEMBER, ROLE_ADMIN]

    # ==================== 加密处理 ====================

    def _get_fernet(self) -> Fernet:
        """
        获取 Fernet 加密器实例
        使用 PBKDF2 从密钥派生出合适的加密密钥
        """
        from config.settings import settings
        
        # 使用 PBKDF2 从配置的密钥派生出 Fernet 兼容的密钥
        secret_key = settings.encryption.secret_key.encode()
        salt = b'auto-trading-salt-v1'  # 固定盐值，确保加密一致性
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key))
        return Fernet(key)

    def _encrypt_api_wallet(self, api_wallet: str) -> str:
        """
        加密 API 钱包私钥
        
        Args:
            api_wallet: 原始 API 钱包私钥
            
        Returns:
            加密后的字符串
        """
        if not api_wallet:
            return api_wallet
        
        try:
            fernet = self._get_fernet()
            encrypted = fernet.encrypt(api_wallet.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"加密 api_wallet 失败: {e}")
            raise

    def _decrypt_api_wallet(self, encrypted_wallet: str) -> str:
        """
        解密 API 钱包私钥
        
        Args:
            encrypted_wallet: 加密后的 API 钱包私钥
            
        Returns:
            解密后的原始字符串
        """
        if not encrypted_wallet:
            return encrypted_wallet
        
        try:
            fernet = self._get_fernet()
            decrypted = fernet.decrypt(encrypted_wallet.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"解密 api_wallet 失败: {e}")
            # 如果解密失败，可能是旧数据未加密，直接返回原值
            return encrypted_wallet

    # ==================== 密码处理 ====================

    def _hash_password(self, password: str) -> str:
        """
        对密码进行哈希处理
        使用 SHA-256 + 盐值
        """
        salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256((password + salt).encode())
        return f"{salt}${hash_obj.hexdigest()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        验证密码是否正确
        """
        try:
            salt, stored_hash = password_hash.split('$')
            hash_obj = hashlib.sha256((password + salt).encode())
            return hash_obj.hexdigest() == stored_hash
        except Exception:
            return False

    # ==================== 用户注册 ====================

    def create_user(
        self,
        account: str,
        password: str,
        secret_key_id: Optional[int] = None,
        role: str = 'user',
        expires_at: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        创建新用户

        Args:
            account: 账号
            password: 密码
            secret_key_id: 关联的秘钥ID（可选）
            role: 用户身份 (user/member/admin)
            expires_at: 过期时间（可选）

        Returns:
            创建成功返回用户信息（不含密码），失败返回 None
        """
        try:
            # 验证用户身份
            if role not in self.VALID_ROLES:
                logger.warning(f"用户注册失败: 无效的用户身份 - {role}")
                return None
            
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 检查账号是否已存在
                cursor.execute(
                    "SELECT id FROM users WHERE account = %s",
                    (account,)
                )
                if cursor.fetchone():
                    logger.warning(f"用户注册失败: 账号已存在 - {account}")
                    return None
                
                # 哈希密码
                password_hash = self._hash_password(password)
                
                # 生成 ULID
                user_ulid = str(ULID())
                
                # 插入用户
                cursor.execute("""
                    INSERT INTO users (
                        ulid, account, password_hash, secret_key_id, role,
                        expires_at, is_active,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, TRUE,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id, ulid, account, secret_key_id, role, api_wallet, wallet_address,
                              allowed_ip, allowed_port,
                              expires_at, is_active, created_at, updated_at
                """, (user_ulid, account, password_hash, secret_key_id, role, expires_at))
                
                user = cursor.fetchone()
                if user:
                    logger.info(f"用户注册成功: {account}, 身份: {role}")
                    return dict(user)
                return None
                
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return None

    # ==================== 用户登录 ====================

    def authenticate_user(self, account: str, password: str) -> Optional[Dict]:
        """
        验证用户登录

        Args:
            account: 账号
            password: 密码

        Returns:
            验证成功返回用户信息（不含密码），失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 查询用户
                cursor.execute("""
                    SELECT id, ulid, account, password_hash, secret_key_id, role,
                           api_wallet, wallet_address,
                           allowed_ip, allowed_port,
                           expires_at, is_active,
                           created_at, updated_at, last_login_at
                    FROM users
                    WHERE account = %s
                """, (account,))
                
                user = cursor.fetchone()
                if not user:
                    logger.warning(f"登录失败: 账号不存在 - {account}")
                    return None
                
                # 验证密码
                if not self._verify_password(password, user['password_hash']):
                    logger.warning(f"登录失败: 密码错误 - {account}")
                    return None
                
                # 检查账户是否激活
                if not user['is_active']:
                    logger.warning(f"登录失败: 账户未激活 - {account}")
                    return None
                
                # 检查是否过期
                if user['expires_at'] and user['expires_at'] < datetime.now():
                    logger.warning(f"登录失败: 账户已过期 - {account}")
                    return None
                
                # 更新最后登录时间
                cursor.execute("""
                    UPDATE users
                    SET last_login_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user['id'],))
                
                # 返回用户信息（不含密码哈希）
                result = dict(user)
                del result['password_hash']
                
                # 解密 api_wallet 后返回
                if result.get('api_wallet'):
                    result['api_wallet'] = self._decrypt_api_wallet(result['api_wallet'])
                
                logger.info(f"用户登录成功: {account}, 身份: {result.get('role', 'user')}")
                return result
                
        except Exception as e:
            logger.error(f"用户认证失败: {e}")
            return None

    # ==================== 修改密码 ====================

    def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改用户密码

        Args:
            user_id: 用户 ID
            old_password: 原密码
            new_password: 新密码

        Returns:
            是否修改成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 获取当前密码哈希
                cursor.execute(
                    "SELECT password_hash FROM users WHERE id = %s",
                    (user_id,)
                )
                user = cursor.fetchone()
                
                if not user:
                    logger.warning(f"修改密码失败: 用户不存在 - id={user_id}")
                    return False
                
                # 验证原密码
                if not self._verify_password(old_password, user['password_hash']):
                    logger.warning(f"修改密码失败: 原密码错误 - id={user_id}")
                    return False
                
                # 更新密码
                new_password_hash = self._hash_password(new_password)
                cursor.execute("""
                    UPDATE users
                    SET password_hash = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (new_password_hash, user_id))
                
                logger.info(f"用户密码修改成功: id={user_id}")
                return True
                
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return False

    # ==================== Hyperliquid API 设置 ====================

    def update_hyperliquid_settings(
        self,
        user_id: int,
        api_wallet: Optional[str] = None,
        wallet_address: Optional[str] = None
    ) -> Optional[Dict]:
        """
        更新用户的 Hyperliquid API 设置

        Args:
            user_id: 用户 ID
            api_wallet: API 钱包私钥（将被加密存储）
            wallet_address: 钱包地址

        Returns:
            更新后的用户信息（api_wallet 已解密），失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 构建更新语句
                updates = []
                params = []
                
                if api_wallet is not None:
                    # 加密 api_wallet 后存储
                    encrypted_wallet = self._encrypt_api_wallet(api_wallet) if api_wallet else ''
                    updates.append("api_wallet = %s")
                    params.append(encrypted_wallet)
                
                if wallet_address is not None:
                    updates.append("wallet_address = %s")
                    params.append(wallet_address)
                
                if not updates:
                    logger.warning("更新 Hyperliquid 设置: 无更新内容")
                    return None
                
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(user_id)
                
                cursor.execute(f"""
                    UPDATE users
                    SET {', '.join(updates)}
                    WHERE id = %s
                    RETURNING id, ulid, account, secret_key_id, role, api_wallet, wallet_address,
                              allowed_ip, allowed_port,
                              expires_at, is_active, created_at, updated_at, last_login_at
                """, params)
                
                user = cursor.fetchone()
                if user:
                    logger.info(f"Hyperliquid 设置更新成功: user_id={user_id}")
                    result = dict(user)
                    # 解密 api_wallet 后返回
                    if result.get('api_wallet'):
                        result['api_wallet'] = self._decrypt_api_wallet(result['api_wallet'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"更新 Hyperliquid 设置失败: {e}")
            return None

    def get_hyperliquid_settings(self, user_id: int) -> Optional[Dict]:
        """
        获取用户的 Hyperliquid API 设置

        Args:
            user_id: 用户 ID

        Returns:
            Hyperliquid 设置信息（api_wallet 已解密）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT api_wallet, wallet_address
                    FROM users
                    WHERE id = %s
                """, (user_id,))
                
                result = cursor.fetchone()
                if result:
                    data = dict(result)
                    # 解密 api_wallet 后返回
                    if data.get('api_wallet'):
                        data['api_wallet'] = self._decrypt_api_wallet(data['api_wallet'])
                    return data
                return None
                
        except Exception as e:
            logger.error(f"获取 Hyperliquid 设置失败: {e}")
            return None

    # ==================== 用户查询 ====================

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        根据 ID 获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            用户信息（不含密码，api_wallet 已解密）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, ulid, account, secret_key_id, role, api_wallet, wallet_address,
                           allowed_ip, allowed_port,
                           expires_at, is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE id = %s
                """, (user_id,))
                
                user = cursor.fetchone()
                if user:
                    result = dict(user)
                    # 解密 api_wallet 后返回
                    if result.get('api_wallet'):
                        result['api_wallet'] = self._decrypt_api_wallet(result['api_wallet'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def get_user_by_account(self, account: str) -> Optional[Dict]:
        """
        根据账号获取用户信息

        Args:
            account: 账号

        Returns:
            用户信息（不含密码，api_wallet 已解密）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, ulid, account, secret_key_id, role, api_wallet, wallet_address,
                           allowed_ip, allowed_port,
                           expires_at, is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE account = %s
                """, (account,))
                
                user = cursor.fetchone()
                if user:
                    result = dict(user)
                    # 解密 api_wallet 后返回
                    if result.get('api_wallet'):
                        result['api_wallet'] = self._decrypt_api_wallet(result['api_wallet'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def get_user_by_ulid(self, ulid: str) -> Optional[Dict]:
        """
        根据 ULID 获取用户信息

        Args:
            ulid: 用户 ULID

        Returns:
            用户信息（不含密码，api_wallet 已解密）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, ulid, account, secret_key_id, role, api_wallet, wallet_address,
                           allowed_ip, allowed_port,
                           expires_at, is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE ulid = %s
                """, (ulid,))
                
                user = cursor.fetchone()
                if user:
                    result = dict(user)
                    # 解密 api_wallet 后返回
                    if result.get('api_wallet'):
                        result['api_wallet'] = self._decrypt_api_wallet(result['api_wallet'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"根据 ULID 获取用户失败: {e}")
            return None

    def check_user_active(self, user_id: int) -> bool:
        """
        检查用户是否处于激活且未过期状态
        注意：管理员用户不检查过期时间

        Args:
            user_id: 用户 ID

        Returns:
            是否激活且未过期
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT is_active, expires_at, role
                    FROM users
                    WHERE id = %s
                """, (user_id,))
                
                result = cursor.fetchone()
                if not result:
                    return False
                
                is_active, expires_at, role = result
                if not is_active:
                    return False
                
                # 管理员不检查过期时间
                if role == 'admin':
                    return True
                
                # 非管理员用户检查过期时间
                if expires_at and expires_at < datetime.now():
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"检查用户状态失败: {e}")
            return False

    # ==================== 用户管理（管理员功能） ====================

    def update_user_expiry(
        self,
        user_id: int,
        expires_at: Optional[datetime]
    ) -> bool:
        """
        更新用户过期时间

        Args:
            user_id: 用户 ID
            expires_at: 新的过期时间（None 表示永不过期）

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE users
                    SET expires_at = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (expires_at, user_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"用户过期时间更新成功: id={user_id}, expires_at={expires_at}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"更新用户过期时间失败: {e}")
            return False

    def set_user_active(self, user_id: int, is_active: bool) -> bool:
        """
        设置用户激活状态

        Args:
            user_id: 用户 ID
            is_active: 是否激活

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE users
                    SET is_active = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (is_active, user_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"用户激活状态更新成功: id={user_id}, is_active={is_active}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"设置用户激活状态失败: {e}")
            return False

    def update_user_role(self, user_id: int, role: str) -> bool:
        """
        更新用户身份

        Args:
            user_id: 用户 ID
            role: 用户身份 (user/member/admin)

        Returns:
            是否更新成功
        """
        try:
            if role not in self.VALID_ROLES:
                logger.warning(f"更新用户身份失败: 无效的身份 - {role}")
                return False
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE users
                    SET role = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (role, user_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"用户身份更新成功: id={user_id}, role={role}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"更新用户身份失败: {e}")
            return False

    def get_users(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        获取用户列表

        Args:
            role: 身份筛选
            is_active: 激活状态筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            用户列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 构建查询条件
                conditions = []
                params = []
                
                if role:
                    conditions.append("role = %s")
                    params.append(role)
                
                if is_active is not None:
                    conditions.append("is_active = %s")
                    params.append(is_active)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                cursor.execute(f"""
                    SELECT id, ulid, account, secret_key_id, role, api_wallet, wallet_address,
                           allowed_ip, allowed_port,
                           expires_at, is_active, created_at, updated_at, last_login_at
                    FROM users
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                
                users = []
                for row in cursor.fetchall():
                    user = dict(row)
                    # 解密 api_wallet 后返回
                    if user.get('api_wallet'):
                        user['api_wallet'] = self._decrypt_api_wallet(user['api_wallet'])
                    users.append(user)
                return users
                
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return []

    def get_user_stats(self) -> Dict:
        """
        获取用户统计信息

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
                        COUNT(*) FILTER (WHERE role = 'user') as user_count,
                        COUNT(*) FILTER (WHERE role = 'member') as member_count,
                        COUNT(*) FILTER (WHERE role = 'admin') as admin_count,
                        COUNT(*) FILTER (WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP) as expired_count
                    FROM users
                """)
                
                row = cursor.fetchone()
                return dict(row) if row else {
                    'total_count': 0,
                    'active_count': 0,
                    'inactive_count': 0,
                    'user_count': 0,
                    'member_count': 0,
                    'admin_count': 0,
                    'expired_count': 0
                }
                
        except Exception as e:
            logger.error(f"获取用户统计失败: {e}")
            return {}

    def update_user_info(
        self,
        user_id: int,
        role: Optional[str] = None,
        expires_at=None,
        allowed_ip: Optional[str] = None,
        allowed_port: Optional[str] = None
    ) -> bool:
        """
        管理员更新用户信息（身份、过期时间、IP、端口）

        Args:
            user_id: 用户 ID
            role: 用户身份 (user/member/admin)
            expires_at: 过期时间（'none' 表示永不过期）
            allowed_ip: 允许的 IP 地址
            allowed_port: 允许的端口

        Returns:
            是否更新成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                updates = []
                params = []

                if role is not None:
                    if role not in self.VALID_ROLES:
                        logger.warning(f"更新用户信息失败: 无效的身份 - {role}")
                        return False
                    updates.append("role = %s")
                    params.append(role)

                if expires_at is not None:
                    updates.append("expires_at = %s")
                    # 'none' 或空值 表示永不过期
                    if expires_at == 'none' or expires_at == '':
                        params.append(None)
                    else:
                        params.append(expires_at)

                if allowed_ip is not None:
                    updates.append("allowed_ip = %s")
                    params.append(allowed_ip)

                if allowed_port is not None:
                    updates.append("allowed_port = %s")
                    params.append(allowed_port)

                if not updates:
                    return False

                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(user_id)

                cursor.execute(f"""
                    UPDATE users
                    SET {', '.join(updates)}
                    WHERE id = %s
                """, params)

                if cursor.rowcount > 0:
                    logger.info(f"用户信息更新成功: id={user_id}")
                    return True
                return False

        except Exception as e:
            logger.error(f"更新用户信息失败: {e}")
            return False

    def is_admin(self, user_id: int) -> bool:
        """
        检查用户是否为管理员

        Args:
            user_id: 用户 ID

        Returns:
            是否为管理员
        """
        try:
            user = self.get_user_by_id(user_id)
            return user is not None and user.get('role') == self.ROLE_ADMIN
        except Exception as e:
            logger.error(f"检查管理员权限失败: {e}")
            return False

    # ==================== API Key 管理 ====================

    def _generate_api_key(self) -> str:
        """
        生成一个安全的 API Key
        
        格式: atk_<48位随机hex> (共52字符)
        
        Returns:
            API Key 字符串
        """
        return f"atk_{secrets.token_hex(24)}"

    def generate_user_api_key(self, user_id: int) -> Optional[str]:
        """
        为用户生成新的 API Key（会覆盖旧的）

        Args:
            user_id: 用户 ID

        Returns:
            生成的 API Key，失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 确认用户存在
                cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cursor.fetchone():
                    logger.warning(f"生成 API Key 失败: 用户不存在 - id={user_id}")
                    return None
                
                # 生成新 API Key
                api_key = self._generate_api_key()
                
                cursor.execute("""
                    UPDATE users
                    SET api_key = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (api_key, user_id))
                
                logger.info(f"用户 API Key 生成成功: user_id={user_id}")
                return api_key
                
        except Exception as e:
            logger.error(f"生成 API Key 失败: {e}")
            return None

    def verify_api_key(self, api_key: str) -> Optional[Dict]:
        """
        验证 API Key 并返回关联的用户信息

        Args:
            api_key: API Key 字符串

        Returns:
            验证成功返回用户信息 (id, account, role, is_active, expires_at)，失败返回 None
        """
        if not api_key:
            return None
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, ulid, account, role, is_active, expires_at
                    FROM users
                    WHERE api_key = %s
                """, (api_key,))
                
                user = cursor.fetchone()
                if not user:
                    return None
                
                user = dict(user)
                
                # 检查账户是否激活
                if not user.get('is_active', True):
                    logger.warning(f"API Key 验证失败: 账户已禁用 - user_id={user['id']}")
                    return None
                
                # 非管理员检查过期
                if user.get('role') != self.ROLE_ADMIN:
                    expires_at = user.get('expires_at')
                    if expires_at and expires_at < datetime.now():
                        logger.warning(f"API Key 验证失败: 账户已过期 - user_id={user['id']}")
                        return None
                
                return user
                
        except Exception as e:
            logger.error(f"验证 API Key 失败: {e}")
            return None

    def revoke_user_api_key(self, user_id: int) -> bool:
        """
        撤销用户的 API Key

        Args:
            user_id: 用户 ID

        Returns:
            是否撤销成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE users
                    SET api_key = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (user_id,))
                
                if cursor.rowcount > 0:
                    logger.info(f"用户 API Key 撤销成功: user_id={user_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"撤销 API Key 失败: {e}")
            return False

    def get_user_api_key(self, user_id: int) -> Optional[str]:
        """
        获取用户的 API Key

        Args:
            user_id: 用户 ID

        Returns:
            API Key 字符串，无则返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT api_key FROM users WHERE id = %s",
                    (user_id,)
                )
                
                result = cursor.fetchone()
                if result and result[0]:
                    return result[0]
                return None
                
        except Exception as e:
            logger.error(f"获取 API Key 失败: {e}")
            return None
