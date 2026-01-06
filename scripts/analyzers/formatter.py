"""
交易员信息格式化器

提供统一的交易员数据格式化方法，用于 AI 提示词构建
"""
from typing import List, Dict, Any, Optional

from .models import TraderData, PositionData, CoinStats
from .utils import format_number, format_percent


class TraderInfoFormatter:
    """
    交易员信息格式化器

    统一处理交易员数据的格式化，避免重复代码

    Example:
        formatter = TraderInfoFormatter()

        # 格式化单个交易员
        info = formatter.format_trader_full(trader, positions, coin_stats)

        # 批量格式化
        infos = formatter.format_traders_batch(traders)
    """

    def __init__(
        self,
        max_positions: int = 5,
        max_coins: int = 5,
        show_address_full: bool = False,
    ):
        """
        初始化格式化器

        Args:
            max_positions: 最多显示持仓数
            max_coins: 最多显示币种数
            show_address_full: 是否显示完整地址
        """
        self.max_positions = max_positions
        self.max_coins = max_coins
        self.show_address_full = show_address_full

    def format_address(self, address: str) -> str:
        """格式化地址"""
        if self.show_address_full:
            return address
        return f"{address[:6]}...{address[-4:]}"

    def format_coin_stats(
        self,
        coin_stats: List[Dict[str, Any]],
        max_show: Optional[int] = None
    ) -> str:
        """
        格式化币种统计

        Args:
            coin_stats: 币种统计列表
            max_show: 最多显示数量

        Returns:
            格式化的字符串
        """
        if not coin_stats:
            return ""

        max_show = max_show or self.max_coins
        lines = []

        for cs in coin_stats[:max_show]:
            pnl = cs.get('total_pnl', 0)
            sign = "+" if pnl >= 0 else ""
            count = cs.get('count', 0)
            coin = cs.get('coin', 'Unknown')
            lines.append(f"  · {coin}: {count}笔, {sign}${pnl:,.0f}")

        if len(coin_stats) > max_show:
            lines.append(f"  · ... 还有 {len(coin_stats) - max_show} 个币种")

        return "\n".join(lines)

    def format_positions(
        self,
        positions: List[Dict[str, Any]],
        max_show: Optional[int] = None
    ) -> str:
        """
        格式化持仓信息

        Args:
            positions: 持仓列表
            max_show: 最多显示数量

        Returns:
            格式化的字符串
        """
        if not positions:
            return ""

        max_show = max_show or self.max_positions
        lines = []
        total_value = 0
        total_upnl = 0

        for pos in positions[:max_show]:
            coin = pos.get('coin', '')
            szi = pos.get('szi', 0)
            direction = "多" if szi > 0 else "空"
            value = abs(pos.get('position_value', 0))
            upnl = pos.get('unrealized_pnl', 0)
            roe = pos.get('return_on_equity', 0) * 100
            leverage = pos.get('leverage_value', 1)
            sign = "+" if upnl >= 0 else ""

            lines.append(
                f"  · {coin} {direction} ${value:,.0f} "
                f"({leverage}x, {sign}{roe:.1f}% ROE)"
            )
            total_value += value
            total_upnl += upnl

        # 显示更多持仓提示
        if len(positions) > max_show:
            remaining = len(positions) - max_show
            remaining_value = sum(
                abs(p.get('position_value', 0))
                for p in positions[max_show:]
            )
            remaining_upnl = sum(
                p.get('unrealized_pnl', 0)
                for p in positions[max_show:]
            )
            total_value += remaining_value
            total_upnl += remaining_upnl
            lines.append(f"  · ... 还有 {remaining} 个持仓")

        # 汇总
        upnl_sign = "+" if total_upnl >= 0 else ""
        lines.append(
            f"  总敞口: ${total_value:,.0f}, "
            f"未实现盈亏: {upnl_sign}${total_upnl:,.0f}"
        )

        return "\n".join(lines)

    def format_trader_basic(self, trader: Dict[str, Any]) -> str:
        """
        格式化交易员基本信息

        Args:
            trader: 交易员数据

        Returns:
            格式化的字符串
        """
        address = trader.get('address', 'Unknown')

        return f"""- 地址: {self.format_address(address)}
- 综合评分: {trader.get('overall_score', 0):.1f}/100
- 胜率: {trader.get('win_rate', 0) * 100:.1f}%
- 盈亏比: {trader.get('profit_factor', 0):.2f}
- 总盈亏: ${trader.get('total_pnl', 0):,.0f}
- 近7天盈亏: ${trader.get('recent_7d_pnl', 0):,.0f}
- 最大回撤: {trader.get('max_drawdown', 0) * 100:.1f}%
- Sharpe比率: {trader.get('sharpe_ratio', 0):.2f}
- Sortino比率: {trader.get('sortino_ratio', 0):.2f}
- 活跃天数: {trader.get('active_days', 0)}"""

    def format_trader_full(
        self,
        trader: Dict[str, Any],
        positions: Optional[List[Dict]] = None,
        coin_stats: Optional[List[Dict]] = None,
        index: Optional[int] = None,
    ) -> str:
        """
        格式化交易员完整信息（含持仓和币种统计）

        Args:
            trader: 交易员数据
            positions: 持仓列表
            coin_stats: 币种统计
            index: 序号

        Returns:
            格式化的字符串
        """
        address = trader.get('address', 'Unknown')

        # 标题
        if index is not None:
            header = f"【交易员 {index}】{address if self.show_address_full else self.format_address(address)}"
        else:
            header = f"【交易员】{address if self.show_address_full else self.format_address(address)}"

        # 基本指标
        info = f"""{header}
- 综合评分: {trader.get('overall_score', 0):.1f}/100
- 胜率: {trader.get('win_rate', 0) * 100:.1f}%
- 盈亏比: {trader.get('profit_factor', 0):.2f}
- 总盈亏: ${trader.get('total_pnl', 0):,.0f}
- 近7天盈亏: ${trader.get('recent_7d_pnl', 0):,.0f}
- 最大回撤: {trader.get('max_drawdown', 0) * 100:.1f}%
- Sharpe: {trader.get('sharpe_ratio', 0):.2f}
- Sortino: {trader.get('sortino_ratio', 0):.2f}
- 活跃天数: {trader.get('active_days', 0)}
"""

        # 币种统计
        if coin_stats:
            coin_str = self.format_coin_stats(coin_stats)
            if coin_str:
                info += f"- 主要交易币种:\n{coin_str}\n"

        # 当前持仓
        if positions:
            pos_str = self.format_positions(positions)
            if pos_str:
                info += f"- 当前持仓:\n{pos_str}\n"
        else:
            info += "- 当前持仓: 无\n"

        return info

    def format_trader_for_comparison(
        self,
        trader: Dict[str, Any],
        positions: Optional[List[Dict]] = None,
        coin_stats: Optional[List[Dict]] = None,
        ai_summary: Optional[str] = None,
        index: Optional[int] = None,
    ) -> str:
        """
        格式化交易员信息（用于综合对比）

        Args:
            trader: 交易员数据
            positions: 持仓列表
            coin_stats: 币种统计
            ai_summary: AI 分析摘要
            index: 序号

        Returns:
            格式化的字符串
        """
        # 基础信息
        info = self.format_trader_full(trader, positions, coin_stats, index)

        # 添加 AI 评价摘要
        if ai_summary:
            info += f"- AI评价摘要: {ai_summary[:200]}\n"

        return info

    def format_traders_table(
        self,
        traders: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
    ) -> str:
        """
        格式化交易员表格

        Args:
            traders: 交易员列表
            columns: 要显示的列

        Returns:
            格式化的表格字符串
        """
        if not traders:
            return "无交易员数据"

        columns = columns or [
            'rank', 'address', 'score', 'win_rate', 'pnl', '7d_pnl', 'drawdown', 'sharpe'
        ]

        # 表头
        header_map = {
            'rank': ('排名', 4),
            'address': ('地址', 14),
            'score': ('评分', 6),
            'win_rate': ('胜率', 7),
            'pnl': ('总PnL', 12),
            '7d_pnl': ('7D PnL', 10),
            'drawdown': ('回撤', 6),
            'sharpe': ('Sharpe', 7),
            'sortino': ('Sortino', 7),
        }

        header_line = "  "
        for col in columns:
            name, width = header_map.get(col, (col, 10))
            header_line += f"{name:<{width}} "

        separator = "-" * len(header_line)

        lines = [separator, header_line, separator]

        # 数据行
        for i, t in enumerate(traders, 1):
            row = "  "
            for col in columns:
                _, width = header_map.get(col, (col, 10))

                if col == 'rank':
                    value = f"{i}."
                elif col == 'address':
                    value = self.format_address(t.get('address', ''))
                elif col == 'score':
                    value = f"{t.get('overall_score', 0):.1f}"
                elif col == 'win_rate':
                    value = f"{t.get('win_rate', 0)*100:.1f}%"
                elif col == 'pnl':
                    value = f"${t.get('total_pnl', 0):,.0f}"
                elif col == '7d_pnl':
                    value = f"${t.get('recent_7d_pnl', 0):,.0f}"
                elif col == 'drawdown':
                    value = f"{t.get('max_drawdown', 0)*100:.1f}%"
                elif col == 'sharpe':
                    value = f"{t.get('sharpe_ratio', 0):.2f}"
                elif col == 'sortino':
                    value = f"{t.get('sortino_ratio', 0):.2f}"
                else:
                    value = str(t.get(col, ''))

                row += f"{value:<{width}} "

            lines.append(row)

        lines.append(separator)
        return "\n".join(lines)


class PromptBuilder:
    """
    AI 提示词构建器

    用于构建各种 AI 分析提示词
    """

    def __init__(self, formatter: Optional[TraderInfoFormatter] = None):
        self.formatter = formatter or TraderInfoFormatter(show_address_full=True)

    def build_group_comparison_prompt(
        self,
        group: List[Dict[str, Any]],
        positions_map: Dict[str, List[Dict]],
        coin_stats_map: Dict[str, List[Dict]],
        group_num: int,
        total_groups: int,
        top_n: int,
    ) -> str:
        """
        构建分组对比提示词

        Args:
            group: 分组交易员列表
            positions_map: 地址 -> 持仓映射
            coin_stats_map: 地址 -> 币种统计映射
            group_num: 当前组号
            total_groups: 总组数
            top_n: 选出前 N 名

        Returns:
            提示词
        """
        traders_info = []

        for i, t in enumerate(group, 1):
            address = t.get('address', '')
            positions = positions_map.get(address, [])
            coin_stats = coin_stats_map.get(address, [])

            info = self.formatter.format_trader_full(t, positions, coin_stats, i)
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
5. 当前持仓风险（杠杆水平、未实现盈亏）
6. 交易专注度（主要币种表现）

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

    def build_final_ranking_prompt(
        self,
        traders: List[Dict[str, Any]],
        positions_map: Dict[str, List[Dict]],
        coin_stats_map: Dict[str, List[Dict]],
        ai_summaries: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        构建最终综合排名提示词

        Args:
            traders: 交易员列表
            positions_map: 地址 -> 持仓映射
            coin_stats_map: 地址 -> 币种统计映射
            ai_summaries: 地址 -> AI 摘要映射

        Returns:
            提示词
        """
        ai_summaries = ai_summaries or {}
        traders_summary = []

        for i, t in enumerate(traders, 1):
            address = t.get('address', '')
            positions = positions_map.get(address, [])
            coin_stats = coin_stats_map.get(address, [])
            ai_summary = ai_summaries.get(address, '')

            info = self.formatter.format_trader_for_comparison(
                t, positions, coin_stats, ai_summary, i
            )
            traders_summary.append(info)

        prompt = f"""
作为专业的加密货币投资顾问，请综合分析以下 {len(traders)} 位顶尖交易员，并给出最终推荐排名。

{''.join(traders_summary)}

请按以下格式输出：

## 一、综合排名

根据以下维度综合评估后，给出最终推荐排名（从最优到次优）：
1. 盈利能力（总盈亏、ROI）
2. 风险控制（最大回撤、Sharpe/Sortino比率）
3. 稳定性（胜率、盈亏比、连续表现）
4. 活跃度（近期表现、交易频率）
5. 跟单适合度（交易风格、杠杆使用）
6. 当前持仓风险（持仓敞口、未实现盈亏、杠杆水平）
7. 交易专注度（主要币种及其盈利情况）

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
5. 结合当前持仓情况评估实时风险
"""
        return prompt
