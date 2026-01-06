"""
交易员预筛选器

通过多维度指标预筛选，减少 AI 分析数量
"""
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional

import pendulum
from loguru import logger

from .models import FilterConfig, TraderData


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

# 筛除原因描述
FILTER_REASON_NAMES = {
    'low_pnl': '总盈亏不足',
    'negative_7d_pnl': '近7天亏损',
    'high_drawdown': '回撤过高',
    'low_sharpe': 'Sharpe比率低',
    'low_sortino': 'Sortino比率低',
    'low_profit_factor': '盈亏比低',
    'low_win_rate': '胜率过低',
    'high_win_rate': '胜率过高（可能小赚大亏）',
    'inactive': '长期不活跃',
}


class TraderPreFilter:
    """
    交易员预筛选器

    通过多维度指标筛选交易员，减少需要 AI 分析的数量

    Example:
        config = FilterConfig(min_pnl=5000, max_drawdown=0.3)
        filter = TraderPreFilter(config)

        passed, filtered_out = filter.filter_traders(traders)
        filter.print_summary(len(traders), len(passed), filtered_out)
    """

    def __init__(self, config: Optional[FilterConfig] = None):
        """
        初始化预筛选器

        Args:
            config: 筛选配置，如果为 None 则使用默认配置
        """
        if config is None:
            self.config = FilterConfig(**DEFAULT_FILTER_CONFIG)
        elif isinstance(config, dict):
            # 兼容字典格式
            merged = {**DEFAULT_FILTER_CONFIG, **config}
            self.config = FilterConfig(**merged)
        else:
            self.config = config

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'TraderPreFilter':
        """
        从字典创建筛选器

        Args:
            config_dict: 配置字典

        Returns:
            TraderPreFilter 实例
        """
        merged = {**DEFAULT_FILTER_CONFIG, **config_dict}
        config = FilterConfig(**merged)
        return cls(config)

    def _check_trader(
        self,
        trader: Dict[str, Any],
        now: datetime,
    ) -> List[str]:
        """
        检查单个交易员，返回筛除原因列表

        Args:
            trader: 交易员数据
            now: 当前时间

        Returns:
            筛除原因列表，空列表表示通过
        """
        reasons = []
        config = self.config

        # 1. 总盈亏检查
        total_pnl = trader.get('total_pnl', 0)
        if total_pnl < config.min_pnl:
            reasons.append('low_pnl')

        # 2. 近7天盈亏检查
        recent_7d_pnl = trader.get('recent_7d_pnl', 0)
        if recent_7d_pnl < config.min_7d_pnl:
            reasons.append('negative_7d_pnl')

        # 3. 最大回撤检查
        max_drawdown = trader.get('max_drawdown', 0)
        if max_drawdown > config.max_drawdown:
            reasons.append('high_drawdown')

        # 4. Sharpe 比率检查
        sharpe_ratio = trader.get('sharpe_ratio', 0)
        if sharpe_ratio < config.min_sharpe:
            reasons.append('low_sharpe')

        # 5. Sortino 比率检查（下行风险）
        sortino_ratio = trader.get('sortino_ratio', 0)
        if config.min_sortino > 0 and sortino_ratio < config.min_sortino:
            reasons.append('low_sortino')

        # 6. 盈亏比检查
        profit_factor = trader.get('profit_factor', 0)
        if profit_factor < config.min_profit_factor:
            reasons.append('low_profit_factor')

        # 7. 胜率检查（最小值）
        win_rate = trader.get('win_rate', 0)
        if win_rate < config.min_win_rate:
            reasons.append('low_win_rate')

        # 8. 胜率检查（最大值）- 避免高胜率低盈亏比的交易员
        if config.max_win_rate < 1.0 and win_rate > config.max_win_rate:
            reasons.append('high_win_rate')

        # 9. 活跃度检查
        last_trade_time = trader.get('last_trade_time')
        if last_trade_time and config.active_days > 0:
            try:
                if isinstance(last_trade_time, str):
                    last_trade = pendulum.parse(last_trade_time)
                elif isinstance(last_trade_time, datetime):
                    last_trade = pendulum.instance(last_trade_time)
                else:
                    last_trade = last_trade_time

                # 确保时区一致
                if last_trade.tzinfo is None:
                    last_trade = pendulum.instance(last_trade, tz=SHANGHAI_TZ)

                days_since_last = (now - last_trade).days
                if days_since_last > config.active_days:
                    reasons.append('inactive')
            except Exception:
                pass  # 解析失败则跳过活跃度检查

        return reasons

    def filter_traders(
        self,
        traders: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        筛选交易员

        Args:
            traders: 交易员列表
            verbose: 是否显示详细信息

        Returns:
            (通过筛选的交易员, 被筛除的交易员分类)

        Example:
            passed, filtered = filter.filter_traders(traders)
            print(f"通过: {len(passed)}, 筛除: {sum(len(v) for v in filtered.values())}")
        """
        passed = []
        filtered_out: Dict[str, List[Dict[str, Any]]] = {
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
            reasons = self._check_trader(trader, now)

            if not reasons:
                passed.append(trader)
            else:
                # 记录每个筛除原因
                for reason in reasons:
                    if reason in filtered_out:
                        filtered_out[reason].append(trader)

                if verbose:
                    short_addr = f"{address[:10]}..." if len(address) > 10 else address
                    logger.debug(f"筛除 {short_addr}: {', '.join(reasons)}")

        return passed, filtered_out

    def get_filter_description(self, reason: str) -> str:
        """
        获取筛选条件描述

        Args:
            reason: 筛除原因代码

        Returns:
            人类可读的描述
        """
        config = self.config

        descriptions = {
            'low_pnl': f'总盈亏 < ${config.min_pnl:,.0f}',
            'negative_7d_pnl': f'近7天盈亏 < ${config.min_7d_pnl:,.0f}',
            'high_drawdown': f'最大回撤 > {config.max_drawdown*100:.0f}%',
            'low_sharpe': f'Sharpe比率 < {config.min_sharpe:.1f}',
            'low_sortino': f'Sortino比率 < {config.min_sortino:.1f}',
            'low_profit_factor': f'盈亏比 < {config.min_profit_factor:.1f}',
            'low_win_rate': f'胜率 < {config.min_win_rate*100:.0f}%',
            'high_win_rate': f'胜率 > {config.max_win_rate*100:.0f}%（可能小赚大亏）',
            'inactive': f'超过 {config.active_days} 天未交易',
        }

        return descriptions.get(reason, reason)

    def print_summary(
        self,
        total: int,
        passed: int,
        filtered_out: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """
        打印筛选摘要

        Args:
            total: 总交易员数
            passed: 通过筛选数
            filtered_out: 被筛除的交易员分类
        """
        logger.info("预筛选结果:")
        logger.info("-" * 60)
        logger.info(f"  总交易员数: {total}")
        logger.info(f"  通过筛选: {passed}")
        logger.info(f"  被筛除: {total - passed}")
        logger.info("-" * 60)
        logger.info("  筛除原因统计:")

        for reason, traders in filtered_out.items():
            if traders:
                desc = self.get_filter_description(reason)
                logger.info(f"    - {desc}: {len(traders)} 人")

        logger.info("-" * 60)

    def print_config(self) -> None:
        """打印当前配置"""
        config = self.config
        logger.info("预筛选条件（专业级标准）:")
        logger.info(f"  - 最小总盈亏: ${config.min_pnl:,.0f}")
        logger.info(f"  - 最小近7天盈亏: ${config.min_7d_pnl:,.0f}")
        logger.info(f"  - 最大回撤: {config.max_drawdown*100:.0f}%")
        logger.info(f"  - 最小Sharpe比率: {config.min_sharpe:.1f}")
        logger.info(f"  - 最小Sortino比率: {config.min_sortino:.1f}")
        logger.info(f"  - 最小盈亏比: {config.min_profit_factor:.1f}")
        logger.info(f"  - 胜率范围: {config.min_win_rate*100:.0f}% - {config.max_win_rate*100:.0f}%")
        logger.info(f"  - 最近活跃天数: {config.active_days} 天")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.config.model_dump()
