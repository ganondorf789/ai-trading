"""
Hyperliquid 优质交易者筛选示例
演示如何使用 TraderScreener 筛选优质交易者
所有分析结果保存到 SQLite 数据库
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from screener.trader_screener import TraderScreener, ScreenerConfig, QualityRating
from screener.address_sources import AddressSource
from database import TraderDatabase


def progress_callback(current: int, total: int, address: str, result):
    """进度回调函数"""
    status = "✓" if result else "✗"
    score = f"{result.overall_score:.1f}" if result else "N/A"
    print(f"\r[{current}/{total}] {status} {address[:10]}... Score: {score}", end="", flush=True)


def example_basic_screening():
    """
    基础筛选示例

    使用默认配置筛选交易者，结果保存到 SQLite 数据库
    """
    print("\n" + "=" * 60)
    print("示例 1: 基础筛选")
    print("=" * 60)

    # 创建筛选器和数据库
    screener = TraderScreener()
    db = TraderDatabase()

    # 候选交易者地址列表
    candidate_addresses = [
        # 在这里添加要分析的交易者地址
        # 例如: "0x1234567890abcdef1234567890abcdef12345678"
    ]

    if not candidate_addresses:
        print("请在 candidate_addresses 列表中添加要分析的交易者地址")
        return

    # 筛选优质交易者
    qualified_traders = screener.screen_traders(
        candidate_addresses,
        progress_callback=progress_callback
    )
    print()  # 换行

    # 打印结果
    screener.print_summary(qualified_traders)

    # 保存结果到数据库
    if qualified_traders:
        session_id = db.save_screening_session(
            traders=qualified_traders,
            config={
                'lookback_days': screener.config.lookback_days,
                'min_total_trades': screener.config.min_total_trades,
                'min_win_rate': screener.config.min_win_rate,
                'min_profit_factor': screener.config.min_profit_factor,
            },
            total_analyzed=len(candidate_addresses)
        )
        print(f"结果已保存到数据库，会话ID: {session_id}")


def example_custom_config():
    """
    自定义配置示例

    使用自定义筛选条件
    """
    print("\n" + "=" * 60)
    print("示例 2: 自定义筛选配置")
    print("=" * 60)

    # 自定义配置
    config = ScreenerConfig(
        # 数据配置
        lookback_days=60,  # 回溯60天数据
        max_fills_per_trader=5000,

        # 严格筛选条件
        min_total_trades=50,  # 至少50笔交易
        min_win_rate=0.55,  # 胜率至少55%
        min_profit_factor=1.5,  # 盈亏比至少1.5
        min_total_pnl=1000.0,  # 至少盈利1000美元
        max_drawdown=0.3,  # 最大回撤不超过30%
        min_active_days=20,  # 至少活跃20天
        min_sharpe_ratio=0.5,  # 夏普比率至少0.5

        # 评分权重
        profitability_weight=0.40,  # 更看重盈利能力
        risk_weight=0.35,  # 风险控制
        consistency_weight=0.15,  # 稳定性
        activity_weight=0.10,  # 活跃度

        # 输出配置
        top_n=10,  # 只输出前10名
    )

    screener = TraderScreener(config)
    db = TraderDatabase()

    # 从文件加载地址
    address_source = AddressSource()
    # address_source.load_from_file("data/candidate_addresses.json")

    # 或者手动添加地址
    addresses = [
        # 添加地址...
    ]

    if not addresses:
        print("请添加候选交易者地址")
        return

    qualified = screener.screen_traders(addresses, progress_callback)
    print()
    screener.print_summary(qualified)

    # 保存到数据库
    if qualified:
        session_id = db.save_screening_session(
            traders=qualified,
            config={
                'lookback_days': config.lookback_days,
                'min_total_trades': config.min_total_trades,
                'min_win_rate': config.min_win_rate,
                'min_profit_factor': config.min_profit_factor,
                'min_total_pnl': config.min_total_pnl,
                'max_drawdown': config.max_drawdown,
            },
            total_analyzed=len(addresses)
        )
        print(f"结果已保存到数据库，会话ID: {session_id}")


def example_batch_screening():
    """
    批量筛选示例

    逐个分析交易者，完成一个后再分析下一个
    """
    print("\n" + "=" * 60)
    print("示例 3: 批量筛选（逐个分析）")
    print("=" * 60)

    config = ScreenerConfig(
        lookback_days=30,
        min_total_trades=20,
        min_win_rate=0.5,
    )

    screener = TraderScreener(config)
    db = TraderDatabase()

    addresses = [
        # 大量候选地址...
    ]

    if not addresses:
        print("请添加候选交易者地址")
        return

    # 逐个分析交易者，完成一个后再分析下一个
    results = []
    total = len(addresses)

    for i, address in enumerate(addresses):
        print(f"\n[{i+1}/{total}] 正在分析: {address}")

        # 分析单个交易者（阻塞直到完成）
        metrics = screener.analyze_trader(address)

        if metrics:
            results.append(metrics)
            # 每个分析结果立即保存到数据库
            db.save_trader(metrics)
            print(f"  ✓ 完成 - 评分: {metrics.overall_score:.1f}, 评级: {metrics.rating.value}")
        else:
            print(f"  ✗ 无法获取数据")

    # 筛选符合条件的交易者
    qualified = [m for m in results if screener._passes_filters(m)]
    qualified.sort(key=lambda x: x.overall_score, reverse=True)

    print()
    screener.print_summary(qualified)


def example_analyze_single():
    """
    分析单个交易者示例

    详细分析特定交易者的表现
    """
    print("\n" + "=" * 60)
    print("示例 4: 分析单个交易者")
    print("=" * 60)

    screener = TraderScreener()
    db = TraderDatabase()

    # 要分析的交易者地址
    address = None  # 替换为实际地址

    if not address:
        print("请设置要分析的交易者地址")
        return

    metrics = screener.analyze_trader(address)

    if not metrics:
        print(f"无法获取交易者 {address[:10]}... 的数据")
        return

    # 保存到数据库
    db.save_trader(metrics)

    print(f"\n交易者分析报告: {address}")
    print("-" * 50)
    print(f"评级: {metrics.rating.value} (评分: {metrics.overall_score:.1f})")
    print()
    print("交易统计:")
    print(f"  总交易次数: {metrics.total_trades}")
    print(f"  盈利次数: {metrics.winning_trades}")
    print(f"  亏损次数: {metrics.losing_trades}")
    print(f"  胜率: {metrics.win_rate:.1%}")
    print()
    print("盈亏情况:")
    print(f"  总盈亏: ${metrics.total_pnl:,.2f}")
    print(f"  已实现盈亏: ${metrics.realized_pnl:,.2f}")
    print(f"  未实现盈亏: ${metrics.unrealized_pnl:,.2f}")
    print(f"  平均每笔盈亏: ${metrics.avg_profit_per_trade:,.2f}")
    print()
    print("风险指标:")
    print(f"  盈亏比: {metrics.profit_factor:.2f}" if metrics.profit_factor != float('inf') else "  盈亏比: ∞")
    print(f"  最大回撤: {metrics.max_drawdown:.1%}")
    print(f"  夏普比率: {metrics.sharpe_ratio:.2f}")
    print(f"  索提诺比率: {metrics.sortino_ratio:.2f}")
    print()
    print("活跃度:")
    print(f"  活跃天数: {metrics.active_days}")
    print(f"  日均交易: {metrics.trade_frequency_per_day:.1f} 笔")
    if metrics.last_trade_time:
        print(f"  最后交易: {metrics.last_trade_time.strftime('%Y-%m-%d %H:%M')}")
    print()
    print("当前状态:")
    print(f"  当前持仓数: {metrics.current_positions}")
    print(f"  账户权益: ${metrics.current_equity:,.2f}")
    print(f"  平均杠杆: {metrics.avg_leverage}x")
    print()
    print("分项评分:")
    print(f"  盈利能力: {metrics.profitability_score:.1f}/100")
    print(f"  风险控制: {metrics.risk_score:.1f}/100")
    print(f"  稳定性: {metrics.consistency_score:.1f}/100")
    print(f"  活跃度: {metrics.activity_score:.1f}/100")

    print(f"\n已保存到数据库")


def example_from_file():
    """
    从文件加载地址进行筛选
    每分析完一个交易者就立即保存到数据库
    """
    print("\n" + "=" * 60)
    print("示例 5: 从文件加载地址")
    print("=" * 60)

    # 创建地址源
    source = AddressSource()

    # 从文件加载（支持 JSON 或文本格式）
    source.load_from_file("data/sample_addresses.txt")
    # source.load_from_file("data/addresses.txt")

    # 或手动添加
    source.add_addresses([
        # "0x..."
    ])

    addresses = source.get_addresses()

    if not addresses:
        print("请先加载或添加交易者地址")
        print("支持的文件格式:")
        print("  - JSON 文件: [\"0x...\", \"0x...\"] 或 {\"addresses\": [...]}")
        print("  - 文本文件: 每行一个地址")
        return

    screener = TraderScreener()
    db = TraderDatabase()
    saved_count = [0]  # 使用列表以便在回调中修改

    fills_count = [0]  # 保存的交易记录总数

    def progress_callback_with_save(current: int, total: int, address: str, result):
        """进度回调函数，每分析完一个就保存到数据库（包括交易记录）"""
        status = "✓" if result else "✗"
        score = f"{result.overall_score:.1f}" if result else "N/A"

        # 如果分析成功，立即保存到数据库（包括交易记录）
        if result:
            _, fills_saved = db.save_trader_with_fills(result, result.fills)
            saved_count[0] += 1
            fills_count[0] += fills_saved
            print(f"\r[{current}/{total}] {status} {address[:10]}... Score: {score} (已保存 {saved_count[0]} 个, {fills_count[0]} 条交易)", end="", flush=True)
        else:
            print(f"\r[{current}/{total}] {status} {address[:10]}... Score: {score}", end="", flush=True)

    qualified = screener.screen_traders(addresses, progress_callback_with_save)
    print()
    print(f"\n已实时保存 {saved_count[0]} 个交易者，{fills_count[0]} 条交易记录到数据库")
    screener.print_summary(qualified)


def example_query_database():
    """
    查询数据库示例

    展示如何查询已保存的分析结果
    """
    print("\n" + "=" * 60)
    print("示例 6: 查询数据库")
    print("=" * 60)

    db = TraderDatabase()

    # 获取数据库统计
    stats = db.get_statistics()
    print("\n数据库统计:")
    print(f"  总记录数: {stats['total_records']}")
    print(f"  唯一地址数: {stats['unique_addresses']}")
    print(f"  筛选会话数: {stats['total_sessions']}")
    print(f"  评级分布: {stats['rating_distribution']}")

    # 获取评分最高的交易者
    print("\n评分最高的交易者 (Top 10):")
    top_traders = db.get_top_traders(limit=10)
    if top_traders:
        print(f"{'排名':<4} {'评级':<4} {'地址':<14} {'评分':<6} {'胜率':<8} {'总PnL':<12}")
        print("-" * 60)
        for i, trader in enumerate(top_traders, 1):
            addr_short = f"{trader['address'][:6]}...{trader['address'][-4:]}"
            pnl_str = f"${trader['total_pnl']:,.2f}"
            print(f"{i:<4} {trader['rating']:<4} {addr_short:<14} "
                  f"{trader['overall_score']:>5.1f} {trader['win_rate']:>7.1%} {pnl_str:>11}")
    else:
        print("  数据库中暂无记录")

    # 获取 S 和 A 级交易者
    print("\n优质交易者 (S/A 级):")
    for rating in ['S', 'A']:
        traders = db.get_traders_by_rating(rating)
        if traders:
            print(f"\n  [{rating}] 级交易者 ({len(traders)} 个):")
            for trader in traders[:5]:  # 只显示前5个
                print(f"    {trader['address']} - 评分: {trader['overall_score']:.1f}")

    # 获取最近的筛选会话
    print("\n最近筛选会话:")
    sessions = db.get_recent_sessions(limit=5)
    if sessions:
        for session in sessions:
            print(f"  会话 #{session['id']}: {session['created_at']} - "
                  f"分析 {session['total_analyzed']} 个，筛选出 {session['qualified_count']} 个")
    else:
        print("  暂无筛选会话")


def example_trader_history():
    """
    查看交易者历史记录示例
    """
    print("\n" + "=" * 60)
    print("示例 7: 交易者历史分析记录")
    print("=" * 60)

    db = TraderDatabase()

    # 设置要查询的地址
    address = None  # 替换为实际地址

    if not address:
        print("请设置要查询的交易者地址")
        return

    history = db.get_trader_history(address, limit=10)

    if not history:
        print(f"未找到交易者 {address[:10]}... 的历史记录")
        return

    print(f"\n交易者 {address[:10]}... 的历史分析记录:")
    print(f"{'分析时间':<20} {'评分':<8} {'评级':<4} {'胜率':<8} {'总PnL':<12}")
    print("-" * 60)

    for record in history:
        print(f"{record['analyzed_at'][:19]:<20} "
              f"{record['overall_score']:>6.1f} "
              f"{record['rating']:<4} "
              f"{record['win_rate']:>7.1%} "
              f"${record['total_pnl']:>10,.2f}")


def main():
    """主函数 - 运行所有示例"""
    print("=" * 60)
    print("Hyperliquid 优质交易者筛选器 - 使用示例")
    print("数据库: data/traders.db")
    print("=" * 60)

    print("\n选择要运行的示例:")
    print("1. 基础筛选")
    print("2. 自定义配置筛选")
    print("3. 批量筛选")
    print("4. 分析单个交易者")
    print("5. 从文件加载地址")
    print("6. 查询数据库")
    print("7. 交易者历史记录")
    print("0. 运行所有示例")

    try:
        choice = input("\n请输入选项 (0-7): ").strip()
    except EOFError:
        choice = "6"  # 默认运行查询数据库示例

    if choice == "1":
        example_basic_screening()
    elif choice == "2":
        example_custom_config()
    elif choice == "3":
        example_batch_screening()
    elif choice == "4":
        example_analyze_single()
    elif choice == "5":
        example_from_file()
    elif choice == "6":
        example_query_database()
    elif choice == "7":
        example_trader_history()
    elif choice == "0":
        example_basic_screening()
        example_custom_config()
        example_batch_screening()
        example_analyze_single()
        example_from_file()
        example_query_database()
        example_trader_history()
    else:
        print("无效选项")


if __name__ == "__main__":
    main()
