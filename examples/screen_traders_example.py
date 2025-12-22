"""
Hyperliquid 优质交易者筛选示例
演示如何使用 TraderScreener 筛选优质交易者
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from screener.trader_screener import TraderScreener, ScreenerConfig, QualityRating
from screener.address_sources import AddressSource


def progress_callback(current: int, total: int, address: str, result):
    """进度回调函数"""
    status = "✓" if result else "✗"
    score = f"{result.overall_score:.1f}" if result else "N/A"
    print(f"\r[{current}/{total}] {status} {address[:10]}... Score: {score}", end="", flush=True)


def example_basic_screening():
    """
    基础筛选示例
    
    使用默认配置筛选交易者
    """
    print("\n" + "=" * 60)
    print("示例 1: 基础筛选")
    print("=" * 60)
    
    # 创建筛选器（使用默认配置）
    screener = TraderScreener()
    
    # 候选交易者地址列表
    # 实际使用时，这些地址应该来自：
    # 1. Hyperliquid 排行榜
    # 2. 社区推荐
    # 3. 链上数据分析
    # 4. 你自己收集的地址
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
    
    # 保存结果
    screener.save_results(qualified_traders, "data/qualified_traders.json")


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
        output_file="data/top_traders_strict.json"
    )
    
    screener = TraderScreener(config)
    
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
    
    # 要分析的交易者地址
    address = None  # 替换为实际地址
    
    if not address:
        print("请设置要分析的交易者地址")
        return
    
    metrics = screener.analyze_trader(address)
    
    if not metrics:
        print(f"无法获取交易者 {address[:10]}... 的数据")
        return
    
    print(f"\n交易者分析报告: {address}")
    print("-" * 50)
    print(f"评级: {metrics.rating.value} (评分: {metrics.overall_score:.1f})")
    print()
    print("📊 交易统计:")
    print(f"  总交易次数: {metrics.total_trades}")
    print(f"  盈利次数: {metrics.winning_trades}")
    print(f"  亏损次数: {metrics.losing_trades}")
    print(f"  胜率: {metrics.win_rate:.1%}")
    print()
    print("💰 盈亏情况:")
    print(f"  总盈亏: ${metrics.total_pnl:,.2f}")
    print(f"  已实现盈亏: ${metrics.realized_pnl:,.2f}")
    print(f"  未实现盈亏: ${metrics.unrealized_pnl:,.2f}")
    print(f"  平均每笔盈亏: ${metrics.avg_profit_per_trade:,.2f}")
    print()
    print("📈 风险指标:")
    print(f"  盈亏比: {metrics.profit_factor:.2f}" if metrics.profit_factor != float('inf') else "  盈亏比: ∞")
    print(f"  最大回撤: {metrics.max_drawdown:.1%}")
    print(f"  夏普比率: {metrics.sharpe_ratio:.2f}")
    print(f"  索提诺比率: {metrics.sortino_ratio:.2f}")
    print()
    print("⏱️ 活跃度:")
    print(f"  活跃天数: {metrics.active_days}")
    print(f"  日均交易: {metrics.trade_frequency_per_day:.1f} 笔")
    if metrics.last_trade_time:
        print(f"  最后交易: {metrics.last_trade_time.strftime('%Y-%m-%d %H:%M')}")
    print()
    print("💼 当前状态:")
    print(f"  当前持仓数: {metrics.current_positions}")
    print(f"  账户权益: ${metrics.current_equity:,.2f}")
    print(f"  平均杠杆: {metrics.avg_leverage}x")
    print()
    print("🎯 分项评分:")
    print(f"  盈利能力: {metrics.profitability_score:.1f}/100")
    print(f"  风险控制: {metrics.risk_score:.1f}/100")
    print(f"  稳定性: {metrics.consistency_score:.1f}/100")
    print(f"  活跃度: {metrics.activity_score:.1f}/100")


def example_from_file():
    """
    从文件加载地址进行筛选
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
    qualified = screener.screen_traders(addresses, progress_callback)
    print()
    screener.print_summary(qualified)
    
    # 保存结果
    screener.save_results(qualified)


def main():
    """主函数 - 运行所有示例"""
    print("=" * 60)
    print("Hyperliquid 优质交易者筛选器 - 使用示例")
    print("=" * 60)
    
    print("\n选择要运行的示例:")
    print("1. 基础筛选")
    print("2. 自定义配置筛选")
    print("3. 批量筛选")
    print("4. 分析单个交易者")
    print("5. 从文件加载地址")
    print("0. 运行所有示例")

    try:
        choice = input("\n请输入选项 (0-5): ").strip()
    except EOFError:
        choice = "0"

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
    elif choice == "0":
        example_basic_screening()
        example_custom_config()
        example_batch_screening()
        example_analyze_single()
        example_from_file()
    else:
        print("无效选项")


if __name__ == "__main__":
    main()

