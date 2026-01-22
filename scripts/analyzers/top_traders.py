"""
顶级交易员分析器

提供 AI 分析、分组对比、综合排名等功能
"""
import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pendulum
from loguru import logger

from .models import (
    AnalysisMetrics,
    AnalysisReport,
    GroupCompareConfig,
    GroupCompareResult,
)
from .formatter import TraderInfoFormatter, PromptBuilder
from .utils import (
    retry_on_timeout,
    run_concurrent,
    AnalysisCheckpoint,
    format_duration,
)


# 上海时区
SHANGHAI_TZ = "Asia/Shanghai"


class TopTradersAnalyzer:
    """
    顶级交易员分析器

    提供以下功能：
    - 刷新交易员持仓（支持并发）
    - AI 分析单个交易员
    - 分组对比淘汰赛
    - 生成综合排名报告

    Example:
        from database import TraderDatabase
        from clients import get_ai_client

        db = TraderDatabase()
        analyzer = TopTradersAnalyzer(db, ai_provider='deepseek')

        # 获取 S 级交易员
        traders = analyzer.get_traders_by_rating('S')

        # 并发刷新持仓
        positions_map = analyzer.refresh_all_positions_concurrent(traders)

        # 分组对比
        finalists, report = analyzer.compare_in_groups(traders)

        # 生成最终排名
        final_report = analyzer.generate_final_ranking(finalists)
    """

    def __init__(
        self,
        db: Any,  # TraderDatabase
        ai_provider: Optional[str] = None,
        verbose: bool = False,
        checkpoint_file: Optional[str] = None,
    ):
        """
        初始化分析器

        Args:
            db: 数据库实例
            ai_provider: AI 提供商 (zhipu/qwen/deepseek/openrouter)
            verbose: 是否显示详细输出
            checkpoint_file: 检查点文件路径
        """
        self.db = db
        self.ai_provider = ai_provider
        self.verbose = verbose

        # 初始化 AI 客户端
        try:
            from clients import get_ai_client
            self.ai_client = get_ai_client(provider=ai_provider)
            logger.info(f"AI 客户端初始化成功，提供商: {ai_provider or '默认'}")
        except Exception as e:
            logger.error(f"AI 客户端初始化失败: {e}")
            raise

        # 初始化 Hyperliquid Info 客户端（用于刷新持仓）
        try:
            from hyperliquid.info import Info
            from hyperliquid.utils import constants
            self.hl_info = Info(constants.MAINNET_API_URL, skip_ws=True)
        except Exception as e:
            logger.warning(f"Hyperliquid 客户端初始化失败: {e}")
            self.hl_info = None

        # 格式化器和提示词构建器
        self.formatter = TraderInfoFormatter(show_address_full=True)
        self.prompt_builder = PromptBuilder(self.formatter)

        # 分析指标
        self.metrics = AnalysisMetrics()

        # 检查点（可选）
        self.checkpoint = None
        if checkpoint_file:
            self.checkpoint = AnalysisCheckpoint(checkpoint_file)

        # 缓存
        self._positions_cache: Dict[str, List[Dict]] = {}
        self._coin_stats_cache: Dict[str, List[Dict]] = {}

    # ==================== 数据获取 ====================

    def get_traders_by_rating(
        self,
        rating: str = 'S',
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
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

    def get_trader_coin_stats(
        self,
        address: str,
        top_n: int = 5,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取交易员的币种统计（Top N）

        Args:
            address: 交易员地址
            top_n: 返回前 N 个币种
            use_cache: 是否使用缓存

        Returns:
            币种统计列表
        """
        if use_cache and address in self._coin_stats_cache:
            return self._coin_stats_cache[address][:top_n]

        try:
            summary = self.db.get_fills_summary(address, exclude_user_perps=True)
            by_coin = summary.get('by_coin', [])

            # 按盈亏绝对值排序
            sorted_coins = sorted(
                by_coin,
                key=lambda x: abs(x.get('total_pnl', 0)),
                reverse=True
            )

            self._coin_stats_cache[address] = sorted_coins
            return sorted_coins[:top_n]
        except Exception as e:
            logger.warning(f"获取币种统计失败 {address[:10]}...: {e}")
            return []

    def get_trader_positions(
        self,
        address: str,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        获取交易员的当前持仓

        Args:
            address: 交易员地址
            use_cache: 是否使用缓存

        Returns:
            持仓列表
        """
        if use_cache and address in self._positions_cache:
            return self._positions_cache[address]

        try:
            positions = self.db.get_positions(address)
            self._positions_cache[address] = positions
            return positions
        except Exception as e:
            logger.warning(f"获取持仓失败 {address[:10]}...: {e}")
            return []

    # ==================== 持仓刷新 ====================

    def refresh_trader_positions(self, address: str) -> List[Dict[str, Any]]:
        """
        刷新单个交易员的持仓数据

        Args:
            address: 交易员地址

        Returns:
            持仓列表
        """
        if not self.hl_info:
            logger.warning("Hyperliquid 客户端未初始化")
            return []

        try:
            user_state = self.hl_info.user_state(address)
            asset_positions = user_state.get('assetPositions', [])

            # 保存到数据库
            if asset_positions:
                self.db.save_positions(address, asset_positions)

            # 更新缓存
            self._positions_cache[address] = asset_positions

            return asset_positions
        except Exception as e:
            logger.warning(f"刷新持仓失败 {address[:10]}...: {e}")
            return []

    def refresh_all_positions(
        self,
        traders: List[Dict[str, Any]],
        delay: float = 0.2,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        串行刷新所有交易员的持仓（原始方法，兼容）

        Args:
            traders: 交易员列表
            delay: 请求间隔（秒）

        Returns:
            {address: positions} 映射
        """
        logger.info(f"开始刷新 {len(traders)} 个交易员的持仓...")
        positions_map = {}

        for i, trader in enumerate(traders, 1):
            address = trader.get('address')
            positions = self.refresh_trader_positions(address)
            positions_map[address] = positions

            if self.verbose:
                pos_count = len(positions)
                logger.debug(f"[{i}/{len(traders)}] {address[:10]}... 持仓: {pos_count} 个")

            if i < len(traders):
                time.sleep(delay)

        total_with_positions = sum(1 for p in positions_map.values() if p)
        logger.info(f"持仓刷新完成: {total_with_positions}/{len(traders)} 个交易员有持仓")

        return positions_map

    def refresh_all_positions_concurrent(
        self,
        traders: List[Dict[str, Any]],
        max_workers: int = 5,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        并发刷新所有交易员的持仓

        Args:
            traders: 交易员列表
            max_workers: 最大并发数

        Returns:
            {address: positions} 映射
        """
        logger.info(f"开始并发刷新 {len(traders)} 个交易员的持仓 (并发数: {max_workers})...")

        addresses = [t.get('address') for t in traders]

        results = run_concurrent(
            self.refresh_trader_positions,
            addresses,
            max_workers=max_workers,
            desc="刷新持仓",
            show_progress=True,
        )

        positions_map = {}
        success_count = 0
        for address, positions, error in results:
            if error:
                positions_map[address] = []
            else:
                positions_map[address] = positions or []
                if positions:
                    success_count += 1

        logger.info(f"持仓刷新完成: {success_count}/{len(traders)} 个交易员有持仓")
        return positions_map

    # ==================== AI 分析 ====================

    def analyze_single_trader(
        self,
        trader: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        分析单个交易员

        Args:
            trader: 交易员数据

        Returns:
            分析结果
        """
        from services.ai_analysis import generate_trader_analysis

        address = trader.get('address')
        if not address:
            logger.warning("交易员数据缺少 address 字段")
            return None

        start_time = time.time()

        try:
            logger.info(f"AI 分析交易员: {address[:10]}...")

            # 使用 AI 分析
            analysis = generate_trader_analysis(trader, provider=self.ai_provider)

            # 添加 AI 提供商信息
            analysis['ai_provider'] = self.ai_provider or 'default'
            analysis['analyzed_at'] = pendulum.now(SHANGHAI_TZ).to_iso8601_string()

            # 保存到数据库
            self.db.save_trader_ai_analysis(address, analysis)

            # 记录指标
            duration = time.time() - start_time
            self.metrics.record_analysis(success=True, duration=duration)

            logger.info(f"✅ 分析完成并已保存: {address[:10]}... ({duration:.1f}s)")

            return analysis

        except Exception as e:
            duration = time.time() - start_time
            self.metrics.record_analysis(success=False, duration=duration)
            logger.error(f"分析交易员 {address[:10]}... 失败: {e}")
            return None

    # ==================== 分组对比 ====================

    def compare_in_groups(
        self,
        traders: List[Dict[str, Any]],
        config: Optional[GroupCompareConfig] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        分组对比：将交易员分组比较，多轮淘汰直到人数足够少

        Args:
            traders: 交易员列表
            config: 分组对比配置

        Returns:
            (决赛交易员列表, 分组对比报告)
        """
        config = config or GroupCompareConfig()

        all_rounds = []
        current_traders = traders
        round_num = 0

        while len(current_traders) > config.final_size:
            round_num += 1
            total = len(current_traders)

            # 分组
            num_groups = math.ceil(total / config.group_size)
            groups = []
            for i in range(num_groups):
                start = i * config.group_size
                end = min(start + config.group_size, total)
                groups.append(current_traders[start:end])

            logger.info("=" * 60)
            logger.info(
                f"第 {round_num} 轮淘汰: {total} 人分为 {num_groups} 组，"
                f"每组选 {config.top_per_group} 人晋级"
            )
            logger.info("=" * 60)

            round_finalists = []
            group_reports = []

            for i, group in enumerate(groups, 1):
                logger.info(f"第 {i}/{num_groups} 组对比 ({len(group)} 人)")
                logger.info("-" * 40)

                # 显示本组交易员
                for j, t in enumerate(group, 1):
                    addr = f"{t['address'][:6]}...{t['address'][-4:]}"
                    logger.info(
                        f"  {j}. {addr} | 评分: {t.get('overall_score', 0):.1f} | "
                        f"PnL: ${t.get('total_pnl', 0):,.0f}"
                    )

                # AI 对比本组
                group_result = self._compare_group(
                    group, i, num_groups, config.top_per_group, config
                )

                if group_result:
                    winners = group_result.get('winners', [])
                    round_finalists.extend(winners)

                    group_reports.append({
                        'group_num': i,
                        'total_in_group': len(group),
                        'all_traders': [t.get('address') for t in group],
                        'winners': [w.get('address') for w in winners],
                        'analysis': group_result.get('analysis', '')
                    })

                    logger.info(f"晋级者: {len(winners)} 人")
                    for w in winners:
                        addr = f"{w['address'][:6]}...{w['address'][-4:]}"
                        logger.info(f"   {addr}")

                # 请求间隔
                if i < num_groups:
                    time.sleep(config.delay)

            all_rounds.append({
                'round': round_num,
                'input_count': total,
                'output_count': len(round_finalists),
                'groups': group_reports
            })

            logger.info(f"第 {round_num} 轮完成: {total} -> {len(round_finalists)} 人")
            current_traders = round_finalists

            if not current_traders:
                logger.warning("没有晋级者，淘汰结束")
                break

        logger.info(f"淘汰赛完成，共 {round_num} 轮，最终 {len(current_traders)} 人进入决赛")

        return current_traders, {
            'total_rounds': round_num,
            'initial_count': len(traders),
            'final_count': len(current_traders),
            'rounds': all_rounds
        }

    @retry_on_timeout(max_retries=3, retry_delay=5.0)
    def _ai_compare_group(
        self,
        prompt: str,
        timeout: float = 60.0,
    ) -> str:
        """
        AI 对比（带重试装饰器）

        Args:
            prompt: 提示词
            timeout: 超时时间

        Returns:
            AI 返回结果
        """
        return self.ai_client.generate(prompt, temperature=0.7)

    def _compare_group(
        self,
        group: List[Dict[str, Any]],
        group_num: int,
        total_groups: int,
        top_n: int,
        config: GroupCompareConfig,
    ) -> Optional[Dict[str, Any]]:
        """
        对比单个分组，选出前 N 名

        Args:
            group: 分组交易员列表
            group_num: 当前组号
            total_groups: 总组数
            top_n: 选出前 N 名
            config: 配置

        Returns:
            {winners: [...], analysis: "..."}
        """
        if len(group) <= top_n:
            return {'winners': group, 'analysis': '人数不足，全部晋级'}

        # 获取持仓和币种统计
        positions_map = {}
        coin_stats_map = {}
        for t in group:
            addr = t.get('address')
            positions_map[addr] = self.get_trader_positions(addr)
            coin_stats_map[addr] = self.get_trader_coin_stats(addr, top_n=3)

        # 构建提示词
        prompt = self.prompt_builder.build_group_comparison_prompt(
            group, positions_map, coin_stats_map,
            group_num, total_groups, top_n
        )

        try:
            logger.info(f"AI 对比中...")
            result = self._ai_compare_group(prompt, timeout=config.timeout)

            # 解析结果，选出前 N 名
            winners = self._parse_group_winners(group, result, top_n)

            return {
                'winners': winners,
                'analysis': result
            }

        except Exception as e:
            # 所有重试都失败，按评分排序选取
            logger.error(f"分组对比最终失败: {e}")
            sorted_group = sorted(
                group,
                key=lambda x: x.get('overall_score', 0),
                reverse=True
            )
            return {
                'winners': sorted_group[:top_n],
                'analysis': f'AI分析失败，按评分排序: {e}'
            }

    def _parse_group_winners(
        self,
        group: List[Dict[str, Any]],
        ai_result: str,
        top_n: int,
    ) -> List[Dict[str, Any]]:
        """从 AI 结果中解析晋级者"""
        winners = []
        group_addresses = {t['address'].lower(): t for t in group}

        # 尝试从结果中提取地址（以太坊地址格式）
        addresses_found = re.findall(r'0x[a-fA-F0-9]{40}', ai_result)

        for addr in addresses_found:
            addr_lower = addr.lower()
            if addr_lower in group_addresses and group_addresses[addr_lower] not in winners:
                winners.append(group_addresses[addr_lower])
                if len(winners) >= top_n:
                    break

        # 如果没找到足够的地址，按评分补充
        if len(winners) < top_n:
            sorted_group = sorted(
                group,
                key=lambda x: x.get('overall_score', 0),
                reverse=True
            )
            for t in sorted_group:
                if t not in winners:
                    winners.append(t)
                    if len(winners) >= top_n:
                        break

        return winners

    # ==================== 综合排名 ====================

    @retry_on_timeout(max_retries=3, retry_delay=5.0)
    def _ai_generate_ranking(self, prompt: str) -> str:
        """AI 生成排名（带重试装饰器）"""
        return self.ai_client.generate(prompt, temperature=0.7)

    def generate_final_ranking(
        self,
        traders_with_analysis: List[Dict[str, Any]],
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

        # 获取持仓和币种统计
        positions_map = {}
        coin_stats_map = {}
        ai_summaries = {}

        for t in traders_with_analysis:
            addr = t.get('address')
            positions_map[addr] = self.get_trader_positions(addr)
            coin_stats_map[addr] = self.get_trader_coin_stats(addr, top_n=5)

            # AI 摘要
            analysis = t.get('ai_analysis', {})
            if analysis.get('summary'):
                ai_summaries[addr] = analysis['summary']

        # 构建提示词
        prompt = self.prompt_builder.build_final_ranking_prompt(
            traders_with_analysis, positions_map, coin_stats_map, ai_summaries
        )

        try:
            logger.info("AI 综合排名中...")
            comparison_result = self._ai_generate_ranking(prompt)

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

    # ==================== 报告和数据库 ====================

    def save_report(self, report: Dict[str, Any], filepath: str) -> None:
        """
        保存报告到文件

        Args:
            report: 报告数据
            filepath: 输出文件路径
        """
        # 确保目录存在
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"报告已保存至: {filepath}")

    def save_to_database(
        self,
        all_traders: List[Dict[str, Any]],
        finalists: List[Dict[str, Any]],
        group_report: Dict[str, Any],
        final_ranking: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        保存分组对比结果到数据库（已禁用）

        Args:
            all_traders: 所有参与的交易员
            finalists: 最终晋级者
            group_report: 分组对比报告
            final_ranking: 最终排名分析
            config: 配置参数

        Returns:
            会话ID (始终返回0)
        """
        logger.warning("分组对比数据库功能已禁用，跳过保存")
        return 0

    def print_report(self, report: Dict[str, Any]) -> None:
        """
        打印报告摘要

        Args:
            report: 报告数据
        """
        logger.info("=" * 80)
        logger.info("顶尖交易员综合分析报告")
        logger.info("=" * 80)
        logger.info(f"生成时间: {report.get('generated_at', 'N/A')}")
        logger.info(f"AI 提供商: {report.get('ai_provider', 'N/A')}")
        logger.info(f"分析交易员数量: {report.get('total_traders_analyzed', 0)}")
        logger.info("-" * 80)

        # 打印交易员列表
        traders = report.get('traders', [])
        if traders:
            table = self.formatter.format_traders_table(
                traders,
                columns=['rank', 'address', 'score', 'win_rate', 'pnl', '7d_pnl', 'drawdown', 'sharpe']
            )
            logger.info("交易员评分排名:")
            for line in table.split('\n'):
                logger.info(line)

        # 打印 AI 综合分析
        if report.get('comparison_analysis'):
            logger.info("-" * 80)
            logger.info("AI 综合分析:")
            logger.info("-" * 80)
            logger.info(report['comparison_analysis'])

        logger.info("=" * 80)

    def clear_cache(self) -> None:
        """清除缓存"""
        self._positions_cache.clear()
        self._coin_stats_cache.clear()
        logger.debug("缓存已清除")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取分析指标摘要"""
        return self.metrics.summary()
