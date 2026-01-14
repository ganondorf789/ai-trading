"""
增量获取成交记录模块

使用自适应5层细分策略（月→周→天→小时→分钟）获取新的成交记录
"""
import time
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
import pendulum
from loguru import logger

from .utils import SHANGHAI_TZ, timestamp_to_pendulum, now_shanghai

if TYPE_CHECKING:
    from .api_client import SyncAPIClient


def fetch_fills_for_period(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    auto_split: bool = True,
    delay: float = 2.0
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
    delay: float = 2.0
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
    delay: float = 2.0
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
    delay: float = 2.0
) -> List[Dict]:
    """按小时获取交易记录"""
    all_fills = []
    current = start_dt
    total_hours = int((end_dt - start_dt).total_seconds() / 3600) + 1
    hour_num = 0
    
    while current < end_dt:
        next_hour = min(current.add(hours=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_hour.timestamp() * 1000)
        hour_num += 1
        
        try:
            hour_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"        获取小时数据失败 [{current.format('MM-DD HH:00')}]: {repr(e)}")
            current = next_hour
            time.sleep(delay)
            continue
        
        if hour_fills:
            if len(hour_fills) >= 2000:
                logger.debug(f"        小时 [{current.format('HH:00')}] 达到 2000 条，按10分钟细分...")
                minute_fills = fetch_fills_by_minutes(client, address, current, next_hour, delay)
                all_fills.extend(minute_fills)
            else:
                all_fills.extend(hour_fills)
                logger.debug(f"        小时 [{hour_num}/{total_hours}] {current.format('HH:00')}: {len(hour_fills)} 条，累计 {len(all_fills)} 条")
        
        current = next_hour
        time.sleep(delay)
    
    logger.debug(f"        小时细分完成: 共 {len(all_fills)} 条")
    return all_fills


def fetch_fills_by_minutes(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 2.0
) -> List[Dict]:
    """按10分钟获取交易记录（用于极度活跃的交易小时）"""
    all_fills = []
    current = start_dt
    total_chunks = int((end_dt - start_dt).total_seconds() / 600) + 1  # 每10分钟一个块
    chunk_num = 0
    
    while current < end_dt:
        next_chunk = min(current.add(minutes=10), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_chunk.timestamp() * 1000)
        chunk_num += 1
        
        try:
            chunk_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"          获取10分钟数据失败 [{current.format('HH:mm')}]: {repr(e)}")
            current = next_chunk
            time.sleep(delay)
            continue
        
        if chunk_fills:
            if len(chunk_fills) >= 2000:
                # 10分钟还达到2000条，按2分钟细分
                logger.debug(f"          10分钟 [{current.format('HH:mm')}-{next_chunk.format('HH:mm')}] 达到 2000 条，按2分钟细分...")
                fine_fills = fetch_fills_by_2minutes(client, address, current, next_chunk, delay)
                all_fills.extend(fine_fills)
            else:
                all_fills.extend(chunk_fills)
                logger.debug(f"          10分钟 [{chunk_num}/{total_chunks}] {current.format('HH:mm')}-{next_chunk.format('HH:mm')}: {len(chunk_fills)} 条，累计 {len(all_fills)} 条")
        
        current = next_chunk
        time.sleep(delay)
    
    logger.debug(f"          10分钟细分完成: 共 {len(all_fills)} 条")
    return all_fills


def fetch_fills_by_2minutes(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 2.0
) -> List[Dict]:
    """按2分钟获取交易记录（用于极度活跃的10分钟段）"""
    all_fills = []
    current = start_dt
    total_chunks = int((end_dt - start_dt).total_seconds() / 120) + 1  # 每2分钟一个块
    chunk_num = 0
    
    while current < end_dt:
        next_chunk = min(current.add(minutes=2), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_chunk.timestamp() * 1000)
        chunk_num += 1
        
        try:
            chunk_fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"            获取2分钟数据失败 [{current.format('HH:mm')}]: {repr(e)}")
            current = next_chunk
            time.sleep(delay)
            continue
        
        if chunk_fills:
            all_fills.extend(chunk_fills)
            if len(chunk_fills) >= 2000:
                logger.warning(f"            2分钟 [{current.format('HH:mm')}-{next_chunk.format('HH:mm')}]: {len(chunk_fills)} 条（达到上限，无法进一步细分）")
            else:
                logger.debug(f"            2分钟 [{chunk_num}/{total_chunks}] {current.format('HH:mm')}-{next_chunk.format('HH:mm')}: {len(chunk_fills)} 条，累计 {len(all_fills)} 条")
        
        current = next_chunk
        time.sleep(delay)
    
    logger.debug(f"            2分钟细分完成: 共 {len(all_fills)} 条")
    return all_fills


def probe_trader_fills(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
) -> Tuple[List[Dict], bool]:
    """
    快速探测交易者是否有交易记录
    
    用一次 API 调用查询全量时间范围，快速判断：
    - 0 条记录：该交易员无交易历史
    - 1-1999 条：已获取全部记录
    - 2000 条：记录可能不完整，需要进一步获取
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 开始时间
        end_dt: 结束时间
    
    Returns:
        (fills, is_complete): fills 是记录列表，is_complete 表示是否已获取全部
    """
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    fills = client.get_user_fills_by_time(address, start_ms, end_ms)
    
    if not fills:
        return [], True
    
    is_complete = len(fills) < 2000
    return fills, is_complete


def find_first_fill_half_year(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 2.0
) -> Optional[pendulum.DateTime]:
    """
    使用半年分块快速定位第一笔交易所在的半年
    
    按半年为单位向前探测，找到第一个有交易记录的半年。
    比逐月探测快 6 倍。
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 开始时间
        end_dt: 结束时间
        delay: API 调用延迟（秒）
    
    Returns:
        第一笔交易所在半年的起始时间，如果无记录返回 None
    """
    current = start_dt.start_of('month')
    
    while current < end_dt:
        # 计算半年的结束时间
        next_half_year = current.add(months=6)
        actual_end = min(next_half_year, end_dt)
        
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(actual_end.timestamp() * 1000)
        
        logger.debug(f"    半年探测: {current.format('YYYY-MM')} 至 {actual_end.format('YYYY-MM')}...")
        
        try:
            fills = client.get_user_fills_by_time(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"    半年探测失败 [{current.format('YYYY-MM')}]: {repr(e)}")
            current = next_half_year
            time.sleep(delay)
            continue
        
        if fills:
            # 找到有记录的半年，返回该半年的起始时间
            logger.debug(f"    找到记录于 {current.format('YYYY-MM')} 半年，共 {len(fills)} 条")
            return current
        
        current = next_half_year
        time.sleep(delay)
    
    return None


def fetch_incremental_fills(
    client: 'SyncAPIClient',
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 2.0
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
    start_dt: Optional[pendulum.DateTime] = None,
    max_retries: int = 3,
    delay: float = 2.0
) -> List[Dict]:
    """
    从前往后获取交易者的历史交易记录（优化版）
    
    策略：
    1. 如果有 start_dt（增量更新），从该时间开始按月获取
    2. 如果无 start_dt（首次获取），先探测全量范围：
       - 0 条记录 → 直接返回空
       - < 2000 条 → 直接返回（已获取全部）
       - = 2000 条 → 用半年分块定位起始时间，再按月获取
    
    优势：
    - 对于无记录或少量记录的交易员，只需 1 次 API 调用
    - 对于近期才开始交易的交易员，快速跳过空白期
    - 按时间顺序获取，早期数据先保存
    - 如果中途失败，已获取的数据不会丢失
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 起始时间（默认 2024-01-01），如果数据库有记录则从最新记录开始
        max_retries: 单次请求最大重试次数，超过则终止整个获取过程
        delay: API 调用之间的延迟（秒）
    
    Returns:
        成交记录列表（已去重）
    """
    # 默认起始时间：2024-01-01
    DEFAULT_START = pendulum.datetime(2024, 1, 1, tz=SHANGHAI_TZ)
    end = now_shanghai()
    
    all_fills = []
    seen_keys = set()  # 用于去重
    
    def add_fills(fills: List[Dict]) -> int:
        """添加记录并去重"""
        added = 0
        for fill in fills:
            key = (fill.get('oid'), fill.get('time'))
            if key not in seen_keys:
                seen_keys.add(key)
                all_fills.append(fill)
                added += 1
        return added
    
    # ========== 优化：首次获取时先探测 ==========
    if start_dt is None:
        logger.debug(f"  首次获取，探测全量范围: {DEFAULT_START.format('YYYY-MM-DD')} → {end.format('YYYY-MM-DD')}")
        
        # 带重试的探测
        probe_fills = None
        is_complete = False
        for retry in range(max_retries):
            try:
                probe_fills, is_complete = probe_trader_fills(client, address, DEFAULT_START, end)
                break
            except Exception as e:
                retry_num = retry + 1
                if retry_num < max_retries:
                    logger.warning(f"    探测失败（重试 {retry_num}/{max_retries}）: {repr(e)}")
                    time.sleep(delay * 2)
                else:
                    logger.error(f"    探测失败（已重试 {max_retries} 次），终止获取: {repr(e)}")
                    return []
        
        # 情况1：无记录
        if not probe_fills:
            logger.debug(f"  无交易记录，跳过")
            return []
        
        # 情况2：< 2000 条，已获取全部
        if is_complete:
            logger.debug(f"  获取完成: 共 {len(probe_fills)} 条记录（< 2000，已全部获取）")
            return probe_fills
        
        # 情况3：= 2000 条，需要进一步获取
        logger.debug(f"  探测返回 2000 条，使用半年分块定位起始时间...")
        time.sleep(delay)
        
        # 用半年分块找到第一笔交易所在的半年
        first_half_year = find_first_fill_half_year(client, address, DEFAULT_START, end, delay)
        
        if first_half_year is None:
            # 理论上不应该发生（因为探测已返回数据），但做个保护
            logger.warning(f"  半年探测未找到记录，使用探测结果")
            return probe_fills
        
        # 从找到的半年开始按月获取
        start = first_half_year
        logger.debug(f"  从 {start.format('YYYY-MM')} 开始按月获取...")
        time.sleep(delay)
    else:
        # 增量更新：从指定时间开始
        start = start_dt
        logger.debug(f"  增量获取: {start.format('YYYY-MM-DD')} → {end.format('YYYY-MM-DD')}")
    
    # ========== 按月获取 ==========
    current = start.start_of('month')
    month_num = 0
    
    while current < end:
        next_month = current.add(months=1)
        # 确保不超过结束时间
        actual_end = min(next_month, end)
        # 确保起始时间不早于指定的 start_dt
        actual_start = max(current, start)
        
        month_num += 1
        logger.debug(
            f"  [月份 {month_num}] {actual_start.format('YYYY-MM-DD')} 至 "
            f"{actual_end.format('YYYY-MM-DD')}..."
        )
        
        # 带重试的获取
        success = False
        month_fills = None
        for retry in range(max_retries):
            try:
                month_fills = fetch_fills_for_period(
                    client, address, actual_start, actual_end, 
                    auto_split=True, delay=delay
                )
                success = True
                break
            except Exception as e:
                retry_num = retry + 1
                if retry_num < max_retries:
                    logger.warning(f"    获取失败（重试 {retry_num}/{max_retries}）: {repr(e)}")
                    time.sleep(delay * 2)  # 失败后等待更长时间
                else:
                    logger.error(f"    获取失败（已重试 {max_retries} 次），终止获取: {repr(e)}")
        
        # 如果3次重试都失败，终止整个获取过程
        if not success:
            logger.warning(f"  因连续失败终止，已获取 {len(all_fills)} 条记录")
            return all_fills
        
        # 添加获取到的记录
        if month_fills:
            new_count = add_fills(month_fills)
            logger.debug(f"    获取 {len(month_fills)} 条，新增 {new_count} 条，累计 {len(all_fills)} 条")
        else:
            logger.debug(f"    无记录")
        
        current = next_month
        time.sleep(delay)
    
    logger.debug(f"  总计获取 {len(all_fills)} 条记录（去重后）")
    
    return all_fills
