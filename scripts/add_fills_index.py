"""
添加 trader_fills 表的关键索引

对于大量数据（如 3000+ 万条记录），缺少合适的复合索引会导致查询卡住。
此脚本添加 (address, time) 复合索引，优化按地址查询并按时间排序的操作。

运行方式：
    python scripts/add_fills_index.py

注意：索引创建可能需要几分钟到几十分钟，取决于数据量。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from loguru import logger
from config.settings import settings


def get_connection():
    """直接获取数据库连接（不使用连接池，无超时限制）"""
    return psycopg2.connect(
        host=settings.postgres.host,
        port=settings.postgres.port,
        user=settings.postgres.user,
        password=settings.postgres.password,
        database=settings.postgres.database
    )


def add_fills_index():
    """添加 trader_fills 表的复合索引"""
    conn = get_connection()
    cursor = conn.cursor()
    
    logger.info("检查并添加 trader_fills 表的复合索引...")
    logger.info("注意: 对于大量数据，此操作可能需要几分钟")
    
    try:
        # 检查索引是否已存在
        cursor.execute("""
            SELECT 1 FROM pg_indexes 
            WHERE tablename = 'trader_fills' 
            AND indexname = 'idx_fills_address_time'
        """)
        
        if cursor.fetchone():
            logger.info("索引 idx_fills_address_time 已存在，跳过创建")
            return
        
        # 获取表大小
        cursor.execute("""
            SELECT COUNT(*) as count FROM trader_fills
        """)
        count = cursor.fetchone()[0]
        logger.info(f"trader_fills 表共有 {count:,} 条记录")
        
        # 创建索引
        logger.info("开始创建索引 idx_fills_address_time (address, time ASC)...")
        logger.info("这可能需要一些时间，请耐心等待...")
        
        # 使用 CONCURRENTLY 选项，不阻塞其他操作（需要在事务外执行）
        conn.commit()  # 先提交当前事务
        conn.autocommit = True  # 启用自动提交
        
        try:
            cursor.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fills_address_time
                ON trader_fills(address, time ASC)
            """)
            logger.info("索引创建成功！")
        except Exception as e:
            logger.error(f"索引创建失败: {e}")
            logger.info("尝试使用普通方式创建索引...")
            conn.autocommit = False
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_address_time
                ON trader_fills(address, time ASC)
            """)
            conn.commit()
            logger.info("索引创建成功！")
        finally:
            conn.autocommit = False
        
        logger.info("完成！")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    add_fills_index()
