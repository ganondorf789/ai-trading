"""
增量获取成交记录模块

使用自适应5层细分策略（月→周→天→小时→分钟）获取新的成交记录
"""
import time
from typing import List, Dict, Optional, TYPE_CHECKING
import pendulum
from loguru import logger

from .utils import SHANGHAI_TZ, timestamp_to_pendulum

if TYPE_CHECKING:
    from .api_client import SyncAPIClient


def fetch_fills_for_period(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    auto_split: bool = True,
    delay: float = 0.5
) -> List[Dict]:
    """
    获取指定时间段的交易记录
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 开始时间
        end_dt: 结束时间
        auto_split: 如果达到 2000 条，是否自动细分
        delay: API 调用延迟（秒）
    
    Returns:
        交易记录列表
    """
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    try:
        fills = client.get_user_fills_by_time(address, start_ms, end_ms)
    except Exception as e:
        logger.error(f"  获取数据失败 [{start_dt.format('YYYY-MM-DD')} 至 {end_dt.format('YYYY-MM-DD')}]: {repr(e)}")
        return []
    
    if not fills:
        return []
    
    # 如果达到上限且允许自动细分
    if auto_split and len(fills) >= 2000:
        duration_days = (end_dt - start_dt).days
        if duration_days > 7:
            logger.debug(f"  达到 2000 条上限，按周细分...")
            return fetch_fills_by_weeks(client, address, start_dt, end_dt, delay)
        elif duration_days > 1:
            logger.debug(f"  达到 2000 条上限，按天细分...")
            return fetch_fills_by_days(client, address, start_dt, end_dt, delay)
        else:
            logger.debug(f"  达到 2000 条上限，按小时细分...")
            return fetch_fills_by_hours(client, address, start_dt, end_dt, delay)
    
    return fills


def fetch_fills_by_weeks(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.5
) -> List[Dict]:
    """按周获取交易记录"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_week = min(current.add(weeks=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_week.timestamp() * 1000)
        
        try:
            week_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"    获取周数据失败 [{current.format('MM-DD')}]: {repr(e)}")
            current = next_week
            time.sleep(delay)
            continue
        
        if week_fills:
            # 如果这周还达到 2000 条，按天细分
            if len(week_fills) >= 2000:
                logger.debug(f"    周 [{current.format('MM-DD')}] 达到 2000 条，按天细分...")
                day_fills = fetch_fills_by_days(client, address, current, next_week, delay)
                all_fills.extend(day_fills)
            else:
                all_fills.extend(week_fills)
        
        current = next_week
        time.sleep(delay)
    
    return all_fills


def fetch_fills_by_days(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.5
) -> List[Dict]:
    """按天获取交易记录"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_day = min(current.add(days=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_day.timestamp() * 1000)
        
        try:
            day_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"      获取日数据失败 [{current.format('MM-DD')}]: {repr(e)}")
            current = next_day
            time.sleep(delay)
            continue
        
        if day_fills:
            if len(day_fills) >= 2000:
                logger.debug(f"      天 [{current.format('MM-DD')}] 达到 2000 条，按小时细分...")
                hour_fills = fetch_fills_by_hours(client, address, current, next_day, delay)
                all_fills.extend(hour_fills)
            else:
                all_fills.extend(day_fills)
        
        current = next_day
        time.sleep(delay)
    
    return all_fills


def fetch_fills_by_hours(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.5
) -> List[Dict]:
    """按小时获取交易记录"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_hour = min(current.add(hours=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_hour.timestamp() * 1000)
        
        try:
            hour_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"        获取小时数据失败 [{current.format('MM-DD HH:00')}]: {repr(e)}")
            current = next_hour
            time.sleep(delay)
            continue
        
        if hour_fills:
            if len(hour_fills) >= 2000:
                logger.debug(f"        小时 [{current.format('HH:00')}] 达到 2000 条，按分钟细分...")
                minute_fills = fetch_fills_by_minutes(client, address, current, next_hour, delay)
                all_fills.extend(minute_fills)
            else:
                all_fills.extend(hour_fills)
        
        current = next_hour
        time.sleep(delay)
    
    return all_fills


def fetch_fills_by_minutes(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.5
) -> List[Dict]:
    """按分钟获取交易记录（用于极度活跃的交易小时）"""
    all_fills = []
    current = start_dt
    
    while current < end_dt:
        next_minute = min(current.add(minutes=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_minute.timestamp() * 1000)
        
        try:
            minute_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"          获取分钟数据失败 [{current.format('HH:mm')}]: {repr(e)}")
            current = next_minute
            time.sleep(delay)
            continue
        
        if minute_fills:
            all_fills.extend(minute_fills)
            if len(minute_fills) >= 2000:
                logger.warning(f"          分钟 [{current.format('HH:mm')}]: {len(minute_fills)} 条（达到上限，无法进一步细分）")
        
        current = next_minute
        time.sleep(delay)
    
    return all_fills


def fetch_incremental_fills(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.5
) -> List[Dict]:
    """
    增量获取成交记录（自适应5层细分）
    
    从 start_dt 开始获取到 end_dt 的所有成交记录。
    如果单次请求达到 2000 条上限，会自动细分时间段：
    月 → 周 → 天 → 小时 → 分钟
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 开始时间（数据库中最新记录的时间）
        end_dt: 结束时间（通常是当前时间）
        delay: API 调用之间的延迟（秒）
    
    Returns:
        新的成交记录列表（已去重）
    """
    duration_days = (end_dt - start_dt).days
    
    if duration_days <= 0:
        # 时间范围太小，直接获取
        return fetch_fills_for_period(client, address, start_dt, end_dt, auto_split=True, delay=delay)
    
    all_fills = []
    seen_keys = set()  # 用于去重
    
    def add_fills(fills: List[Dict]):
        """添加记录并去重"""
        for fill in fills:
            key = (fill.get('oid'), fill.get('time'))
            if key not in seen_keys:
                seen_keys.add(key)
                all_fills.append(fill)
    
    if duration_days > 30:
        # 按月获取
        current = start_dt.start_of('month')
        while current < end_dt:
            next_month = min(current.add(months=1), end_dt)
            actual_start = max(current, start_dt)
            
            logger.debug(f"  获取月度数据 [{actual_start.format('YYYY-MM-DD')} 至 {next_month.format('YYYY-MM-DD')}]...")
            month_fills = fetch_fills_for_period(client, address, actual_start, next_month, auto_split=True, delay=delay)
            
            if month_fills:
                add_fills(month_fills)
                logger.debug(f"    获取 {len(month_fills)} 条，累计 {len(all_fills)} 条")
            
            current = next_month
            time.sleep(delay)
    else:
        # 时间范围较短，直接获取
        fills = fetch_fills_for_period(client, address, start_dt, end_dt, auto_split=True, delay=delay)
        add_fills(fills)
    
    return all_fills


def fetch_all_history_fills(
    client: 'SyncAPIClient',
    address: str,
    empty_months_threshold: int = 3,
    delay: float = 0.5
) -> List[Dict]:
    """
    获取交易者的完整历史交易记录
    
    策略：
    1. 先获取最近的 2000 条记录
    2. 找到最早的交易时间，从这个时间往前按月查找
    3. 连续 N 个月没有订单则停止
    
    Args:
        client: API 客户端
        address: 交易者地址
        empty_months_threshold: 连续多少个空月份后停止（默认 3）
        delay: API 调用之间的延迟（秒）
    
    Returns:
        所有成交记录列表（已去重）
    """
    all_fills = []
    seen_keys = set()  # 用于去重
    
    def add_fills(fills: List[Dict]):
        """添加记录并去重"""
        added = 0
        for fill in fills:
            key = (fill.get('oid'), fill.get('time'))
            if key not in seen_keys:
                seen_keys.add(key)
                all_fills.append(fill)
                added += 1
        return added
    
    # 步骤1：获取最近的 2000 条记录
    logger.debug(f"  获取最近的交易记录...")
    try:
        recent_fills = client.get_user_fills(address, limit=0)
    except Exception as e:
        logger.error(f"  获取最近记录失败: {repr(e)}")
        return []
    
    if not recent_fills:
        logger.debug(f"  该地址没有任何交易记录")
        return []
    
    logger.debug(f"  获取到 {len(recent_fills)} 条最近记录")
    
    # 分析时间范围
    times = [fill.get('time', 0) for fill in recent_fills]
    earliest_recent_ms = min(times)
    earliest_recent_dt = timestamp_to_pendulum(earliest_recent_ms)
    
    logger.debug(f"  最早记录: {earliest_recent_dt.to_datetime_string()}")
    
    # 添加最近的记录
    add_fills(recent_fills)
    
    # 步骤2：往前按月查找历史记录
    current_end = earliest_recent_dt.start_of('month')
    empty_months_count = 0
    month_num = 0
    
    while empty_months_count < empty_months_threshold:
        current_start = current_end.subtract(months=1)
        month_num += 1
        
        logger.debug(
            f"  [月份 {month_num}] {current_start.format('YYYY-MM-DD')} 至 "
            f"{current_end.format('YYYY-MM-DD')}..."
        )
        
        month_fills = fetch_fills_for_period(
            client, address, current_start, current_end, auto_split=True, delay=delay
        )
        
        if month_fills:
            new_count = add_fills(month_fills)
            logger.debug(f"    获取 {len(month_fills)} 条，新增 {new_count} 条，累计 {len(all_fills)} 条")
            empty_months_count = 0
        else:
            empty_months_count += 1
            logger.debug(f"    无记录（连续 {empty_months_count}/{empty_months_threshold} 个空月份）")
        
        current_end = current_start
        time.sleep(delay)
    
    logger.debug(f"  总计获取 {len(all_fills)} 条记录（去重后）")
    
    return all_fills
