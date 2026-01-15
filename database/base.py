"""
数据库基础模块
提供 PostgreSQL 连接池和通用工具方法
"""
import psycopg2
from psycopg2 import pool, extras
from contextlib import contextmanager
from loguru import logger

from config.settings import settings


class DatabaseBase:
    """数据库基础类，提供 PostgreSQL 连接池管理和通用方法"""

    _pool: pool.ThreadedConnectionPool = None

    def __init__(self):
        """初始化数据库连接池"""
        self._ensure_pool()

    @classmethod
    def _ensure_pool(cls):
        """确保连接池已创建"""
        if cls._pool is None:
            try:
                cls._pool = pool.ThreadedConnectionPool(
                    minconn=settings.postgres.min_connections,
                    maxconn=settings.postgres.max_connections,
                    host=settings.postgres.host,
                    port=settings.postgres.port,
                    user=settings.postgres.user,
                    password=settings.postgres.password,
                    database=settings.postgres.database
                )
                logger.info(f"PostgreSQL 连接池创建成功: {settings.postgres.host}:{settings.postgres.port}")
            except Exception as e:
                logger.error(f"PostgreSQL 连接池创建失败: {e}")
                raise

    @classmethod
    def close_pool(cls):
        """关闭连接池"""
        if cls._pool is not None:
            cls._pool.closeall()
            cls._pool = None
            logger.info("PostgreSQL 连接池已关闭")

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        self._ensure_pool()
        conn = self._pool.getconn()
        try:
            # 使用 RealDictCursor 使结果可通过字典方式访问
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def _get_cursor(self, dict_cursor: bool = True):
        """获取游标的上下文管理器"""
        with self._get_connection() as conn:
            cursor_factory = extras.RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

    def _column_exists(self, cursor, table: str, column: str) -> bool:
        """检查列是否存在"""
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            )
        """, (table, column))
        return cursor.fetchone()[0]

    def _migrate_add_column_if_not_exists(self, cursor, table: str, column: str, column_def: str):
        """安全地添加列（如果不存在）"""
        if not self._column_exists(cursor, table, column):
            # 转换 SQLite 类型到 PostgreSQL 类型
            pg_column_def = self._convert_column_def(column_def)
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {pg_column_def}')
            logger.info(f"数据库迁移: 添加列 {table}.{column}")

    def _convert_column_def(self, sqlite_def: str) -> str:
        """将 SQLite 列定义转换为 PostgreSQL 格式"""
        # 移除 DEFAULT 值中的双引号
        result = sqlite_def.replace('"', "'")
        # BOOLEAN DEFAULT FALSE/TRUE
        result = result.replace('BOOLEAN DEFAULT FALSE', 'BOOLEAN DEFAULT FALSE')
        result = result.replace('BOOLEAN DEFAULT TRUE', 'BOOLEAN DEFAULT TRUE')
        return result
