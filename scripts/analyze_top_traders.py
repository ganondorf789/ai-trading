#!/usr/bin/env python
"""
AI 分析顶级交易员脚本

功能：
1. 从数据库获取所有 S 级交易员
2. 使用 AI 对每个交易员进行深度分析
3. 综合比较所有 S 级交易员
4. 找出最优秀的交易员并给出推荐排名
5. 生成综合分析报告

用法：
    python scripts/analyze_top_traders.py [选项]

选项：
    --rating RATING     筛选评级 (默认: S，可选: S,A,B,C,D,F)
    --top N             分析前 N 名交易员 (默认: 全部)
    --provider PROVIDER AI 提供商 (默认: 自动选择，可选: zhipu/qwen/deepseek/openrouter)
    --output FILE       输出报告文件路径 (默认: data/top_traders_analysis.json)
    --refresh           强制重新分析（忽略已有分析）
    --dry-run           仅显示要分析的交易员，不实际分析
    --verbose           显示详细输出
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
import pendulum

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from screener.database import TraderDatabase
from services.ai_analysis import TraderAIAnalyzer, generate_trader_analysis
from clients import get_ai_client

# 上海时区
SHANGHAI_TZ = "Asia/Shanghai"


class TopTradersAnalyzer:
    """顶级交易员分析器"""

    def __init__(
        self,
        db: TraderDatabase,
        ai_provider: Optional[str] = None,
        verbose: bool = False
    ):
        """
        初始化分析器

        Args:
            db: 数据库实例
            ai_provider: AI 提供商
            verbose: 是否显示详细输出
        """
        self.db = db
        self.ai_provider = ai_provider
        self.verbose = verbose

        # 初始化 AI 客户端
        try:
            self.ai_client = get_ai_client(provider=ai_provider)
            logger.info(f"AI 客户端初始化成功，提供商: {ai_provider or '默认'}")
        except Exception as e:
            logger.error(f"AI 客户端初始化失败: {e}")
            raise

    def get_traders_by_rating(
        self,
        rating: str = 'S',
        top_n: Optional[int] = None
    ) -> List[Dict]:
        """
        获取指定评级的交易员

        Args:
            rating: 评级 (S/A/B/C/D/F)
            top_n: 获取前 N 名

        Returns:
            交易员列表
        """
        traders = self.db.get_traders_by_rating(rating)

        # 按评分排序
        traders.sort(key=lambda x: x.get('overall_score', 0), reverse=True)

        if top_n and top_n > 0:
            traders = traders[:top_n]

        logger.info(f"获取到 {len(traders)} 个 {rating} 级交易员")
        return traders

    def analyze_single_trader(
        self,
        trader: Dict,
        force_refresh: bool = False
    ) -> Optional[Dict]:
        """
        分析单个交易员

        Args:
            trader: 交易员数据
            force_refresh: 是否强制重新分析

        Returns:
            分析结果
        """
        address = trader.get('address')

        # 检查是否已有分析
        if not force_refresh:
            existing = self.db.get_trader_ai_analysis(address)
            if existing:
                if self.verbose:
                    logger.info(f"使用已有分析: {address[:10]}...")
                return existing

        try:
            logger.info(f"AI 分析交易员: {address[:10]}...")

            # 使用 AI 分析
            analysis = generate_trader_analysis(trader, provider=self.ai_provider)

            # 添加 AI 提供商信息
            analysis['ai_provider'] = self.ai_provider or 'default'
            analysis['analyzed_at'] = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            # 保存到数据库
            self.db.save_trader_ai_analysis(address, analysis)

            return analysis

        except Exception as e:
            logger.error(f"分析交易员 {address[:10]}... 失败: {e}")
            return None

    def analyze_all_traders(
        self,
        traders: List[Dict],
        force_refresh: bool = False,
        delay: float = 1.0
    ) -> List[Dict]:
        """
        分析所有交易员

        Args:
            traders: 交易员列表
            force_refresh: 是否强制重新分析
            delay: 请求间隔（秒）

        Returns:
            分析结果列表
        """
        results = []
        total = len(traders)

        for i, trader in enumerate(traders, 1):
            address = trader.get('address')
            logger.info(f"[{i}/{total}] 分析: {address[:10]}...")

            analysis = self.analyze_single_trader(trader, force_refresh)
            if analysis:
                # 合并交易员数据和分析结果
                combined = {**trader, 'ai_analysis': analysis}
                results.append(combined)

            # 请求间隔
            if i < total:
                time.sleep(delay)

        logger.info(f"完成 {len(results)}/{total} 个交易员分析")
        return results

    def generate_comparison_prompt(self, traders_with_analysis: List[Dict]) -> str:
        """
        生成综合比较提示词

        Args:
            traders_with_analysis: 带分析结果的交易员列表

        Returns:
            提示词
        """
        traders_summary = []

        for i, t in enumerate(traders_with_analysis, 1):
            analysis = t.get('ai_analysis', {})
            summary = f"""
【交易员 {i}】
- 地址: {t.get('address')[:10]}...{t.get('address')[-6:]}
- 综合评分: {t.get('overall_score', 0):.1f}/100
- 胜率: {t.get('win_rate', 0) * 100:.1f}%
- 盈亏比: {t.get('profit_factor', 0):.2f}
- 总盈亏: ${t.get('total_pnl', 0):,.2f}
- 最大回撤: {t.get('max_drawdown', 0) * 100:.1f}%
- Sharpe比率: {t.get('sharpe_ratio', 0):.2f}
- 活跃天数: {t.get('active_days', 0)}
- 常用品种: {t.get('favorite_symbol', '-')}
- 近7天盈亏: ${t.get('recent_7d_pnl', 0):,.2f}
- AI评价摘要: {analysis.get('summary', '无')[:200]}
"""
            traders_summary.append(summary)

        prompt = f"""
作为专业的加密货币投资顾问，请综合分析以下 {len(traders_with_analysis)} 位 S 级顶尖交易员，并给出最终推荐排名。

{''.join(traders_summary)}

请按以下格式输出：

## 一、综合排名

根据以下维度综合评估后，给出最终推荐排名（从最优到次优）：
1. 盈利能力（总盈亏、ROI）
2. 风险控制（最大回撤、Sharpe比率）
3. 稳定性（胜率、盈亏比、连续表现）
4. 活跃度（近期表现、交易频率）
5. 跟单适合度（交易风格、杠杆使用）

列出排名及简要理由。

## 二、最佳跟单推荐

推荐 1-3 位最适合跟单的交易员，详细说明：
- 为什么推荐
- 适合什么类型的跟单者
- 建议跟单比例
- 风险提示

## 三、交易风格分类

将这些交易员按交易风格分类：
- 稳健型：低回撤、稳定收益
- 激进型：高收益、高风险
- 均衡型：收益和风险平衡

## 四、特别警示

指出任何需要特别注意的风险点或问题交易员。

## 五、总结建议

给出整体投资建议和注意事项。

要求：
1. 分析要专业、客观、基于数据
2. 排名要有明确依据
3. 推荐要考虑不同投资者需求
4. 风险提示要明确具体
"""
        return prompt

    def generate_final_ranking(
        self,
        traders_with_analysis: List[Dict]
    ) -> Dict[str, Any]:
        """
        生成最终综合排名报告

        Args:
            traders_with_analysis: 带分析结果的交易员列表

        Returns:
            综合排名报告
        """
        if not traders_with_analysis:
            return {'error': '没有可分析的交易员'}

        logger.info(f"生成 {len(traders_with_analysis)} 位交易员的综合排名...")

        # 构建比较提示词
        prompt = self.generate_comparison_prompt(traders_with_analysis)

        try:
            # 调用 AI 生成综合排名
            comparison_result = self.ai_client.generate(
                prompt,
                temperature=0.7,
                max_tokens=3000
            )

            # 构建报告
            report = {
                'generated_at': pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
                'ai_provider': self.ai_provider or 'default',
                'total_traders_analyzed': len(traders_with_analysis),
                'comparison_analysis': comparison_result,
                'traders': [
                    {
                        'rank': i + 1,
                        'address': t.get('address'),
                        'overall_score': t.get('overall_score', 0),
                        'win_rate': t.get('win_rate', 0),
                        'profit_factor': t.get('profit_factor', 0),
                        'total_pnl': t.get('total_pnl', 0),
                        'max_drawdown': t.get('max_drawdown', 0),
                        'sharpe_ratio': t.get('sharpe_ratio', 0),
                        'recent_7d_pnl': t.get('recent_7d_pnl', 0),
                        'ai_summary': t.get('ai_analysis', {}).get('summary', '')
                    }
                    for i, t in enumerate(traders_with_analysis)
                ]
            }

            logger.info("综合排名报告生成完成")
            return report

        except Exception as e:
            logger.error(f"生成综合排名失败: {e}")
            return {'error': str(e)}

    def save_report(self, report: Dict, filepath: str):
        """
        保存报告

        Args:
            report: 报告数据
            filepath: 输出文件路径
        """
        # 确保目录存在
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"报告已保存至: {filepath}")

    def print_report(self, report: Dict):
        """
        打印报告摘要

        Args:
            report: 报告数据
        """
        print("\n" + "=" * 100)
        print("🏆 S 级顶尖交易员综合分析报告")
        print("=" * 100)
        print(f"📅 生成时间: {report.get('generated_at', 'N/A')}")
        print(f"🤖 AI 提供商: {report.get('ai_provider', 'N/A')}")
        print(f"👥 分析交易员数量: {report.get('total_traders_analyzed', 0)}")
        print("-" * 100)

        # 打印交易员列表
        print("\n📊 交易员评分排名:")
        print("-" * 100)
        print(f"{'排名':<4} {'地址':<18} {'评分':<8} {'胜率':<8} {'盈亏比':<8} {'总PnL':<14} {'回撤':<8} {'Sharpe':<8}")
        print("-" * 100)

        for t in report.get('traders', []):
            addr = f"{t['address'][:6]}...{t['address'][-4:]}"
            pnl_str = f"${t['total_pnl']:,.0f}"
            print(f"{t['rank']:<4} {addr:<18} {t['overall_score']:>6.1f} "
                  f"{t['win_rate']*100:>6.1f}% {t['profit_factor']:>7.2f} "
                  f"{pnl_str:>13} {t['max_drawdown']*100:>6.1f}% {t['sharpe_ratio']:>7.2f}")

        print("-" * 100)

        # 打印 AI 综合分析
        if report.get('comparison_analysis'):
            print("\n🤖 AI 综合分析:")
            print("-" * 100)
            print(report['comparison_analysis'])

        print("\n" + "=" * 100)


def main():
    parser = argparse.ArgumentParser(
        description='AI 分析顶级交易员并生成推荐排名',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

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
    parser.add_argument(
        '--refresh',
        action='store_true',
        help='强制重新分析（忽略已有分析）'
    )
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
        '--skip-individual',
        action='store_true',
        help='跳过单个交易员分析，直接进行综合比较'
    )

    args = parser.parse_args()

    # 配置日志
    if args.verbose:
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=''),
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
            level="DEBUG"
        )
    else:
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=''),
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
            level="INFO"
        )

    print("\n" + "=" * 80)
    print("🚀 S 级顶尖交易员 AI 分析工具")
    print("=" * 80)
    print(f"📋 配置:")
    print(f"   - 筛选评级: {args.rating}")
    print(f"   - 分析数量: {args.top or '全部'}")
    print(f"   - AI 提供商: {args.provider or '自动选择'}")
    print(f"   - 输出文件: {args.output}")
    print(f"   - 强制刷新: {'是' if args.refresh else '否'}")
    print("-" * 80)

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
        traders = analyzer.get_traders_by_rating(args.rating, args.top)

        if not traders:
            logger.warning(f"未找到 {args.rating} 级交易员")
            return

        print(f"\n📊 找到 {len(traders)} 个 {args.rating} 级交易员:")
        print("-" * 80)
        for i, t in enumerate(traders, 1):
            addr = f"{t['address'][:6]}...{t['address'][-4:]}"
            pnl = f"${t.get('total_pnl', 0):,.0f}"
            print(f"  {i}. {addr} | 评分: {t.get('overall_score', 0):.1f} | "
                  f"胜率: {t.get('win_rate', 0)*100:.1f}% | PnL: {pnl}")
        print("-" * 80)

        # Dry run 模式
        if args.dry_run:
            print("\n⚠️  Dry-run 模式，不执行实际分析")
            return

        # 分析每个交易员
        if not args.skip_individual:
            print("\n🔍 开始逐个分析交易员...")
            traders_with_analysis = analyzer.analyze_all_traders(
                traders,
                force_refresh=args.refresh,
                delay=args.delay
            )
        else:
            # 跳过单个分析，使用已有数据
            print("\n⏩ 跳过单个分析，使用已有数据...")
            traders_with_analysis = []
            for t in traders:
                existing = db.get_trader_ai_analysis(t['address'])
                if existing:
                    traders_with_analysis.append({**t, 'ai_analysis': existing})
                else:
                    traders_with_analysis.append({**t, 'ai_analysis': {}})

        if not traders_with_analysis:
            logger.warning("没有成功分析的交易员")
            return

        # 生成综合排名
        print("\n📈 生成综合排名报告...")
        report = analyzer.generate_final_ranking(traders_with_analysis)

        if 'error' in report:
            logger.error(f"生成报告失败: {report['error']}")
            return

        # 保存报告
        analyzer.save_report(report, args.output)

        # 打印报告
        analyzer.print_report(report)

        print("\n✅ 分析完成!")
        print(f"📄 完整报告已保存至: {args.output}")

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        logger.exception(f"发生错误: {e}")
        raise


if __name__ == '__main__':
    main()

