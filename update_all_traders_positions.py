"""
全量交易员持仓更新脚本

功能说明：
1. 获取所有交易员，按评分（overall_score）从高到低排序
2. 异步更新每个交易员的当前持仓并保存到数据库
3. 支持 --offset, --limit, --rate 参数控制范围和速率

运行模式：单次执行

示例：
  python update_all_traders_positions.py --rate 10
    以每秒10个请求的速率更新所有交易员持仓

  python update_all_traders_positions.py -r 5 --limit 500
    以每秒5个请求的速率，只更新评分最高的前500个交易员

  python update_all_traders_positions.py -r 10 --offset 100 --limit 200
    跳过前100个，更新第101-300名的交易员
"""
import sys
import asyncio
import argparse
import time
from pathlib import Path
from typing import List, Dict, Optional

from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from database import TraderDatabase
from clients.hyperliquid_client import HyperliquidClient
from screener.utils import now_shanghai


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


def get_all_traders_sorted(db: TraderDatabase, limit: int = 0, offset: int = 0) -> List[Dict]:
    """
    获取所有交易员，按评分从高到低排序

    Args:
        db: 数据库实例
        limit: 限制返回数量，0表示不限制
        offset: 跳过前N个交易员，0表示不跳过

    Returns:
        交易员列表（按 overall_score 降序排序）
    """
    # 使用 get_top_traders 获取所有交易员（传入一个足够大的 limit）
    # 如果不限制则获取全部
    fetch_limit = 100000  # 足够大以获取所有交易员
    traders = db.get_top_traders(limit=fetch_limit)

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
        logger.info(f"获取到 {total_count} 个交易员，选取第 {range_start}-{range_end} 名（按评分排序）")
    else:
        logger.info(f"获取到 {total_count} 个交易员（按评分排序）")

    return traders


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
        user_state = await asyncio.to_thread(hl_client.info.user_state, address)
        return user_state
    except Exception as e:
        logger.debug(f"获取用户状态异常 {address[:10]}...: {e}")
        return None


def update_trader_positions(
    db: TraderDatabase,
    trader: Dict,
    user_state: Optional[Dict]
) -> int:
    """
    更新单个交易员的持仓

    Args:
        db: 数据库实例
        trader: 交易员信息
        user_state: 从API获取的用户状态

    Returns:
        保存的持仓数量
    """
    address = trader['address']

    if user_state is None:
        return 0

    asset_positions = user_state.get('assetPositions', [])

    # 保存持仓到数据库（空列表会清空该交易员的持仓）
    positions_saved = db.save_positions(address, asset_positions)

    return positions_saved


async def run_update(
    db: TraderDatabase,
    hl_client: HyperliquidClient,
    rate: float = 10.0,
    limit: int = 0,
    offset: int = 0
) -> Dict:
    """
    异步运行持仓更新

    Args:
        db: 数据库实例
        hl_client: HyperliquidClient 实例
        rate: 每秒请求数
        limit: 限制处理的交易员数量，0表示不限制
        offset: 跳过前N个交易员，0表示不跳过

    Returns:
        统计信息
    """
    stats = {
        'traders_total': 0,
        'traders_processed': 0,
        'traders_with_positions': 0,
        'total_positions': 0,
        'errors': 0
    }

    # 获取所有交易员（按评分排序）
    traders = get_all_traders_sorted(db, limit=limit, offset=offset)

    if not traders:
        logger.warning("没有找到交易员")
        return stats

    stats['traders_total'] = len(traders)

    logger.info(f"开始更新 {len(traders)} 个交易员的持仓，速率: {rate} 请求/秒")
    logger.info("-" * 60)

    # 创建速率限制器
    rate_limiter = AsyncRateLimiter(rate=rate)
    start_time = time.perf_counter()

    total_traders = len(traders)

    async def fetch_and_update(idx: int, trader: Dict):
        """获取并更新单个交易员的持仓"""
        address = trader['address']
        name = trader.get('name', '')
        rating = trader.get('rating', '?')
        score = trader.get('overall_score', 0) or 0

        # 等待速率限制
        await rate_limiter.acquire()

        # 获取用户状态
        user_state = await fetch_user_state_async(hl_client, address)

        if user_state is None:
            logger.warning(f"[{idx+1}/{total_traders}] ✗ {address[:16]}... ({rating}/{score:.1f}) 获取失败")
            return {'success': False, 'positions': 0}

        # 统计仓位数量
        positions = user_state.get('assetPositions', [])
        positions_count = len([p for p in positions if float(p.get('position', {}).get('szi', 0)) != 0])

        # 更新持仓
        try:
            saved = update_trader_positions(db, trader, user_state)
            if positions_count > 0:
                logger.info(f"[{idx+1}/{total_traders}] ✓ {address[:16]}... ({rating}/{score:.1f}) 持仓: {positions_count}")
            else:
                logger.debug(f"[{idx+1}/{total_traders}] ✓ {address[:16]}... ({rating}/{score:.1f}) 无持仓")
            return {'success': True, 'positions': positions_count}
        except Exception as e:
            logger.error(f"[{idx+1}/{total_traders}] ✗ {address[:16]}... 更新失败: {e}")
            return {'success': False, 'positions': 0}

    # 创建所有任务
    tasks = [
        fetch_and_update(i, trader)
        for i, trader in enumerate(traders)
    ]

    # 并发执行（受速率限制）
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 统计结果
    for result in results:
        if isinstance(result, Exception):
            stats['errors'] += 1
        elif result['success']:
            stats['traders_processed'] += 1
            if result['positions'] > 0:
                stats['traders_with_positions'] += 1
                stats['total_positions'] += result['positions']
        else:
            stats['errors'] += 1

    total_duration = time.perf_counter() - start_time
    actual_rate = len(traders) / total_duration if total_duration > 0 else 0

    logger.info("-" * 60)
    logger.info(f"更新完成: 处理 {stats['traders_processed']}/{stats['traders_total']} 个交易员, "
                f"有持仓 {stats['traders_with_positions']} 个, "
                f"总持仓数 {stats['total_positions']}, "
                f"错误 {stats['errors']} 个")
    logger.info(f"耗时: {total_duration:.1f}s, 实际速率: {actual_rate:.2f} 请求/秒")

    return stats


async def main_async(args):
    """异步主函数"""
    logger.info("=" * 60)
    logger.info("全量交易员持仓更新脚本")
    logger.info("=" * 60)
    logger.info(f"运行模式: 单次执行")
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

    logger.info("")

    try:
        stats = await run_update(
            db, hl_client,
            rate=args.rate,
            limit=args.limit,
            offset=args.offset
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("执行完毕")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.warning("\n用户中断")
    finally:
        db.close()
        logger.info("数据库连接已关闭")


def main():
    parser = argparse.ArgumentParser(
        description="全量交易员持仓更新脚本（单次执行）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python update_all_traders_positions.py --rate 10
    以每秒10个请求的速率更新所有交易员持仓

  python update_all_traders_positions.py -r 5 --limit 500
    以每秒5个请求的速率，只更新评分最高的前500个交易员

  python update_all_traders_positions.py -r 10 --offset 100 --limit 200
    跳过前100个，更新第101-300名的交易员
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
        help="限制更新的交易员数量，按评分从高到低选取（默认: 0，不限制）"
    )
    parser.add_argument(
        "--offset", "-o",
        type=int,
        default=0,
        help="跳过前N个交易员（默认: 0，不跳过）"
    )

    args = parser.parse_args()

    # 运行异步主函数
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
