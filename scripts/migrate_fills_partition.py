"""
将 trader_fills 表迁移为分区表

分区策略：按时间（月）分区
- 每个月的数据存储在独立分区中
- 查询特定时间范围时只扫描相关分区
- 可以轻松删除旧数据（DROP 分区）

运行方式：
    python scripts/migrate_fills_partition.py

注意：
1. 迁移过程中会创建新表并复制数据，需要足够的磁盘空间
2. 对于 3000 万+ 条数据，迁移可能需要 30-60 分钟
3. 建议在低峰期执行
4. 执行前请备份数据！
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from loguru import logger
from config.settings import settings


def get_connection():
    """直接获取数据库连接（不使用连接池）"""
    return psycopg2.connect(
        host=settings.postgres.host,
        port=settings.postgres.port,
        user=settings.postgres.user,
        password=settings.postgres.password,
        database=settings.postgres.database
    )


def migrate_to_partitioned_table():
    """将 trader_fills 迁移为分区表"""
    conn = get_connection()
    conn.autocommit = False
    cursor = conn.cursor()
    
    try:
        # 1. 检查是否已经是分区表
        cursor.execute("""
            SELECT 1 FROM pg_partitioned_table pt
            JOIN pg_class c ON pt.partrelid = c.oid
            WHERE c.relname = 'trader_fills'
        """)
        if cursor.fetchone():
            logger.info("trader_fills 已经是分区表，无需迁移")
            return
        
        # 2. 获取当前表的数据量和时间范围
        cursor.execute("SELECT COUNT(*) FROM trader_fills")
        total_count = cursor.fetchone()[0]
        logger.info(f"当前 trader_fills 表共有 {total_count:,} 条记录")
        
        if total_count == 0:
            logger.info("表为空，直接创建分区表结构")
            create_empty_partitioned_table(cursor)
            conn.commit()
            return
        
        cursor.execute("""
            SELECT 
                MIN(time) as min_time,
                MAX(time) as max_time,
                MIN(DATE_TRUNC('month', to_timestamp(time/1000))) as min_month,
                MAX(DATE_TRUNC('month', to_timestamp(time/1000))) as max_month
            FROM trader_fills
        """)
        row = cursor.fetchone()
        min_month, max_month = row[2], row[3]
        logger.info(f"数据时间范围: {min_month} 至 {max_month}")
        
        # 3. 重命名旧表
        logger.info("步骤 1/5: 重命名旧表...")
        cursor.execute("ALTER TABLE trader_fills RENAME TO trader_fills_old")
        conn.commit()
        
        # 4. 创建分区主表
        logger.info("步骤 2/5: 创建分区主表...")
        # 注意：分区表的唯一约束必须包含分区键(time)
        cursor.execute("""
            CREATE TABLE trader_fills (
                id SERIAL,
                address TEXT NOT NULL,
                coin TEXT,
                side TEXT,
                px NUMERIC,
                sz NUMERIC,
                time BIGINT NOT NULL,
                trade_time TIMESTAMP,
                closed_pnl NUMERIC,
                hash TEXT,
                start_position NUMERIC,
                dir TEXT,
                crossed BOOLEAN,
                fee NUMERIC,
                oid BIGINT,
                tid BIGINT,
                trade_type INTEGER,
                PRIMARY KEY (id, time),
                UNIQUE (address, tid, time)
            ) PARTITION BY RANGE (time)
        """)
        conn.commit()
        
        # 5. 创建分区（按月）
        logger.info("步骤 3/5: 创建分区...")
        create_monthly_partitions(cursor, min_month, max_month)
        conn.commit()
        
        # 6. 复制数据
        logger.info("步骤 4/5: 复制数据（这可能需要较长时间）...")
        cursor.execute("""
            INSERT INTO trader_fills (
                address, coin, side, px, sz, time, trade_time,
                closed_pnl, hash, start_position, dir, crossed, fee, oid, tid, trade_type
            )
            SELECT 
                address, coin, side, px, sz, time, trade_time,
                closed_pnl, hash, start_position, dir, crossed, fee, oid, tid, trade_type
            FROM trader_fills_old
        """)
        inserted = cursor.rowcount
        logger.info(f"已复制 {inserted:,} 条记录")
        conn.commit()
        
        # 7. 创建索引
        logger.info("步骤 5/5: 创建索引...")
        create_partition_indexes(cursor)
        conn.commit()
        
        # 8. 验证数据
        cursor.execute("SELECT COUNT(*) FROM trader_fills")
        new_count = cursor.fetchone()[0]
        
        if new_count == total_count:
            logger.info(f"数据验证通过: 原 {total_count:,} 条，新 {new_count:,} 条")
            
            # 删除旧表
            logger.info("删除旧表...")
            cursor.execute("DROP TABLE trader_fills_old")
            conn.commit()
            logger.info("迁移完成！")
        else:
            logger.error(f"数据数量不匹配！原 {total_count:,} 条，新 {new_count:,} 条")
            logger.error("保留旧表 trader_fills_old，请手动检查")
            
    except Exception as e:
        conn.rollback()
        logger.error(f"迁移失败: {e}")
        
        # 尝试恢复旧表名
        try:
            cursor.execute("""
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'trader_fills_old'
            """)
            if cursor.fetchone():
                cursor.execute("DROP TABLE IF EXISTS trader_fills")
                cursor.execute("ALTER TABLE trader_fills_old RENAME TO trader_fills")
                conn.commit()
                logger.info("已恢复原表")
        except:
            pass
        raise
    finally:
        cursor.close()
        conn.close()


def create_empty_partitioned_table(cursor):
    """创建空的分区表结构"""
    cursor.execute("DROP TABLE IF EXISTS trader_fills CASCADE")
    cursor.execute("""
        CREATE TABLE trader_fills (
            id SERIAL,
            address TEXT NOT NULL,
            coin TEXT,
            side TEXT,
            px NUMERIC,
            sz NUMERIC,
            time BIGINT NOT NULL,
            trade_time TIMESTAMP,
            closed_pnl NUMERIC,
            hash TEXT,
            start_position NUMERIC,
            dir TEXT,
            crossed BOOLEAN,
            fee NUMERIC,
            oid BIGINT,
            tid BIGINT,
            trade_type INTEGER,
            PRIMARY KEY (id, time),
            UNIQUE (address, tid, time)
        ) PARTITION BY RANGE (time)
    """)
    
    # 创建默认分区和未来几个月的分区
    import pendulum
    now = pendulum.now()
    for i in range(-12, 13):  # 过去12个月到未来12个月
        month = now.add(months=i)
        create_partition_for_month(cursor, month)
    
    create_partition_indexes(cursor)


def create_monthly_partitions(cursor, min_month, max_month):
    """创建月度分区"""
    import pendulum
    
    # 从最早的月份创建到未来3个月
    current = pendulum.instance(min_month)
    end = pendulum.instance(max_month).add(months=3)
    
    while current <= end:
        create_partition_for_month(cursor, current)
        current = current.add(months=1)
    
    # 创建默认分区（处理超出范围的数据）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trader_fills_default
        PARTITION OF trader_fills DEFAULT
    """)
    logger.info("已创建默认分区")


def create_partition_for_month(cursor, month):
    """为指定月份创建分区"""
    import pendulum
    
    partition_name = f"trader_fills_{month.format('YYYY_MM')}"
    start_ts = int(month.start_of('month').timestamp() * 1000)
    end_ts = int(month.add(months=1).start_of('month').timestamp() * 1000)
    
    try:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF trader_fills
            FOR VALUES FROM ({start_ts}) TO ({end_ts})
        """)
        logger.debug(f"创建分区: {partition_name}")
    except psycopg2.errors.DuplicateTable:
        pass  # 分区已存在


def create_partition_indexes(cursor):
    """为分区表创建索引"""
    indexes = [
        ("idx_fills_address", "address"),
        ("idx_fills_time", "time DESC"),
        ("idx_fills_coin", "coin"),
        ("idx_fills_trade_type", "trade_type"),
        ("idx_fills_address_time", "address, time ASC"),
        ("idx_fills_trade_time", "trade_time DESC"),
    ]
    
    for idx_name, columns in indexes:
        try:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {idx_name}
                ON trader_fills({columns})
            """)
            logger.debug(f"创建索引: {idx_name}")
        except Exception as e:
            logger.warning(f"创建索引 {idx_name} 失败: {e}")


def add_future_partitions():
    """添加未来月份的分区（可定期运行）"""
    import pendulum
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # 添加未来 6 个月的分区
        now = pendulum.now()
        for i in range(1, 7):
            month = now.add(months=i)
            create_partition_for_month(cursor, month)
        
        conn.commit()
        logger.info("已添加未来 6 个月的分区")
    except Exception as e:
        conn.rollback()
        logger.error(f"添加分区失败: {e}")
    finally:
        cursor.close()
        conn.close()


def show_partition_info():
    """显示分区信息"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                child.relname AS partition_name,
                pg_size_pretty(pg_relation_size(child.oid)) AS size,
                (SELECT COUNT(*) FROM trader_fills WHERE time >= 
                    CASE WHEN child.relname ~ '_\\d{4}_\\d{2}$' 
                    THEN (regexp_matches(child.relname, '_(\\d{4})_(\\d{2})$'))[1]::int * 100000000000 
                    ELSE 0 END
                ) as approx_count
            FROM pg_inherits
            JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child ON pg_inherits.inhrelid = child.oid
            WHERE parent.relname = 'trader_fills'
            ORDER BY child.relname
        """)
        
        print("\n=== 分区信息 ===")
        print(f"{'分区名':<30} {'大小':<15}")
        print("-" * 45)
        
        for row in cursor.fetchall():
            print(f"{row[0]:<30} {row[1]:<15}")
            
    except Exception as e:
        # 可能不是分区表
        cursor.execute("SELECT COUNT(*) FROM trader_fills")
        count = cursor.fetchone()[0]
        print(f"\ntrader_fills 不是分区表，共 {count:,} 条记录")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="trader_fills 分区表管理")
    parser.add_argument("--migrate", action="store_true", help="执行迁移")
    parser.add_argument("--add-future", action="store_true", help="添加未来分区")
    parser.add_argument("--info", action="store_true", help="显示分区信息")
    
    args = parser.parse_args()
    
    if args.migrate:
        logger.warning("=" * 60)
        logger.warning("警告：此操作将迁移 trader_fills 表为分区表")
        logger.warning("请确保已备份数据！")
        logger.warning("=" * 60)
        
        confirm = input("确认执行迁移？(yes/no): ")
        if confirm.lower() == 'yes':
            migrate_to_partitioned_table()
        else:
            logger.info("已取消")
    elif args.add_future:
        add_future_partitions()
    elif args.info:
        show_partition_info()
    else:
        parser.print_help()
