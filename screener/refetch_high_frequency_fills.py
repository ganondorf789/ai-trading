"""
高频时间段数据补充脚本

扫描数据库中 2 分钟内 >= 2000 条记录的时间段，
按 1 分钟粒度重新获取数据，补充可能丢失的记录。

用法:
    # 扫描最近30天的高频时间段（仅查看）
    python -m screener.refetch_high_frequency_fills --dry-run
    
    # 补充最近30天的高频时间段数据
    python -m screener.refetch_high_frequency_fills
    
    # 只处理指定交易者
    python -m screener.refetch_high_frequency_fills --address 0x1234...
    
    # 限制处理数量
    python -m screener.refetch_high_frequency_fills --limit 10
    
    # 扫描最近7天的数据
    python -m screener.refetch_high_frequency_fills --lookback-days 7 --dry-run
    
    # 扫描所有历史数据（慎用，可能很慢）
    python -m screener.refetch_high_frequency_fills --lookback-days 0 --dry-run
"""
import argparse
import time
from typing import List, Dict, Tuple, Optional
import pendulum
from loguru import logger

from .api_client import SyncAPIClient, get_proxy_manager
from .config import APIConfig
from .utils import SHANGHAI_TZ, calculate_trade_type, timestamp_to_pendulum


def enrich_fills(fills: List[Dict]) -> List[Dict]:
    """
    为成交记录添加 trade_type 字段
    
    Args:
        fills: 原始成交记录列表
    
    Returns:
        添加了 trade_type 的成交记录列表
    """
    if not fills:
        return fills
    
    for fill in fills:
        if 'trade_type' not in fill or fill['trade_type'] is None:
            dir_val = fill.get('dir', '')
            start_pos = float(fill.get('startPosition', 0)) if fill.get('startPosition') else 0
            fill['trade_type'] = calculate_trade_type(dir_val, start_pos)
    
    return fills


def fetch_fills_by_1minute(
    client: SyncAPIClient,
    address: str,
    start_ms: int,
    end_ms: int,
    delay: float = 0.5
) -> List[Dict]:
    """
    按 1 分钟粒度获取成交记录
    
    Args:
        client: API 客户端
        address: 交易者地址
        start_ms: 开始时间（毫秒）
        end_ms: 结束时间（毫秒）
        delay: API 调用间隔（秒）
    
    Returns:
        成交记录列表（已添加 trade_type）
    """
    all_fills = []
    current_ms = start_ms
    
    while current_ms < end_ms:
        next_ms = min(current_ms + 60000, end_ms)  # 1分钟 = 60000毫秒
        
        try:
            fills = client.get_user_fills_by_time(address, current_ms, next_ms)
            if fills:
                all_fills.extend(enrich_fills(fills))
                
                if len(fills) >= 2000:
                    logger.warning(
                        f"    1分钟 [{timestamp_to_pendulum(current_ms).format('HH:mm:ss')}-"
                        f"{timestamp_to_pendulum(next_ms).format('HH:mm:ss')}]: "
                        f"{len(fills)} 条（达到上限，可能仍有数据丢失）"
                    )
                else:
                    logger.debug(
                        f"    1分钟 [{timestamp_to_pendulum(current_ms).format('HH:mm:ss')}-"
                        f"{timestamp_to_pendulum(next_ms).format('HH:mm:ss')}]: "
                        f"{len(fills)} 条"
                    )
        except Exception as e:
            logger.error(
                f"    获取1分钟数据失败 [{timestamp_to_pendulum(current_ms).format('HH:mm:ss')}]: {repr(e)}"
            )
        
        current_ms = next_ms
        if delay > 0:
            time.sleep(delay)
    
    return all_fills


def refetch_window(
    client: SyncAPIClient,
    db,
    window: Dict,
    delay: float = 0.5
) -> Tuple[int, int]:
    """
    重新获取一个高频时间窗口的数据
    
    Args:
        client: API 客户端
        db: 数据库实例
        window: 时间窗口信息
        delay: API 调用间隔（秒）
    
    Returns:
        (获取的记录数, 保存的记录数)
    """
    address = window['address']
    start_ms = window['window_start']
    end_ms = window['window_end']
    
    window_time = timestamp_to_pendulum(start_ms)
    logger.info(
        f"  处理窗口: {address[:10]}... @ {window_time.format('YYYY-MM-DD HH:mm:ss')} "
        f"(原有 {window['fill_count']} 条)"
    )
    
    # 按 1 分钟获取数据
    fills = fetch_fills_by_1minute(client, address, start_ms, end_ms, delay)
    
    if not fills:
        logger.info(f"    未获取到数据")
        return 0, 0
    
    # 保存到数据库
    saved_count = db.save_fills(address, fills)
    
    logger.info(f"    获取 {len(fills)} 条，保存 {saved_count} 条（新增或更新）")
    
    return len(fills), saved_count


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='补充高频时间段的成交数据')
    parser.add_argument('--address', '-a', type=str, help='指定交易者地址（不指定则扫描全部）')
    parser.add_argument('--threshold', '-t', type=int, default=2000, help='阈值（默认 2000）')
    parser.add_argument('--delay', '-d', type=float, default=0.5, help='API 调用间隔（秒，默认 0.5）')
    parser.add_argument('--dry-run', action='store_true', help='只扫描不获取')
    parser.add_argument('--no-proxy', action='store_true', help='不使用代理')
    parser.add_argument('--limit', '-l', type=int, default=0, help='限制处理的窗口数量（0=不限制）')
    parser.add_argument('--lookback-days', type=int, default=30, help='回溯天数（默认 30，0=查询所有）')
    
    args = parser.parse_args()
    
    # 初始化数据库
    from database import TraderDatabase
    db = TraderDatabase()
    
    logger.info("=" * 60)
    logger.info("高频时间段数据补充脚本")
    logger.info("=" * 60)
    
    # 查找高频时间段
    lookback_info = f"最近 {args.lookback_days} 天" if args.lookback_days > 0 else "全部数据"
    logger.info(f"正在扫描高频时间段 (阈值: {args.threshold} 条/2分钟, 范围: {lookback_info})...")
    windows = db.get_high_frequency_windows(
        address=args.address,
        window_minutes=2,
        threshold=args.threshold,
        lookback_days=args.lookback_days
    )
    
    if not windows:
        logger.info("未找到高频时间段，无需补充数据")
        return
    
    logger.info(f"找到 {len(windows)} 个高频时间段:")
    for i, w in enumerate(windows[:10]):  # 只显示前10个
        window_time = timestamp_to_pendulum(w['window_start'])
        logger.info(
            f"  [{i+1}] {w['address'][:10]}... @ {window_time.format('YYYY-MM-DD HH:mm:ss')} "
            f"- {w['fill_count']} 条"
        )
    if len(windows) > 10:
        logger.info(f"  ... 还有 {len(windows) - 10} 个")
    
    if args.dry_run:
        logger.info("--dry-run 模式，仅扫描不获取数据")
        return
    
    # 初始化 API 客户端
    config = APIConfig(proxy_enabled=not args.no_proxy)
    proxy_manager = get_proxy_manager(enabled=not args.no_proxy)
    client = SyncAPIClient(config=config, proxy_manager=proxy_manager, cache_fills=False)
    
    # 处理限制
    if args.limit > 0:
        windows = windows[:args.limit]
        logger.info(f"限制处理前 {args.limit} 个窗口")
    
    # 处理每个高频时间段
    total_fetched = 0
    total_saved = 0
    
    logger.info(f"\n开始补充数据 (共 {len(windows)} 个窗口)...")
    
    for i, window in enumerate(windows):
        logger.info(f"\n[{i+1}/{len(windows)}]")
        try:
            fetched, saved = refetch_window(client, db, window, args.delay)
            total_fetched += fetched
            total_saved += saved
        except Exception as e:
            logger.error(f"  处理窗口失败: {repr(e)}")
        
        # 窗口间延迟
        if args.delay > 0:
            time.sleep(args.delay)
    
    # 关闭客户端
    client.close()
    
    logger.info("\n" + "=" * 60)
    logger.info("处理完成:")
    logger.info(f"  - 处理窗口数: {len(windows)}")
    logger.info(f"  - 获取记录数: {total_fetched}")
    logger.info(f"  - 保存记录数: {total_saved}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
