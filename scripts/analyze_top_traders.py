#!/usr/bin/env python
"""
AI 分析顶级交易员脚本

功能：
1. 从数据库获取所有 S 级交易员
2. 通过多维度指标预筛选，减少 AI 分析数量
3. 使用 AI 对筛选后的交易员进行深度分析
4. 综合比较所有顶尖交易员
5. 找出最优秀的交易员并给出推荐排名
6. 生成综合分析报告

预筛选指标（在 analyzers/pre_filter.py 的 DEFAULT_FILTER_CONFIG 中配置）：
- 近7天盈亏：筛选近期盈利的交易员
- 最大回撤：控制风险，排除高回撤交易员
- Sharpe比率：综合考虑收益和风险
- 盈亏比：确保盈利能力
- 活跃度：排除长期不活跃的交易员
- 总盈亏：确保有足够的盈利历史

用法：
    python scripts/analyze_top_traders.py [选项]

选项：
    --rating RATING           筛选评级 (默认: S，可选: S,A,B,C,D,F)
    --top N                   分析前 N 名交易员 (默认: 全部)
    --provider PROVIDER       AI 提供商 (默认: 自动选择)
    --output FILE             输出报告文件路径 (默认: data/top_traders_analysis.json)
    --no-filter               禁用所有预筛选条件
    --dry-run                 仅显示要分析的交易员，不实际分析
    --verbose                 显示详细输出
    --concurrent              使用并发刷新持仓（更快）
"""
import argparse
import math
import sys
from pathlib import Path

import pendulum
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import TraderDatabase

# 导入重构后的模块
from analyzers import (
    FilterConfig,
    GroupCompareConfig,
    TraderPreFilter,
    TopTradersAnalyzer,
    DEFAULT_FILTER_CONFIG,
)

# 上海时区
SHANGHAI_TZ = "Asia/Shanghai"


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='AI 分析顶级交易员并生成推荐排名',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    # 基本选项
    parser.add_argument(
        '--rating',
        type=str,
        default='S',
        choices=['S', 'A', 'B', 'C', 'D', 'F'],
        help='筛选评级 (默认: S)'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=None,
        help='分析前 N 名交易员 (默认: 全部)'
    )
    parser.add_argument(
        '--provider',
        type=str,
        default=None,
        choices=['zhipu', 'qwen', 'deepseek', 'openrouter'],
        help='AI 提供商 (默认: 自动选择)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/top_traders_analysis.json',
        help='输出报告文件路径 (默认: data/top_traders_analysis.json)'
    )

    # 预筛选条件
    parser.add_argument(
        '--no-filter',
        action='store_true',
        help='禁用所有预筛选条件（筛选参数在 DEFAULT_FILTER_CONFIG 中配置）'
    )

    # 分组对比选项
    group_compare = parser.add_argument_group('分组对比选项')
    group_compare.add_argument(
        '--group-size',
        type=int,
        default=6,
        help='每组人数 (默认: 6)'
    )
    group_compare.add_argument(
        '--top-per-group',
        type=int,
        default=2,
        help='每组晋级人数 (默认: 2)'
    )
    group_compare.add_argument(
        '--final-size',
        type=int,
        default=6,
        help='决赛最大人数，超过则继续淘汰 (默认: 6)'
    )
    group_compare.add_argument(
        '--skip-group-compare',
        action='store_true',
        help='跳过分组对比，直接进行决赛（适用于人数较少时）'
    )
    group_compare.add_argument(
        '--skip-final',
        action='store_true',
        help='只进行分组对比，跳过决赛'
    )

    # 其他选项
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅显示要分析的交易员，不实际分析'
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='显示详细输出'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='API 请求间隔（秒，默认: 1.0）'
    )
    parser.add_argument(
        '--concurrent',
        action='store_true',
        help='使用并发刷新持仓（更快，默认: 否）'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='并发刷新的最大线程数（默认: 5）'
    )

    return parser.parse_args()


def print_traders_list(traders: list, title: str = "交易员列表") -> None:
    """打印交易员列表"""
    logger.info(f"{title}:")
    logger.info("-" * 100)
    logger.info(f"  {'#':>2}  {'地址':<14} {'评分':>5} {'胜率':>6} {'PnL':>12} {'7D PnL':>10} {'DD':>6} {'Sharpe':>7} {'Sortino':>7}")
    logger.info("-" * 100)

    for i, t in enumerate(traders, 1):
        addr = f"{t['address'][:6]}...{t['address'][-4:]}"
        pnl = f"${t.get('total_pnl', 0):,.0f}"
        pnl_7d = f"${t.get('recent_7d_pnl', 0):,.0f}"
        drawdown = f"{t.get('max_drawdown', 0)*100:.1f}%"
        sharpe = f"{t.get('sharpe_ratio', 0):.2f}"
        sortino = f"{t.get('sortino_ratio', 0):.2f}"
        logger.info(f"  {i:>2}. {addr} {t.get('overall_score', 0):>5.1f} "
              f"{t.get('win_rate', 0)*100:>5.1f}% {pnl:>12} "
              f"{pnl_7d:>10} {drawdown:>6} {sharpe:>7} {sortino:>7}")

    logger.info("-" * 100)


def estimate_ai_calls(num_traders: int, group_size: int, top_per_group: int, final_size: int) -> dict:
    """预估 AI 调用次数"""
    current = num_traders
    round_num = 0
    total_ai_calls = 0
    rounds_detail = []

    while current > final_size:
        round_num += 1
        num_groups = math.ceil(current / group_size)
        next_round = num_groups * top_per_group
        total_ai_calls += num_groups
        rounds_detail.append({
            'round': round_num,
            'input': current,
            'groups': num_groups,
            'output': next_round
        })
        current = next_round

    total_ai_calls += 1  # 决赛

    return {
        'total_rounds': round_num,
        'total_ai_calls': total_ai_calls,
        'final_count': current,
        'rounds': rounds_detail
    }


def main():
    args = parse_args()

    # 配置日志
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
        level="DEBUG" if args.verbose else "INFO",
        colorize=True
    )

    logger.info("=" * 60)
    logger.info("S 级顶尖交易员 AI 分析工具")
    logger.info("=" * 60)
    logger.info(f"基本配置:")
    logger.info(f"  - 筛选评级: {args.rating}")
    logger.info(f"  - 分析数量: {args.top or '全部'}")
    logger.info(f"  - AI 提供商: {args.provider or '自动选择'}")
    logger.info(f"  - 输出文件: {args.output}")
    logger.info(f"  - 并发刷新: {'是' if args.concurrent else '否'}")

    logger.info(f"分组对比配置:")
    logger.info(f"  - 每组人数: {args.group_size}")
    logger.info(f"  - 每组晋级: {args.top_per_group}")
    logger.info(f"  - 决赛人数: {args.final_size}")
    logger.info(f"  - 跳过分组: {'是' if args.skip_group_compare else '否'}")
    logger.info(f"  - 跳过决赛: {'是' if args.skip_final else '否'}")

    # 构建筛选配置（使用 DEFAULT_FILTER_CONFIG）
    filter_config = None
    if not args.no_filter:
        filter_config = FilterConfig(**DEFAULT_FILTER_CONFIG)
        pre_filter = TraderPreFilter(filter_config)
        pre_filter.print_config()
    else:
        logger.info("预筛选: 已禁用")

    logger.info("-" * 60)

    try:
        # 初始化数据库
        db = TraderDatabase()

        # 初始化分析器
        analyzer = TopTradersAnalyzer(
            db=db,
            ai_provider=args.provider,
            verbose=args.verbose
        )

        # 获取指定评级的交易员
        traders = analyzer.get_traders_by_rating(args.rating, None)

        if not traders:
            logger.warning(f"未找到 {args.rating} 级交易员")
            return

        logger.info(f"找到 {len(traders)} 个 {args.rating} 级交易员:")
        print_traders_list(traders, f"{args.rating} 级交易员")

        # 预筛选
        if not args.no_filter:
            traders, filtered_out = pre_filter.filter_traders(traders, args.verbose)
            pre_filter.print_summary(
                total=len(traders) + sum(len(v) for v in filtered_out.values()),
                passed=len(traders),
                filtered_out=filtered_out
            )

            if not traders:
                logger.warning("所有交易员都被预筛选条件筛除")
                logger.info("建议: 修改 analyzers/pre_filter.py 中的 DEFAULT_FILTER_CONFIG 放宽筛选条件")
                logger.info("   或使用 --no-filter 禁用预筛选")
                return

        # 限制分析数量
        if args.top and args.top > 0 and len(traders) > args.top:
            traders = traders[:args.top]
            logger.info(f"限制分析数量为前 {args.top} 名")

        # 打印最终待分析列表
        logger.info(f"最终待分析交易员: {len(traders)} 个")
        print_traders_list(traders, "待分析交易员")

        # Dry run 模式
        if args.dry_run:
            logger.warning("Dry-run 模式，不执行实际分析")
            estimate = estimate_ai_calls(
                len(traders), args.group_size, args.top_per_group, args.final_size
            )
            logger.info(f"预估淘汰赛情况:")
            for r in estimate['rounds']:
                logger.info(f"   第 {r['round']} 轮: {r['input']} 人 -> {r['groups']} 组 -> {r['output']} 人晋级")
            logger.info(f"   决赛: {estimate['final_count']} 人")
            logger.info(f"   预计 AI 调用次数: {estimate['total_ai_calls']} (淘汰赛 {estimate['total_ai_calls'] - 1} + 决赛 1)")
            return

        # ========== 刷新持仓数据 ==========
        logger.info("刷新所有交易员的持仓数据...")
        if args.concurrent:
            analyzer.refresh_all_positions_concurrent(traders, max_workers=args.max_workers)
        else:
            analyzer.refresh_all_positions(traders, delay=0.2)

        # ========== 分组对比流程 ==========
        group_report = {}
        finalists = traders

        # 构建分组对比配置
        group_config = GroupCompareConfig(
            group_size=args.group_size,
            top_per_group=args.top_per_group,
            final_size=args.final_size,
            delay=args.delay,
        )

        # Step 1: 分组对比（如果人数较多）
        if not args.skip_group_compare and len(traders) > args.final_size:
            logger.info(f"开始分组淘汰赛...")
            logger.info(f"   每组 {args.group_size} 人，每组选 {args.top_per_group} 人，决赛最多 {args.final_size} 人")

            finalists, group_report = analyzer.compare_in_groups(traders, group_config)

            if not finalists:
                logger.warning("分组对比后没有晋级者")
                return

            logger.info(f"淘汰赛完成! 晋级决赛: {len(finalists)} 人")
            print_traders_list(finalists, "决赛选手")
        else:
            if args.skip_group_compare:
                logger.info("跳过分组对比，直接进入决赛...")
            else:
                logger.info(f"人数 ({len(traders)}) <= 决赛人数 ({args.final_size})，直接进入决赛...")

        # Step 2: 决赛（综合排名）
        if args.skip_final:
            logger.info("分组对比完成，跳过决赛!")
            # 保存分组对比结果
            if group_report:
                report = {
                    'generated_at': pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
                    'mode': 'group_compare_only',
                    'group_compare': group_report,
                    'finalists': [
                        {
                            'address': f['address'],
                            'overall_score': f.get('overall_score', 0),
                            'total_pnl': f.get('total_pnl', 0),
                        }
                        for f in finalists
                    ]
                }
                analyzer.save_report(report, args.output)

                # 保存到数据库
                config = {
                    'rating': args.rating,
                    'group_size': args.group_size,
                    'top_per_group': args.top_per_group,
                    'final_size': args.final_size,
                }
                if filter_config:
                    config.update(filter_config.model_dump())
                session_id = analyzer.save_to_database(
                    all_traders=traders,
                    finalists=finalists,
                    group_report=group_report,
                    final_ranking=None,
                    config=config
                )
                logger.info(f"分组对比结果已保存至: {args.output}")
                logger.info(f"数据库会话ID: {session_id}")
            return

        logger.info(f"开始决赛（综合排名）...")
        logger.info(f"   参与决赛: {len(finalists)} 人")

        # 为决赛选手添加空的 ai_analysis
        finalists_with_analysis = [
            {**f, 'ai_analysis': {}}
            for f in finalists
        ]

        # 生成综合排名
        report = analyzer.generate_final_ranking(finalists_with_analysis)

        if 'error' in report:
            logger.error(f"生成报告失败: {report['error']}")
            return

        # 添加分组对比信息
        if group_report:
            report['group_compare'] = group_report

        # 保存报告到文件
        analyzer.save_report(report, args.output)

        # 保存到数据库
        config = {
            'rating': args.rating,
            'group_size': args.group_size,
            'top_per_group': args.top_per_group,
            'final_size': args.final_size,
        }
        if filter_config:
            config.update(filter_config.model_dump())
        session_id = analyzer.save_to_database(
            all_traders=traders,
            finalists=finalists,
            group_report=group_report,
            final_ranking=report.get('comparison_analysis'),
            config=config
        )

        # 打印报告
        analyzer.print_report(report)

        # 打印指标摘要
        metrics = analyzer.get_metrics_summary()
        logger.info(f"分析指标: {metrics}")

        logger.info("分析完成!")
        logger.info(f"完整报告已保存至: {args.output}")
        logger.info(f"数据库会话ID: {session_id}")

    except KeyboardInterrupt:
        logger.warning("用户中断")
    except Exception as e:
        logger.exception(f"发生错误: {e}")
        raise


if __name__ == '__main__':
    main()
