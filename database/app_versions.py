"""
应用版本管理模块 (PostgreSQL)
用于存储和管理应用程序版本信息
"""
from typing import Optional, Dict, List
from datetime import datetime
from psycopg2 import extras
from loguru import logger


class AppVersionsOps:
    """应用版本相关数据库操作"""

    # ==================== 版本管理 ====================

    def create_app_version(
        self,
        version: str,
        version_name: str = '',
        description: str = '',
        release_notes: str = '',
        download_url: str = '',
        is_force_update: bool = False,
        is_visible: bool = True,
        min_supported_version: str = '',
        platform: str = 'all',
        created_by: Optional[int] = None
    ) -> Optional[Dict]:
        """
        创建新版本

        Args:
            version: 版本号（如 1.0.0）
            version_name: 版本名称/别名
            description: 版本描述
            release_notes: 更新日志
            download_url: 下载链接
            is_force_update: 是否强制更新
            is_visible: 是否对用户可见
            min_supported_version: 最低支持版本
            platform: 平台 (all/android/ios/web)
            created_by: 创建者用户ID

        Returns:
            创建成功返回版本信息，失败返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 检查版本号是否已存在
                cursor.execute(
                    "SELECT id FROM app_versions WHERE version = %s AND platform = %s",
                    (version, platform)
                )
                if cursor.fetchone():
                    logger.warning(f"创建版本失败: 版本 {version} ({platform}) 已存在")
                    return None
                
                # 插入版本
                cursor.execute("""
                    INSERT INTO app_versions (
                        version, version_name, description, release_notes,
                        download_url, is_force_update, is_visible,
                        min_supported_version, platform, created_by,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id, version, version_name, description, release_notes,
                              download_url, is_force_update, is_visible,
                              min_supported_version, platform, created_by,
                              created_at, updated_at
                """, (
                    version, version_name, description, release_notes,
                    download_url, is_force_update, is_visible,
                    min_supported_version, platform, created_by
                ))
                
                app_version = cursor.fetchone()
                if app_version:
                    logger.info(f"版本创建成功: {version} ({platform})")
                    return dict(app_version)
                return None
                
        except Exception as e:
            logger.error(f"创建版本失败: {e}")
            return None

    def get_app_version(self, version_id: int) -> Optional[Dict]:
        """
        获取版本信息

        Args:
            version_id: 版本ID

        Returns:
            版本信息
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, version, version_name, description, release_notes,
                           download_url, is_force_update, is_visible,
                           min_supported_version, platform, created_by,
                           created_at, updated_at
                    FROM app_versions
                    WHERE id = %s
                """, (version_id,))
                
                app_version = cursor.fetchone()
                return dict(app_version) if app_version else None
                
        except Exception as e:
            logger.error(f"获取版本失败: {e}")
            return None

    def get_app_version_by_version(self, version: str, platform: str = 'all') -> Optional[Dict]:
        """
        通过版本号获取版本信息

        Args:
            version: 版本号
            platform: 平台

        Returns:
            版本信息
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                cursor.execute("""
                    SELECT id, version, version_name, description, release_notes,
                           download_url, is_force_update, is_visible,
                           min_supported_version, platform, created_by,
                           created_at, updated_at
                    FROM app_versions
                    WHERE version = %s AND platform = %s
                """, (version, platform))
                
                app_version = cursor.fetchone()
                return dict(app_version) if app_version else None
                
        except Exception as e:
            logger.error(f"获取版本失败: {e}")
            return None

    def get_app_versions(
        self,
        is_visible: Optional[bool] = None,
        platform: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        获取版本列表

        Args:
            is_visible: 是否可见筛选
            platform: 平台筛选
            limit: 每页数量
            offset: 偏移量

        Returns:
            版本列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 构建查询条件
                conditions = []
                params = []
                
                if is_visible is not None:
                    conditions.append("is_visible = %s")
                    params.append(is_visible)
                
                if platform:
                    conditions.append("platform = %s")
                    params.append(platform)
                
                where_clause = " AND ".join(conditions) if conditions else "1=1"
                
                cursor.execute(f"""
                    SELECT id, version, version_name, description, release_notes,
                           download_url, is_force_update, is_visible,
                           min_supported_version, platform, created_by,
                           created_at, updated_at
                    FROM app_versions
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"获取版本列表失败: {e}")
            return []

    def get_latest_version(self, platform: str = 'all', visible_only: bool = True) -> Optional[Dict]:
        """
        获取最新版本

        Args:
            platform: 平台
            visible_only: 是否只获取可见版本

        Returns:
            最新版本信息
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                conditions = ["platform = %s"]
                params = [platform]
                
                if visible_only:
                    conditions.append("is_visible = TRUE")
                
                where_clause = " AND ".join(conditions)
                
                cursor.execute(f"""
                    SELECT id, version, version_name, description, release_notes,
                           download_url, is_force_update, is_visible,
                           min_supported_version, platform, created_by,
                           created_at, updated_at
                    FROM app_versions
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT 1
                """, params)
                
                app_version = cursor.fetchone()
                return dict(app_version) if app_version else None
                
        except Exception as e:
            logger.error(f"获取最新版本失败: {e}")
            return None

    def update_app_version(
        self,
        version_id: int,
        version_name: Optional[str] = None,
        description: Optional[str] = None,
        release_notes: Optional[str] = None,
        download_url: Optional[str] = None,
        is_force_update: Optional[bool] = None,
        is_visible: Optional[bool] = None,
        min_supported_version: Optional[str] = None
    ) -> Optional[Dict]:
        """
        更新版本信息

        Args:
            version_id: 版本ID
            version_name: 版本名称
            description: 版本描述
            release_notes: 更新日志
            download_url: 下载链接
            is_force_update: 是否强制更新
            is_visible: 是否可见
            min_supported_version: 最低支持版本

        Returns:
            更新后的版本信息
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
                
                # 构建更新语句
                updates = ["updated_at = CURRENT_TIMESTAMP"]
                params = []
                
                if version_name is not None:
                    updates.append("version_name = %s")
                    params.append(version_name)
                
                if description is not None:
                    updates.append("description = %s")
                    params.append(description)
                
                if release_notes is not None:
                    updates.append("release_notes = %s")
                    params.append(release_notes)
                
                if download_url is not None:
                    updates.append("download_url = %s")
                    params.append(download_url)
                
                if is_force_update is not None:
                    updates.append("is_force_update = %s")
                    params.append(is_force_update)
                
                if is_visible is not None:
                    updates.append("is_visible = %s")
                    params.append(is_visible)
                
                if min_supported_version is not None:
                    updates.append("min_supported_version = %s")
                    params.append(min_supported_version)
                
                if len(updates) == 1:  # 只有 updated_at
                    return self.get_app_version(version_id)
                
                params.append(version_id)
                
                cursor.execute(f"""
                    UPDATE app_versions
                    SET {', '.join(updates)}
                    WHERE id = %s
                    RETURNING id, version, version_name, description, release_notes,
                              download_url, is_force_update, is_visible,
                              min_supported_version, platform, created_by,
                              created_at, updated_at
                """, params)
                
                app_version = cursor.fetchone()
                if app_version:
                    logger.info(f"版本更新成功: id={version_id}")
                    return dict(app_version)
                return None
                
        except Exception as e:
            logger.error(f"更新版本失败: {e}")
            return None

    def delete_app_version(self, version_id: int) -> bool:
        """
        删除版本

        Args:
            version_id: 版本ID

        Returns:
            是否删除成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "DELETE FROM app_versions WHERE id = %s",
                    (version_id,)
                )
                
                if cursor.rowcount > 0:
                    logger.info(f"版本删除成功: id={version_id}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"删除版本失败: {e}")
            return False

    def toggle_version_visibility(self, version_id: int, is_visible: bool) -> bool:
        """
        切换版本可见性

        Args:
            version_id: 版本ID
            is_visible: 是否可见

        Returns:
            是否成功
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE app_versions
                    SET is_visible = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (is_visible, version_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"版本可见性更新成功: id={version_id}, is_visible={is_visible}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"切换版本可见性失败: {e}")
            return False

    def check_version_update(self, current_version: str, platform: str = 'all') -> Optional[Dict]:
        """
        检查版本更新

        Args:
            current_version: 当前版本号
            platform: 平台

        Returns:
            如果有更新返回最新版本信息，否则返回 None
        """
        try:
            latest = self.get_latest_version(platform, visible_only=True)
            
            if not latest:
                return None
            
            # 简单的版本比较（假设版本格式为 x.y.z）
            def parse_version(v: str) -> tuple:
                parts = v.split('.')
                return tuple(int(p) for p in parts if p.isdigit())
            
            try:
                current = parse_version(current_version)
                newest = parse_version(latest['version'])
                
                if newest > current:
                    return {
                        'has_update': True,
                        'latest_version': latest,
                        'is_force_update': latest.get('is_force_update', False)
                    }
            except Exception:
                pass
            
            return {'has_update': False}
                
        except Exception as e:
            logger.error(f"检查版本更新失败: {e}")
            return None
