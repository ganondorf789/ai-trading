"""
S级交易员仓位监控脚本

功能说明：
1. 获取所有S级的交易员
2. 异步更新交易员的当前仓位并保存到数据库
3. 如果发现有新仓位，通过飞书通知

运行模式：
- 定时循环执行：每隔N分钟运行一次
- 一次性执行：运行一次后退出（使用 --once 参数）

示例：
  python monitor_s_traders_positions.py --workers 10 --proxy --delay 1
  每隔1秒钟更新10个交易员的当前仓位，并且使用代理
"""
import sys
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import TraderDatabase
from screener.api_client import AsyncAPIClient, APIConfig, get_proxy_manager, reset_proxy_manager
from clients.feishu_client import FeishuClient, CopyTradingNotifier
from config.settings import settings


def get_s_rated_traders(db: TraderDatabase) -> List[Dict]:
    """
    获取所有S级交易员
    
    Args:
        db: 数据库实例
    
    Returns:
        S级交易员列表
    """
    traders = db.get_traders_by_rating('S')
    logger.info(f"获取到 {len(traders)} 个S级交易员")
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
    dry_run: bool = False
) -> int:
    """
    处理单个交易员的持仓结果
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        trader: 交易员信息
        asset_positions: 从API获取的持仓数据
        old_positions: 更新前的持仓
        dry_run: 是否仅预览不发送通知
    
    Returns:
        新仓位数量
    """
    address = trader['address']
    trader_name = trader.get('trader_name')
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
        
        if dry_run:
            logger.info(f"    [DRY-RUN] 新仓位: {coin} {direction} {abs(szi):.4f}")
        else:
            success = notifier.notify_new_position(
                address, pos, rating=rating, score=score, trader_name=trader_name
            )
            if success:
                logger.success(f"    ✓ 已通知: {coin} {direction}")
            else:
                logger.error(f"    ✗ 通知失败: {coin}")
    
    return len(new_position_list)


async def process_batch(
    db: TraderDatabase,
    notifier: CopyTradingNotifier,
    traders: List[Dict],
    config: APIConfig,
    dry_run: bool = False
) -> Dict:
    """
    异步处理一批交易员
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        traders: 交易员列表
        config: API配置
        dry_run: 是否仅预览
    
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
    
    # 创建异步客户端并发获取持仓
    clients = []
    tasks = []
    
    for i, trader in enumerate(traders):
        # 每个worker使用不同的代理索引
        client = AsyncAPIClient(config, worker_index=i)
        clients.append(client)
        tasks.append(fetch_positions_async(client, trader['address']))
    
    # 并发执行所有请求
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 关闭所有客户端
    for client in clients:
        await client.close()
    
    # 处理结果
    for trader, result in zip(traders, results):
        address = trader['address']
        old_positions = old_positions_map[address]
        
        if isinstance(result, Exception):
            logger.error(f"处理交易员失败 {address[:10]}...: {result}")
            stats['errors'] += 1
            continue
        
        try:
            new_count = process_trader_result(
                db, notifier, trader, result, old_positions, dry_run
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
    delay: float = 1.0,
    dry_run: bool = False
) -> Dict:
    """
    异步运行一次监控周期
    
    Args:
        db: 数据库实例
        notifier: 飞书通知器
        config: API配置
        workers: 并发worker数量
        delay: 批次间延迟（秒）
        dry_run: 是否仅预览
    
    Returns:
        统计信息
    """
    total_stats = {
        'traders_processed': 0,
        'new_positions_total': 0,
        'errors': 0
    }
    
    # 获取S级交易员
    traders = get_s_rated_traders(db)
    
    if not traders:
        logger.warning("没有找到S级交易员")
        return total_stats
    
    logger.info(f"开始处理 {len(traders)} 个S级交易员 (workers={workers}, delay={delay}s)")
    logger.info("-" * 60)
    
    # 分批处理
    total_batches = (len(traders) + workers - 1) // workers
    
    for batch_idx in range(0, len(traders), workers):
        batch = traders[batch_idx:batch_idx + workers]
        batch_num = batch_idx // workers + 1
        
        logger.info(f"处理批次 {batch_num}/{total_batches} ({len(batch)} 个交易员)")
        
        batch_stats = await process_batch(db, notifier, batch, config, dry_run)
        
        total_stats['traders_processed'] += batch_stats['traders_processed']
        total_stats['new_positions_total'] += batch_stats['new_positions_total']
        total_stats['errors'] += batch_stats['errors']
        
        # 批次间延迟
        if batch_idx + workers < len(traders) and delay > 0:
            await asyncio.sleep(delay)
    
    logger.info("-" * 60)
    logger.info(f"本轮完成: 处理 {total_stats['traders_processed']} 个交易员, "
                f"发现 {total_stats['new_positions_total']} 个新仓位, "
                f"错误 {total_stats['errors']} 个")
    
    return total_stats


async def main_async(args):
    """异步主函数"""
    logger.info("=" * 60)
    logger.info("S级交易员仓位监控脚本 (异步版)")
    logger.info("=" * 60)
    logger.info(f"运行模式: {'一次性执行' if args.once else f'循环执行（间隔 {args.interval} 分钟）'}")
    logger.info(f"并发数: {args.workers}, 批次延迟: {args.delay}s, 代理: {'启用' if args.proxy else '禁用'}")
    if args.dry_run:
        logger.info("预览模式: 不发送飞书通知")
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
        webhook_url=settings.feishu_position.webhook_url,
        default_user_id=settings.feishu_position.default_user_id
    )
    notifier = CopyTradingNotifier(feishu)
    
    if not feishu.webhook_url and not feishu.app_id:
        logger.warning("⚠ 飞书新仓位推送未配置，通知功能将不可用")
    else:
        logger.success("✓ 飞书通知器初始化成功（新仓位推送）")
    
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
                delay=args.delay,
                dry_run=args.dry_run
            )
            
            if args.once:
                logger.info("一次性执行完成，退出")
                break
            
            logger.info(f"等待 {args.interval} 分钟后进行下一轮...")
            await asyncio.sleep(args.interval * 60)
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断")
    finally:
        db.close()
        logger.info("数据库连接已关闭")


def main():
    parser = argparse.ArgumentParser(
        description="S级交易员仓位监控脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python monitor_s_traders_positions.py --workers 10 --proxy --delay 1
    每隔1秒钟并发更新10个交易员的当前仓位，使用代理
  
  python monitor_s_traders_positions.py --workers 5 --delay 2 --once
    一次性执行，每批5个交易员，批次间隔2秒，不使用代理
  
  python monitor_s_traders_positions.py -w 20 -p -d 0.5 -i 3
    每0.5秒并发更新20个交易员，每3分钟循环一次，使用代理
"""
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=10,
        help="并发worker数量，即每批处理的交易员数量（默认: 10）"
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
        "--interval", "-i",
        type=int,
        default=0,
        help="循环间隔（分钟），默认: 5"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅运行一次后退出"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不发送通知"
    )
    
    args = parser.parse_args()
    
    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
