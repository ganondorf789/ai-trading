"""
S级交易员历史交易记录获取脚本

功能说明：
1. 从 trader_metrics 表筛选出 S级评分 且 交易数大于2000 的交易员
2. 获取这些交易员的完整历史交易记录
3. 保存到 trader_fills 表中

策略（参考 fetch_all_fills_optimized.py）：
- 先用 user_fills 获取最近的 2000 条记录
- 找到最早的交易时间，从这个时间往前按月查找
- 连续 3 个月没有订单则停止
- 自适应4层细分策略：按月 → 按周 → 按天 → 按小时
"""
import sys
from pathlib import Path
import pendulum
from loguru import logger
import time
from typing import List, Dict, Optional
import argparse

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from screener.api_client import SyncAPIClient
from screener.config import APIConfig
from screener.utils import SHANGHAI_TZ, timestamp_to_pendulum
from database import TraderDatabase


def fetch_fills_for_period(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    auto_split: bool = True
) -> List[Dict]:
    """
    获取指定时间段的交易记录
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 开始时间
        end_dt: 结束时间
        auto_split: 如果达到 2000 条，是否自动细分
    
    Returns:
        交易记录列表
    """
    fills = client.get_user_fills_by_time(
        address,
        int(start_dt.timestamp() * 1000),
        int(end_dt.timestamp() * 1000)
    )
    
    if not fills:
        return []
    
    # 如果达到上限且允许自动细分
    if auto_split and len(fills) >= 2000 and (end_dt - start_dt).days > 1:
        logger.warning(f"  该月达到 2000 条上限，按周细分...")
        return fetch_fills_by_weeks(client, address, start_dt, end_dt)
    
    return fills


def fetch_fills_by_weeks(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime
) -> List[Dict]:
    """按周获取交易记录"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_week = min(current.add(weeks=1), end_dt)
        
        logger.info(f"    [{current.format('MM-DD')} 至 {next_week.format('MM-DD')}]...")
        
        week_fills = client.get_user_fills_by_time(
            address,
            int(current.timestamp() * 1000),
            int(next_week.timestamp() * 1000)
        )
        
        if week_fills:
            logger.info(f"      获取 {len(week_fills)} 条")
            
            # 如果这周还达到 2000 条，按天细分
            if len(week_fills) >= 2000:
                logger.warning(f"      单周达到 2000 条，按天细分...")
                day_fills = fetch_fills_by_days(client, address, current, next_week)
                all_fills.extend(day_fills)
            else:
                all_fills.extend(week_fills)
        else:
            logger.info(f"      0 条")
        
        current = next_week
        time.sleep(3.0)
    
    return all_fills


def fetch_fills_by_days(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime
) -> List[Dict]:
    """按天获取交易记录"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_day = min(current.add(days=1), end_dt)
        
        day_fills = client.get_user_fills_by_time(
            address,
            int(current.timestamp() * 1000),
            int(next_day.timestamp() * 1000)
        )
        
        if day_fills:
            if len(day_fills) >= 2000:
                logger.warning(f"        {current.format('MM-DD')}: {len(day_fills)} 条（达到上限，按小时细分...）")
                hour_fills = fetch_fills_by_hours(client, address, current, next_day)
                all_fills.extend(hour_fills)
            else:
                logger.info(f"        {current.format('MM-DD')}: {len(day_fills)} 条")
                all_fills.extend(day_fills)
        
        current = next_day
        time.sleep(3.0)
    
    return all_fills


def fetch_fills_by_hours(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime
) -> List[Dict]:
    """按小时获取交易记录（用于极度活跃的交易日）"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_hour = min(current.add(hours=1), end_dt)
        
        hour_fills = client.get_user_fills_by_time(
            address,
            int(current.timestamp() * 1000),
            int(next_hour.timestamp() * 1000)
        )
        
        if hour_fills:
            all_fills.extend(hour_fills)
            if len(hour_fills) >= 2000:
                logger.error(f"          {current.format('MM-DD HH:00')}: {len(hour_fills)} 条（单小时达到2000条上限！无法进一步细分）")
            elif len(hour_fills) >= 500:
                logger.warning(f"          {current.format('MM-DD HH:00')}: {len(hour_fills)} 条")
            else:
                logger.info(f"          {current.format('MM-DD HH:00')}: {len(hour_fills)} 条")
        
        current = next_hour
        time.sleep(3.0)
    
    return all_fills


def fetch_and_save_fills_for_trader(
    client: SyncAPIClient,
    db: TraderDatabase,
    address: str,
    empty_months_threshold: int = 3,
    batch_size: int = 5000
) -> int:
    """
    获取单个交易者的所有交易记录并分批保存到数据库
    
    采用分批处理策略，避免内存溢出：
    - 每获取一批数据（达到 batch_size）就保存到数据库
    - 使用 set 记录已处理的 oid+time 组合用于去重，而不是存储完整记录
    
    Args:
        client: API 客户端
        db: 数据库实例
        address: 交易者地址
        empty_months_threshold: 连续多少个空月份后停止
        batch_size: 批量保存的阈值
    
    Returns:
        保存的记录总数
    """
    total_saved = 0
    pending_fills = []  # 待保存的记录
    seen_keys = set()   # 已处理的记录键（用于去重，只存储键而非完整记录）
    
    def save_batch():
        """保存当前批次并清空"""
        nonlocal total_saved, pending_fills
        if pending_fills:
            saved = db.save_fills(address, pending_fills)
            total_saved += saved
            logger.info(f"    💾 批量保存 {saved} 条（累计: {total_saved}）")
            pending_fills = []  # 清空待保存列表，释放内存
    
    def add_fills(fills: List[Dict]):
        """添加记录到待保存列表，自动去重和批量保存"""
        nonlocal pending_fills
        for fill in fills:
            key = (fill.get('oid'), fill.get('time'))
            if key not in seen_keys:
                seen_keys.add(key)
                pending_fills.append(fill)
        
        # 达到批量保存阈值时保存
        if len(pending_fills) >= batch_size:
            save_batch()
    
    # 步骤1：获取最近的 2000 条记录
    logger.info(f"  获取最近的 2000 条记录...")
    recent_fills = client.get_user_fills(address, limit=0)
    
    if not recent_fills:
        logger.warning(f"  该地址没有任何交易记录")
        return 0
    
    logger.info(f"  ✓ 获取到 {len(recent_fills)} 条最近记录")
    
    # 分析时间范围
    times = [fill.get('time', 0) for fill in recent_fills]
    earliest_recent_ms = min(times)
    earliest_recent_dt = timestamp_to_pendulum(earliest_recent_ms)
    
    logger.info(f"    最早记录: {earliest_recent_dt.to_datetime_string()}")
    
    # 添加最近的记录
    add_fills(recent_fills)
    del recent_fills  # 释放内存
    
    # 步骤2：往前按月查找历史记录
    current_end = earliest_recent_dt.start_of('month')
    empty_months_count = 0
    month_num = 0
    
    while empty_months_count < empty_months_threshold:
        current_start = current_end.subtract(months=1)
        month_num += 1
        
        logger.info(
            f"  [月份 {month_num}] {current_start.format('YYYY-MM-DD')} 至 "
            f"{current_end.format('YYYY-MM-DD')}..."
        )
        
        month_fills = fetch_fills_for_period(
            client, address, current_start, current_end, auto_split=True
        )
        
        if month_fills:
            old_seen_count = len(seen_keys)
            add_fills(month_fills)
            new_count = len(seen_keys) - old_seen_count
            
            logger.success(f"    ✓ 获取 {len(month_fills)} 条，新增 {new_count} 条")
            del month_fills  # 释放内存
            empty_months_count = 0
        else:
            logger.info(f"    - 无记录（连续 {empty_months_count + 1}/{empty_months_threshold} 个空月份）")
            empty_months_count += 1
        
        current_end = current_start
        time.sleep(3.0)
    
    # 保存剩余的记录
    save_batch()
    
    logger.info(f"  ✓ 总计保存 {total_saved} 条记录（去重后）")
    
    return total_saved


def get_s_rated_traders(db: TraderDatabase, min_trades: int = 2000) -> List[Dict]:
    """
    获取S级评分且交易数大于指定值的交易员
    
    Args:
        db: 数据库实例
        min_trades: 最小交易数
    
    Returns:
        符合条件的交易员列表
    """
    from psycopg2 import extras
    
    with db._get_connection() as conn:
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute("""
            SELECT address, total_trades, total_pnl, win_rate, overall_score
            FROM trader_metrics
            WHERE rating = 'S' AND total_trades > %s
            ORDER BY overall_score DESC
        """, (min_trades,))
        return [dict(row) for row in cursor.fetchall()]


def get_existing_fills_count(db: TraderDatabase, address: str) -> int:
    """获取交易员在数据库中已有的交易记录数"""
    from psycopg2 import extras
    
    with db._get_connection() as conn:
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute(
            "SELECT COUNT(*) as count FROM trader_fills WHERE address = %s",
            (address,)
        )
        result = cursor.fetchone()
        return result['count'] if result else 0


def main():
    parser = argparse.ArgumentParser(description="获取S级交易员的完整历史交易记录")
    parser.add_argument(
        "--min-trades", "-t",
        type=int,
        default=2000,
        help="最小交易数（默认: 2000）"
    )
    parser.add_argument(
        "--empty-months", "-e",
        type=int,
        default=3,
        help="连续多少个空月份后停止（默认: 3）"
    )
    parser.add_argument(
        "--skip-existing", "-s",
        action="store_true",
        help="跳过已有交易记录的交易员"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="仅显示符合条件的交易员，不获取数据"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="限制处理的交易员数量（0 表示不限制）"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("S级交易员历史交易记录获取工具")
    logger.info("=" * 80)
    logger.info(f"筛选条件: rating='S' AND total_trades > {args.min_trades}")
    logger.info(f"停止条件: 连续 {args.empty_months} 个月无记录")
    if args.skip_existing:
        logger.info("模式: 跳过已有交易记录的交易员")
    if args.dry_run:
        logger.info("模式: 仅预览，不获取数据")
    logger.info("")
    
    # 初始化数据库
    logger.info("初始化数据库连接...")
    db = TraderDatabase()
    
    # 获取符合条件的交易员
    traders = get_s_rated_traders(db, args.min_trades)
    
    if not traders:
        logger.warning("没有找到符合条件的交易员")
        db.close()
        return
    
    logger.info(f"找到 {len(traders)} 个符合条件的S级交易员:")
    logger.info("")
    
    for i, trader in enumerate(traders, 1):
        existing_fills = get_existing_fills_count(db, trader['address'])
        logger.info(
            f"  {i:>2}. {trader['address'][:10]}... | "
            f"交易数: {trader['total_trades']:>6} | "
            f"总盈亏: ${trader['total_pnl']:>12,.2f} | "
            f"胜率: {trader['win_rate']*100:>5.1f}% | "
            f"评分: {trader['overall_score']:.1f} | "
            f"已存记录: {existing_fills}"
        )
    
    if args.dry_run:
        logger.info("")
        logger.info("预览模式，已退出")
        db.close()
        return
    
    # 确认执行
    logger.info("")
    logger.info("准备开始获取交易记录...")
    logger.info("等待 5 秒后开始（按 Ctrl+C 取消）")
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        logger.warning("\n用户取消")
        db.close()
        return
    
    # 初始化 API 客户端
    logger.info("")
    logger.info("初始化 API 客户端...")
    
    config = APIConfig()
    config.api_call_delay = 3.0
    config.max_retries = 5
    config.retry_delay = 3.0
    
    max_init_retries = 3
    client = None
    
    for retry in range(max_init_retries):
        try:
            client = SyncAPIClient(config)
            logger.success("✓ API 客户端初始化成功")
            break
        except Exception as e:
            if retry < max_init_retries - 1:
                wait_time = (retry + 1) * 10
                logger.warning(f"API 客户端初始化失败，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"API 客户端初始化失败: {str(e)}")
                db.close()
                return
    
    if not client:
        db.close()
        return
    
    # 限制处理数量
    if args.limit > 0:
        traders = traders[:args.limit]
        logger.info(f"限制处理前 {args.limit} 个交易员")
    
    # 处理统计
    total_processed = 0
    total_fills_saved = 0
    skipped_count = 0
    error_count = 0
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("开始处理交易员")
    logger.info("=" * 80)
    
    for i, trader in enumerate(traders, 1):
        address = trader['address']
        
        logger.info("")
        logger.info(f"[{i}/{len(traders)}] 处理交易员: {address[:16]}...")
        
        # 检查是否跳过
        if args.skip_existing:
            existing_fills = get_existing_fills_count(db, address)
            if existing_fills > 0:
                logger.info(f"  ⏭ 已有 {existing_fills} 条记录，跳过")
                skipped_count += 1
                continue
        
        try:
            # 获取并保存所有交易记录（分批处理，避免内存溢出）
            saved_count = fetch_and_save_fills_for_trader(
                client,
                db,
                address,
                empty_months_threshold=args.empty_months,
                batch_size=5000  # 每 5000 条保存一次
            )
            
            if saved_count > 0:
                logger.success(f"  ✓ 总共保存 {saved_count} 条记录")
                total_fills_saved += saved_count
            else:
                logger.warning(f"  - 没有获取到交易记录")
            
            total_processed += 1
            
        except KeyboardInterrupt:
            logger.warning("\n用户中断")
            break
        except Exception as e:
            logger.error(f"  ✗ 处理失败: {repr(e)}")
            error_count += 1
            # 继续处理下一个
            continue
        
        # 每个交易员处理完后等待一段时间
        if i < len(traders):
            logger.info("  等待 10 秒后继续...")
            time.sleep(10)
    
    # 汇总统计
    logger.info("")
    logger.info("=" * 80)
    logger.info("处理完成")
    logger.info("=" * 80)
    logger.info(f"符合条件交易员: {len(traders)} 个")
    logger.info(f"成功处理:       {total_processed} 个")
    logger.info(f"跳过:           {skipped_count} 个")
    logger.info(f"失败:           {error_count} 个")
    logger.info(f"总保存记录:     {total_fills_saved} 条")
    
    db.close()


if __name__ == "__main__":
    main()
