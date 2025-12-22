#!/usr/bin/env python
"""
Hyperliquid 优质交易者筛选脚本
自动分析和筛选优质交易者地址

使用方法:
    # 分析单个地址
    python screen_traders.py --address 0x1234...
    
    # 从文件批量筛选
    python screen_traders.py --file addresses.txt
    
    # 使用自定义参数
    python screen_traders.py --file addresses.json --min-win-rate 0.55 --min-pnl 1000 --top 20
    
    # 输出到文件
    python screen_traders.py --file addresses.txt --output results.json
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

from loguru import logger

from screener.trader_screener import TraderScreener, ScreenerConfig, QualityRating
from screener.address_sources import AddressSource


def setup_logging(verbose: bool = False):
    """配置日志"""
    logger.remove()
    
    if verbose:
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
        )
    else:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
        )


def progress_callback(current: int, total: int, address: str, result):
    """进度回调"""
    pct = current / total * 100
    status = "✓" if result else "✗"
    score = f"{result.overall_score:.1f}" if result else "---"
    rating = result.rating.value if result else "-"
    
    bar_len = 30
    filled = int(bar_len * current / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    print(f"\r[{bar}] {pct:5.1f}% ({current}/{total}) "
          f"{status} {address[:10]}... [{rating}] {score}", end="", flush=True)


def load_addresses_from_input(args) -> list:
    """从各种输入源加载地址"""
    addresses = []
    source = AddressSource(testnet=args.testnet)
    
    # 从命令行参数加载单个地址
    if args.address:
        addresses.append(args.address)
    
    # 从文件加载
    if args.file:
        source.load_from_file(args.file)
        addresses.extend(source.get_addresses())
    
    # 从标准输入加载
    if args.stdin:
        print("从标准输入读取地址 (每行一个, Ctrl+D 结束):")
        for line in sys.stdin:
            addr = line.strip()
            if addr and addr.startswith('0x'):
                addresses.append(addr)
    
    # 去重
    addresses = list(dict.fromkeys(addresses))
    
    return addresses


def analyze_single_trader(screener: TraderScreener, address: str):
    """分析并显示单个交易者详情"""
    print(f"\n正在分析交易者: {address}")
    print("-" * 60)
    
    metrics = screener.analyze_trader(address)
    
    if not metrics:
        print(f"❌ 无法获取交易者数据")
        return None
    
    # 详细报告
    print(f"\n📊 交易者分析报告")
    print(f"地址: {address}")
    print(f"评级: {metrics.rating.value} (综合评分: {metrics.overall_score:.1f}/100)")
    print()
    
    # 交易统计
    print("【交易统计】")
    print(f"  • 总交易次数: {metrics.total_trades}")
    print(f"  • 盈利交易: {metrics.winning_trades} ({metrics.win_rate:.1%})")
    print(f"  • 亏损交易: {metrics.losing_trades}")
    print(f"  • 活跃天数: {metrics.active_days}")
    if metrics.first_trade_time:
        print(f"  • 首次交易: {metrics.first_trade_time.strftime('%Y-%m-%d')}")
    if metrics.last_trade_time:
        print(f"  • 最后交易: {metrics.last_trade_time.strftime('%Y-%m-%d %H:%M')}")
    print()
    
    # 盈亏情况
    print("【盈亏情况】")
    pnl_sign = "+" if metrics.total_pnl >= 0 else ""
    print(f"  • 总盈亏: {pnl_sign}${metrics.total_pnl:,.2f}")
    print(f"  • 已实现: ${metrics.realized_pnl:,.2f}")
    print(f"  • 未实现: ${metrics.unrealized_pnl:,.2f}")
    print(f"  • 均笔盈亏: ${metrics.avg_profit_per_trade:,.2f}")
    print(f"  • 总交易额: ${metrics.total_volume:,.2f}")
    print()
    
    # 风险指标
    print("【风险指标】")
    pf_str = f"{metrics.profit_factor:.2f}" if metrics.profit_factor != float('inf') else "∞"
    print(f"  • 盈亏比: {pf_str}")
    print(f"  • 最大回撤: {metrics.max_drawdown:.1%}")
    print(f"  • 夏普比率: {metrics.sharpe_ratio:.2f}")
    print(f"  • 索提诺比率: {metrics.sortino_ratio:.2f}")
    print()
    
    # 当前状态
    print("【当前状态】")
    print(f"  • 持仓数量: {metrics.current_positions}")
    print(f"  • 账户权益: ${metrics.current_equity:,.2f}")
    print(f"  • 平均杠杆: {metrics.avg_leverage}x")
    print()
    
    # 分项评分
    print("【分项评分】")
    print(f"  • 盈利能力: {metrics.profitability_score:.1f}/100 {'🔥' if metrics.profitability_score >= 70 else ''}")
    print(f"  • 风险控制: {metrics.risk_score:.1f}/100 {'🛡️' if metrics.risk_score >= 70 else ''}")
    print(f"  • 稳定性:   {metrics.consistency_score:.1f}/100 {'📈' if metrics.consistency_score >= 70 else ''}")
    print(f"  • 活跃度:   {metrics.activity_score:.1f}/100 {'⚡' if metrics.activity_score >= 70 else ''}")
    
    print()
    
    # 评级说明
    rating_desc = {
        QualityRating.S_TIER: "🏆 顶级交易者 - 强烈推荐跟单",
        QualityRating.A_TIER: "⭐ 优秀交易者 - 推荐跟单",
        QualityRating.B_TIER: "👍 良好交易者 - 可考虑跟单",
        QualityRating.C_TIER: "📊 一般交易者 - 需谨慎观察",
        QualityRating.D_TIER: "⚠️ 较差交易者 - 不建议跟单",
        QualityRating.F_TIER: "❌ 不推荐 - 避免跟单"
    }
    print(f"结论: {rating_desc.get(metrics.rating, '未知')}")
    print("-" * 60)
    
    return metrics


def screen_traders_batch(screener: TraderScreener, addresses: list, args):
    """批量筛选交易者"""
    print(f"\n开始筛选 {len(addresses)} 个交易者地址...")
    print(f"筛选条件:")
    print(f"  • 最小交易次数: {screener.config.min_total_trades}")
    print(f"  • 最小胜率: {screener.config.min_win_rate:.0%}")
    print(f"  • 最小盈亏比: {screener.config.min_profit_factor:.1f}")
    print(f"  • 最小总盈利: ${screener.config.min_total_pnl:,.0f}")
    print(f"  • 最大回撤: {screener.config.max_drawdown:.0%}")
    print(f"  • 回溯天数: {screener.config.lookback_days}")
    print()
    
    # 执行筛选
    if args.async_mode:
        qualified = asyncio.run(
            screener.screen_traders_async(addresses, progress_callback)
        )
    else:
        qualified = screener.screen_traders(addresses, progress_callback)
    
    print()  # 换行
    
    # 打印结果
    screener.print_summary(qualified)
    
    # 保存结果
    if args.output:
        screener.save_results(qualified, args.output)
    elif qualified:
        # 默认保存位置
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_output = f"data/screener_results_{timestamp}.json"
        screener.save_results(qualified, default_output)
    
    return qualified


def main():
    parser = argparse.ArgumentParser(
        description="Hyperliquid 优质交易者筛选器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 分析单个交易者
  python screen_traders.py -a 0x1234567890abcdef1234567890abcdef12345678
  
  # 从文件批量筛选
  python screen_traders.py -f addresses.txt
  
  # 使用严格条件筛选
  python screen_traders.py -f addresses.json --min-win-rate 0.6 --min-pnl 5000 --max-drawdown 0.2
  
  # 异步模式加速筛选
  python screen_traders.py -f addresses.txt --async --concurrent 10
        """
    )
    
    # 输入源
    input_group = parser.add_argument_group("输入源")
    input_group.add_argument(
        "-a", "--address",
        help="分析单个交易者地址"
    )
    input_group.add_argument(
        "-f", "--file",
        help="从文件加载地址 (JSON 或 TXT 格式)"
    )
    input_group.add_argument(
        "--stdin",
        action="store_true",
        help="从标准输入读取地址"
    )
    
    # 筛选条件
    filter_group = parser.add_argument_group("筛选条件")
    filter_group.add_argument(
        "--min-trades",
        type=int,
        default=10,
        help="最小交易次数 (默认: 10)"
    )
    filter_group.add_argument(
        "--min-win-rate",
        type=float,
        default=0.45,
        help="最小胜率 (默认: 0.45)"
    )
    filter_group.add_argument(
        "--min-pf",
        type=float,
        default=1.0,
        help="最小盈亏比 (默认: 1.0)"
    )
    filter_group.add_argument(
        "--min-pnl",
        type=float,
        default=0.0,
        help="最小总盈利 (默认: 0)"
    )
    filter_group.add_argument(
        "--max-drawdown",
        type=float,
        default=0.5,
        help="最大回撤 (默认: 0.5)"
    )
    filter_group.add_argument(
        "--min-days",
        type=int,
        default=5,
        help="最小活跃天数 (默认: 5)"
    )
    filter_group.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="回溯天数 (默认: 30)"
    )
    
    # 输出配置
    output_group = parser.add_argument_group("输出配置")
    output_group.add_argument(
        "-o", "--output",
        help="输出文件路径"
    )
    output_group.add_argument(
        "--top",
        type=int,
        default=20,
        help="输出前 N 名 (默认: 20)"
    )
    output_group.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出到标准输出"
    )
    
    # 性能配置
    perf_group = parser.add_argument_group("性能配置")
    perf_group.add_argument(
        "--async",
        dest="async_mode",
        action="store_true",
        help="使用异步模式加速"
    )
    perf_group.add_argument(
        "--concurrent",
        type=int,
        default=5,
        help="并发请求数 (默认: 5)"
    )
    perf_group.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="请求间隔秒数 (默认: 0.2)"
    )
    
    # 其他选项
    parser.add_argument(
        "--testnet",
        action="store_true",
        help="使用测试网"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging(args.verbose)
    
    # 检查是否有输入
    if not args.address and not args.file and not args.stdin:
        parser.print_help()
        print("\n❌ 错误: 请指定输入源 (-a, -f, 或 --stdin)")
        sys.exit(1)
    
    # 创建配置
    config = ScreenerConfig(
        testnet=args.testnet,
        lookback_days=args.lookback,
        min_total_trades=args.min_trades,
        min_win_rate=args.min_win_rate,
        min_profit_factor=args.min_pf,
        min_total_pnl=args.min_pnl,
        max_drawdown=args.max_drawdown,
        min_active_days=args.min_days,
        top_n=args.top,
        max_concurrent_requests=args.concurrent,
        request_delay=args.delay,
    )
    
    # 创建筛选器
    screener = TraderScreener(config)
    
    # 加载地址
    addresses = load_addresses_from_input(args)
    
    if not addresses:
        print("❌ 错误: 未找到有效的交易者地址")
        sys.exit(1)
    
    print(f"\n🔍 Hyperliquid 优质交易者筛选器")
    print(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 网络: {'测试网' if args.testnet else '主网'}")
    
    # 执行分析
    if len(addresses) == 1 and args.address:
        # 单个地址详细分析
        metrics = analyze_single_trader(screener, addresses[0])
        
        if args.json and metrics:
            print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))
    else:
        # 批量筛选
        qualified = screen_traders_batch(screener, addresses, args)
        
        if args.json and qualified:
            result = [t.to_dict() for t in qualified]
            print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

