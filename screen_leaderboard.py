"""
Hyperliquid 排行榜交易者批量分析
获取 month PnL 前 5000 名交易者，分析并保存到数据库
"""
import sys
import argparse
import io
from pathlib import Path

# 设置 stdout 为 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from leaderboard.fetch_leaderboard import fetch_leaderboard
from screener.trader_screener import TraderScreener, ScreenerConfig
from screener.database import TraderDatabase


def screen_leaderboard_traders(
    limit: int = 3000,
    lookback_days: int = 0,
    max_fills: int = 0,
    resume_from: int = 0
):
    """
    获取排行榜前N名交易者并分析保存到数据库

    Args:
        limit: 获取前N名交易者
        lookback_days: 分析回溯天数
        max_fills: 每个交易者最大获取的交易记录数 (0=不限制)
        resume_from: 从第N个地址开始（用于断点续传）
    """
    print("=" * 70)
    print("Hyperliquid 排行榜交易者批量分析")
    print("=" * 70)

    # 1. 获取排行榜数据（按 month PnL 排序）
    print(f"\n[1/3] 正在获取排行榜前 {limit} 名交易者...")
    leaderboard_rows = fetch_leaderboard(save_to_file=False, sort_by_pnl=True)

    if not leaderboard_rows:
        print("获取排行榜数据失败")
        return

    # 提取地址（取前 limit 个）
    addresses = [row["ethAddress"] for row in leaderboard_rows[:limit]]
    print(f"获取到 {len(addresses)} 个交易者地址")

    # 处理断点续传
    if resume_from > 0:
        addresses = addresses[resume_from:]
        print(f"从第 {resume_from + 1} 个地址开始，剩余 {len(addresses)} 个")

    if not addresses:
        print("没有需要分析的地址")
        return

    # 2. 初始化筛选器和数据库
    print(f"\n[2/3] 初始化分析器...")
    config = ScreenerConfig(
        lookback_days=lookback_days,
        max_fills_per_trader=max_fills,
        api_call_delay=0.5,  # 避免请求过快
        max_retries=3,
    )
    screener = TraderScreener(config)
    db = TraderDatabase()

    # 3. 逐个分析并保存
    print(f"\n[3/3] 开始分析交易者...")
    print("-" * 70)

    saved_count = 0
    fills_count = 0
    failed_count = 0
    total = len(addresses)

    for i, address in enumerate(addresses):
        current_index = resume_from + i + 1 if resume_from > 0 else i + 1

        try:
            # 分析单个交易者
            metrics = screener.analyze_trader(address)

            if metrics and metrics.total_trades > 0:
                # 保存到数据库（包括交易记录）
                _, fills_saved = db.save_trader_with_fills(metrics, metrics.fills)
                saved_count += 1
                fills_count += fills_saved

                print(
                    f"[{current_index}/{resume_from + total if resume_from else total}] "
                    f"✓ {address[:10]}... "
                    f"评分: {metrics.overall_score:.1f} "
                    f"评级: {metrics.rating.value} "
                    f"交易: {metrics.total_trades} "
                    f"胜率: {metrics.win_rate:.1%} "
                    f"PnL: ${metrics.total_pnl:,.0f}"
                )
            else:
                failed_count += 1
                print(
                    f"[{current_index}/{resume_from + total if resume_from else total}] "
                    f"✗ {address[:10]}... 无交易数据"
                )

        except KeyboardInterrupt:
            print(f"\n\n用户中断，已保存 {saved_count} 个交易者")
            print(f"断点续传命令: python screen_leaderboard.py --resume {current_index}")
            return
        except Exception as e:
            failed_count += 1
            print(
                f"[{current_index}/{resume_from + total if resume_from else total}] "
                f"✗ {address[:10]}... 错误: {str(e)[:50]}"
            )

    # 打印统计
    print("\n" + "=" * 70)
    print("分析完成!")
    print("=" * 70)
    print(f"  成功保存: {saved_count} 个交易者")
    print(f"  交易记录: {fills_count} 条")
    print(f"  失败/跳过: {failed_count} 个")
    print(f"  数据库: {db.db_path}")

    # 显示评级分布
    stats = db.get_statistics()
    if stats.get('rating_distribution'):
        print(f"\n评级分布:")
        for rating, count in sorted(stats['rating_distribution'].items()):
            print(f"  {rating}: {count} 个")


def main():
    parser = argparse.ArgumentParser(
        description="Hyperliquid 排行榜交易者批量分析"
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

    args = parser.parse_args()

    screen_leaderboard_traders(
        limit=args.limit,
        lookback_days=args.days,
        max_fills=args.max_fills,
        resume_from=args.resume
    )


if __name__ == "__main__":
    main()
