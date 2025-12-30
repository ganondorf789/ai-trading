"""
将评分最高的前30名交易员添加到跟单管理数据库

使用方法:
    python scripts/add_top_traders_to_copy.py
    python scripts/add_top_traders_to_copy.py --limit 50  # 添加前50名
    python scripts/add_top_traders_to_copy.py --min-score 70  # 只添加评分>=70的
    python scripts/add_top_traders_to_copy.py --dry-run  # 模拟运行，不实际写入
"""
import argparse
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from screener.database import TraderDatabase


def add_top_traders_to_copy_trading(
    db_path: str = "data/traders.db",
    limit: int = 30,
    min_score: float = 0,
    copy_ratio: float = 0.1,
    max_position_size_usd: float = 500.0,
    dry_run_mode: bool = True,
    preview_only: bool = False
):
    """
    将评分最高的交易员添加到跟单管理数据库

    Args:
        db_path: 数据库路径
        limit: 添加数量
        min_score: 最低评分要求
        copy_ratio: 跟单比例
        max_position_size_usd: 最大仓位价值
        dry_run_mode: 跟单模式是否为模拟
        preview_only: 只预览不写入
    """
    db = TraderDatabase(db_path)

    # 获取评分最高的交易员
    logger.info(f"正在获取评分最高的前 {limit} 名交易员...")

    top_traders = db.get_top_traders(limit=limit)

    if not top_traders:
        logger.warning("没有找到交易员数据")
        return

    # 过滤评分
    if min_score > 0:
        top_traders = [t for t in top_traders if t.get('overall_score', 0) >= min_score]
        logger.info(f"过滤后剩余 {len(top_traders)} 名交易员 (评分 >= {min_score})")

    if not top_traders:
        logger.warning(f"没有评分 >= {min_score} 的交易员")
        return

    # 显示预览
    logger.info("\n" + "=" * 80)
    logger.info(f"将添加以下 {len(top_traders)} 名交易员到跟单管理:")
    logger.info("=" * 80)
    logger.info(f"{'排名':<4} {'地址':<44} {'评分':<8} {'评级':<4} {'胜率':<8} {'PnL':<12}")
    logger.info("-" * 80)

    for i, trader in enumerate(top_traders, 1):
        address = trader.get('address', '')
        score = trader.get('overall_score', 0)
        rating = trader.get('rating', 'F')
        win_rate = trader.get('win_rate', 0) * 100
        total_pnl = trader.get('total_pnl', 0)

        logger.info(f"{i:<4} {address:<44} {score:<8.1f} {rating:<4} {win_rate:<7.1f}% ${total_pnl:<11.2f}")

    logger.info("=" * 80)
    logger.info(f"\n跟单配置:")
    logger.info(f"  - 跟单比例: {copy_ratio * 100}%")
    logger.info(f"  - 最大仓位: ${max_position_size_usd}")
    logger.info(f"  - 模拟模式: {dry_run_mode}")

    if preview_only:
        logger.info("\n[预览模式] 不会实际写入数据库")
        return

    # 添加到跟单数据库
    added_count = 0
    skipped_count = 0

    for i, trader in enumerate(top_traders, 1):
        address = trader.get('address', '')

        # 检查是否已存在
        existing = db.get_copy_trading_address(address)
        if existing:
            logger.debug(f"跳过已存在的地址: {address[:10]}...")
            skipped_count += 1
            continue

        # 添加到跟单管理
        data = {
            'address': address,
            'name': f"Top{i}_{trader.get('rating', 'F')}_{address[:6]}",
            'group_id': None,
            'is_enabled': True,
            'copy_ratio': copy_ratio,
            'max_position_size_usd': max_position_size_usd,
            'min_position_size_usd': 20.0,
            'copy_leverage': True,
            'max_leverage': 10,
            'default_leverage': 5,
            'max_total_positions': 10,
            'max_daily_trades': 50,
            'slippage': 0.01,
            'symbols_whitelist': [],
            'symbols_blacklist': [],
            'check_interval': 10.0,
            'dry_run': dry_run_mode,
        }

        try:
            db.save_copy_trading_address(data)
            added_count += 1
            logger.info(f"[{i}/{len(top_traders)}] 添加成功: {address[:10]}... (评分: {trader.get('overall_score', 0):.1f})")
        except Exception as e:
            logger.error(f"添加失败 {address[:10]}...: {e}")

    logger.info("\n" + "=" * 80)
    logger.info(f"完成! 新增: {added_count}, 跳过(已存在): {skipped_count}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="将评分最高的交易员添加到跟单管理")
    parser.add_argument("--db", default="data/traders.db", help="数据库路径")
    parser.add_argument("--limit", type=int, default=30, help="添加数量 (默认: 30)")
    parser.add_argument("--min-score", type=float, default=0, help="最低评分要求 (默认: 0)")
    parser.add_argument("--copy-ratio", type=float, default=0.1, help="跟单比例 (默认: 0.1)")
    parser.add_argument("--max-position", type=float, default=500.0, help="最大仓位USD (默认: 500)")
    parser.add_argument("--live", action="store_true", help="实盘模式 (默认为模拟模式)")
    parser.add_argument("--dry-run", action="store_true", help="只预览不写入")

    args = parser.parse_args()

    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )

    add_top_traders_to_copy_trading(
        db_path=args.db,
        limit=args.limit,
        min_score=args.min_score,
        copy_ratio=args.copy_ratio,
        max_position_size_usd=args.max_position,
        dry_run_mode=not args.live,
        preview_only=args.dry_run
    )


if __name__ == "__main__":
    main()
