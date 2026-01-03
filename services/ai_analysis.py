"""
AI分析服务
使用AI模型分析交易员表现并生成专业报告
"""
from typing import Dict, Any, Optional, List
from loguru import logger
from clients import get_ai_client


class TraderAIAnalyzer:
    """交易员AI分析器"""

    def __init__(self, provider: Optional[str] = None):
        """
        初始化AI分析器

        Args:
            provider: AI提供商 (zhipu/qwen/deepseek/openrouter)，None则使用默认
        """
        try:
            self.client = get_ai_client(provider=provider)
            logger.info(f"AI分析器初始化成功，使用提供商: {provider or '默认'}")
        except Exception as e:
            logger.error(f"AI分析器初始化失败: {e}")
            raise

    def analyze_trader(
        self,
        trader_data: Dict[str, Any],
        coin_stats: Optional[List[Dict[str, Any]]] = None,
        positions: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        分析交易员并生成AI报告

        Args:
            trader_data: 交易员数据字典
            coin_stats: 币种统计数据列表
            positions: 当前持仓数据列表

        Returns:
            包含AI分析结果的字典
        """
        try:
            # 构建分析提示词
            prompt = self._build_analysis_prompt(trader_data, coin_stats, positions)

            # 调用AI模型生成分析
            logger.info(f"开始AI分析交易员: {trader_data.get('address', 'Unknown')}")
            analysis_result = self.client.generate(
                prompt,
                temperature=0.7,
                max_tokens=2000
            )

            # 解析并结构化分析结果
            structured_analysis = self._parse_analysis(analysis_result, trader_data)

            logger.info(f"AI分析完成: {trader_data.get('address', 'Unknown')}")
            return structured_analysis

        except Exception as e:
            logger.error(f"AI分析失败: {e}")
            raise

    def _build_analysis_prompt(
        self,
        trader: Dict[str, Any],
        coin_stats: Optional[List[Dict[str, Any]]] = None,
        positions: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """构建分析提示词"""

        # 提取关键数据
        address = trader.get('address', 'Unknown')
        rating = trader.get('rating', 'F')
        score = trader.get('overall_score', 0)

        # 基础统计
        total_trades = trader.get('total_trades', 0)
        win_rate = trader.get('win_rate', 0) * 100
        active_days = trader.get('active_days', 0)

        # 盈亏指标
        total_pnl = trader.get('total_pnl', 0)
        roi = trader.get('roi', 0) * 100
        profit_factor = trader.get('profit_factor', 0)

        # 风险指标
        max_drawdown = trader.get('max_drawdown', 0) * 100
        sharpe_ratio = trader.get('sharpe_ratio', 0)
        avg_leverage = trader.get('avg_leverage', 1)

        # 交易特征
        max_consecutive_wins = trader.get('max_consecutive_wins', 0)
        max_consecutive_losses = trader.get('max_consecutive_losses', 0)
        avg_win_amount = trader.get('avg_win_amount', 0)
        avg_loss_amount = trader.get('avg_loss_amount', 0)
        favorite_symbol = trader.get('favorite_symbol', '-')

        # 近期表现
        recent_7d_pnl = trader.get('recent_7d_pnl', 0)
        recent_7d_win_rate = trader.get('recent_7d_win_rate', 0) * 100

        # 构建币种统计部分
        coin_stats_text = ""
        if coin_stats and len(coin_stats) > 0:
            coin_stats_text = "\n【币种统计】\n"
            # 按盈亏排序，取前10个
            sorted_coins = sorted(coin_stats, key=lambda x: abs(x.get('total_pnl', 0)), reverse=True)[:10]
            for coin in sorted_coins:
                coin_name = coin.get('coin', '-')
                coin_count = coin.get('count', 0)
                coin_pnl = coin.get('total_pnl', 0)
                avg_pnl = coin_pnl / coin_count if coin_count > 0 else 0
                coin_stats_text += f"- {coin_name}: {coin_count}笔交易, 总盈亏${coin_pnl:.2f}, 平均${avg_pnl:.2f}\n"

        # 构建当前持仓部分
        positions_text = ""
        if positions and len(positions) > 0:
            positions_text = "\n【当前持仓】\n"
            total_unrealized_pnl = 0
            for pos in positions:
                coin = pos.get('coin', '-')
                szi = pos.get('szi', 0)
                side = "多" if szi > 0 else "空"
                entry_px = pos.get('entry_px', 0)
                position_value = abs(pos.get('position_value', 0))
                unrealized_pnl = pos.get('unrealized_pnl', 0)
                roe = pos.get('return_on_equity', 0) * 100
                leverage = pos.get('leverage_value', 1)
                total_unrealized_pnl += unrealized_pnl
                positions_text += f"- {coin} ({side}): 数量{abs(szi):.4f}, 开仓价${entry_px:.4f}, 持仓价值${position_value:.2f}, 未实现盈亏${unrealized_pnl:.2f} ({roe:.2f}%), {leverage}x杠杆\n"
            positions_text += f"- 总未实现盈亏: ${total_unrealized_pnl:.2f}\n"
        else:
            positions_text = "\n【当前持仓】\n- 无当前持仓\n"

        prompt = f"""
作为专业的加密货币交易分析师，请深度分析以下交易员的表现数据，并提供专业的投资建议。

【交易员基本信息】
- 地址: {address}
- 综合评级: {rating} (满分S)
- 综合得分: {score:.1f}/100

【基础统计】
- 总交易次数: {total_trades}
- 胜率: {win_rate:.2f}%
- 活跃天数: {active_days}天
- 常用交易品种: {favorite_symbol}

【盈亏分析】
- 总盈亏: ${total_pnl:.2f}
- 投资回报率(ROI): {roi:.2f}%
- 盈亏比: {profit_factor:.2f}
- 平均单笔盈利: ${avg_win_amount:.2f}
- 平均单笔亏损: ${avg_loss_amount:.2f}

【风险控制】
- 最大回撤: {max_drawdown:.2f}%
- Sharpe比率: {sharpe_ratio:.2f}
- 平均杠杆: {avg_leverage:.1f}x

【交易心理】
- 最大连胜次数: {max_consecutive_wins}
- 最大连亏次数: {max_consecutive_losses}

【近期表现】
- 7天盈亏: ${recent_7d_pnl:.2f}
- 7天胜率: {recent_7d_win_rate:.2f}%
{coin_stats_text}{positions_text}
请按以下格式提供分析报告：

## 一、综合评价
（用2-3句话总结该交易员的整体表现和水平）

## 二、优势分析
（列举3-5个该交易员的主要优势，每点1-2句话）

## 三、风险提示
（列举2-4个需要注意的风险点，每点1-2句话）

## 四、交易风格
（分析交易员的交易风格特点，如激进/稳健、偏好品种、持仓特点等）

## 五、跟单建议
（提供具体的跟单建议，包括建议跟单比例、止损设置等）

## 六、改进建议
（如果有明显的问题，提供改进建议）

要求：
1. 分析要专业、客观、具体
2. 避免空洞的套话
3. 数据支撑每个观点
4. 风险提示要明确
5. 建议要可执行
6. 结合币种统计分析交易偏好
7. 结合当前持仓分析仓位风险
"""
        return prompt

    def _parse_analysis(self, raw_analysis: str, trader: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析AI分析结果并结构化

        Args:
            raw_analysis: AI生成的原始分析文本
            trader: 交易员原始数据

        Returns:
            结构化的分析结果
        """
        return {
            'address': trader.get('address'),
            'rating': trader.get('rating'),
            'overall_score': trader.get('overall_score'),
            'analysis_text': raw_analysis,
            'analyzed_at': trader.get('analyzed_at'),
            'summary': self._extract_summary(raw_analysis),
            'strengths': self._extract_section(raw_analysis, '优势分析'),
            'risks': self._extract_section(raw_analysis, '风险提示'),
            'trading_style': self._extract_section(raw_analysis, '交易风格'),
            'copy_trading_advice': self._extract_section(raw_analysis, '跟单建议'),
            'improvement_suggestions': self._extract_section(raw_analysis, '改进建议'),
        }

    def _extract_summary(self, text: str) -> str:
        """提取综合评价部分"""
        try:
            if '## 一、综合评价' in text:
                start = text.find('## 一、综合评价')
                end = text.find('## 二、', start)
                if end == -1:
                    end = len(text)
                section = text[start:end].strip()
                # 移除标题行
                lines = section.split('\n')
                return '\n'.join(lines[1:]).strip()
            return text[:200] + '...'  # 如果没找到，返回前200字符
        except:
            return ''

    def _extract_section(self, text: str, section_name: str) -> str:
        """提取特定章节内容"""
        try:
            # 查找章节标题（支持多种可能的标题格式）
            patterns = [
                f'## {section_name}',
                f'##  {section_name}',
                f'## 【{section_name}】',
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


def generate_trader_analysis(
    trader_data: Dict[str, Any],
    provider: Optional[str] = None,
    coin_stats: Optional[List[Dict[str, Any]]] = None,
    positions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    生成交易员AI分析（便捷函数）

    Args:
        trader_data: 交易员数据
        provider: AI提供商
        coin_stats: 币种统计数据列表
        positions: 当前持仓数据列表

    Returns:
        AI分析结果
    """
    analyzer = TraderAIAnalyzer(provider=provider)
    return analyzer.analyze_trader(trader_data, coin_stats, positions)
