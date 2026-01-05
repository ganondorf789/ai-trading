"""
数据库基础模块
提供数据库连接和通用工具方法
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from loguru import logger


class DatabaseBase:
    """数据库基础类，提供连接管理和通用方法"""

    DEFAULT_DB_PATH = "data/traders.db"

    def __init__(self, db_path: str = None):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _migrate_add_column_if_not_exists(self, cursor, table: str, column: str, column_def: str):
        """安全地添加列（如果不存在）"""
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
            logger.info(f"数据库迁移: 添加列 {table}.{column}")

    @staticmethod
    def calculate_trade_type(dir_val: str, start_position: float) -> str:
        """
        根据 dir 和 start_position 计算交易类型

        Args:
            dir_val: 方向字符串，如 'Open Long', 'Close Short' 等
            start_position: 开始仓位

        Returns:
            交易类型: open_long/add_long/close_long/open_short/add_short/close_short
        """
        if not dir_val:
            return None

        start_pos = start_position or 0

        if 'Open' in dir_val:
            if 'Long' in dir_val:
                return 'open_long' if start_pos == 0 else 'add_long'
            elif 'Short' in dir_val:
                return 'open_short' if start_pos == 0 else 'add_short'
        elif 'Close' in dir_val:
            if 'Long' in dir_val:
                return 'close_long'
            elif 'Short' in dir_val:
                return 'close_short'

        return None
