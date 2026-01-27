"""
S级交易员仓位监控脚本

功能说明：
1. 获取所有S级的交易员
2. 异步更新交易员的当前仓位并保存到数据库
3. 如果发现有新仓位，通过 Redis WebSocket 通知
4. 如果1分钟内新仓位>=阈值，发送行情通知（通过 Redis WebSocket 广播，10分钟内只推送一次）

运行模式：无限循环执行

示例：
  python monitor_s_traders_positions.py --rate 10
    以每秒10个请求的速率获取仓位
  
  python monitor_s_traders_positions.py -r 5 --limit 500
    以每秒5个请求的速率，只监控评分最高的前500个交易员
  
  python monitor_s_traders_positions.py -r 10 --offset 100 --limit 200
    跳过前100个，监控第101-300名的交易员
  
  python monitor_s_traders_positions.py -r 10 --redis
    启用 Redis 推送，本地运行 local_position_listener.py 可接收通知
"""
import sys
import asyncio
import argparse
import time
import json
from pathlib import Path
from typing import List, Dict, Optional
from collections import deque
import pendulum

import redis
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import TraderDatabase
from clients.hyperliquid_client import HyperliquidClient
from config.settings import settings
from screener.utils import now_shanghai

# Redis 新仓位推送 channel
REDIS_POSITION_CHANNEL = "new_positions"
# Redis 立即跟单开仓通知 channel（与 engine/position_copy_trading.py 一致）
REDIS_OPEN_CHANNEL = "position_tracking_open"
# Redis WebSocket 广播 channel（供 WebSocket 服务接收并广播给客户端）
REDIS_WS_CHANNEL = "ws_new_positions"
# Redis 通知 channel（行情提醒等通知，与 services/websocket.py 一致）
REDIS_NOTIFICATIONS_CHANNEL = "notifications"

# 行情检测配置
MARKET_ACTIVITY_WINDOW = 60  # 1分钟窗口（秒）
MARKET_ACTIVITY_THRESHOLD = 5  # 触发阈值：新仓位数量
MARKET_ACTIVITY_COOLDOWN = 600  # 10分钟冷却时间（秒）


class AsyncRateLimiter:
    """异步速率限制器 - 令牌桶算法"""
    
    def __init__(self, rate: float, max_tokens: Optional[int] = None):
        """
        Args:
            rate: 每秒允许的请求数
            max_tokens: 最大令牌数（突发容量），默认等于rate
        """
        self.rate = rate
        self.max_tokens = max_tokens or int(rate)
        self.tokens = self.max_tokens
        self.last_update = time.perf_counter()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """获取一个令牌，如果没有可用令牌则等待"""
        async with self._lock:
            now = time.perf_counter()
            # 补充令牌
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1:
                # 需要等待
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = time.perf_counter()
            else:
                self.tokens -= 1


class MarketActivityTracker:
    """
    行情活动追踪器
    
    追踪1分钟内的新仓位数量，如果达到阈值则触发通知
    10分钟内只通知一次
    
    支持 Redis 存储以实现多服务器共享状态
    """
    
    # Redis 键名
    REDIS_POSITION_TIMESTAMPS_KEY = "market_activity:position_timestamps"
    REDIS_LAST_NOTIFICATION_KEY = "market_activity:last_notification_time"
    
    def __init__(
        self,
        window_seconds: int = MARKET_ACTIVITY_WINDOW,
        threshold: int = MARKET_ACTIVITY_THRESHOLD,
        cooldown_seconds: int = MARKET_ACTIVITY_COOLDOWN,
        redis_client: redis.Redis = None
    ):
        self.window_seconds = window_seconds
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        self.redis_client = redis_client
        
        # 本地备用存储（当 Redis 不可用时）
        self._local_position_timestamps: deque = deque()
        self._local_last_notification_time: Optional[pendulum.DateTime] = None
    
    def add_positions(self, count: int) -> None:
        """记录新仓位"""
        now = now_shanghai()
        timestamp = now.timestamp()
        
        if self.redis_client:
            try:
                # 使用 Redis ZSET，score 为时间戳
                pipe = self.redis_client.pipeline()
                for _ in range(count):
                    # 使用唯一的成员值（时间戳+随机后缀）
                    member = f"{timestamp}:{time.perf_counter_ns()}"
                    pipe.zadd(self.REDIS_POSITION_TIMESTAMPS_KEY, {member: timestamp})
                # 设置 key 过期时间（比窗口时间稍长一点，自动清理）
                pipe.expire(self.REDIS_POSITION_TIMESTAMPS_KEY, self.window_seconds + 60)
                pipe.execute()
                return
            except Exception as e:
                logger.debug(f"Redis add_positions 失败，使用本地存储: {e}")
        
        # 本地备用
        for _ in range(count):
            self._local_position_timestamps.append(now)
    
    def _clean_old_positions(self) -> None:
        """清理超出时间窗口的记录"""
        now = now_shanghai()
        cutoff_timestamp = now.subtract(seconds=self.window_seconds).timestamp()
        
        if self.redis_client:
            try:
                # 删除时间窗口之前的记录
                self.redis_client.zremrangebyscore(
                    self.REDIS_POSITION_TIMESTAMPS_KEY,
                    "-inf",
                    cutoff_timestamp
                )
                return
            except Exception as e:
                logger.debug(f"Redis _clean_old_positions 失败: {e}")
        
        # 本地备用
        cutoff = now.subtract(seconds=self.window_seconds)
        while self._local_position_timestamps and self._local_position_timestamps[0] < cutoff:
            self._local_position_timestamps.popleft()
    
    def get_recent_count(self) -> int:
        """获取时间窗口内的新仓位数量"""
        self._clean_old_positions()
        
        if self.redis_client:
            try:
                now = now_shanghai()
                cutoff_timestamp = now.subtract(seconds=self.window_seconds).timestamp()
                # 统计在时间窗口内的记录数
                count = self.redis_client.zcount(
                    self.REDIS_POSITION_TIMESTAMPS_KEY,
                    cutoff_timestamp,
                    "+inf"
                )
                return count
            except Exception as e:
                logger.debug(f"Redis get_recent_count 失败: {e}")
        
        # 本地备用
        return len(self._local_position_timestamps)
    
    def _get_last_notification_time(self):
        """获取上次通知时间"""
        import pendulum
        if self.redis_client:
            try:
                value = self.redis_client.get(self.REDIS_LAST_NOTIFICATION_KEY)
                if value:
                    return pendulum.from_timestamp(float(value), tz="Asia/Shanghai")
                return None
            except Exception as e:
                logger.debug(f"Redis _get_last_notification_time 失败: {e}")
        
        return self._local_last_notification_time
    
    def should_notify(self) -> bool:
        """
        检查是否应该发送通知
        
        Returns:
            True 如果满足条件：
            1. 1分钟内新仓位 >= 阈值
            2. 距离上次通知超过10分钟（或从未通知过）
        """
        # 获取最近的仓位数量
        recent_count = self.get_recent_count()
        
        # 检查数量是否达到阈值
        if recent_count < self.threshold:
            return False
        
        # 检查冷却时间
        now = now_shanghai()
        last_notification = self._get_last_notification_time()
        if last_notification is not None:
            time_since_last = (now - last_notification).in_seconds()
            if time_since_last < self.cooldown_seconds:
                return False
        
        return True
    
    def mark_notified(self) -> None:
        """标记已发送通知"""
        now = now_shanghai()
        
        if self.redis_client:
            try:
                # 存储时间戳，并设置过期时间
                self.redis_client.set(
                    self.REDIS_LAST_NOTIFICATION_KEY,
                    str(now.timestamp()),
                    ex=self.cooldown_seconds + 60  # 过期时间比冷却时间稍长
                )
                return
            except Exception as e:
                logger.debug(f"Redis mark_notified 失败: {e}")
        
        # 本地备用
        self._local_last_notification_time = now
    
    def get_cooldown_remaining(self) -> int:
        """获取剩余冷却时间（秒）"""
        last_notification = self._get_last_notification_time()
        if last_notification is None:
            return 0
        
        elapsed = (now_shanghai() - last_notification).in_seconds()
        remaining = self.cooldown_seconds - elapsed
        return max(0, int(remaining))


def get_s_rated_traders(db: TraderDatabase, limit: int = 0, offset: int = 0) -> List[Dict]:
    """
    获取所有S级交易员，按评分从高到低排序
    
    Args:
        db: 数据库实例
        limit: 限制返回数量，0表示不限制
        offset: 跳过前N个交易员，0表示不跳过
    
    Returns:
        S级交易员列表（按 overall_score 降序排序）
    """
    traders = db.get_traders_by_rating('S')
    
    # 按 overall_score 从高到低排序
    traders.sort(key=lambda x: x.get('overall_score', 0) or 0, reverse=True)
    
    total_count = len(traders)
    
    # 应用 offset 和 limit
    if offset > 0:
        traders = traders[offset:]
    
    if limit > 0 and len(traders) > limit:
        traders = traders[:limit]
    
    # 日志输出
    if offset > 0 or limit > 0:
        range_start = offset + 1
        range_end = offset + len(traders)
        logger.info(f"获取到 {total_count} 个S级交易员，选取第 {range_start}-{range_end} 名（按评分排序）")
    else:
        logger.info(f"获取到 {total_count} 个S级交易员（按评分排序）")
    
    return traders


def get_current_positions_from_db(db: TraderDatabase, address: str) -> Dict[str, Dict]:
    """
    从数据库获取交易员的当前持仓
    
    Args:
        db: 数据库实例
        address: 交易员地址
    
    Returns:
        {coin: position_data} 字典
    """
    positions = db.get_positions(address)
    return {pos['coin']: pos for pos in positions}


def detect_new_positions(
    old_positions: Dict[str, Dict],
    new_positions: Dict[str, Dict]
) -> List[Dict]:
    """
    检测新开的仓位
    
    Args:
        old_positions: 更新前的持仓 {coin: position_data}
        new_positions: 更新后的持仓 {coin: position_data}
    
    Returns:
        新仓位列表
    """
    old_coins = set(old_positions.keys())
    new_coins = set(new_positions.keys())
    
    # 新出现的币种就是新仓位
    new_coin_set = new_coins - old_coins
    
    new_positions_list = []
    for coin in new_coin_set:
        pos = new_positions[coin]
        new_positions_list.append(pos)
    
    return new_positions_list


def format_position_direction(szi: float) -> tuple[str, str]:
    """
    根据szi判断仓位方向
    
    Args:
        szi: 仓位数量（正数=多，负数=空）
    
    Returns:
        (方向文字, emoji)
    """
    if szi > 0:
        return "做多", "🟢"
    else:
        return "做空", "🔴"


def create_position_tracking_for_copy(
    db: TraderDatabase,
    trader: Dict,
    position: Dict,
    redis_client: redis.Redis = None
) -> Optional[int]:
    """
    为符合条件的仓位创建跟单记录并发送 Redis 通知
    
    会根据仓位杠杆匹配对应的配置规则：
    - 如果有匹配的立即跟单配置规则，使用规则中的参数创建跟单记录
    - 如果没有匹配的规则，则不创建跟单记录
    
    Args:
        db: 数据库实例
        trader: 交易员信息
        position: 仓位信息
        redis_client: Redis 客户端
    
    Returns:
        创建的 tracking_id，如果没有匹配规则/已存在/创建失败则返回 None
    """
    address = trader['address']
    coin = position.get('coin', '')
    
    # 获取仓位详情
    szi = float(position.get('szi', 0) or 0)
    entry_px = float(position.get('entry_px', 0) or 0)
    leverage = float(position.get('leverage', 1) or 1)
    side = 'long' if szi > 0 else 'short'
    
    # 根据杠杆匹配配置规则
    matched_config = db.get_copy_config_by_leverage('immediate', leverage)
    matched_rule_name = matched_config.get('_matched_rule_name')
    
    # 如果没有匹配的规则，不创建跟单记录
    if not matched_rule_name:
        logger.debug(f"    跳过立即跟单: {coin} 杠杆 {leverage}x 无匹配规则")
        return None
    
    # 检查是否已存在活跃的跟单记录
    if db.check_position_tracking_exists(address, coin):
        logger.debug(f"    跳过立即跟单: {coin} 已有活跃跟单记录")
        return None
    
    # 使用匹配的配置
    effective_config = matched_config
    
    if matched_rule_name:
        logger.info(f"    → 杠杆 {leverage}x 匹配规则: {matched_rule_name}")
    
    # 创建跟单记录
    tracking_data = {
        'target_address': address,
        'target_name': trader.get('name', '') or address[:10] + '...',
        'symbol': coin,
        'is_enabled': True,
        # 从匹配的配置获取跟单参数
        'copy_ratio': effective_config.get('copy_ratio', 0.1),
        'max_position_size_usd': effective_config.get('max_position_size_usd', 500.0),
        'min_position_size_usd': effective_config.get('min_position_size_usd', 20.0),
        'copy_leverage': effective_config.get('copy_leverage', False),
        'max_leverage': effective_config.get('max_leverage', 10),
        'default_leverage': effective_config.get('default_leverage', 3),
        'slippage': effective_config.get('slippage', 0.001),
        # 目标仓位快照
        'target_initial_size': abs(szi),
        'target_initial_side': side,
        'target_initial_entry_price': entry_px,
        'target_initial_leverage': leverage,
        'target_is_starred': trader.get('is_starred', False),
        'status': 'pending'
    }
    
    try:
        tracking_id = db.save_position_tracking(tracking_data)
        
        if tracking_id:
            logger.success(f"    ✓ 创建立即跟单记录: {coin} {side} (tracking_id={tracking_id})")
            
            # 发送 Redis 通知触发开仓
            if redis_client:
                try:
                    redis_client.publish(REDIS_OPEN_CHANNEL, str(tracking_id))
                    logger.info(f"    ✓ 已发送开仓通知 (channel={REDIS_OPEN_CHANNEL})")
                except Exception as e:
                    logger.warning(f"    ⚠ Redis 开仓通知发送失败: {e}")
            
            return tracking_id
        else:
            logger.error(f"    ✗ 创建跟单记录失败: {coin}")
            return None
            
    except Exception as e:
        logger.error(f"    ✗ 创建跟单记录异常: {coin} - {e}")
        return None


async def fetch_user_state_async(
    hl_client: HyperliquidClient,
    address: str
) -> Optional[Dict]:
    """
    异步获取用户状态
    
    Args:
        hl_client: HyperliquidClient 实例
        address: 交易员地址
    
    Returns:
        用户状态字典或 None
    """
    try:
        # 使用 asyncio.to_thread 将同步调用转换为异步
        user_state = await asyncio.to_thread(hl_client.info.user_state, address)
        return user_state
    except Exception as e:
        logger.debug(f"获取用户状态异常 {address[:10]}...: {e}")
        return None


def process_trader_result(
    db: TraderDatabase,
    trader: Dict,
    user_state: Optional[Dict],
    old_positions: Dict[str, Dict],
    redis_client: redis.Redis = None
) -> int:
    """
    处理单个交易员的持仓结果
    
    Args:
        db: 数据库实例
        trader: 交易员信息
        user_state: 从API获取的用户状态
        old_positions: 更新前的持仓
        redis_client: Redis 客户端
    
    Returns:
        新仓位数量
    """
    address = trader['address']
    rating = trader.get('rating')
    score = trader.get('overall_score')
    
    if user_state is None:
        return 0
    
    asset_positions = user_state.get('assetPositions', [])
    
    if not asset_positions:
        # 清空数据库中的持仓
        db.save_positions(address, [])
        return 0
    
    # 构建原始仓位数据映射（用于立即跟单条件检查）
    raw_positions_map = {}
    for pos_data in asset_positions:
        pos = pos_data.get('position', {})
        coin = pos.get('coin', '')
        if coin:
            leverage_info = pos.get('leverage', {})
            raw_positions_map[coin] = {
                'coin': coin,
                'szi': pos.get('szi', 0),
                'entry_px': pos.get('entryPx', 0),
                'leverage': leverage_info.get('value', 1) if isinstance(leverage_info, dict) else leverage_info
            }
    
    # 保存持仓到数据库
    positions_saved = db.save_positions(address, asset_positions)
    
    # 获取更新后的持仓
    new_positions = get_current_positions_from_db(db, address)
    
    # 检测新仓位
    new_position_list = detect_new_positions(old_positions, new_positions)
    
    if not new_position_list:
        return 0
    
    logger.success(f"  {address[:16]}... 检测到 {len(new_position_list)} 个新仓位!")
    
    for pos in new_position_list:
        coin = pos.get('coin', 'Unknown')
        szi = float(pos.get('szi', 0))
        direction, _ = format_position_direction(szi)
        
        # 设置开仓时间为当前时间
        pos['open_time'] = now_shanghai().format('YYYY-MM-DD HH:mm:ss')
        
        # 获取原始仓位数据（包含杠杆等完整信息）
        raw_pos = raw_positions_map.get(coin, pos)
        
        # 保存新仓位记录到数据库
        record_id = db.save_new_position(
            trader_address=address,
            position=raw_pos,
            trader_name=trader.get('name'),
            trader_rating=rating,
            trader_score=score,
            notified=True,  # 通过 Redis WebSocket 通知
            target_is_starred=trader.get('is_starred', False)
        )
        if record_id:
            logger.debug(f"    ✓ 已保存新仓位记录: id={record_id}")
        else:
            logger.warning(f"    ⚠ 保存新仓位记录失败: {coin}")
        
        # Redis Pub/Sub 推送（供本地客户端接收）
        if redis_client:
            try:
                redis_client.publish(REDIS_POSITION_CHANNEL, f"https://app.hyperliquid.xyz/trade/{coin}")
            except Exception as e:
                logger.debug(f"    Redis 推送失败: {e}")
            
            # 发送详细数据到 WebSocket 广播 channel
            try:
                szi_val = float(raw_pos.get('szi', 0) or 0)
                entry_px_val = float(raw_pos.get('entry_px', 0) or 0)
                leverage_val = raw_pos.get('leverage', 1)
                if isinstance(leverage_val, dict):
                    leverage_val = leverage_val.get('value', 1)
                
                ws_data = {
                    'id': record_id,
                    'trader_address': address,
                    'trader_name': trader.get('name', ''),
                    'trader_rating': rating,
                    'trader_score': score,
                    'target_is_starred': trader.get('is_starred', False),
                    'coin': coin,
                    'direction': 'long' if szi_val > 0 else 'short',
                    'szi': abs(szi_val),
                    'entry_px': entry_px_val,
                    'position_value': abs(szi_val) * entry_px_val,
                    'leverage': int(leverage_val or 1),
                    'detected_at': now_shanghai().to_iso8601_string(),
                    'trade_url': f"https://app.hyperliquid.xyz/trade/{coin}"
                }
                redis_client.publish(REDIS_WS_CHANNEL, json.dumps(ws_data))
                logger.debug(f"    ✓ 已发送 WebSocket 广播")
            except Exception as e:
                logger.debug(f"    WebSocket 广播失败: {e}")
        
        # 立即跟单：根据杠杆匹配配置规则
        if redis_client:
            # 尝试创建跟单记录（内部会根据杠杆匹配规则）
            create_position_tracking_for_copy(
                db, trader, raw_pos, redis_client
            )
    
    return len(new_position_list)


async def run_monitoring_cycle_async(
    db: TraderDatabase,
    hl_client: HyperliquidClient,
    rate: float = 10.0,
    limit: int = 0,
    offset: int = 0,
    redis_client: redis.Redis = None,
    activity_tracker: MarketActivityTracker = None
) -> Dict:
    """
    异步运行一次监控周期
    
    Args:
        db: 数据库实例
        hl_client: HyperliquidClient 实例
        rate: 每秒请求数
        limit: 限制处理的交易员数量，0表示不限制
        offset: 跳过前N个交易员，0表示不跳过
        redis_client: Redis 客户端
        activity_tracker: 行情活动追踪器
    
    Returns:
        统计信息
    """
    total_stats = {
        'traders_processed': 0,
        'new_positions_total': 0,
        'errors': 0
    }
    
    # 获取S级交易员（按评分排序，可限制数量和偏移）
    traders = get_s_rated_traders(db, limit=limit, offset=offset)
    
    if not traders:
        logger.warning("没有找到S级交易员")
        return total_stats
    
    # 先获取所有交易员的当前持仓（用于对比）
    old_positions_map = {}
    for trader in traders:
        address = trader['address']
        old_positions_map[address] = get_current_positions_from_db(db, address)
    
    logger.info(f"开始处理 {len(traders)} 个S级交易员，速率: {rate} 请求/秒")
    logger.info("-" * 60)
    
    # 创建速率限制器
    rate_limiter = AsyncRateLimiter(rate=rate)
    start_time = time.perf_counter()
    
    total_traders = len(traders)
    
    async def fetch_and_process(idx: int, trader: Dict):
        """获取并处理单个交易员"""
        address = trader['address']
        old_positions = old_positions_map.get(address, {})
        
        # 等待速率限制
        await rate_limiter.acquire()
        
        # 获取用户状态
        user_state = await fetch_user_state_async(hl_client, address)
        
        if user_state is None:
            logger.warning(f"[{idx+1}/{total_traders}] ✗ {address[:16]}... 获取失败")
            return {'success': False, 'new_count': 0}
        
        # 统计仓位数量
        positions = user_state.get('assetPositions', [])
        positions_count = len([p for p in positions if float(p.get('position', {}).get('szi', 0)) != 0])
        
        # 处理结果
        try:
            new_count = process_trader_result(
                db, trader, user_state, old_positions,
                redis_client=redis_client
            )
            if new_count > 0:
                logger.success(f"[{idx+1}/{total_traders}] ✓ {address[:16]}... 仓位: {positions_count}, 新增: {new_count}")
            else:
                logger.info(f"[{idx+1}/{total_traders}] ✓ {address[:16]}... 仓位: {positions_count}")
            return {'success': True, 'new_count': new_count}
        except Exception as e:
            logger.error(f"[{idx+1}/{total_traders}] ✗ {address[:16]}... 处理失败: {e}")
            return {'success': False, 'new_count': 0}
    
    # 创建所有任务
    tasks = [
        fetch_and_process(i, trader)
        for i, trader in enumerate(traders)
    ]
    
    # 并发执行（受速率限制）
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 统计结果
    for result in results:
        if isinstance(result, Exception):
            total_stats['errors'] += 1
        elif result['success']:
            total_stats['traders_processed'] += 1
            total_stats['new_positions_total'] += result['new_count']
        else:
            total_stats['errors'] += 1
    
    total_duration = time.perf_counter() - start_time
    actual_rate = len(traders) / total_duration if total_duration > 0 else 0
    
    logger.info("-" * 60)
    logger.info(f"本轮完成: 处理 {total_stats['traders_processed']} 个交易员, "
                f"发现 {total_stats['new_positions_total']} 个新仓位, "
                f"错误 {total_stats['errors']} 个")
    logger.info(f"耗时: {total_duration:.1f}s, 实际速率: {actual_rate:.2f} 请求/秒")
    
    # 记录新仓位到活动追踪器并检查是否需要通知
    if activity_tracker and total_stats['new_positions_total'] > 0:
        activity_tracker.add_positions(total_stats['new_positions_total'])
        
        # 检查是否需要发送行情通知
        if activity_tracker.should_notify() and redis_client:
            recent_count = activity_tracker.get_recent_count()
            logger.warning(f"🔥 检测到行情活动: 1分钟内 {recent_count} 个新仓位!")
            
            # 通过 Redis notifications channel 广播行情通知
            try:
                content = (
                    f"**检测到市场活动频繁！**\n\n"
                    f"最近1分钟内发现 **{recent_count}** 个新仓位\n\n"
                    f"⏰ 时间: {now_shanghai().format('YYYY-MM-DD HH:mm:ss')}\n"
                    f"📊 建议关注市场动态"
                )
                market_alert_data = {
                    'type': 'market_alert',
                    'title': '🔥 行情提醒',
                    'content': content,
                    'target_address': None,
                    'symbol': None,
                    'side': None,
                    'size': None,
                    'pnl': None
                }
                redis_client.publish(REDIS_NOTIFICATIONS_CHANNEL, json.dumps(market_alert_data))
                activity_tracker.mark_notified()
                logger.success("✓ 行情通知已发送（10分钟内不再重复）")
            except Exception as e:
                logger.error(f"发送行情通知异常: {e}")
    
    # 显示行情追踪状态
    if activity_tracker:
        recent = activity_tracker.get_recent_count()
        cooldown = activity_tracker.get_cooldown_remaining()
        if cooldown > 0:
            logger.info(f"行情追踪: 近1分钟 {recent} 个新仓位, 通知冷却剩余 {cooldown}s")
        else:
            logger.info(f"行情追踪: 近1分钟 {recent} 个新仓位")
    
    return total_stats


async def main_async(args):
    """异步主函数"""
    logger.info("=" * 60)
    logger.info("S级交易员仓位监控脚本")
    logger.info("=" * 60)
    logger.info(f"运行模式: 无限循环")
    logger.info(f"请求速率: {args.rate} 请求/秒")
    logger.info(f"交易员偏移: {args.offset}（跳过前N个）")
    logger.info(f"交易员限制: {args.limit if args.limit > 0 else '不限制'}（按评分排序）")
    logger.info("")
    
    # 初始化 Hyperliquid 客户端
    logger.info("初始化 Hyperliquid 客户端...")
    hl_client = HyperliquidClient()
    logger.success("✓ Hyperliquid 客户端初始化成功")
    
    # 初始化数据库
    logger.info("初始化数据库连接...")
    db = TraderDatabase()
    logger.success("✓ 数据库连接成功")
    
    # 初始化 Redis（用于本地推送、WebSocket 广播和行情追踪共享状态）
    logger.info("初始化 Redis 连接...")
    redis_client = None
    try:
        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=True
        )
        redis_client.ping()
        logger.success(f"✓ Redis 已连接 ({settings.redis.host}:{settings.redis.port})")
        if args.redis:
            logger.info(f"  本地监听: python local_position_listener.py")
    except Exception as e:
        logger.warning(f"⚠ Redis 连接失败: {e}，行情追踪将使用本地存储（不跨服务器共享）")
        redis_client = None
    
    # 初始化行情活动追踪器（使用 Redis 共享状态）
    activity_tracker = MarketActivityTracker(redis_client=redis_client)
    logger.info(f"行情追踪器: 阈值={activity_tracker.threshold}个/分钟, 冷却={activity_tracker.cooldown_seconds}秒")
    if redis_client:
        logger.info(f"  行情追踪状态通过 Redis 共享（支持多服务器）")
    
    logger.info("")
    
    # 主循环
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            logger.info(f"{'='*60}")
            logger.info(f"第 {cycle_count} 轮监控 - {now_shanghai().format('YYYY-MM-DD HH:mm:ss')}")
            logger.info(f"{'='*60}")
            
            await run_monitoring_cycle_async(
                db, hl_client,
                rate=args.rate,
                limit=args.limit,
                offset=args.offset,
                redis_client=redis_client if args.redis else None,  # 用于位置推送和 WebSocket 广播
                activity_tracker=activity_tracker
            )
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断")
    finally:
        db.close()
        logger.info("数据库连接已关闭")


def main():
    parser = argparse.ArgumentParser(
        description="S级交易员仓位监控脚本（无限循环）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python monitor_s_traders_positions.py --rate 10
    以每秒10个请求的速率获取仓位
  
  python monitor_s_traders_positions.py -r 5 --limit 500
    以每秒5个请求的速率，只监控评分最高的前500个交易员
  
  python monitor_s_traders_positions.py -r 10 --offset 100 --limit 200
    跳过前100个，监控第101-300名的交易员
  
  python monitor_s_traders_positions.py -r 10 --redis
    启用 Redis 推送，本地运行 local_position_listener.py 可接收通知
"""
    )
    parser.add_argument(
        "--rate", "-r",
        type=float,
        default=10.0,
        help="每秒请求数（默认: 10）"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="限制监控的交易员数量，按评分从高到低选取（默认: 0，不限制）"
    )
    parser.add_argument(
        "--offset", "-o",
        type=int,
        default=0,
        help="跳过前N个交易员（默认: 0，不跳过）"
    )
    parser.add_argument(
        "--redis",
        action="store_true",
        help="启用 Redis 推送（本地监听脚本可接收新仓位通知）"
    )
    
    args = parser.parse_args()
    
    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
