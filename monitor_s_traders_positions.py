"""
S级交易员仓位监控脚本

功能说明：
1. 获取所有S级的交易员
2. 异步更新交易员的当前仓位并保存到数据库
3. 如果发现有新仓位，通过飞书通知
4. 如果1分钟内新仓位>=10个，发送行情通知（10分钟内只推送一次）

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
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque

import redis
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import TraderDatabase
from clients.feishu_client import FeishuClient, CopyTradingNotifier
from clients.hyperliquid_client import HyperliquidClient
from config.settings import settings

# Redis 新仓位推送 channel
REDIS_POSITION_CHANNEL = "new_positions"

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
    """
    
    def __init__(
        self,
        window_seconds: int = MARKET_ACTIVITY_WINDOW,
        threshold: int = MARKET_ACTIVITY_THRESHOLD,
        cooldown_seconds: int = MARKET_ACTIVITY_COOLDOWN
    ):
        self.window_seconds = window_seconds
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds
        
        # 存储新仓位的时间戳
        self.position_timestamps: deque = deque()
        # 上次发送通知的时间
        self.last_notification_time: Optional[datetime] = None
    
    def add_positions(self, count: int) -> None:
        """记录新仓位"""
        now = datetime.now()
        for _ in range(count):
            self.position_timestamps.append(now)
    
    def _clean_old_positions(self) -> None:
        """清理超出时间窗口的记录"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        
        while self.position_timestamps and self.position_timestamps[0] < cutoff:
            self.position_timestamps.popleft()
    
    def get_recent_count(self) -> int:
        """获取时间窗口内的新仓位数量"""
        self._clean_old_positions()
        return len(self.position_timestamps)
    
    def should_notify(self) -> bool:
        """
        检查是否应该发送通知
        
        Returns:
            True 如果满足条件：
            1. 1分钟内新仓位 >= 阈值
            2. 距离上次通知超过10分钟（或从未通知过）
        """
        self._clean_old_positions()
        
        # 检查数量是否达到阈值
        if len(self.position_timestamps) < self.threshold:
            return False
        
        # 检查冷却时间
        now = datetime.now()
        if self.last_notification_time is not None:
            time_since_last = (now - self.last_notification_time).total_seconds()
            if time_since_last < self.cooldown_seconds:
                return False
        
        return True
    
    def mark_notified(self) -> None:
        """标记已发送通知"""
        self.last_notification_time = datetime.now()
    
    def get_cooldown_remaining(self) -> int:
        """获取剩余冷却时间（秒）"""
        if self.last_notification_time is None:
            return 0
        
        elapsed = (datetime.now() - self.last_notification_time).total_seconds()
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
    notifier: CopyTradingNotifier,
    trader: Dict,
    user_state: Optional[Dict],
    old_positions: Dict[str, Dict],
    redis_client: redis.Redis = None
) -> int:
    """
    处理单个交易员的持仓结果
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
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
        pos['open_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        success = notifier.notify_new_position(
            address, pos, rating=rating, score=score
        )
        if success:
            logger.success(f"    ✓ 已通知: {coin} {direction}")
        else:
            logger.error(f"    ✗ 通知失败: {coin}")
        
        # Redis Pub/Sub 推送（供本地客户端接收）
        if redis_client:
            try:
                redis_client.publish(REDIS_POSITION_CHANNEL, f"https://app.hyperliquid.xyz/trade/{coin}")
            except Exception as e:
                logger.debug(f"    Redis 推送失败: {e}")
    
    return len(new_position_list)


async def run_monitoring_cycle_async(
    db: TraderDatabase,
    notifier: CopyTradingNotifier,
    hl_client: HyperliquidClient,
    rate: float = 10.0,
    limit: int = 0,
    offset: int = 0,
    redis_client: redis.Redis = None,
    activity_tracker: MarketActivityTracker = None,
    important_feishu: FeishuClient = None
) -> Dict:
    """
    异步运行一次监控周期
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        hl_client: HyperliquidClient 实例
        rate: 每秒请求数
        limit: 限制处理的交易员数量，0表示不限制
        offset: 跳过前N个交易员，0表示不跳过
        redis_client: Redis 客户端
        activity_tracker: 行情活动追踪器
        important_feishu: 重要通知飞书客户端
    
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
                db, notifier, trader, user_state, old_positions,
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
        if activity_tracker.should_notify() and important_feishu:
            recent_count = activity_tracker.get_recent_count()
            logger.warning(f"🔥 检测到行情活动: 1分钟内 {recent_count} 个新仓位!")
            
            # 发送重要通知
            try:
                message = (
                    f"🔥 行情提醒\n\n"
                    f"检测到市场活动频繁！\n"
                    f"最近1分钟内发现 {recent_count} 个新仓位\n\n"
                    f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📊 建议关注市场动态"
                )
                success = important_feishu.send_text(message)
                if success:
                    activity_tracker.mark_notified()
                    logger.success("✓ 行情通知已发送（10分钟内不再重复）")
                else:
                    logger.error("✗ 行情通知发送失败")
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
    
    # 初始化飞书通知器（使用新仓位推送专用配置）
    logger.info("初始化飞书通知器（新仓位推送）...")
    feishu = FeishuClient(
        app_id=settings.feishu_position.app_id,
        app_secret=settings.feishu_position.app_secret,
        default_user_id=settings.feishu_position.default_user_id
    )
    notifier = CopyTradingNotifier(feishu)
    
    if not feishu.app_id:
        logger.warning("⚠ 飞书新仓位推送未配置，通知功能将不可用")
    else:
        logger.success("✓ 飞书通知器初始化成功（新仓位推送）")
    
    # 初始化飞书重要通知客户端（行情提醒）
    logger.info("初始化飞书通知器（重要通知）...")
    important_feishu = FeishuClient(
        app_id=settings.feishu_important.app_id,
        app_secret=settings.feishu_important.app_secret,
        default_user_id=settings.feishu_important.default_user_id
    )
    
    if not important_feishu.app_id:
        logger.warning("⚠ 飞书重要通知未配置，行情提醒功能将不可用")
        important_feishu = None
    else:
        logger.success("✓ 飞书通知器初始化成功（重要通知）")
    
    # 初始化行情活动追踪器
    activity_tracker = MarketActivityTracker()
    logger.info(f"行情追踪器: 阈值={activity_tracker.threshold}个/分钟, 冷却={activity_tracker.cooldown_seconds}秒")
    
    # 初始化 Redis（用于本地推送）
    redis_client = None
    if args.redis:
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
            logger.info(f"  本地监听: python local_position_listener.py")
        except Exception as e:
            logger.warning(f"⚠ Redis 连接失败: {e}，本地推送将不可用")
            redis_client = None
    
    logger.info("")
    
    # 主循环
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            logger.info(f"{'='*60}")
            logger.info(f"第 {cycle_count} 轮监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            await run_monitoring_cycle_async(
                db, notifier, hl_client,
                rate=args.rate,
                limit=args.limit,
                offset=args.offset,
                redis_client=redis_client,
                activity_tracker=activity_tracker,
                important_feishu=important_feishu
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
