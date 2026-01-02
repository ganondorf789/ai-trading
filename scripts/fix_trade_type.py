#!/usr/bin/env python3
"""
修复 trader_fills 表中的 trade_type 字段

根据 dir 和 start_position 字段计算并更新 trade_type
"""
import sqlite3
from pathlib import Path


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


def fix_trade_type(db_path: str = "data/traders.db", batch_size: int = 1000):
    """
    修复 trader_fills 表中的 trade_type 字段
    
    Args:
        db_path: 数据库路径
        batch_size: 每批处理的记录数
    """
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 检查 trade_type 列是否存在
    cursor.execute("PRAGMA table_info(trader_fills)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if 'trade_type' not in columns:
        print("⚠️ trade_type 列不存在，正在添加...")
        cursor.execute("ALTER TABLE trader_fills ADD COLUMN trade_type TEXT")
        conn.commit()
        print("✅ 已添加 trade_type 列")
    
    # 统计需要修复的记录数
    cursor.execute("""
        SELECT COUNT(*) FROM trader_fills 
        WHERE trade_type IS NULL AND dir IS NOT NULL
    """)
    total_to_fix = cursor.fetchone()[0]
    
    if total_to_fix == 0:
        print("✅ 没有需要修复的记录")
        conn.close()
        return
    
    print(f"📊 需要修复的记录数: {total_to_fix}")
    
    # 分批处理
    fixed_count = 0
    offset = 0
    
    while True:
        # 获取一批需要修复的记录
        cursor.execute("""
            SELECT id, dir, start_position FROM trader_fills 
            WHERE trade_type IS NULL AND dir IS NOT NULL
            LIMIT ?
        """, (batch_size,))
        
        rows = cursor.fetchall()
        if not rows:
            break
        
        # 批量更新
        updates = []
        for row in rows:
            trade_type = calculate_trade_type(
                row['dir'], 
                float(row['start_position']) if row['start_position'] else 0
            )
            if trade_type:
                updates.append((trade_type, row['id']))
        
        if updates:
            cursor.executemany("""
                UPDATE trader_fills SET trade_type = ? WHERE id = ?
            """, updates)
            conn.commit()
            fixed_count += len(updates)
        
        print(f"✅ 已修复 {fixed_count}/{total_to_fix} 条记录 ({fixed_count * 100 // total_to_fix}%)")
    
    # 统计修复结果
    cursor.execute("""
        SELECT trade_type, COUNT(*) as count 
        FROM trader_fills 
        WHERE trade_type IS NOT NULL
        GROUP BY trade_type
        ORDER BY count DESC
    """)
    
    print("\n📈 trade_type 分布统计:")
    print("-" * 40)
    for row in cursor.fetchall():
        print(f"  {row['trade_type']:15} : {row['count']:>8} 条")
    
    # 检查还有多少记录没有 trade_type
    cursor.execute("""
        SELECT COUNT(*) FROM trader_fills WHERE trade_type IS NULL
    """)
    remaining = cursor.fetchone()[0]
    
    if remaining > 0:
        print(f"\n⚠️ 仍有 {remaining} 条记录没有 trade_type（可能是 dir 字段为空）")
    else:
        print(f"\n✅ 所有记录都已修复完成！")
    
    conn.close()
    print(f"\n🎉 修复完成！共修复 {fixed_count} 条记录")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="修复 trader_fills 表中的 trade_type 字段")
    parser.add_argument(
        "--db", 
        default="data/traders.db",
        help="数据库路径 (默认: data/traders.db)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="每批处理的记录数 (默认: 1000)"
    )
    
    args = parser.parse_args()
    fix_trade_type(args.db, args.batch_size)

