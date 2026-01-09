"""
优化的交易记录完整获取策略

策略说明：
1. 先用 user_fills 获取最近的 2000 条记录
2. 找到最早的交易时间（如 12/31）
3. 从这个时间往前按月查找，直到连续 3 个月都没有订单
4. 自适应4层细分策略：
   - 按月获取 → 如果达到 2000 条，按周细分
   - 按周获取 → 如果达到 2000 条，按天细分
   - 按天获取 → 如果达到 2000 条，按小时细分
   - 按小时获取 → 如果还达到 2000 条，记录警告（无法进一步细分）

优势：
- 避免预设时间范围过大或过小
- 从已知最早时间往前推，更准确
- 自适应停止条件，节省 API 调用
- 4层细分策略，最大程度获取完整数据
- 每次API调用后等待3秒，避免速率限制
"""
import sys
from pathlib import Path
import pendulum
from loguru import logger
from collections import defaultdict
import time
from typing import List, Dict, Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from screener.api_client import SyncAPIClient
from screener.config import APIConfig
from screener.utils import SHANGHAI_TZ, timestamp_to_pendulum


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
    """
    按周获取交易记录
    """
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_week = min(current.add(weeks=1), end_dt)
        
        logger.info(f"    [{current.format('MM-DD')} 至 {next_week.format('MM-DD')}]...", end="")
        
        week_fills = client.get_user_fills_by_time(
            address,
            int(current.timestamp() * 1000),
            int(next_week.timestamp() * 1000)
        )
        
        if week_fills:
            logger.info(f" {len(week_fills)} 条")
            all_fills.extend(week_fills)
            
            # 如果这周还达到 2000 条，按天细分
            if len(week_fills) >= 2000:
                logger.warning(f"      单周达到 2000 条，按天细分...")
                day_fills = fetch_fills_by_days(client, address, current, next_week)
                all_fills = all_fills[:-len(week_fills)]  # 移除周数据
                all_fills.extend(day_fills)
        else:
            logger.info(" 0 条")
        
        current = next_week
        time.sleep(3.0)  # 每次API调用后等待3秒
    
    return all_fills


def fetch_fills_by_days(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime
) -> List[Dict]:
    """
    按天获取交易记录
    """
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
                # 按小时细分
                hour_fills = fetch_fills_by_hours(client, address, current, next_day)
                all_fills.extend(hour_fills)
            else:
                logger.info(f"        {current.format('MM-DD')}: {len(day_fills)} 条")
                all_fills.extend(day_fills)
        
        current = next_day
        time.sleep(3.0)  # 每次API调用后等待3秒
    
    return all_fills


def fetch_fills_by_hours(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime
) -> List[Dict]:
    """
    按小时获取交易记录（用于极度活跃的交易日）
    """
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
        time.sleep(3.0)  # 每次API调用后等待3秒
    
    return all_fills


def fetch_all_fills_smart(
    address: str,
    empty_months_threshold: int = 3,
    verbose: bool = True
) -> List[Dict]:
    """
    智能获取交易者的所有交易记录
    
    Args:
        address: 交易者地址
        empty_months_threshold: 连续多少个空月份后停止
        verbose: 是否显示详细信息
    
    Returns:
        所有交易记录列表（已去重）
    """
    logger.info("=" * 80)
    logger.info(f"智能获取完整交易记录")
    logger.info("=" * 80)
    logger.info(f"地址: {address}")
    logger.info(f"停止条件: 连续 {empty_months_threshold} 个月无记录")
    logger.info("")
    
    # 初始化 API 客户端
    config = APIConfig()
    config.api_call_delay = 3.0  # 每次API调用后等待3秒
    config.max_retries = 5
    config.retry_delay = 3.0
    
    logger.info("初始化 API 客户端...")
    logger.info("等待 5 秒以避免速率限制...")
    time.sleep(5)  # 增加初始延迟
    
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
                logger.warning(f"API 客户端初始化失败（速率限制），等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"API 客户端初始化失败: {str(e)}")
                logger.error("建议等待 1-2 分钟后再试")
                return []
    
    if not client:
        return []
    
    # ==================== 第1步：获取最近的记录 ====================
    logger.info("")
    logger.info("[步骤 1] 获取最近的 2000 条记录...")
    recent_fills = client.get_user_fills(address, limit=0)
    
    if not recent_fills:
        logger.warning("该地址没有任何交易记录")
        return []
    
    logger.info(f"✓ 获取到 {len(recent_fills)} 条最近记录")
    
    # 分析时间范围
    times = [fill.get('time', 0) for fill in recent_fills]
    earliest_recent_ms = min(times)
    latest_recent_ms = max(times)
    
    earliest_recent_dt = timestamp_to_pendulum(earliest_recent_ms)
    latest_recent_dt = timestamp_to_pendulum(latest_recent_ms)
    
    logger.info(f"  最早: {earliest_recent_dt.to_datetime_string()}")
    logger.info(f"  最晚: {latest_recent_dt.to_datetime_string()}")
    
    # 所有记录（包括最近的）
    all_fills_map = {}
    for fill in recent_fills:
        key = (fill.get('oid'), fill.get('time'))
        all_fills_map[key] = fill
    
    # ==================== 第2步：往前按月查找 ====================
    logger.info("")
    logger.info("[步骤 2] 从最早记录往前按月查找历史数据...")
    logger.info("")
    
    # 从最早记录的月初开始往前推
    current_end = earliest_recent_dt.start_of('month')
    empty_months_count = 0
    month_num = 0
    total_historical = 0
    
    while empty_months_count < empty_months_threshold:
        # 往前推一个月
        current_start = current_end.subtract(months=1)
        month_num += 1
        
        logger.info(
            f"[月份 {month_num}] {current_start.format('YYYY-MM-DD')} 至 "
            f"{current_end.format('YYYY-MM-DD')}..."
        )
        
        # 获取这个月的数据
        month_fills = fetch_fills_for_period(
            client, address, current_start, current_end, auto_split=True
        )
        
        if month_fills:
            # 去重并添加
            new_count = 0
            for fill in month_fills:
                key = (fill.get('oid'), fill.get('time'))
                if key not in all_fills_map:
                    all_fills_map[key] = fill
                    new_count += 1
            
            logger.success(f"  ✓ 获取 {len(month_fills)} 条，新增 {new_count} 条")
            total_historical += new_count
            
            # 重置空月份计数
            empty_months_count = 0
        else:
            logger.info(f"  - 无记录")
            empty_months_count += 1
            logger.info(f"  （连续 {empty_months_count}/{empty_months_threshold} 个空月份）")
        
        logger.info("")
        
        # 更新下一次的结束时间
        current_end = current_start
        time.sleep(3.0)  # 每次API调用后等待3秒
    
    logger.info(f"✓ 已连续 {empty_months_threshold} 个月无记录，停止查找")
    
    # ==================== 第3步：汇总结果 ====================
    all_fills = list(all_fills_map.values())
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("获取完成")
    logger.info("=" * 80)
    logger.info(f"最近记录:   {len(recent_fills):>6} 条")
    logger.info(f"历史记录:   {total_historical:>6} 条（新增）")
    logger.info(f"总计:       {len(all_fills):>6} 条（去重后）")
    logger.info(f"查找月份:   {month_num:>6} 个月")
    
    if all_fills:
        all_times = [f.get('time', 0) for f in all_fills]
        earliest_all = timestamp_to_pendulum(min(all_times))
        latest_all = timestamp_to_pendulum(max(all_times))
        
        logger.info("")
        logger.info(f"完整时间范围:")
        logger.info(f"  最早: {earliest_all.to_datetime_string()}")
        logger.info(f"  最晚: {latest_all.to_datetime_string()}")
        logger.info(f"  跨度: {(latest_all - earliest_all).days} 天")
        
        # 统计币种
        coins = defaultdict(int)
        for fill in all_fills:
            coins[fill.get('coin', 'Unknown')] += 1
        
        logger.info("")
        logger.info(f"交易币种分布（Top 10）:")
        for coin, count in sorted(coins.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = count / len(all_fills) * 100
            logger.info(f"  {coin:<15} {count:>6} 笔 ({pct:>5.1f}%)")
    
    return all_fills


def save_fills_to_file(fills: List[Dict], address: str, output_dir: str = "data"):
    """
    保存交易记录到文件
    """
    import json
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 保存为 JSON
    filename = f"fills_{address[:10]}_{len(fills)}.json"
    filepath = output_path / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(fills, f, indent=2, ensure_ascii=False)
    
    logger.success(f"✓ 已保存到: {filepath}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="智能获取交易者完整记录")
    parser.add_argument(
        "--address", "-a",
        required=True,
        help="交易者地址"
    )
    parser.add_argument(
        "--empty-months", "-e",
        type=int,
        default=3,
        help="连续多少个空月份后停止（默认: 3）"
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="保存到文件"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="data",
        help="输出目录（默认: data）"
    )
    
    args = parser.parse_args()
    
    try:
        fills = fetch_all_fills_smart(
            args.address,
            empty_months_threshold=args.empty_months
        )
        
        if fills and args.save:
            save_fills_to_file(fills, args.address, args.output_dir)
        
    except KeyboardInterrupt:
        logger.warning("\n用户中断")
    except Exception as e:
        logger.error(f"执行失败: {repr(e)}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()

