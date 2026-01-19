"""
S级交易员仓位监控脚本

功能说明：
1. 获取所有S级的交易员
2. 异步更新交易员的当前仓位并保存到数据库
3. 如果发现有新仓位，通过飞书通知
4. 如果1分钟内新仓位>=5个，发送行情通知（10分钟内只推送一次）

运行模式：无限循环执行

示例：
  python monitor_s_traders_positions.py --workers 10 --proxy --delay 1
  每个 worker 异步获取100个地址，10个 worker 并行 = 每批1000个地址
  
  python monitor_s_traders_positions.py --workers 5 --batch-size 50 --proxy
  每个 worker 异步获取50个地址，5个 worker 并行 = 每批250个地址
"""
import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque

import redis
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import TraderDatabase
from screener.api_client import AsyncAPIClient, APIConfig, get_proxy_manager, reset_proxy_manager
from clients.feishu_client import FeishuClient, CopyTradingNotifier
from config.settings import settings

# Redis 新仓位推送 channel
REDIS_POSITION_CHANNEL = "new_positions"

# 行情检测配置
MARKET_ACTIVITY_WINDOW = 60  # 1分钟窗口（秒）
MARKET_ACTIVITY_THRESHOLD = 10  # 触发阈值：新仓位数量
MARKET_ACTIVITY_COOLDOWN = 600  # 10分钟冷却时间（秒）


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


def get_s_rated_traders(db: TraderDatabase, limit: int = 0) -> List[Dict]:
    """
    获取所有S级交易员，按评分从高到低排序
    
    Args:
        db: 数据库实例
        limit: 限制返回数量，0表示不限制
    
    Returns:
        S级交易员列表（按 overall_score 降序排序）
    """
    traders = db.get_traders_by_rating('S')
    
    # 按 overall_score 从高到低排序
    traders.sort(key=lambda x: x.get('overall_score', 0) or 0, reverse=True)
    
    total_count = len(traders)
    
    # 应用 limit
    if limit > 0 and len(traders) > limit:
        traders = traders[:limit]
        logger.info(f"获取到 {total_count} 个S级交易员，限制为前 {limit} 个（按评分排序）")
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


async def fetch_positions_async(
    client: AsyncAPIClient,
    address: str
) -> Optional[List[Dict]]:
    """
    异步获取交易员最新的持仓
    
    Args:
        client: 异步API客户端
        address: 交易员地址
    
    Returns:
        持仓列表 (assetPositions) 或 None
    """
    try:
        user_state = await client.get_user_state(address)
        if not user_state:
            return None
        return user_state.get('assetPositions', [])
    except Exception as e:
        logger.error(f"获取持仓失败 {address[:10]}...: {e}")
        return None


def process_trader_result(
    db: TraderDatabase,
    notifier: CopyTradingNotifier,
    trader: Dict,
    asset_positions: Optional[List[Dict]],
    old_positions: Dict[str, Dict],
    redis_client: redis.Redis = None
) -> int:
    """
    处理单个交易员的持仓结果
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        trader: 交易员信息
        asset_positions: 从API获取的持仓数据
        old_positions: 更新前的持仓
    
    Returns:
        新仓位数量
    """
    address = trader['address']
    rating = trader.get('rating')
    score = trader.get('overall_score')
    
    if asset_positions is None:
        logger.debug(f"  {address[:16]}... 获取持仓失败")
        return 0
    
    if not asset_positions:
        logger.debug(f"  {address[:16]}... 当前无持仓")
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
        logger.debug(f"  {address[:16]}... 保存 {positions_saved} 个持仓，无新仓位")
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


async def worker_fetch_batch(
    client: AsyncAPIClient,
    traders: List[Dict],
    worker_id: int
) -> List[tuple]:
    """
    单个 worker 异步获取一批交易员的仓位
    
    Args:
        client: 异步API客户端
        traders: 该 worker 负责的交易员列表
        worker_id: worker 编号
    
    Returns:
        [(trader, result), ...] 列表
    """
    async def fetch_one(trader: Dict):
        result = await fetch_positions_async(client, trader['address'])
        return (trader, result)
    
    # 该 worker 内部并发获取所有地址
    tasks = [fetch_one(trader) for trader in traders]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理异常情况
    processed_results = []
    for i, result in enumerate(results):
        trader = traders[i]
        if isinstance(result, Exception):
            logger.debug(f"Worker {worker_id}: 获取失败 {trader['address'][:10]}...: {result}")
            processed_results.append((trader, None))
        else:
            processed_results.append(result)
    
    return processed_results


async def process_batch(
    db: TraderDatabase,
    notifier: CopyTradingNotifier,
    traders: List[Dict],
    config: APIConfig,
    workers: int = 10,
    redis_client: redis.Redis = None
) -> Dict:
    """
    异步处理一批交易员（多 worker 模式）
    
    每个 worker 使用独立的代理，异步获取分配给它的所有地址
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        traders: 交易员列表
        config: API配置
        workers: worker 数量（每个 worker 使用不同的代理）
        redis_client: Redis 客户端
    
    Returns:
        统计信息
    """
    stats = {
        'traders_processed': 0,
        'new_positions_total': 0,
        'errors': 0
    }
    
    if not traders:
        return stats
    
    # 先获取所有交易员的当前持仓（用于对比）
    old_positions_map = {}
    for trader in traders:
        address = trader['address']
        old_positions_map[address] = get_current_positions_from_db(db, address)
    
    # 将交易员分配给各个 worker
    # 例如：100个交易员，10个worker -> 每个worker负责10个
    traders_per_worker = len(traders) // workers if workers > 0 else len(traders)
    if traders_per_worker == 0:
        traders_per_worker = 1
    
    worker_assignments = []
    for i in range(workers):
        start_idx = i * traders_per_worker
        if i == workers - 1:
            # 最后一个 worker 处理剩余的所有
            end_idx = len(traders)
        else:
            end_idx = start_idx + traders_per_worker
        
        if start_idx < len(traders):
            worker_assignments.append(traders[start_idx:end_idx])
    
    # 创建 workers 个异步客户端，每个使用不同的代理
    clients = []
    worker_tasks = []
    
    for worker_id, assignment in enumerate(worker_assignments):
        if not assignment:
            continue
        client = AsyncAPIClient(config, worker_index=worker_id)
        clients.append(client)
        worker_tasks.append(worker_fetch_batch(client, assignment, worker_id))
    
    logger.debug(f"启动 {len(worker_tasks)} 个 worker，共处理 {len(traders)} 个地址")
    
    # 并发执行所有 worker
    worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
    
    # 关闭所有客户端
    for client in clients:
        await client.close()
    
    # 汇总所有 worker 的结果
    all_results = []
    for worker_id, result in enumerate(worker_results):
        if isinstance(result, Exception):
            logger.error(f"Worker {worker_id} 执行失败: {result}")
            # 该 worker 的所有交易员标记为错误
            if worker_id < len(worker_assignments):
                stats['errors'] += len(worker_assignments[worker_id])
            continue
        all_results.extend(result)
    
    # 处理结果
    for trader, result in all_results:
        address = trader['address']
        old_positions = old_positions_map.get(address, {})
        
        if result is None:
            stats['errors'] += 1
            continue
        
        try:
            new_count = process_trader_result(
                db, notifier, trader, result, old_positions,
                redis_client=redis_client
            )
            stats['traders_processed'] += 1
            stats['new_positions_total'] += new_count
        except Exception as e:
            logger.error(f"处理交易员结果失败 {address[:10]}...: {e}")
            stats['errors'] += 1
    
    return stats


async def run_monitoring_cycle_async(
    db: TraderDatabase,
    notifier: CopyTradingNotifier,
    config: APIConfig,
    workers: int = 10,
    batch_size: int = 100,
    delay: float = 1.0,
    limit: int = 0,
    redis_client: redis.Redis = None,
    activity_tracker: MarketActivityTracker = None,
    important_feishu: FeishuClient = None
) -> Dict:
    """
    异步运行一次监控周期
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        config: API配置
        workers: 并发worker数量（每个worker使用不同的代理）
        batch_size: 每个worker异步获取的地址数量（默认100）
        delay: 批次间延迟（秒）
        limit: 限制处理的交易员数量，0表示不限制
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
    
    # 获取S级交易员（按评分排序，可限制数量）
    traders = get_s_rated_traders(db, limit=limit)
    
    if not traders:
        logger.warning("没有找到S级交易员")
        return total_stats
    
    # 每批处理的总地址数 = workers * batch_size
    addresses_per_batch = workers * batch_size
    
    logger.info(f"开始处理 {len(traders)} 个S级交易员")
    logger.info(f"  配置: workers={workers}, batch_size={batch_size}/worker, "
                f"每批={addresses_per_batch}个地址, delay={delay}s")
    logger.info("-" * 60)
    
    # 分批处理
    total_batches = (len(traders) + addresses_per_batch - 1) // addresses_per_batch
    
    for batch_idx in range(0, len(traders), addresses_per_batch):
        batch = traders[batch_idx:batch_idx + addresses_per_batch]
        batch_num = batch_idx // addresses_per_batch + 1
        
        logger.info(f"处理批次 {batch_num}/{total_batches} ({len(batch)} 个交易员, {workers} workers)")
        
        batch_stats = await process_batch(
            db, notifier, batch, config, 
            workers=workers,
            redis_client=redis_client
        )
        
        total_stats['traders_processed'] += batch_stats['traders_processed']
        total_stats['new_positions_total'] += batch_stats['new_positions_total']
        total_stats['errors'] += batch_stats['errors']
        
        # 记录新仓位到活动追踪器
        if activity_tracker and batch_stats['new_positions_total'] > 0:
            activity_tracker.add_positions(batch_stats['new_positions_total'])
            
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
        
        # 批次间延迟
        if batch_idx + addresses_per_batch < len(traders) and delay > 0:
            await asyncio.sleep(delay)
    
    logger.info("-" * 60)
    logger.info(f"本轮完成: 处理 {total_stats['traders_processed']} 个交易员, "
                f"发现 {total_stats['new_positions_total']} 个新仓位, "
                f"错误 {total_stats['errors']} 个")
    
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
    logger.info("S级交易员仓位监控脚本 (异步版)")
    logger.info("=" * 60)
    logger.info(f"运行模式: 无限循环")
    logger.info(f"Workers: {args.workers}, 每Worker获取: {args.batch_size}个地址")
    logger.info(f"每批总量: {args.workers * args.batch_size}个地址, 批次延迟: {args.delay}s")
    logger.info(f"交易员限制: {args.limit if args.limit > 0 else '不限制'}（按评分排序）")
    logger.info(f"代理: {'启用' if args.proxy else '禁用'}")
    logger.info("")
    
    # 重置代理管理器（确保使用新配置）
    reset_proxy_manager()
    
    # 初始化代理管理器
    if args.proxy:
        proxy_manager = get_proxy_manager(enabled=True)
        logger.info(f"代理管理器: 加载 {proxy_manager.get_proxy_count()} 个代理")
    
    # 初始化数据库
    logger.info("初始化数据库连接...")
    db = TraderDatabase()
    logger.success("✓ 数据库连接成功")
    
    # 配置 API
    config = APIConfig()
    config.proxy_enabled = args.proxy
    config.max_retries = 3
    config.api_call_delay = 0  # 异步模式下不需要单个调用延迟
    logger.success("✓ API 配置完成")
    
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
                db, notifier, config,
                workers=args.workers,
                batch_size=args.batch_size,
                delay=args.delay,
                limit=args.limit,
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
  python monitor_s_traders_positions.py --workers 10 --proxy --delay 1
    10个worker并行，每个worker异步获取100个地址 = 每批1000个地址
  
  python monitor_s_traders_positions.py -w 5 -b 50 -p
    5个worker并行，每个worker异步获取50个地址 = 每批250个地址
  
  python monitor_s_traders_positions.py -w 10 -p --limit 500
    只监控评分最高的前500个交易员
  
  python monitor_s_traders_positions.py -w 10 -p --redis
    启用 Redis 推送，本地运行 local_position_listener.py 可接收通知
"""
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=10,
        help="并发worker数量，每个worker使用不同的代理（默认: 10）"
    )
    parser.add_argument(
        "--batch-size", "-b",
        type=int,
        default=100,
        help="每个worker异步获取的地址数量（默认: 100）"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=0,
        help="限制监控的交易员数量，按评分从高到低选取（默认: 0，不限制）"
    )
    parser.add_argument(
        "--proxy", "-p",
        action="store_true",
        help="启用代理"
    )
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.0,
        help="批次间延迟（秒），默认: 1.0"
    )
    parser.add_argument(
        "--redis", "-r",
        action="store_true",
        help="启用 Redis 推送（本地监听脚本可接收新仓位通知）"
    )
    
    args = parser.parse_args()
    
    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
