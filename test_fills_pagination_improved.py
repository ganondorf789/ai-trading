"""
改进的交易记录分页测试 - 使用更小的时间段（按周）

测试策略：
1. 先用直接获取方式找出时间范围
2. 按周分段获取
3. 如果某周超过2000条，再细分为按天
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pendulum
from loguru import logger
from collections import defaultdict
import time

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from screener.api_client import SyncAPIClient
from screener.config import APIConfig
from screener.utils import SHANGHAI_TZ, timestamp_to_pendulum


def get_fills_with_adaptive_pagination(
    client: SyncAPIClient,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime
) -> list:
    """
    自适应分页获取交易记录
    
    如果某个时间段的记录达到2000条上限，自动细分时间段
    """
    all_fills = []
    
    # 先尝试按整个时间段获取
    logger.info(f"获取 {start_dt.format('YYYY-MM-DD')} 至 {end_dt.format('YYYY-MM-DD')}...")
    
    fills = client.get_user_fills_by_time(
        address,
        int(start_dt.timestamp() * 1000),
        int(end_dt.timestamp() * 1000)
    )
    
    logger.info(f"  获取到 {len(fills)} 条记录")
    
    # 如果达到上限且时间段大于1天，则细分
    if len(fills) >= 2000 and (end_dt - start_dt).days > 1:
        logger.warning(f"  ⚠ 达到2000条上限，按更小时间段重新获取...")
        
        # 按天分段
        current = start_dt
        day_fills = []
        
        while current < end_dt:
            next_day = min(current.add(days=1), end_dt)
            
            logger.info(f"    [{current.format('YYYY-MM-DD')}]...", end="")
            
            day_data = client.get_user_fills_by_time(
                address,
                int(current.timestamp() * 1000),
                int(next_day.timestamp() * 1000)
            )
            
            if day_data:
                logger.info(f" {len(day_data)} 条")
                day_fills.extend(day_data)
                
                if len(day_data) >= 2000:
                    logger.warning(f"      ⚠ 单天就有{len(day_data)}条！可能仍有遗漏")
            else:
                logger.info(f" 0 条")
            
            current = next_day
            time.sleep(0.3)  # 避免速率限制
        
        return day_fills
    else:
        return fills


def test_improved_pagination(address: str):
    """
    改进的分页测试
    """
    logger.info("=" * 80)
    logger.info("改进的交易记录分页测试（自适应时间段）")
    logger.info("=" * 80)
    logger.info(f"测试地址: {address}")
    logger.info("")
    
    # 初始化 API 客户端
    config = APIConfig()
    config.api_call_delay = 0.8
    config.max_retries = 5
    config.retry_delay = 2.0
    
    logger.info("正在初始化 API 客户端...")
    time.sleep(2)
    
    try:
        client = SyncAPIClient(config)
    except Exception as e:
        logger.error(f"API 客户端初始化失败: {str(e)}")
        return
    
    # ==================== 方法1: 直接获取 ====================
    logger.info("")
    logger.info("[方法1] 直接调用 user_fills API...")
    fills_direct = client.get_user_fills(address, limit=0)
    
    if not fills_direct:
        logger.error("没有获取到任何交易记录")
        return
    
    logger.info(f"✓ 获取到 {len(fills_direct)} 条记录")
    
    # 分析时间范围
    times = [fill.get('time', 0) for fill in fills_direct]
    earliest_time_ms = min(times)
    latest_time_ms = max(times)
    
    earliest_dt = timestamp_to_pendulum(earliest_time_ms)
    latest_dt = timestamp_to_pendulum(latest_time_ms)
    
    logger.info(f"  最早交易: {earliest_dt.to_datetime_string()}")
    logger.info(f"  最晚交易: {latest_dt.to_datetime_string()}")
    logger.info(f"  时间跨度: {(latest_dt - earliest_dt).days} 天")
    
    # ==================== 方法2: 自适应分页 ====================
    logger.info("")
    logger.info("[方法2] 自适应时间段分页获取...")
    
    # 往前推一个月作为安全边界
    start_dt = earliest_dt.subtract(months=1)
    end_dt = pendulum.now(SHANGHAI_TZ)
    
    logger.info(f"查询范围: {start_dt.to_datetime_string()} -> {end_dt.to_datetime_string()}")
    logger.info("")
    
    all_fills_paginated = []
    
    # 按周分段
    current_start = start_dt
    week_num = 0
    
    while current_start < end_dt:
        current_end = min(current_start.add(weeks=1), end_dt)
        week_num += 1
        
        logger.info(f"[第 {week_num} 周]")
        week_fills = get_fills_with_adaptive_pagination(
            client, address, current_start, current_end
        )
        
        if week_fills:
            all_fills_paginated.extend(week_fills)
        
        logger.info("")
        current_start = current_end
        time.sleep(0.5)
    
    # 去重
    unique_fills_map = {}
    for fill in all_fills_paginated:
        key = (fill.get('oid'), fill.get('time'))
        unique_fills_map[key] = fill
    
    fills_paginated_unique = list(unique_fills_map.values())
    
    logger.info(f"✓ 自适应分页获取完成")
    logger.info(f"  总记录数: {len(all_fills_paginated)} 条")
    logger.info(f"  去重后: {len(fills_paginated_unique)} 条")
    logger.info(f"  重复记录: {len(all_fills_paginated) - len(fills_paginated_unique)} 条")
    
    # ==================== 对比结果 ====================
    logger.info("")
    logger.info("=" * 80)
    logger.info("结果对比")
    logger.info("=" * 80)
    logger.info(f"方法1 (直接获取):         {len(fills_direct):>6} 条")
    logger.info(f"方法2 (自适应分页):       {len(fills_paginated_unique):>6} 条")
    diff = len(fills_paginated_unique) - len(fills_direct)
    logger.info(f"差异:                    {diff:>6} 条 ({diff/len(fills_direct)*100:+.1f}%)")
    logger.info("")
    
    # 分析差异
    paginated_keys = {(f.get('oid'), f.get('time')) for f in fills_paginated_unique}
    direct_keys = {(f.get('oid'), f.get('time')) for f in fills_direct}
    
    missing_in_paginated = direct_keys - paginated_keys
    extra_in_paginated = paginated_keys - direct_keys
    
    if len(fills_paginated_unique) > len(fills_direct):
        logger.success(f"✓ 自适应分页成功获取了更多记录！")
        logger.info(f"  额外获取: {len(extra_in_paginated)} 条")
        
        if missing_in_paginated:
            logger.warning(f"  但缺失: {len(missing_in_paginated)} 条（在方法1中有）")
        
        # 分析额外记录的时间分布
        if extra_in_paginated:
            extra_fills = [f for f in fills_paginated_unique 
                          if (f.get('oid'), f.get('time')) in extra_in_paginated]
            extra_times = [f.get('time', 0) for f in extra_fills]
            
            if extra_times:
                extra_earliest = timestamp_to_pendulum(min(extra_times))
                extra_latest = timestamp_to_pendulum(max(extra_times))
                logger.info(f"  额外记录时间: {extra_earliest.to_datetime_string()} ~ {extra_latest.to_datetime_string()}")
    
    elif len(fills_paginated_unique) == len(fills_direct):
        logger.info("✓ 两种方式获取的记录数量一致")
        
        if missing_in_paginated:
            logger.warning(f"  但有 {len(missing_in_paginated)} 条不同的记录")
    
    else:
        logger.warning(f"⚠ 自适应分页反而获取更少（少 {-diff} 条）")
        logger.warning(f"  缺失: {len(missing_in_paginated)} 条")
    
    # ==================== 总结 ====================
    logger.info("")
    logger.info("=" * 80)
    logger.info("测试结论")
    logger.info("=" * 80)
    
    if len(fills_direct) >= 2000:
        logger.warning("✓ 该地址交易记录超过2000条，API单次调用被截断")
        
        if len(fills_paginated_unique) > len(fills_direct):
            logger.success(f"✓ 使用自适应分页成功突破2000条限制")
            logger.success(f"✓ 建议在生产环境使用自适应分页方式")
        else:
            logger.warning("⚠ 时间范围分页方式存在问题，需要进一步优化")
    else:
        logger.info("✓ 该地址交易记录未超过2000条")
        logger.info("✓ 直接调用 user_fills 即可")
    
    # 数据质量评估
    logger.info("")
    logger.info("数据质量评估:")
    overlap = len(direct_keys & paginated_keys)
    logger.info(f"  重叠记录: {overlap} 条 ({overlap/len(fills_direct)*100:.1f}%)")
    
    if overlap / len(fills_direct) < 0.9:
        logger.error("  ⚠ 数据重叠率过低，两种API可能返回不同的数据！")
    elif overlap / len(fills_direct) < 0.95:
        logger.warning("  ⚠ 数据重叠率偏低，需要注意数据一致性")
    else:
        logger.success("  ✓ 数据重叠率良好")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="改进的交易记录分页测试")
    parser.add_argument(
        "--address", "-a",
        default="0x7c4b71c1d8a11ed426f301c372a72e06f528e00b",
        help="测试地址"
    )
    
    args = parser.parse_args()
    
    try:
        test_improved_pagination(args.address)
    except KeyboardInterrupt:
        logger.warning("\n用户中断测试")
    except Exception as e:
        logger.error(f"测试失败: {repr(e)}")
        import traceback
        logger.error(traceback.format_exc())

