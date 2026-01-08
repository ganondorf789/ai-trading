"""
测试 Hyperliquid API 时间范围分页获取所有交易记录

对比两种方式：
1. 直接调用 user_fills（可能被限制在2000条）
2. 使用时间范围分页获取（理论上可以获取所有记录）
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pendulum
from loguru import logger
from collections import defaultdict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from screener.api_client import SyncAPIClient
from screener.config import APIConfig
from screener.utils import SHANGHAI_TZ, timestamp_to_pendulum


def test_fills_pagination(address: str):
    """
    测试时间范围分页获取交易记录
    
    Args:
        address: 测试地址
    """
    logger.info("=" * 80)
    logger.info("测试 Hyperliquid API 交易记录获取")
    logger.info("=" * 80)
    logger.info(f"测试地址: {address}")
    logger.info("")
    
    # 初始化 API 客户端
    config = APIConfig()
    config.api_call_delay = 1.0  # 增加延迟避免速率限制
    config.max_retries = 5
    config.retry_delay = 2.0
    
    logger.info("正在初始化 API 客户端...")
    import time
    time.sleep(2)  # 初始延迟
    
    try:
        client = SyncAPIClient(config)
    except Exception as e:
        logger.error(f"API 客户端初始化失败: {str(e)}")
        logger.error("可能是API速率限制，请稍后重试")
        return
    
    # ==================== 方法1: 直接获取 ====================
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
    
    # 统计交易类型
    coins = defaultdict(int)
    for fill in fills_direct:
        coins[fill.get('coin', 'Unknown')] += 1
    
    logger.info(f"  交易币种: {len(coins)} 个")
    top_coins = sorted(coins.items(), key=lambda x: x[1], reverse=True)[:5]
    for coin, count in top_coins:
        logger.info(f"    - {coin}: {count} 笔")
    
    # ==================== 方法2: 时间范围分页 ====================
    logger.info("")
    logger.info("[方法2] 使用时间范围分页获取...")
    
    # 从最早的交易时间开始，到现在
    # 为了保险，往前推30天
    start_dt = earliest_dt.subtract(days=30)
    end_dt = pendulum.now(SHANGHAI_TZ)
    
    logger.info(f"  查询范围: {start_dt.to_datetime_string()} -> {end_dt.to_datetime_string()}")
    
    # 按月分段获取
    all_fills_paginated = []
    segment_count = 0
    
    current_start = start_dt
    
    while current_start < end_dt:
        # 每次获取1个月的数据
        current_end = min(current_start.add(months=1), end_dt)
        segment_count += 1
        
        logger.info(f"  [{segment_count}] 获取 {current_start.format('YYYY-MM-DD')} 至 {current_end.format('YYYY-MM-DD')}...")
        
        segment_fills = client.get_user_fills_by_time(
            address,
            int(current_start.timestamp() * 1000),
            int(current_end.timestamp() * 1000)
        )
        
        if segment_fills:
            logger.info(f"      ✓ 获取到 {len(segment_fills)} 条记录")
            all_fills_paginated.extend(segment_fills)
            
            # 如果这一段就有2000条，说明可能还有更多，需要更细分
            if len(segment_fills) >= 2000:
                logger.warning(f"      ⚠ 该时间段记录达到2000条上限，可能有遗漏！")
        else:
            logger.info(f"      - 无记录")
        
        current_start = current_end
    
    # 去重（根据 oid + time）
    unique_fills = {}
    for fill in all_fills_paginated:
        key = (fill.get('oid'), fill.get('time'))
        unique_fills[key] = fill
    
    fills_paginated_unique = list(unique_fills.values())
    
    logger.info("")
    logger.info(f"✓ 分页获取完成")
    logger.info(f"  总记录数: {len(all_fills_paginated)} 条")
    logger.info(f"  去重后: {len(fills_paginated_unique)} 条")
    
    # ==================== 对比结果 ====================
    logger.info("")
    logger.info("=" * 80)
    logger.info("结果对比")
    logger.info("=" * 80)
    logger.info(f"方法1 (直接获取):     {len(fills_direct):>6} 条")
    logger.info(f"方法2 (时间范围分页): {len(fills_paginated_unique):>6} 条")
    logger.info(f"差异:                {len(fills_paginated_unique) - len(fills_direct):>6} 条")
    logger.info("")
    
    if len(fills_paginated_unique) > len(fills_direct):
        logger.success(f"✓ 时间范围分页获取了更多记录（多 {len(fills_paginated_unique) - len(fills_direct)} 条）")
        logger.success("  建议使用时间范围分页方式获取完整历史记录")
    elif len(fills_paginated_unique) == len(fills_direct):
        logger.info("✓ 两种方式获取的记录数量一致")
        logger.info("  该地址的交易记录未超过API单次返回上限")
    else:
        logger.warning("⚠ 时间范围分页获取的记录反而更少")
        logger.warning("  可能是时间范围设置问题或API限制")
    
    # ==================== 检查是否有遗漏 ====================
    logger.info("")
    logger.info("=" * 80)
    logger.info("遗漏检查")
    logger.info("=" * 80)
    
    # 检查方法1中的记录是否都在方法2中
    paginated_keys = {(f.get('oid'), f.get('time')) for f in fills_paginated_unique}
    direct_keys = {(f.get('oid'), f.get('time')) for f in fills_direct}
    
    missing_in_paginated = direct_keys - paginated_keys
    extra_in_paginated = paginated_keys - direct_keys
    
    if missing_in_paginated:
        logger.warning(f"⚠ 方法2中缺失 {len(missing_in_paginated)} 条记录（在方法1中有）")
    else:
        logger.success("✓ 方法1的所有记录都在方法2中找到")
    
    if extra_in_paginated:
        logger.success(f"✓ 方法2多获取了 {len(extra_in_paginated)} 条记录（方法1中没有）")
        
        # 分析这些额外的记录
        extra_fills = [f for f in fills_paginated_unique 
                      if (f.get('oid'), f.get('time')) in extra_in_paginated]
        extra_times = [f.get('time', 0) for f in extra_fills]
        
        if extra_times:
            extra_earliest = timestamp_to_pendulum(min(extra_times))
            extra_latest = timestamp_to_pendulum(max(extra_times))
            logger.info(f"  额外记录时间范围: {extra_earliest.to_datetime_string()} ~ {extra_latest.to_datetime_string()}")
            
            # 统计额外记录的币种
            extra_coins = defaultdict(int)
            for fill in extra_fills:
                extra_coins[fill.get('coin', 'Unknown')] += 1
            
            logger.info(f"  额外记录币种分布:")
            for coin, count in sorted(extra_coins.items(), key=lambda x: x[1], reverse=True)[:5]:
                logger.info(f"    - {coin}: {count} 笔")
    
    # ==================== 总结 ====================
    logger.info("")
    logger.info("=" * 80)
    logger.info("测试结论")
    logger.info("=" * 80)
    
    if len(fills_direct) >= 2000:
        logger.warning("✓ 该地址的交易记录超过2000条，API单次调用被截断")
        logger.info("✓ 使用时间范围分页可以突破2000条限制")
        
        if len(fills_paginated_unique) > len(fills_direct):
            logger.success(f"✓ 成功获取额外的 {len(fills_paginated_unique) - len(fills_direct)} 条历史记录")
        
        # 检查是否还有遗漏
        max_segment = max([len(client.get_user_fills_by_time(
            address,
            int(current_start.timestamp() * 1000),
            int(current_start.add(months=1).timestamp() * 1000)
        )) for current_start in [start_dt.add(months=i) for i in range(segment_count)]], default=0)
        
        if max_segment >= 2000:
            logger.warning("⚠ 某些时间段的记录仍达到2000条上限")
            logger.warning("⚠ 建议使用更小的时间段（如按周或按天）进行分页")
    else:
        logger.info(f"✓ 该地址的交易记录未超过2000条（{len(fills_direct)} 条）")
        logger.info("✓ 直接调用 user_fills 即可获取全部记录")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试交易记录分页获取")
    parser.add_argument(
        "--address", "-a",
        default="0x7c4b71c1d8a11ed426f301c372a72e06f528e00b",
        help="测试地址"
    )
    
    args = parser.parse_args()
    
    try:
        test_fills_pagination(args.address)
    except KeyboardInterrupt:
        logger.warning("\n用户中断测试")
    except Exception as e:
        logger.error(f"测试失败: {repr(e)}")
        import traceback
        logger.error(traceback.format_exc())

