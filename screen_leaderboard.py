"""
Hyperliquid 排行榜交易者批量分析
获取 month PnL 前 5000 名交易者，分析并保存到数据库

支持多线程并发分析（默认10个并发）
"""
import sys
import argparse
import io
import gc
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, field

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# 设置 stdout 为 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from leaderboard.fetch_leaderboard import fetch_leaderboard
from screener.trader_screener import TraderScreener, ScreenerConfig
from database import TraderDatabase


@dataclass
class AnalysisResult:
    """分析结果"""
    address: str
    success: bool
    metrics: Optional[Any] = None
    fills_saved: int = 0
    error: Optional[str] = None


@dataclass
class AnalysisStats:
    """线程安全的统计计数器"""
    saved_count: int = 0
    fills_count: int = 0
    failed_count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def add_success(self, fills_saved: int):
        with self._lock:
            self.saved_count += 1
            self.fills_count += fills_saved
    
    def add_failure(self):
        with self._lock:
            self.failed_count += 1


def get_memory_usage():
    """获取当前进程内存使用（MB）"""
    if not PSUTIL_AVAILABLE:
        return 0.0
    try:
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


def analyze_single_trader_sync(
    address: str,
    lookback_days: int,
    max_fills: int,
    index: int,
    total: int,
    resume_from: int,
    use_proxy: bool = False
) -> AnalysisResult:
    """
    同步分析单个交易者（在独立线程中运行）
    
    每个调用创建独立的 screener 和 db 实例，确保线程安全
    """
    # 每个线程创建独立的配置和实例
    config = ScreenerConfig()
    config.data.lookback_days = lookback_days
    config.data.max_fills_per_trader = max_fills
    config.api.api_call_delay = 0 if use_proxy else 0.5  # 代理模式下可以设为0，否则需要延迟避免限流
    config.api.max_retries = 3
    config.api.proxy.enabled = use_proxy  # 设置代理开关
    
    screener = None
    db = None
    
    try:
        # 创建独立的 screener 和数据库连接
        screener = TraderScreener(config, cache_fills=False)
        db = TraderDatabase()
        
        # 分析交易者
        metrics = screener.analyze_trader(address, store_fills=True)
        
        if metrics and metrics.total_trades > 0:
            # 提取 fills 用于保存到数据库
            fills = metrics.fills
            
            # 保存到数据库
            _, fills_saved = db.save_trader_with_fills(metrics, fills)
            
            result = AnalysisResult(
                address=address,
                success=True,
                metrics=metrics,
                fills_saved=fills_saved
            )
            
            # 清理内存
            if hasattr(metrics, 'fills'):
                metrics.fills.clear()
                metrics.fills = []
            if hasattr(metrics, 'asset_positions'):
                metrics.asset_positions.clear()
                metrics.asset_positions = []
            
            return result
        else:
            return AnalysisResult(
                address=address,
                success=False,
                error="无交易数据"
            )
            
    except Exception as e:
        return AnalysisResult(
            address=address,
            success=False,
            error=str(e)[:100]
        )
    finally:
        # 清理资源
        if screener:
            try:
                screener._api_client.close()
                screener.clear_cache()
            except:
                pass
        gc.collect()


async def analyze_traders_concurrent(
    addresses: list,
    lookback_days: int,
    max_fills: int,
    resume_from: int,
    max_workers: int = 10,
    use_proxy: bool = False
) -> Tuple[AnalysisStats, bool]:
    """
    并发分析多个交易者
    
    Args:
        addresses: 交易者地址列表
        lookback_days: 回溯天数
        max_fills: 最大交易记录数
        resume_from: 断点续传起始位置
        max_workers: 最大并发数（默认10）
        use_proxy: 是否启用代理
    
    Returns:
        (统计结果, 是否被中断)
    """
    stats = AnalysisStats()
    total = len(addresses)
    completed = 0
    interrupted = False
    completed_lock = threading.Lock()
    
    # 用于控制并发的信号量
    semaphore = asyncio.Semaphore(max_workers)
    
    async def analyze_with_semaphore(address: str, index: int):
        nonlocal completed, interrupted
        
        if interrupted:
            return
        
        async with semaphore:
            if interrupted:
                return
            
            # 在线程池中运行同步分析函数
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # 使用默认线程池
                analyze_single_trader_sync,
                address,
                lookback_days,
                max_fills,
                index,
                total,
                resume_from,
                use_proxy
            )
            
            # 更新统计和进度
            current_index = resume_from + index + 1 if resume_from > 0 else index + 1
            display_total = resume_from + total if resume_from else total
            
            with completed_lock:
                completed += 1
                current_completed = completed
            
            if result.success and result.metrics:
                stats.add_success(result.fills_saved)
                metrics = result.metrics
                logger.info(
                    f"[{current_index}/{display_total}] ({current_completed}/{total} done) "
                    f"✓ {address[:10]}... "
                    f"评分: {metrics.overall_score:.1f} "
                    f"评级: {metrics.rating.value} "
                    f"交易: {metrics.total_trades} "
                    f"胜率: {metrics.win_rate:.1%} "
                    f"PnL: ${metrics.total_pnl:,.0f}"
                )
            else:
                stats.add_failure()
                error_msg = result.error or "未知错误"
                logger.warning(
                    f"[{current_index}/{display_total}] ({current_completed}/{total} done) "
                    f"✗ {address[:10]}... {error_msg}"
                )
            
            # 定期清理内存
            if current_completed % 50 == 0:
                gc.collect()
                if PSUTIL_AVAILABLE:
                    logger.info(f"内存使用: {get_memory_usage():.1f} MB")
    
    # 创建所有任务
    tasks = [
        analyze_with_semaphore(address, i)
        for i, address in enumerate(addresses)
    ]
    
    try:
        # 并发执行所有任务
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        interrupted = True
        logger.warning("任务被取消")
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("用户中断")
    
    return stats, interrupted


def screen_leaderboard_traders(
    limit: int = 3000,
    lookback_days: int = 0,
    max_fills: int = 0,
    resume_from: int = 0,
    max_workers: int = 10,
    use_proxy: bool = False
):
    """
    获取排行榜前N名交易者并分析保存到数据库（并发版本）

    Args:
        limit: 获取前N名交易者
        lookback_days: 分析回溯天数
        max_fills: 每个交易者最大获取的交易记录数 (0=不限制)
        resume_from: 从第N个地址开始（用于断点续传）
        max_workers: 最大并发数（默认10）
        use_proxy: 是否启用代理
    """
    logger.info("=" * 70)
    logger.info("Hyperliquid 排行榜交易者批量分析（并发版本）")
    logger.info(f"并发数: {max_workers}, 代理: {'启用' if use_proxy else '禁用'}")
    logger.info("=" * 70)

    # 1. 获取排行榜数据（按 month PnL 排序）
    logger.info(f"\n[1/3] 正在获取排行榜前 {limit} 名交易者...")
    leaderboard_rows = fetch_leaderboard(save_to_file=False, sort_by_pnl=True)

    if not leaderboard_rows:
        logger.error("获取排行榜数据失败")
        return

    # 提取地址（取前 limit 个）
    addresses = [row["ethAddress"] for row in leaderboard_rows[:limit]]
    logger.info(f"获取到 {len(addresses)} 个交易者地址")

    # 处理断点续传
    if resume_from > 0:
        addresses = addresses[resume_from:]
        logger.info(f"从第 {resume_from + 1} 个地址开始，剩余 {len(addresses)} 个")

    if not addresses:
        logger.warning("没有需要分析的地址")
        return

    # 2. 开始并发分析
    logger.info(f"\n[2/3] 初始化并发分析器（{max_workers} 个并发）...")
    logger.info(f"\n[3/3] 开始并发分析交易者...")
    logger.info("-" * 70)
    if PSUTIL_AVAILABLE:
        logger.info(f"初始内存使用: {get_memory_usage():.1f} MB")

    # 运行异步任务
    try:
        stats, interrupted = asyncio.run(
            analyze_traders_concurrent(
                addresses=addresses,
                lookback_days=lookback_days,
                max_fills=max_fills,
                resume_from=resume_from,
                max_workers=max_workers,
                use_proxy=use_proxy
            )
        )
    except KeyboardInterrupt:
        logger.warning("\n\n用户中断")
        logger.warning(f"断点续传命令: python screen_leaderboard.py --resume {resume_from}")
        return

    # 最终内存清理
    gc.collect()

    # 打印统计
    logger.info("\n" + "=" * 70)
    logger.info("分析完成!" if not interrupted else "分析中断!")
    logger.info("=" * 70)
    logger.info(f"  成功保存: {stats.saved_count} 个交易者")
    logger.info(f"  交易记录: {stats.fills_count} 条")
    logger.info(f"  失败/跳过: {stats.failed_count} 个")
    if PSUTIL_AVAILABLE:
        logger.info(f"  最终内存使用: {get_memory_usage():.1f} MB")

    # 显示评级分布
    db = TraderDatabase()
    db_stats = db.get_statistics()
    if db_stats.get('rating_distribution'):
        logger.info(f"\n评级分布:")
        for rating, count in sorted(db_stats['rating_distribution'].items()):
            logger.info(f"  {rating}: {count} 个")


def main():
    parser = argparse.ArgumentParser(
        description="Hyperliquid 排行榜交易者批量分析（支持并发）"
    )
    parser.add_argument(
        "--limit", "-n",
        type=int,
        default=5000,
        help="获取前N名交易者 (默认: 5000)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=0,
        help="分析回溯天数 (0=获取所有记录, 默认: 0)"
    )
    parser.add_argument(
        "--max-fills", "-m",
        type=int,
        default=0,
        help="每个交易者最大获取的交易记录数 (0=不限制, 默认: 0)"
    )
    parser.add_argument(
        "--resume", "-r",
        type=int,
        default=0,
        help="从第N个地址开始（断点续传）"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="并发数/线程数 (默认: 1)"
    )
    parser.add_argument(
        "--proxy",
        action="store_true",
        default=False,
        help="启用代理 (默认: 不启用)"
    )
    parser.add_argument(
        "--no-proxy",
        action="store_true",
        default=False,
        help="禁用代理 (默认行为)"
    )

    args = parser.parse_args()

    # 确定代理设置：--proxy 优先，否则检查 --no-proxy
    use_proxy = args.proxy and not args.no_proxy
    
    screen_leaderboard_traders(
        limit=args.limit,
        lookback_days=args.days,
        max_fills=args.max_fills,
        resume_from=args.resume,
        max_workers=args.workers,
        use_proxy=use_proxy
    )


if __name__ == "__main__":
    main()
