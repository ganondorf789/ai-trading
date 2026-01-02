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


def fix_trade_type(db_path: str = "data/traders.db", batch_size: int = 10000):
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
    
    # 获取 ID 范围
    cursor.execute("SELECT MIN(id), MAX(id) FROM trader_fills WHERE trade_type IS NULL")
    row = cursor.fetchone()
    min_id, max_id = row[0], row[1]
    
    if min_id is None:
        print("✅ 没有需要修复的记录")
        conn.close()
        return
    
    # 统计需要修复的记录数
    cursor.execute("SELECT COUNT(*) FROM trader_fills WHERE trade_type IS NULL")
    total_to_fix = cursor.fetchone()[0]
    
    print(f"📊 需要修复的记录数: {total_to_fix}")
    print(f"📊 ID 范围: {min_id} ~ {max_id}")
    
    # 按 ID 范围分批处理
    fixed_count = 0
    skipped_count = 0
    current_id = min_id
    
    while current_id <= max_id:
        end_id = current_id + batch_size
        
        # 获取当前批次的记录
        cursor.execute("""
            SELECT id, dir, start_position FROM trader_fills 
            WHERE id >= ? AND id < ? AND trade_type IS NULL
        """, (current_id, end_id))
        
        rows = cursor.fetchall()
        
        if rows:
            # 分别处理可计算和不可计算的记录
            updates_with_type = []
            updates_unknown = []
            
            for row in rows:
                trade_type = calculate_trade_type(
                    row['dir'], 
                    float(row['start_position']) if row['start_position'] else 0
                )
                if trade_type:
                    updates_with_type.append((trade_type, row['id']))
                else:
                    # 无法计算的标记为 unknown，避免重复处理
                    updates_unknown.append((row['id'],))
            
            # 批量更新有效的 trade_type
            if updates_with_type:
                cursor.executemany("""
                    UPDATE trader_fills SET trade_type = ? WHERE id = ?
                """, updates_with_type)
                fixed_count += len(updates_with_type)
            
            # 批量更新无法计算的记录为 'unknown'
            if updates_unknown:
                cursor.executemany("""
                    UPDATE trader_fills SET trade_type = 'unknown' WHERE id = ?
                """, updates_unknown)
                skipped_count += len(updates_unknown)
            
            conn.commit()
        
        # 计算进度
        progress = min(100, (current_id - min_id) * 100 // (max_id - min_id + 1))
        print(f"\r✅ 进度: {progress}% | 已修复: {fixed_count} | 跳过: {skipped_count} | 当前ID: {current_id}", end="", flush=True)
        
        current_id = end_id
    
    print()  # 换行
    
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
        print(f"  {row['trade_type']:15} : {row['count']:>10} 条")
    
    # 检查还有多少记录没有 trade_type
    cursor.execute("SELECT COUNT(*) FROM trader_fills WHERE trade_type IS NULL")
    remaining = cursor.fetchone()[0]
    
    if remaining > 0:
        print(f"\n⚠️ 仍有 {remaining} 条记录没有 trade_type")
    else:
        print(f"\n✅ 所有记录都已处理完成！")
    
    conn.close()
    print(f"\n🎉 修复完成！有效修复 {fixed_count} 条，跳过 {skipped_count} 条")


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
        default=10000,
        help="每批处理的记录数 (默认: 10000)"
    )
    
    args = parser.parse_args()
    fix_trade_type(args.db, args.batch_size)
