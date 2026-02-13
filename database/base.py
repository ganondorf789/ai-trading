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
                    database=settings.postgres.database,
                    # TCP Keepalive 参数，防止连接被中间设备断开
                    keepalives=1,  # 启用 keepalive
                    keepalives_idle=30,  # 空闲 30 秒后发送 keepalive 探测
                    keepalives_interval=10,  # 每 10 秒发送一次探测
                    keepalives_count=5  # 5 次探测失败后断开连接
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
    def _get_connection(self, timeout: int = 60, statement_timeout: str = '60s'):
        """
        获取数据库连接的上下文管理器
        
        Args:
            timeout: 获取连接的超时时间（秒），默认60秒
            statement_timeout: SQL语句超时时间，默认60秒，设为 '0' 表示不限制
        """
        import time
        self._ensure_pool()
        
        # 尝试获取连接，带超时
        start_time = time.time()
        conn = None
        while conn is None:
            try:
                conn = self._pool.getconn()
            except pool.PoolError:
                # 连接池耗尽，等待后重试
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"获取数据库连接超时（{timeout}秒）")
                time.sleep(0.1)
        
        try:
            # 设置语句超时，防止长时间查询阻塞
            if statement_timeout and statement_timeout != '0':
                cursor = conn.cursor()
                cursor.execute(f"SET statement_timeout = '{statement_timeout}'")
                cursor.close()
            
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

