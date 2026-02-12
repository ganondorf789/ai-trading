"""
账户历史数据获取模块

获取交易员的资金费历史 (userFunding)、历史委托 (historicalOrders)、
出入金 (userNonFundingLedgerUpdates) 数据。

资金费与出入金使用自适应分层策略（参考 incremental_fetcher.py），
尽量获取全部数据。API 限制：
- userFunding / userNonFundingLedgerUpdates: 每次最多 500 条
- historicalOrders: 最多 2000 条最近记录（无时间范围参数）
"""
import time
from typing import List, Dict, Optional, Tuple, Callable, TYPE_CHECKING
import pendulum
from loguru import logger

from .utils import SHANGHAI_TZ, now_shanghai

if TYPE_CHECKING:
    from .api_client import SyncAPIClient

# 每次 API 返回的上限
PAGE_LIMIT_FUNDING = 2000   # userFunding / userNonFundingLedgerUpdates
PAGE_LIMIT_ORDERS = 2000   # historicalOrders


# ============================================================
# 通用的自适应分层获取框架
# ============================================================

def _fetch_paged_for_period(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    auto_split: bool = True,
    delay: float = 0.0,
    label: str = "数据",
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> List[Dict]:
    """
    获取指定时间段的分页数据（通用框架）

    如果单次请求达到 page_limit 上限，会自动分割时间段：
    月 → 周 → 天 → 小时

    Args:
        api_func: API 调用函数 (address, start_ms, end_ms) -> List[Dict]
        address: 交易者地址
        start_dt: 开始时间
        end_dt: 结束时间
        auto_split: 如果达到上限，是否自动细分
        delay: API 调用延迟（秒）
        label: 日志标签
        page_limit: API 单次返回上限

    Returns:
        记录列表
    """
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    try:
        records = api_func(address, start_ms, end_ms)
    except Exception as e:
        logger.error(f"  获取{label}失败 [{start_dt.format('YYYY-MM-DD')} 至 {end_dt.format('YYYY-MM-DD')}]: {repr(e)}")
        return []

    if not records:
        return []

    # 如果达到上限且允许自动细分
    if auto_split and len(records) >= page_limit:
        duration_days = (end_dt - start_dt).days
        if duration_days > 7:
            logger.debug(f"  {label}达到 {page_limit} 条上限，按周细分...")
            return _fetch_paged_by_weeks(api_func, address, start_dt, end_dt, delay, label, page_limit)
        elif duration_days > 1:
            logger.debug(f"  {label}达到 {page_limit} 条上限，按天细分...")
            return _fetch_paged_by_days(api_func, address, start_dt, end_dt, delay, label, page_limit)
        else:
            logger.debug(f"  {label}达到 {page_limit} 条上限，按小时细分...")
            return _fetch_paged_by_hours(api_func, address, start_dt, end_dt, delay, label, page_limit)

    return records


def _fetch_paged_by_weeks(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.0,
    label: str = "数据",
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> List[Dict]:
    """按周获取分页数据"""
    all_records = []
    current = start_dt

    while current < end_dt:
        next_week = min(current.add(weeks=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_week.timestamp() * 1000)

        try:
            week_records = api_func(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"    获取周{label}失败 [{current.format('MM-DD')}]: {repr(e)}")
            current = next_week
            if delay > 0:
                time.sleep(delay)
            continue

        if week_records:
            if len(week_records) >= page_limit:
                logger.debug(f"    周 [{current.format('MM-DD')}] 达到 {page_limit} 条，按天细分...")
                day_records = _fetch_paged_by_days(api_func, address, current, next_week, delay, label, page_limit)
                all_records.extend(day_records)
            else:
                all_records.extend(week_records)

        current = next_week
        if delay > 0:
            time.sleep(delay)

    return all_records


def _fetch_paged_by_days(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.0,
    label: str = "数据",
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> List[Dict]:
    """按天获取分页数据"""
    all_records = []
    current = start_dt

    while current < end_dt:
        next_day = min(current.add(days=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_day.timestamp() * 1000)

        try:
            day_records = api_func(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"      获取日{label}失败 [{current.format('MM-DD')}]: {repr(e)}")
            current = next_day
            if delay > 0:
                time.sleep(delay)
            continue

        if day_records:
            if len(day_records) >= page_limit:
                logger.debug(f"      天 [{current.format('MM-DD')}] 达到 {page_limit} 条，按小时细分...")
                hour_records = _fetch_paged_by_hours(api_func, address, current, next_day, delay, label, page_limit)
                all_records.extend(hour_records)
            else:
                all_records.extend(day_records)

        current = next_day
        if delay > 0:
            time.sleep(delay)

    return all_records


def _fetch_paged_by_hours(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.0,
    label: str = "数据",
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> List[Dict]:
    """按小时获取分页数据"""
    all_records = []
    current = start_dt
    total_hours = int((end_dt - start_dt).total_seconds() / 3600) + 1
    hour_num = 0

    while current < end_dt:
        next_hour = min(current.add(hours=1), end_dt)
        start_ms = int(current.timestamp() * 1000)
        end_ms = int(next_hour.timestamp() * 1000)
        hour_num += 1

        try:
            hour_records = api_func(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"        获取小时{label}失败 [{current.format('MM-DD HH:00')}]: {repr(e)}")
            current = next_hour
            if delay > 0:
                time.sleep(delay)
            continue

        if hour_records:
            if len(hour_records) >= page_limit:
                # 小时级别还达到上限，用游标分页
                logger.debug(f"        小时 [{current.format('HH:00')}] 达到 {page_limit} 条，使用游标分页...")
                cursor_records = _fetch_paged_by_cursor(
                    api_func, address, current, next_hour, delay, label, page_limit
                )
                all_records.extend(cursor_records)
            else:
                all_records.extend(hour_records)
                logger.debug(
                    f"        小时 [{hour_num}/{total_hours}] "
                    f"{current.format('HH:00')}: {len(hour_records)} 条，"
                    f"累计 {len(all_records)} 条"
                )

        current = next_hour
        if delay > 0:
            time.sleep(delay)

    logger.debug(f"        小时细分完成: 共 {len(all_records)} 条")
    return all_records


def _fetch_paged_by_cursor(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.0,
    label: str = "数据",
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> List[Dict]:
    """
    使用游标分页获取数据（当时间细分仍达到上限时的兜底策略）

    利用 Hyperliquid API 的分页特性：
    "use the last returned timestamp as the next startTime for pagination"
    """
    all_records = []
    current_start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    max_pages = 100  # 防止死循环

    for page in range(max_pages):
        try:
            records = api_func(address, current_start_ms, end_ms)
        except Exception as e:
            logger.error(f"          游标分页失败 (page {page}): {repr(e)}")
            break

        if not records:
            break

        all_records.extend(records)

        # 如果返回数量 < page_limit，说明已经获取完毕
        if len(records) < page_limit:
            break

        # 使用最后一条记录的时间戳作为下一次查询的起始时间
        last_time = records[-1].get('time', 0)
        if last_time <= current_start_ms:
            # 时间没有前进，防止死循环
            logger.warning(f"          游标分页时间未前进，终止 (time={last_time})")
            break

        current_start_ms = last_time
        logger.debug(
            f"          游标分页 page {page + 1}: {len(records)} 条，累计 {len(all_records)} 条"
        )

        if delay > 0:
            time.sleep(delay)

    return all_records


# ============================================================
# 探测函数
# ============================================================

def _probe_records(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> Tuple[List[Dict], bool]:
    """
    快速探测是否有记录

    用一次 API 调用查询全量时间范围：
    - 0 条记录：无历史
    - < page_limit 条：已获取全部
    - >= page_limit 条：记录可能不完整，需要进一步获取

    Returns:
        (records, is_complete)
    """
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    records = api_func(address, start_ms, end_ms)

    if not records:
        return [], True

    is_complete = len(records) < page_limit
    return records, is_complete


def _find_first_record_half_year(
    api_func: Callable,
    address: str,
    start_dt: pendulum.DateTime,
    end_dt: pendulum.DateTime,
    delay: float = 0.0,
    label: str = "数据",
) -> Optional[pendulum.DateTime]:
    """
    使用半年分块快速定位第一条记录所在的半年

    按半年为单位向前探测，找到第一个有记录的半年。

    Returns:
        第一条记录所在半年的起始时间，如果无记录返回 None
    """
    current = start_dt.start_of('month')

    while current < end_dt:
        next_half_year = current.add(months=6)
        actual_end = min(next_half_year, end_dt)

        start_ms = int(current.timestamp() * 1000)
        end_ms = int(actual_end.timestamp() * 1000)

        logger.debug(f"    半年探测{label}: {current.format('YYYY-MM')} 至 {actual_end.format('YYYY-MM')}...")

        try:
            records = api_func(address, start_ms, end_ms)
        except Exception as e:
            logger.error(f"    半年探测{label}失败 [{current.format('YYYY-MM')}]: {repr(e)}")
            current = next_half_year
            if delay > 0:
                time.sleep(delay)
            continue

        if records:
            logger.debug(f"    找到{label}记录于 {current.format('YYYY-MM')} 半年，共 {len(records)} 条")
            return current

        current = next_half_year
        if delay > 0:
            time.sleep(delay)

    return None


# ============================================================
# 资金费历史获取
# ============================================================

def fetch_all_funding_history(
    client: 'SyncAPIClient',
    address: str,
    start_dt: Optional[pendulum.DateTime] = None,
    max_retries: int = 3,
    delay: float = 1.0,
) -> List[Dict]:
    """
    获取交易者的全部资金费历史记录

    策略：
    1. 如果有 start_dt（增量更新），从该时间开始按月获取
    2. 如果无 start_dt（首次获取），先探测全量范围：
       - 0 条记录 → 直接返回空
       - < 500 条 → 直接返回（已获取全部）
       - = 500 条 → 用半年分块定位起始时间，再按月获取

    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 起始时间，如果数据库有记录则从最新记录开始
        max_retries: 单次请求最大重试次数
        delay: API 调用之间的延迟（秒）

    Returns:
        资金费记录列表（已去重）
    """
    DEFAULT_START = pendulum.datetime(2024, 1, 1, tz=SHANGHAI_TZ)
    end = now_shanghai()
    label = "资金费"

    def api_func(addr, start_ms, end_ms):
        return client.get_user_funding_history(addr, start_ms, end_ms)

    return _fetch_all_history_generic(
        api_func=api_func,
        address=address,
        default_start=DEFAULT_START,
        end=end,
        start_dt=start_dt,
        max_retries=max_retries,
        delay=delay,
        label=label,
        dedup_key_func=lambda r: (r.get('hash', ''), r.get('time', 0)),
        page_limit=PAGE_LIMIT_FUNDING,
    )


# ============================================================
# 出入金（账本更新）获取
# ============================================================

def fetch_all_ledger_updates(
    client: 'SyncAPIClient',
    address: str,
    start_dt: Optional[pendulum.DateTime] = None,
    max_retries: int = 3,
    delay: float = 1.0,
) -> List[Dict]:
    """
    获取交易者的全部出入金（非资金费账本更新）记录

    策略同资金费历史获取，使用自适应分层。

    Args:
        client: API 客户端
        address: 交易者地址
        start_dt: 起始时间
        max_retries: 单次请求最大重试次数
        delay: API 调用之间的延迟（秒）

    Returns:
        账本记录列表（已去重）
    """
    DEFAULT_START = pendulum.datetime(2024, 1, 1, tz=SHANGHAI_TZ)
    end = now_shanghai()
    label = "出入金"

    def api_func(addr, start_ms, end_ms):
        return client.get_user_non_funding_ledger(addr, start_ms, end_ms)

    return _fetch_all_history_generic(
        api_func=api_func,
        address=address,
        default_start=DEFAULT_START,
        end=end,
        start_dt=start_dt,
        max_retries=max_retries,
        delay=delay,
        label=label,
        dedup_key_func=lambda r: (r.get('hash', ''), r.get('time', 0)),
        page_limit=PAGE_LIMIT_FUNDING,
    )


# ============================================================
# 历史委托获取
# ============================================================

def fetch_all_historical_orders(
    client: 'SyncAPIClient',
    address: str,
    max_retries: int = 3,
    delay: float = 1.0,
) -> List[Dict]:
    """
    获取交易者的全部历史委托记录

    注意：historicalOrders API 最多只返回 2000 条最近的委托，
    没有时间范围参数，无法翻页获取更早的数据。

    Args:
        client: API 客户端
        address: 交易者地址
        max_retries: 最大重试次数
        delay: API 调用之间的延迟（秒）

    Returns:
        历史委托列表
    """
    logger.debug(f"  获取历史委托（最多 2000 条最近记录）...")

    for retry in range(max_retries):
        try:
            orders = client.get_historical_orders(address)
            if orders:
                logger.debug(f"  获取历史委托完成: 共 {len(orders)} 条")
            else:
                logger.debug(f"  无历史委托记录")
            return orders or []
        except Exception as e:
            retry_num = retry + 1
            if retry_num < max_retries:
                logger.warning(f"  获取历史委托失败（重试 {retry_num}/{max_retries}）: {repr(e)}")
                if delay > 0:
                    time.sleep(delay * 2)
            else:
                logger.error(f"  获取历史委托失败（已重试 {max_retries} 次）: {repr(e)}")
                return []

    return []


# ============================================================
# 通用历史数据获取框架
# ============================================================

def _fetch_all_history_generic(
    api_func: Callable,
    address: str,
    default_start: pendulum.DateTime,
    end: pendulum.DateTime,
    start_dt: Optional[pendulum.DateTime],
    max_retries: int,
    delay: float,
    label: str,
    dedup_key_func: Callable,
    page_limit: int = PAGE_LIMIT_FUNDING,
) -> List[Dict]:
    """
    通用的从前往后获取历史数据框架（优化版）

    策略：
    1. 如果有 start_dt（增量更新），从该时间开始按月获取
    2. 如果无 start_dt（首次获取），先探测全量范围：
       - 0 条 → 直接返回空
       - < page_limit 条 → 已获取全部
       - = page_limit 条 → 半年分块定位，按月获取

    Args:
        api_func: API 调用函数 (address, start_ms, end_ms) -> List[Dict]
        address: 交易者地址
        default_start: 默认起始时间
        end: 结束时间
        start_dt: 指定起始时间（增量更新时使用）
        max_retries: 最大重试次数
        delay: API 调用延迟
        label: 日志标签
        dedup_key_func: 去重键提取函数
        page_limit: API 单次返回上限

    Returns:
        记录列表（已去重）
    """
    all_records = []
    seen_keys = set()

    def add_records(records: List[Dict]) -> int:
        """添加记录并去重"""
        added = 0
        for record in records:
            key = dedup_key_func(record)
            if key not in seen_keys:
                seen_keys.add(key)
                all_records.append(record)
                added += 1
        return added

    # ========== 首次获取：先探测 ==========
    if start_dt is None:
        logger.debug(f"  首次获取{label}，探测全量范围: {default_start.format('YYYY-MM-DD')} → {end.format('YYYY-MM-DD')}")

        probe_records = None
        is_complete = False
        for retry in range(max_retries):
            try:
                probe_records, is_complete = _probe_records(
                    api_func, address, default_start, end, page_limit
                )
                break
            except Exception as e:
                retry_num = retry + 1
                if retry_num < max_retries:
                    logger.warning(f"    探测{label}失败（重试 {retry_num}/{max_retries}）: {repr(e)}")
                    if delay > 0:
                        time.sleep(delay * 2)
                else:
                    logger.error(f"    探测{label}失败（已重试 {max_retries} 次），终止: {repr(e)}")
                    return []

        # 情况1：无记录
        if not probe_records:
            logger.debug(f"  无{label}记录，跳过")
            return []

        # 情况2：< page_limit 条，已获取全部
        if is_complete:
            logger.debug(f"  {label}获取完成: 共 {len(probe_records)} 条（< {page_limit}，已全部获取）")
            return probe_records

        # 情况3：= page_limit 条，需要进一步获取
        logger.debug(f"  {label}探测返回 {page_limit} 条，使用半年分块定位起始时间...")
        if delay > 0:
            time.sleep(delay)

        first_half_year = _find_first_record_half_year(
            api_func, address, default_start, end, delay, label
        )

        if first_half_year is None:
            logger.warning(f"  半年探测未找到{label}记录，使用探测结果")
            return probe_records

        start = first_half_year
        logger.debug(f"  从 {start.format('YYYY-MM')} 开始按月获取{label}...")
        if delay > 0:
            time.sleep(delay)
    else:
        # 增量更新
        start = start_dt
        logger.debug(f"  增量获取{label}: {start.format('YYYY-MM-DD')} → {end.format('YYYY-MM-DD')}")

    # ========== 按月获取 ==========
    current = start.start_of('month')
    month_num = 0

    while current < end:
        next_month = current.add(months=1)
        actual_end = min(next_month, end)
        actual_start = max(current, start)

        month_num += 1
        logger.debug(
            f"  [{label} 月份 {month_num}] {actual_start.format('YYYY-MM-DD')} 至 "
            f"{actual_end.format('YYYY-MM-DD')}..."
        )

        # 带重试的获取
        success = False
        month_records = None
        for retry in range(max_retries):
            try:
                month_records = _fetch_paged_for_period(
                    api_func, address, actual_start, actual_end,
                    auto_split=True, delay=delay, label=label,
                    page_limit=page_limit
                )
                success = True
                break
            except Exception as e:
                retry_num = retry + 1
                if retry_num < max_retries:
                    logger.warning(f"    获取{label}失败（重试 {retry_num}/{max_retries}）: {repr(e)}")
                    if delay > 0:
                        time.sleep(delay * 2)
                else:
                    logger.error(f"    获取{label}失败（已重试 {max_retries} 次），终止: {repr(e)}")

        if not success:
            logger.warning(f"  因连续失败终止{label}获取，已获取 {len(all_records)} 条记录")
            return all_records

        if month_records:
            new_count = add_records(month_records)
            logger.debug(f"    获取 {len(month_records)} 条，新增 {new_count} 条，累计 {len(all_records)} 条")
        else:
            logger.debug(f"    无记录")

        current = next_month
        if delay > 0:
            time.sleep(delay)

    logger.debug(f"  {label}总计获取 {len(all_records)} 条记录（去重后）")
    return all_records


# ============================================================
# 综合获取入口
# ============================================================

def fetch_trader_account_history(
    client: 'SyncAPIClient',
    address: str,
    funding_start_dt: Optional[pendulum.DateTime] = None,
    ledger_start_dt: Optional[pendulum.DateTime] = None,
    max_retries: int = 3,
    delay: float = 1.0,
    fetch_funding: bool = True,
    fetch_orders: bool = True,
    fetch_ledger: bool = True,
) -> Dict[str, List[Dict]]:
    """
    综合获取交易员的全部账户历史数据

    Args:
        client: API 客户端
        address: 交易者地址
        funding_start_dt: 资金费历史的起始时间（增量更新时使用）
        ledger_start_dt: 出入金的起始时间（增量更新时使用）
        max_retries: 最大重试次数
        delay: API 调用之间的延迟（秒）
        fetch_funding: 是否获取资金费历史
        fetch_orders: 是否获取历史委托
        fetch_ledger: 是否获取出入金

    Returns:
        {
            'funding': List[Dict],      # 资金费历史
            'orders': List[Dict],       # 历史委托
            'ledger': List[Dict],       # 出入金记录
        }
    """
    result = {
        'funding': [],
        'orders': [],
        'ledger': [],
    }

    logger.info(f"开始获取交易员 {address[:10]}... 的账户历史数据")

    # 1. 获取资金费历史
    if fetch_funding:
        logger.info(f"[1/3] 获取资金费历史...")
        result['funding'] = fetch_all_funding_history(
            client, address,
            start_dt=funding_start_dt,
            max_retries=max_retries,
            delay=delay
        )
        logger.info(f"  资金费历史: {len(result['funding'])} 条")

    # 2. 获取历史委托
    if fetch_orders:
        logger.info(f"[2/3] 获取历史委托...")
        result['orders'] = fetch_all_historical_orders(
            client, address,
            max_retries=max_retries,
            delay=delay
        )
        logger.info(f"  历史委托: {len(result['orders'])} 条")

    # 3. 获取出入金
    if fetch_ledger:
        logger.info(f"[3/3] 获取出入金记录...")
        result['ledger'] = fetch_all_ledger_updates(
            client, address,
            start_dt=ledger_start_dt,
            max_retries=max_retries,
            delay=delay
        )
        logger.info(f"  出入金记录: {len(result['ledger'])} 条")

    total = len(result['funding']) + len(result['orders']) + len(result['ledger'])
    logger.info(
        f"交易员 {address[:10]}... 账户历史数据获取完成: "
        f"资金费 {len(result['funding'])} 条, "
        f"委托 {len(result['orders'])} 条, "
        f"出入金 {len(result['ledger'])} 条, "
        f"共 {total} 条"
    )

    return result
