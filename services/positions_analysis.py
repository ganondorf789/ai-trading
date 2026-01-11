"""
持仓AI分析服务
对当前持仓进行多维度的AI分析
"""
from typing import Dict, Any, Optional, List
from loguru import logger
from clients import get_ai_client


class PositionsAIAnalyzer:
    """持仓AI分析器"""

    def __init__(self, provider: Optional[str] = None):
        """
        初始化AI分析器

        Args:
            provider: AI提供商 (zhipu/qwen/deepseek/openrouter)，None则使用默认
        """
        try:
            self.client = get_ai_client(provider=provider)
            logger.info(f"持仓AI分析器初始化成功，使用提供商: {provider or '默认'}")
        except Exception as e:
            logger.error(f"持仓AI分析器初始化失败: {e}")
            raise

    def analyze_all_positions(
        self,
        positions: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析所有持仓（整体分析）

        Args:
            positions: 所有持仓数据列表
            stats: 持仓统计数据

        Returns:
            包含AI分析结果的字典
        """
        try:
            prompt = self._build_overall_analysis_prompt(positions, stats)
            
            logger.info(f"开始整体持仓AI分析，共 {len(positions)} 个持仓")
            analysis_result = self.client.generate(
                prompt,
                temperature=0.7,
                max_tokens=3000
            )

            return {
                'analysis_type': 'overall',
                'position_count': len(positions),
                'analysis_text': analysis_result,
                'sections': self._parse_overall_analysis(analysis_result)
            }

        except Exception as e:
            logger.error(f"整体持仓AI分析失败: {e}")
            raise

    def analyze_coin_positions(
        self,
        coin: str,
        positions: List[Dict[str, Any]],
        coin_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析单个币种的所有持仓

        Args:
            coin: 币种名称
            positions: 该币种的持仓列表
            coin_stats: 该币种的统计数据

        Returns:
            包含AI分析结果的字典
        """
        try:
            prompt = self._build_coin_analysis_prompt(coin, positions, coin_stats)
            
            logger.info(f"开始币种 {coin} 持仓AI分析，共 {len(positions)} 个持仓")
            analysis_result = self.client.generate(
                prompt,
                temperature=0.7,
                max_tokens=2000
            )

            return {
                'analysis_type': 'coin',
                'coin': coin,
                'position_count': len(positions),
                'analysis_text': analysis_result,
                'sections': self._parse_coin_analysis(analysis_result)
            }

        except Exception as e:
            logger.error(f"币种 {coin} 持仓AI分析失败: {e}")
            raise

    def analyze_single_position(
        self,
        position: Dict[str, Any],
        trader_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        分析单个仓位的风险

        Args:
            position: 仓位数据
            trader_info: 交易员信息（可选）

        Returns:
            包含AI分析结果的字典
        """
        try:
            prompt = self._build_position_analysis_prompt(position, trader_info)
            
            coin = position.get('coin', 'Unknown')
            logger.info(f"开始单仓位 {coin} AI分析")
            analysis_result = self.client.generate(
                prompt,
                temperature=0.7,
                max_tokens=1500
            )

            return {
                'analysis_type': 'single',
                'coin': coin,
                'address': position.get('address'),
                'analysis_text': analysis_result,
                'sections': self._parse_position_analysis(analysis_result)
            }

        except Exception as e:
            logger.error(f"单仓位AI分析失败: {e}")
            raise

    def _build_overall_analysis_prompt(
        self,
        positions: List[Dict[str, Any]],
        stats: Dict[str, Any]
    ) -> str:
        """构建整体分析提示词"""
        
        # 基础统计
        total_positions = stats.get('total_positions', len(positions))
        total_traders = stats.get('total_traders', 0)
        total_notional = stats.get('total_notional', 0)
        long_count = stats.get('long_count', 0)
        short_count = stats.get('short_count', 0)
        long_notional = stats.get('long_notional', 0)
        short_notional = stats.get('short_notional', 0)
        
        # 盈亏统计
        total_unrealized_pnl = stats.get('total_unrealized_pnl', 0)
        profit_count = stats.get('profit_count', 0)
        loss_count = stats.get('loss_count', 0)
        profit_pnl = stats.get('profit_pnl', 0)
        loss_pnl = stats.get('loss_pnl', 0)
        
        # 多空比例
        long_ratio = long_count / total_positions * 100 if total_positions > 0 else 0
        short_ratio = short_count / total_positions * 100 if total_positions > 0 else 0
        
        # 构建币种分布
        by_coin = stats.get('by_coin', [])
        coin_distribution = "\n".join([
            f"- {c.get('coin', '-')}: {c.get('count', 0)}个仓位, "
            f"做多{c.get('long', 0)}个, 做空{c.get('short', 0)}个, "
            f"总价值${c.get('notional', 0):,.2f}"
            for c in by_coin[:10]
        ]) if by_coin else "无数据"
        
        # 按交易员分布
        by_trader = stats.get('by_trader', [])
        trader_distribution = "\n".join([
            f"- {t.get('name') or t.get('address', '-')[:10]+'...'}: "
            f"{t.get('count', 0)}个仓位, 总价值${t.get('notional', 0):,.2f}"
            for t in by_trader[:10]
        ]) if by_trader else "无数据"
        
        # 高杠杆仓位列表
        high_leverage_positions = [p for p in positions if p.get('leverage_value', 1) >= 10]
        high_leverage_text = ""
        if high_leverage_positions:
            high_leverage_text = "\n【高杠杆仓位(≥10x)】\n"
            for p in sorted(high_leverage_positions, key=lambda x: x.get('leverage_value', 0), reverse=True)[:5]:
                side = "多" if p.get('szi', 0) > 0 else "空"
                high_leverage_text += (
                    f"- {p.get('coin', '-')} ({side}): {p.get('leverage_value', 1):.0f}x杠杆, "
                    f"持仓价值${abs(p.get('position_value', 0)):,.2f}, "
                    f"未实现盈亏${p.get('unrealized_pnl', 0):,.2f}\n"
                )
        
        # 大额仓位
        large_positions = sorted(positions, key=lambda x: abs(x.get('position_value', 0)), reverse=True)[:5]
        large_positions_text = "\n【大额仓位 Top5】\n"
        for p in large_positions:
            side = "多" if p.get('szi', 0) > 0 else "空"
            trader_name = p.get('trader_name') or p.get('address', '-')[:10] + '...'
            large_positions_text += (
                f"- {p.get('coin', '-')} ({side}) by {trader_name}: "
                f"持仓价值${abs(p.get('position_value', 0)):,.2f}, "
                f"未实现盈亏${p.get('unrealized_pnl', 0):,.2f} ({p.get('return_on_equity', 0)*100:.2f}%)\n"
            )
        
        # 分析交易员持仓共识（同一币种多个交易员持仓）
        coin_traders = {}
        for p in positions:
            coin = p.get('coin', '-')
            if coin not in coin_traders:
                coin_traders[coin] = {'long': [], 'short': []}
            side = 'long' if p.get('szi', 0) > 0 else 'short'
            trader_name = p.get('trader_name') or p.get('address', '-')[:10]
            rating = p.get('rating', 'N/A')
            coin_traders[coin][side].append(f"{trader_name}({rating})")
        
        consensus_text = "\n【交易员共识分析】\n"
        for coin, sides in sorted(coin_traders.items(), key=lambda x: len(x[1]['long']) + len(x[1]['short']), reverse=True)[:5]:
            if len(sides['long']) + len(sides['short']) > 1:
                consensus_text += f"- {coin}: "
                if sides['long']:
                    consensus_text += f"做多 {len(sides['long'])}人"
                if sides['short']:
                    consensus_text += f"{' / ' if sides['long'] else ''}做空 {len(sides['short'])}人"
                consensus_text += "\n"

        prompt = f"""
作为专业的加密货币交易分析师，请对当前的交易员持仓情况进行深度分析，提供市场洞察和操作建议。

【整体统计】
- 总持仓数: {total_positions}
- 交易员数: {total_traders}
- 总持仓价值: ${total_notional:,.2f}
- 总未实现盈亏: ${total_unrealized_pnl:,.2f}

【多空分布】
- 做多: {long_count}个仓位 ({long_ratio:.1f}%)，价值${long_notional:,.2f}
- 做空: {short_count}个仓位 ({short_ratio:.1f}%)，价值${short_notional:,.2f}

【盈亏分布】
- 盈利仓位: {profit_count}个，累计盈利${profit_pnl:,.2f}
- 亏损仓位: {loss_count}个，累计亏损${loss_pnl:,.2f}

【币种分布 Top10】
{coin_distribution}

【交易员持仓分布 Top10】
{trader_distribution}
{high_leverage_text}{large_positions_text}{consensus_text}
请按以下格式提供分析报告：

## 一、市场情绪概览
（用2-3句话总结当前交易员的整体市场判断和情绪）

## 二、多空力量分析
（分析多空比例、资金分布、主要分歧点）

## 三、热门币种解读
（分析交易员最关注的币种，以及持仓方向的共识或分歧）

## 四、风险聚集警示
（识别可能存在的风险聚集点，如：单币种过度集中、高杠杆风险、交易员持仓高度一致等）

## 五、关注要点
（列出3-5个值得关注的交易信号或机会）

## 六、操作建议
（给出具体可执行的建议，包括跟单策略调整、风险控制措施等）

要求：
1. 分析要基于数据，专业客观
2. 注意识别潜在风险
3. 建议要具体可执行
4. 关注交易员共识与分歧
5. 用中文回答
"""
        return prompt

    def _build_coin_analysis_prompt(
        self,
        coin: str,
        positions: List[Dict[str, Any]],
        coin_stats: Dict[str, Any]
    ) -> str:
        """构建币种分析提示词"""
        
        long_positions = [p for p in positions if p.get('szi', 0) > 0]
        short_positions = [p for p in positions if p.get('szi', 0) < 0]
        
        long_count = len(long_positions)
        short_count = len(short_positions)
        total_count = len(positions)
        
        # 计算多空价值
        long_value = sum(abs(p.get('position_value', 0)) for p in long_positions)
        short_value = sum(abs(p.get('position_value', 0)) for p in short_positions)
        total_value = coin_stats.get('notional', long_value + short_value)
        
        # 计算平均开仓价
        avg_long_entry = sum(p.get('entry_px', 0) * abs(p.get('szi', 0)) for p in long_positions) / sum(abs(p.get('szi', 0)) for p in long_positions) if long_positions and sum(abs(p.get('szi', 0)) for p in long_positions) > 0 else 0
        avg_short_entry = sum(p.get('entry_px', 0) * abs(p.get('szi', 0)) for p in short_positions) / sum(abs(p.get('szi', 0)) for p in short_positions) if short_positions and sum(abs(p.get('szi', 0)) for p in short_positions) > 0 else 0
        
        # 计算未实现盈亏
        total_pnl = sum(p.get('unrealized_pnl', 0) for p in positions)
        long_pnl = sum(p.get('unrealized_pnl', 0) for p in long_positions)
        short_pnl = sum(p.get('unrealized_pnl', 0) for p in short_positions)
        
        # 构建持仓详情
        position_details = "\n【持仓详情】\n"
        for p in sorted(positions, key=lambda x: abs(x.get('position_value', 0)), reverse=True):
            side = "多" if p.get('szi', 0) > 0 else "空"
            trader_name = p.get('trader_name') or p.get('address', '-')[:10] + '...'
            rating = p.get('rating', 'N/A')
            roe = p.get('return_on_equity', 0) * 100
            position_details += (
                f"- [{rating}] {trader_name} ({side}): "
                f"开仓价${p.get('entry_px', 0):.4f}, "
                f"持仓价值${abs(p.get('position_value', 0)):,.2f}, "
                f"杠杆{p.get('leverage_value', 1):.0f}x, "
                f"盈亏${p.get('unrealized_pnl', 0):,.2f} ({roe:.2f}%)\n"
            )

        # 按评级统计
        rating_stats = {}
        for p in positions:
            rating = p.get('rating', 'N/A')
            if rating not in rating_stats:
                rating_stats[rating] = {'long': 0, 'short': 0}
            if p.get('szi', 0) > 0:
                rating_stats[rating]['long'] += 1
            else:
                rating_stats[rating]['short'] += 1
        
        rating_text = "\n【按评级分布】\n"
        for rating in ['S', 'A', 'B', 'C', 'D', 'F']:
            if rating in rating_stats:
                r = rating_stats[rating]
                rating_text += f"- {rating}级: 做多{r['long']}人, 做空{r['short']}人\n"

        prompt = f"""
作为专业的加密货币交易分析师，请对 {coin} 币种的当前持仓情况进行深度分析。

【{coin} 持仓概览】
- 总持仓数: {total_count}
- 总持仓价值: ${total_value:,.2f}
- 总未实现盈亏: ${total_pnl:,.2f}

【多空分布】
- 做多: {long_count}个仓位，价值${long_value:,.2f}，平均开仓价${avg_long_entry:.4f}
  盈亏: ${long_pnl:,.2f}
- 做空: {short_count}个仓位，价值${short_value:,.2f}，平均开仓价${avg_short_entry:.4f}
  盈亏: ${short_pnl:,.2f}
{rating_text}{position_details}
请按以下格式提供分析报告：

## 一、多空力量对比
（分析做多与做空的力量对比，高评级交易员的持仓方向）

## 二、关键价位分析
（根据开仓价格分布，分析可能的支撑/阻力位）

## 三、交易员共识
（分析不同评级交易员对该币种的看法是否一致）

## 四、风险评估
（评估该币种持仓的整体风险水平）

## 五、操作建议
（基于分析给出具体的操作建议）

要求：
1. 分析要基于数据，专业客观
2. 关注高评级交易员的判断
3. 建议要具体可执行
4. 用中文回答
"""
        return prompt

    def _build_position_analysis_prompt(
        self,
        position: Dict[str, Any],
        trader_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建单仓位分析提示词"""
        
        coin = position.get('coin', 'Unknown')
        side = "做多" if position.get('szi', 0) > 0 else "做空"
        entry_px = position.get('entry_px', 0)
        position_value = abs(position.get('position_value', 0))
        unrealized_pnl = position.get('unrealized_pnl', 0)
        roe = position.get('return_on_equity', 0) * 100
        leverage = position.get('leverage_value', 1)
        liquidation_px = position.get('liquidation_px')
        margin_used = position.get('margin_used', 0)
        
        # 交易员信息
        trader_name = position.get('trader_name') or position.get('address', '-')[:10] + '...'
        rating = position.get('rating', 'N/A')
        overall_score = position.get('overall_score', 0)
        
        trader_text = ""
        if trader_info:
            trader_text = f"""
【交易员详细信息】
- 胜率: {trader_info.get('win_rate', 0)*100:.2f}%
- 总盈亏: ${trader_info.get('total_pnl', 0):,.2f}
- 盈亏比: {trader_info.get('profit_factor', 0):.2f}
- 最大回撤: {trader_info.get('max_drawdown', 0)*100:.2f}%
- Sharpe比率: {trader_info.get('sharpe_ratio', 0):.2f}
- 近7天盈亏: ${trader_info.get('recent_7d_pnl', 0):,.2f}
"""

        # 处理清算价格显示
        liquidation_px_str = f'${liquidation_px:.4f}' if liquidation_px else '未知'
        
        prompt = f"""
作为专业的加密货币交易分析师，请对以下仓位进行风险分析。

【仓位信息】
- 币种: {coin}
- 方向: {side}
- 开仓价格: ${entry_px:.4f}
- 持仓价值: ${position_value:,.2f}
- 杠杆倍数: {leverage:.0f}x
- 使用保证金: ${margin_used:,.2f}
- 清算价格: {liquidation_px_str}
- 未实现盈亏: ${unrealized_pnl:,.2f} ({roe:.2f}%)

【交易员信息】
- 名称/地址: {trader_name}
- 评级: {rating}
- 综合得分: {overall_score:.1f}/100
{trader_text}
请按以下格式提供分析报告：

## 一、风险评级
（给出该仓位的风险等级：低/中/高/极高，并说明原因）

## 二、关键风险点
（列出2-3个该仓位面临的主要风险）

## 三、盈亏分析
（分析当前盈亏状态和潜在的盈亏空间）

## 四、建议
（给出是否跟单该仓位的建议，以及风险控制措施）

要求：
1. 分析要基于数据，专业客观
2. 重点关注风险因素
3. 建议要具体可执行
4. 用中文回答
"""
        return prompt

    def _parse_overall_analysis(self, text: str) -> Dict[str, str]:
        """解析整体分析结果"""
        return {
            'market_sentiment': self._extract_section(text, '市场情绪概览'),
            'long_short_analysis': self._extract_section(text, '多空力量分析'),
            'hot_coins': self._extract_section(text, '热门币种解读'),
            'risk_warning': self._extract_section(text, '风险聚集警示'),
            'key_points': self._extract_section(text, '关注要点'),
            'suggestions': self._extract_section(text, '操作建议'),
        }

    def _parse_coin_analysis(self, text: str) -> Dict[str, str]:
        """解析币种分析结果"""
        return {
            'long_short_comparison': self._extract_section(text, '多空力量对比'),
            'key_levels': self._extract_section(text, '关键价位分析'),
            'trader_consensus': self._extract_section(text, '交易员共识'),
            'risk_assessment': self._extract_section(text, '风险评估'),
            'suggestions': self._extract_section(text, '操作建议'),
        }

    def _parse_position_analysis(self, text: str) -> Dict[str, str]:
        """解析单仓位分析结果"""
        return {
            'risk_level': self._extract_section(text, '风险评级'),
            'key_risks': self._extract_section(text, '关键风险点'),
            'pnl_analysis': self._extract_section(text, '盈亏分析'),
            'suggestions': self._extract_section(text, '建议'),
        }

    def _extract_section(self, text: str, section_name: str) -> str:
        """提取特定章节内容"""
        try:
            # 查找章节标题
            patterns = [
                f'## {section_name}',
                f'##  {section_name}',
                f'## 【{section_name}】',
                f'**{section_name}**',
            ]

            start_idx = -1
            for pattern in patterns:
                if pattern in text:
                    start_idx = text.find(pattern)
                    break

            if start_idx == -1:
                return ''

            # 查找下一个章节的开始
            next_section_idx = text.find('##', start_idx + 3)

            if next_section_idx == -1:
                section_text = text[start_idx:]
            else:
                section_text = text[start_idx:next_section_idx]

            # 移除标题行，只保留内容
            lines = section_text.split('\n')
            content_lines = [line.strip() for line in lines[1:] if line.strip()]

            return '\n'.join(content_lines)
        except:
            return ''


def analyze_all_positions(
    positions: List[Dict[str, Any]],
    stats: Dict[str, Any],
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """整体持仓分析（便捷函数）"""
    analyzer = PositionsAIAnalyzer(provider=provider)
    return analyzer.analyze_all_positions(positions, stats)


def analyze_coin_positions(
    coin: str,
    positions: List[Dict[str, Any]],
    coin_stats: Dict[str, Any],
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """币种持仓分析（便捷函数）"""
    analyzer = PositionsAIAnalyzer(provider=provider)
    return analyzer.analyze_coin_positions(coin, positions, coin_stats)


def analyze_single_position(
    position: Dict[str, Any],
    trader_info: Optional[Dict[str, Any]] = None,
    provider: Optional[str] = None
) -> Dict[str, Any]:
    """单仓位分析（便捷函数）"""
    analyzer = PositionsAIAnalyzer(provider=provider)
    return analyzer.analyze_single_position(position, trader_info)
