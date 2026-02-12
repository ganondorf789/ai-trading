"""
清空数据库所有表数据（保留表结构）
或删除所有表（包括表结构）
"""
import sys
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import TraderDatabase


def truncate_all_tables():
    """清空所有表数据（保留表结构）"""
    db = TraderDatabase()
    
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            logger.info("=" * 70)
            logger.info("清空所有表数据")
            logger.info("=" * 70)
            
            # 获取所有表名
            cursor.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"找到 {len(tables)} 个表:")
            for table in tables:
                logger.info(f"  - {table}")
            
            # 确认操作
            logger.warning("\n⚠️  警告：此操作将清空所有表的数据！")
            response = input("确定要继续吗？(输入 'yes' 确认): ")
            
            if response.lower() != 'yes':
                logger.info("操作已取消")
                return
            
            # 清空所有表
            logger.info("\n开始清空表数据...")
            for table in tables:
                try:
                    cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
                    logger.info(f"✓ 已清空表: {table}")
                except Exception as e:
                    logger.error(f"✗ 清空表 {table} 失败: {e}")
            
            conn.commit()
            logger.success("\n✓ 所有表数据已清空")
            
    except Exception as e:
        logger.error(f"操作失败: {e}")
        raise
    finally:
        db.close()


def drop_all_tables():
    """删除所有表（包括表结构）"""
    db = TraderDatabase()
    
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            
            logger.info("=" * 70)
            logger.info("删除所有表")
            logger.info("=" * 70)
            
            # 获取所有表名
            cursor.execute("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"找到 {len(tables)} 个表:")
            for table in tables:
                logger.info(f"  - {table}")
            
            # 确认操作
            logger.warning("\n⚠️  警告：此操作将删除所有表及其结构！")
            logger.warning("     数据库将完全清空，需要重新初始化！")
            response = input("确定要继续吗？(输入 'DELETE ALL' 确认): ")
            
            if response != 'DELETE ALL':
                logger.info("操作已取消")
                return
            
            # 删除所有表
            logger.info("\n开始删除表...")
            for table in tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    logger.info(f"✓ 已删除表: {table}")
                except Exception as e:
                    logger.error(f"✗ 删除表 {table} 失败: {e}")
            
            conn.commit()
            logger.success("\n✓ 所有表已删除")
            logger.info("下次运行程序时会自动重新创建表结构")
            
    except Exception as e:
        logger.error(f"操作失败: {e}")
        raise
    finally:
        db.close()


def drop_database():
    """完全删除数据库（需要超级用户权限）"""
    logger.warning("=" * 70)
    logger.warning("删除整个数据库")
    logger.warning("=" * 70)
    logger.warning("此操作需要在 PostgreSQL 中手动执行")
    logger.info("\n请使用以下命令：")
    logger.info("1. 连接到 PostgreSQL:")
    logger.info("   docker exec -it auto-trading-postgres psql -U trading")
    logger.info("")
    logger.info("2. 切换到 postgres 数据库:")
    logger.info("   \\c postgres")
    logger.info("")
    logger.info("3. 强制断开所有连接:")
    logger.info("   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'autotrading';")
    logger.info("")
    logger.info("4. 删除数据库:")
    logger.info("   DROP DATABASE autotrading;")
    logger.info("")
    logger.info("5. 重新创建数据库:")
    logger.info("   CREATE DATABASE autotrading OWNER trading;")
    logger.info("")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据库清理工具")
    parser.add_argument(
        "action",
        choices=["truncate", "drop-tables", "drop-db"],
        help="操作类型: truncate(清空数据), drop-tables(删除所有表), drop-db(显示删除数据库命令)"
    )
    
    args = parser.parse_args()
    
    if args.action == "truncate":
        truncate_all_tables()
    elif args.action == "drop-tables":
        drop_all_tables()
    elif args.action == "drop-db":
        drop_database()