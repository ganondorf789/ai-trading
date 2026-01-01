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

预筛选指标：
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
    
    预筛选条件：
    --min-pnl FLOAT           最小总盈亏 (默认: 10000)
    --min-7d-pnl FLOAT        最小近7天盈亏 (默认: 0，不筛选负收益)
    --max-drawdown FLOAT      最大回撤比例 (默认: 0.3，即30%)
    --min-sharpe FLOAT        最小Sharpe比率 (默认: 0.5)
    --min-profit-factor FLOAT 最小盈亏比 (默认: 1.2)
    --min-win-rate FLOAT      最小胜率 (默认: 0.35，即35%)
    --active-days INT         最近N天内有交易 (默认: 7)
    --no-filter               禁用所有预筛选条件
    
    其他选项：
    --refresh                 强制重新分析（忽略已有分析）
    --dry-run                 仅显示要分析的交易员，不实际分析
    --verbose                 显示详细输出
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


# 预筛选条件默认值（专业交易员筛选标准）
DEFAULT_FILTER_CONFIG = {
    'min_pnl': 10000,           # 最小总盈亏 $10,000
    'min_7d_pnl': 0,            # 最小近7天盈亏（0 表示不允许亏损）
    'max_drawdown': 0.25,       # 最大回撤 25%
    'min_sharpe': 1.5,          # 最小 Sharpe 比率
    'min_sortino': 2.5,         # 最小 Sortino 比率（关注下行风险）
    'min_profit_factor': 1.2,   # 最小盈亏比
    'min_win_rate': 0.40,       # 最小胜率 40%
    'max_win_rate': 0.65,       # 最大胜率 65%（避免小赚大亏型）
    'active_days': 7,           # 最近7天内有交易
}


class TraderPreFilter:
    """交易员预筛选器"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化预筛选器

        Args:
            config: 筛选配置
        """
        self.config = {**DEFAULT_FILTER_CONFIG, **(config or {})}

    def filter_traders(
        self,
        traders: List[Dict],
        verbose: bool = False
    ) -> tuple[List[Dict], Dict[str, List[Dict]]]:
        """
        筛选交易员

        Args:
            traders: 交易员列表
            verbose: 是否显示详细信息

        Returns:
            (通过筛选的交易员, 被筛除的交易员分类)
        """
        passed = []
        filtered_out = {
            'low_pnl': [],
            'negative_7d_pnl': [],
            'high_drawdown': [],
            'low_sharpe': [],
            'low_sortino': [],
            'low_profit_factor': [],
            'low_win_rate': [],
            'high_win_rate': [],
            'inactive': [],
        }

        now = pendulum.now(SHANGHAI_TZ)

        for trader in traders:
            address = trader.get('address', 'Unknown')
            reasons = []

            # 1. 总盈亏检查
            total_pnl = trader.get('total_pnl', 0)
            if total_pnl < self.config['min_pnl']:
                reasons.append('low_pnl')
                filtered_out['low_pnl'].append(trader)

            # 2. 近7天盈亏检查
            recent_7d_pnl = trader.get('recent_7d_pnl', 0)
            if recent_7d_pnl < self.config['min_7d_pnl']:
                reasons.append('negative_7d_pnl')
                filtered_out['negative_7d_pnl'].append(trader)

            # 3. 最大回撤检查
            max_drawdown = trader.get('max_drawdown', 0)
            if max_drawdown > self.config['max_drawdown']:
                reasons.append('high_drawdown')
                filtered_out['high_drawdown'].append(trader)

            # 4. Sharpe 比率检查
            sharpe_ratio = trader.get('sharpe_ratio', 0)
            if sharpe_ratio < self.config['min_sharpe']:
                reasons.append('low_sharpe')
                filtered_out['low_sharpe'].append(trader)

            # 5. Sortino 比率检查（下行风险）
            sortino_ratio = trader.get('sortino_ratio', 0)
            if self.config.get('min_sortino', 0) > 0 and sortino_ratio < self.config['min_sortino']:
                reasons.append('low_sortino')
                filtered_out['low_sortino'].append(trader)

            # 7. 盈亏比检查
            profit_factor = trader.get('profit_factor', 0)
            if profit_factor < self.config['min_profit_factor']:
                reasons.append('low_profit_factor')
                filtered_out['low_profit_factor'].append(trader)

            # 8. 胜率检查（最小值）
            win_rate = trader.get('win_rate', 0)
            if win_rate < self.config['min_win_rate']:
                reasons.append('low_win_rate')
                filtered_out['low_win_rate'].append(trader)

            # 9. 胜率检查（最大值）- 避免高胜率低盈亏比的交易员
            max_win_rate = self.config.get('max_win_rate', 1.0)
            if max_win_rate < 1.0 and win_rate > max_win_rate:
                reasons.append('high_win_rate')
                filtered_out['high_win_rate'].append(trader)

            # 10. 活跃度检查
            last_trade_time = trader.get('last_trade_time')
            if last_trade_time and self.config['active_days'] > 0:
                try:
                    if isinstance(last_trade_time, str):
                        last_trade = pendulum.parse(last_trade_time)
                    else:
                        last_trade = last_trade_time
                    days_since_last = (now - last_trade).days
                    if days_since_last > self.config['active_days']:
                        reasons.append('inactive')
                        filtered_out['inactive'].append(trader)
                except Exception:
                    pass  # 解析失败则跳过活跃度检查

            # 如果没有被任何条件筛除，则通过
            if not reasons:
                passed.append(trader)
            elif verbose:
                logger.debug(f"筛除 {address[:10]}...: {', '.join(reasons)}")

        return passed, filtered_out

    def print_filter_summary(
        self,
        total: int,
        passed: int,
        filtered_out: Dict[str, List[Dict]]
    ):
        """打印筛选摘要"""
        print(f"\n📊 预筛选结果:")
        print("-" * 60)
        print(f"  总交易员数: {total}")
        print(f"  通过筛选: {passed} ✅")
        print(f"  被筛除: {total - passed} ❌")
        print("-" * 60)
        print(f"  筛除原因统计:")

        reason_names = {
            'low_pnl': f'总盈亏 < ${self.config["min_pnl"]:,.0f}',
            'negative_7d_pnl': f'近7天盈亏 < ${self.config["min_7d_pnl"]:,.0f}',
            'high_drawdown': f'最大回撤 > {self.config["max_drawdown"]*100:.0f}%',
            'low_sharpe': f'Sharpe比率 < {self.config["min_sharpe"]:.1f}',
            'low_sortino': f'Sortino比率 < {self.config.get("min_sortino", 0):.1f}',
            'low_profit_factor': f'盈亏比 < {self.config["min_profit_factor"]:.1f}',
            'low_win_rate': f'胜率 < {self.config["min_win_rate"]*100:.0f}%',
            'high_win_rate': f'胜率 > {self.config.get("max_win_rate", 1.0)*100:.0f}%（可能小赚大亏）',
            'inactive': f'超过 {self.config["active_days"]} 天未交易',
        }

        for reason, traders in filtered_out.items():
            if traders:
                print(f"    - {reason_names[reason]}: {len(traders)} 人")

        print("-" * 60)


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

    def check_analysis_freshness(
        self,
        address: str,
        max_age_days: int = 7
    ) -> tuple[bool, Optional[Dict], Optional[int]]:
        """
        检查交易员的 AI 分析是否在有效期内

        Args:
            address: 交易员地址
            max_age_days: 分析有效期（天）

        Returns:
            (需要重新分析, 已有分析结果, 距离上次分析的天数)
        """
        existing = self.db.get_trader_ai_analysis(address)

        if not existing:
            return True, None, None

        analyzed_at = existing.get('analyzed_at') or existing.get('updated_at')
        if not analyzed_at:
            return True, existing, None

        try:
            if isinstance(analyzed_at, str):
                last_analyzed = pendulum.parse(analyzed_at)
            else:
                last_analyzed = analyzed_at

            days_since = (pendulum.now(SHANGHAI_TZ) - last_analyzed).days

            if days_since < max_age_days:
                return False, existing, days_since
            else:
                return True, existing, days_since

        except Exception:
            return True, existing, None

    def analyze_single_trader(
        self,
        trader: Dict,
        force_refresh: bool = False,
        max_age_days: int = 7
    ) -> Optional[Dict]:
        """
        分析单个交易员

        Args:
            trader: 交易员数据
            force_refresh: 是否强制重新分析
            max_age_days: 分析有效期（天），在此期间内不重复分析

        Returns:
            分析结果
        """
        address = trader.get('address')

        # 检查是否在有效期内
        if not force_refresh:
            needs_analysis, existing, days_since = self.check_analysis_freshness(
                address, max_age_days
            )

            if not needs_analysis:
                if self.verbose:
                    logger.info(f"跳过 {address[:10]}... (已有分析，{days_since} 天前)")
                return existing

            if existing and days_since is not None:
                logger.info(f"重新分析 {address[:10]}... (上次分析 {days_since} 天前，超过 {max_age_days} 天)")

        try:
            logger.info(f"AI 分析交易员: {address[:10]}...")

            # 使用 AI 分析
            analysis = generate_trader_analysis(trader, provider=self.ai_provider)

            # 添加 AI 提供商信息
            analysis['ai_provider'] = self.ai_provider or 'default'
            analysis['analyzed_at'] = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            # 保存到数据库
            self.db.save_trader_ai_analysis(address, analysis)

            logger.info(f"✅ 分析完成并已保存: {address[:10]}...")

            return analysis

        except Exception as e:
            logger.error(f"分析交易员 {address[:10]}... 失败: {e}")
            return None

    def analyze_all_traders(
        self,
        traders: List[Dict],
        force_refresh: bool = False,
        delay: float = 1.0,
        max_age_days: int = 7,
        one_by_one: bool = False
    ) -> List[Dict]:
        """
        分析所有交易员

        Args:
            traders: 交易员列表
            force_refresh: 是否强制重新分析
            delay: 请求间隔（秒）
            max_age_days: 分析有效期（天）
            one_by_one: 逐个分析模式（分析完一个后询问是否继续）

        Returns:
            分析结果列表
        """
        results = []
        total = len(traders)
        skipped = 0
        analyzed = 0

        for i, trader in enumerate(traders, 1):
            address = trader.get('address')

            # 先检查是否需要分析
            if not force_refresh:
                needs_analysis, existing, days_since = self.check_analysis_freshness(
                    address, max_age_days
                )

                if not needs_analysis:
                    logger.info(f"[{i}/{total}] 跳过 {address[:10]}... ({days_since} 天前已分析)")
                    combined = {**trader, 'ai_analysis': existing}
                    results.append(combined)
                    skipped += 1
                    continue

            # 逐个分析模式：分析前确认
            if one_by_one and analyzed > 0:
                print(f"\n{'='*60}")
                print(f"已完成 {analyzed} 个分析，还剩 {total - i + 1} 个待分析")
                try:
                    user_input = input("继续分析下一个? (y/n/q): ").strip().lower()
                    if user_input in ('n', 'q', 'quit', 'exit'):
                        logger.info("用户中断分析")
                        break
                except KeyboardInterrupt:
                    logger.info("\n用户中断分析")
                    break

            logger.info(f"[{i}/{total}] 分析: {address[:10]}...")

            analysis = self.analyze_single_trader(trader, force_refresh, max_age_days)
            if analysis:
                # 合并交易员数据和分析结果
                combined = {**trader, 'ai_analysis': analysis}
                results.append(combined)
                analyzed += 1

                # 逐个分析模式：显示分析结果摘要
                if one_by_one:
                    self._print_analysis_summary(trader, analysis)

            # 请求间隔
            if i < total and not one_by_one:
                time.sleep(delay)

        logger.info(f"分析完成: 新分析 {analyzed} 个，跳过 {skipped} 个（有效期内），共 {len(results)} 个结果")
        return results

    def _print_analysis_summary(self, trader: Dict, analysis: Dict):
        """打印单个分析结果摘要"""
        print("\n" + "-" * 60)
        print(f"📊 交易员: {trader.get('address')[:10]}...{trader.get('address')[-6:]}")
        print(f"   评分: {trader.get('overall_score', 0):.1f} | "
              f"胜率: {trader.get('win_rate', 0)*100:.1f}% | "
              f"PnL: ${trader.get('total_pnl', 0):,.0f}")
        print("-" * 60)

        if analysis.get('summary'):
            print(f"📝 综合评价:\n   {analysis['summary'][:200]}...")

        if analysis.get('copy_trading_advice'):
            print(f"\n💡 跟单建议:\n   {analysis['copy_trading_advice'][:200]}...")

        print("-" * 60)

    def compare_in_groups(
        self,
        traders: List[Dict],
        group_size: int = 6,
        top_per_group: int = 2,
        delay: float = 1.0
    ) -> tuple[List[Dict], Dict[str, Any]]:
        """
        分组对比：将交易员分组比较，每组选出前N名进入决赛

        Args:
            traders: 交易员列表
            group_size: 每组人数
            top_per_group: 每组晋级人数
            delay: 请求间隔

        Returns:
            (决赛交易员列表, 分组对比报告)
        """
        import math

        total = len(traders)

        if total <= group_size:
            # 人数少，直接进入决赛
            logger.info(f"交易员数量 ({total}) <= 分组大小 ({group_size})，直接进入决赛")
            return traders, {'groups': [], 'direct_final': True}

        # 分组
        num_groups = math.ceil(total / group_size)
        groups = []
        for i in range(num_groups):
            start = i * group_size
            end = min(start + group_size, total)
            groups.append(traders[start:end])

        logger.info(f"🏆 分组对比: {total} 人分为 {num_groups} 组，每组选 {top_per_group} 人晋级")

        finalists = []
        group_reports = []

        for i, group in enumerate(groups, 1):
            print(f"\n{'='*60}")
            print(f"🔍 第 {i}/{num_groups} 组对比 ({len(group)} 人)")
            print("-" * 60)

            # 显示本组交易员
            for j, t in enumerate(group, 1):
                addr = f"{t['address'][:6]}...{t['address'][-4:]}"
                print(f"  {j}. {addr} | 评分: {t.get('overall_score', 0):.1f} | "
                      f"PnL: ${t.get('total_pnl', 0):,.0f}")

            # AI 对比本组
            logger.info(f"AI 分析第 {i} 组...")
            group_result = self._compare_group(group, i, num_groups, top_per_group)

            if group_result:
                # 添加晋级者
                winners = group_result.get('winners', [])
                finalists.extend(winners)

                group_reports.append({
                    'group_num': i,
                    'total_in_group': len(group),
                    'winners': [w.get('address') for w in winners],
                    'analysis': group_result.get('analysis', '')
                })

                # 打印本组结果
                print(f"\n✅ 第 {i} 组晋级者:")
                for w in winners:
                    addr = f"{w['address'][:6]}...{w['address'][-4:]}"
                    print(f"   🏅 {addr} | 评分: {w.get('overall_score', 0):.1f}")

            # 请求间隔
            if i < num_groups:
                time.sleep(delay)

        logger.info(f"🎯 分组对比完成，共 {len(finalists)} 人进入决赛")

        return finalists, {
            'total_traders': total,
            'num_groups': num_groups,
            'group_size': group_size,
            'top_per_group': top_per_group,
            'groups': group_reports
        }

    def _compare_group(
        self,
        group: List[Dict],
        group_num: int,
        total_groups: int,
        top_n: int
    ) -> Optional[Dict]:
        """
        对比单个分组，选出前 N 名

        Args:
            group: 分组交易员列表
            group_num: 当前组号
            total_groups: 总组数
            top_n: 选出前 N 名

        Returns:
            {winners: [...], analysis: "..."}
        """
        if len(group) <= top_n:
            return {'winners': group, 'analysis': '人数不足，全部晋级'}

        # 构建分组对比提示词
        prompt = self._build_group_comparison_prompt(group, group_num, total_groups, top_n)

        try:
            # AI 对比
            result = self.ai_client.generate(
                prompt,
                temperature=0.7,
                max_tokens=1500
            )

            # 解析结果，选出前 N 名
            winners = self._parse_group_winners(group, result, top_n)

            return {
                'winners': winners,
                'analysis': result
            }

        except Exception as e:
            logger.error(f"分组对比失败: {e}")
            # 失败时按评分排序选取
            sorted_group = sorted(group, key=lambda x: x.get('overall_score', 0), reverse=True)
            return {
                'winners': sorted_group[:top_n],
                'analysis': f'AI分析失败，按评分排序: {e}'
            }

    def _build_group_comparison_prompt(
        self,
        group: List[Dict],
        group_num: int,
        total_groups: int,
        top_n: int
    ) -> str:
        """构建分组对比提示词"""
        traders_info = []

        for i, t in enumerate(group, 1):
            info = f"""
【交易员 {i}】{t.get('address')}
- 综合评分: {t.get('overall_score', 0):.1f}/100
- 胜率: {t.get('win_rate', 0) * 100:.1f}%
- 盈亏比: {t.get('profit_factor', 0):.2f}
- 总盈亏: ${t.get('total_pnl', 0):,.0f}
- 近7天盈亏: ${t.get('recent_7d_pnl', 0):,.0f}
- 最大回撤: {t.get('max_drawdown', 0) * 100:.1f}%
- Sharpe: {t.get('sharpe_ratio', 0):.2f}
- Sortino: {t.get('sortino_ratio', 0):.2f}
- 活跃天数: {t.get('active_days', 0)}
"""
            traders_info.append(info)

        prompt = f"""
你是专业的加密货币交易分析师。这是第 {group_num}/{total_groups} 组对比。

请从以下 {len(group)} 位交易员中选出最优秀的 {top_n} 位进入决赛。

{''.join(traders_info)}

选择标准：
1. 风险调整收益（Sharpe/Sortino 比率）
2. 盈利稳定性（盈亏比、胜率在合理范围）
3. 风险控制（最大回撤）
4. 近期表现（近7天盈亏）

请输出：
## 晋级名单
按推荐顺序列出 {top_n} 位晋级者的地址（完整地址），并简述理由。

格式：
1. 0x... - 理由
2. 0x... - 理由

## 淘汰原因
简述其他交易员未晋级的主要原因。
"""
        return prompt

    def _parse_group_winners(
        self,
        group: List[Dict],
        ai_result: str,
        top_n: int
    ) -> List[Dict]:
        """从 AI 结果中解析晋级者"""
        winners = []
        group_addresses = {t['address']: t for t in group}

        # 尝试从结果中提取地址
        import re
        # 匹配以太坊地址
        addresses_found = re.findall(r'0x[a-fA-F0-9]{40}', ai_result)

        for addr in addresses_found:
            if addr in group_addresses and group_addresses[addr] not in winners:
                winners.append(group_addresses[addr])
                if len(winners) >= top_n:
                    break

        # 如果没找到足够的地址，按评分补充
        if len(winners) < top_n:
            sorted_group = sorted(group, key=lambda x: x.get('overall_score', 0), reverse=True)
            for t in sorted_group:
                if t not in winners:
                    winners.append(t)
                    if len(winners) >= top_n:
                        break

        return winners

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
    filter_group = parser.add_argument_group('预筛选条件')
    filter_group.add_argument(
        '--min-pnl',
        type=float,
        default=DEFAULT_FILTER_CONFIG['min_pnl'],
        help=f'最小总盈亏 (默认: {DEFAULT_FILTER_CONFIG["min_pnl"]:,.0f})'
    )
    filter_group.add_argument(
        '--min-7d-pnl',
        type=float,
        default=DEFAULT_FILTER_CONFIG['min_7d_pnl'],
        help=f'最小近7天盈亏 (默认: {DEFAULT_FILTER_CONFIG["min_7d_pnl"]:,.0f})'
    )
    filter_group.add_argument(
        '--max-drawdown',
        type=float,
        default=DEFAULT_FILTER_CONFIG['max_drawdown'],
        help=f'最大回撤比例 (默认: {DEFAULT_FILTER_CONFIG["max_drawdown"]})'
    )
    filter_group.add_argument(
        '--min-sharpe',
        type=float,
        default=DEFAULT_FILTER_CONFIG['min_sharpe'],
        help=f'最小Sharpe比率 (默认: {DEFAULT_FILTER_CONFIG["min_sharpe"]})'
    )
    filter_group.add_argument(
        '--min-sortino',
        type=float,
        default=DEFAULT_FILTER_CONFIG['min_sortino'],
        help=f'最小Sortino比率 (默认: {DEFAULT_FILTER_CONFIG["min_sortino"]})'
    )
    filter_group.add_argument(
        '--min-profit-factor',
        type=float,
        default=DEFAULT_FILTER_CONFIG['min_profit_factor'],
        help=f'最小盈亏比 (默认: {DEFAULT_FILTER_CONFIG["min_profit_factor"]})'
    )
    filter_group.add_argument(
        '--min-win-rate',
        type=float,
        default=DEFAULT_FILTER_CONFIG['min_win_rate'],
        help=f'最小胜率 (默认: {DEFAULT_FILTER_CONFIG["min_win_rate"]})'
    )
    filter_group.add_argument(
        '--max-win-rate',
        type=float,
        default=DEFAULT_FILTER_CONFIG['max_win_rate'],
        help=f'最大胜率 (默认: {DEFAULT_FILTER_CONFIG["max_win_rate"]}，避免小赚大亏型)'
    )
    filter_group.add_argument(
        '--active-days',
        type=int,
        default=DEFAULT_FILTER_CONFIG['active_days'],
        help=f'最近N天内有交易 (默认: {DEFAULT_FILTER_CONFIG["active_days"]})'
    )
    filter_group.add_argument(
        '--no-filter',
        action='store_true',
        help='禁用所有预筛选条件'
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
    print(f"📋 基本配置:")
    print(f"   - 筛选评级: {args.rating}")
    print(f"   - 分析数量: {args.top or '全部'}")
    print(f"   - AI 提供商: {args.provider or '自动选择'}")
    print(f"   - 输出文件: {args.output}")

    print(f"\n📋 分组对比配置:")
    print(f"   - 每组人数: {args.group_size}")
    print(f"   - 每组晋级: {args.top_per_group}")
    print(f"   - 跳过分组: {'是' if args.skip_group_compare else '否'}")
    print(f"   - 跳过决赛: {'是' if args.skip_final else '否'}")

    if not args.no_filter:
        print(f"\n📋 预筛选条件（专业级标准）:")
        print(f"   - 最小总盈亏: ${args.min_pnl:,.0f}")
        print(f"   - 最小近7天盈亏: ${args.min_7d_pnl:,.0f}")
        print(f"   - 最大回撤: {args.max_drawdown*100:.0f}%")
        print(f"   - 最小Sharpe比率: {args.min_sharpe:.1f}")
        print(f"   - 最小Sortino比率: {args.min_sortino:.1f}")
        print(f"   - 最小盈亏比: {args.min_profit_factor:.1f}")
        print(f"   - 胜率范围: {args.min_win_rate*100:.0f}% - {args.max_win_rate*100:.0f}%")
        print(f"   - 最近活跃天数: {args.active_days} 天")
    else:
        print(f"\n📋 预筛选: 已禁用")

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
        traders = analyzer.get_traders_by_rating(args.rating, None)  # 先获取全部

        if not traders:
            logger.warning(f"未找到 {args.rating} 级交易员")
            return

        print(f"\n📊 找到 {len(traders)} 个 {args.rating} 级交易员:")
        print("-" * 120)
        print(f"  {'#':>2}  {'地址':<14} {'评分':>5} {'胜率':>6} {'PnL':>12} {'7D PnL':>10} {'DD':>6} {'Sharpe':>7} {'Sortino':>7}")
        print("-" * 120)
        for i, t in enumerate(traders, 1):
            addr = f"{t['address'][:6]}...{t['address'][-4:]}"
            pnl = f"${t.get('total_pnl', 0):,.0f}"
            pnl_7d = f"${t.get('recent_7d_pnl', 0):,.0f}"
            drawdown = f"{t.get('max_drawdown', 0)*100:.1f}%"
            sharpe = f"{t.get('sharpe_ratio', 0):.2f}"
            sortino = f"{t.get('sortino_ratio', 0):.2f}"
            print(f"  {i:>2}. {addr} {t.get('overall_score', 0):>5.1f} "
                  f"{t.get('win_rate', 0)*100:>5.1f}% {pnl:>12} "
                  f"{pnl_7d:>10} {drawdown:>6} {sharpe:>7} {sortino:>7}")
        print("-" * 120)

        # 预筛选
        if not args.no_filter:
            filter_config = {
                'min_pnl': args.min_pnl,
                'min_7d_pnl': args.min_7d_pnl,
                'max_drawdown': args.max_drawdown,
                'min_sharpe': args.min_sharpe,
                'min_sortino': args.min_sortino,
                'min_profit_factor': args.min_profit_factor,
                'min_win_rate': args.min_win_rate,
                'max_win_rate': args.max_win_rate,
                'active_days': args.active_days,
            }
            pre_filter = TraderPreFilter(filter_config)
            traders, filtered_out = pre_filter.filter_traders(traders, args.verbose)

            # 打印筛选摘要
            pre_filter.print_filter_summary(
                total=len(traders) + sum(len(v) for v in filtered_out.values()),
                passed=len(traders),
                filtered_out=filtered_out
            )

            if not traders:
                logger.warning("所有交易员都被预筛选条件筛除")
                print("\n💡 建议: 可以尝试放宽筛选条件，例如:")
                print("   --min-pnl 5000 --max-drawdown 0.4 --min-sharpe 0.3")
                return

        # 限制分析数量
        if args.top and args.top > 0 and len(traders) > args.top:
            traders = traders[:args.top]
            print(f"\n📌 限制分析数量为前 {args.top} 名")

        # 打印最终待分析列表
        print(f"\n✅ 最终待分析交易员: {len(traders)} 个")
        print("-" * 80)
        for i, t in enumerate(traders, 1):
            addr = f"{t['address'][:6]}...{t['address'][-4:]}"
            pnl = f"${t.get('total_pnl', 0):,.0f}"
            print(f"  {i}. {addr} | 评分: {t.get('overall_score', 0):.1f} | PnL: {pnl}")
        print("-" * 80)

        # Dry run 模式
        if args.dry_run:
            print("\n⚠️  Dry-run 模式，不执行实际分析")
            print(f"\n💡 预估分组情况:")
            import math
            num_groups = math.ceil(len(traders) / args.group_size)
            finalists = min(len(traders), num_groups * args.top_per_group)
            print(f"   - 总人数: {len(traders)}")
            print(f"   - 分组数: {num_groups}")
            print(f"   - 每组晋级: {args.top_per_group}")
            print(f"   - 预计决赛人数: {finalists}")
            print(f"   - 预计 AI 调用次数: {num_groups + 1}")
            return

        # ========== 分组对比流程 ==========
        group_report = {}
        finalists = traders

        # Step 1: 分组对比（如果人数较多）
        if not args.skip_group_compare and len(traders) > args.group_size:
            print(f"\n🏆 开始分组对比...")
            print(f"   每组 {args.group_size} 人，每组选 {args.top_per_group} 人晋级")

            finalists, group_report = analyzer.compare_in_groups(
                traders,
                group_size=args.group_size,
                top_per_group=args.top_per_group,
                delay=args.delay
            )

            if not finalists:
                logger.warning("分组对比后没有晋级者")
                return

            print(f"\n🎯 分组对比完成!")
            print(f"   晋级决赛: {len(finalists)} 人")
            print("-" * 60)
            for i, f in enumerate(finalists, 1):
                addr = f"{f['address'][:6]}...{f['address'][-4:]}"
                print(f"   {i}. {addr} | 评分: {f.get('overall_score', 0):.1f} | "
                      f"PnL: ${f.get('total_pnl', 0):,.0f}")
            print("-" * 60)
        else:
            if args.skip_group_compare:
                print("\n⏩ 跳过分组对比，直接进入决赛...")
            else:
                print(f"\n📌 人数 ({len(traders)}) <= 分组大小 ({args.group_size})，直接进入决赛...")

        # Step 2: 决赛（综合排名）
        if args.skip_final:
            print("\n✅ 分组对比完成，跳过决赛!")
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
                print(f"📄 分组对比结果已保存至: {args.output}")
            return

        print(f"\n🏁 开始决赛（综合排名）...")
        print(f"   参与决赛: {len(finalists)} 人")

        # 为决赛选手添加空的 ai_analysis（因为使用分组对比，不需要单独分析）
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

