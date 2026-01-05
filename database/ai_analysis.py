"""
AI 分析管理模块
"""
from typing import Dict, Any, Optional
from loguru import logger


class AIAnalysisOps:
    """AI 分析相关操作"""

    def save_trader_ai_analysis(self, address: str, analysis: Dict[str, Any]) -> None:
        """
        保存交易员AI分析结果

        Args:
            address: 交易员地址
            analysis: AI分析结果字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO trader_ai_analysis (
                    address,
                    rating,
                    overall_score,
                    analysis_text,
                    summary,
                    strengths,
                    risks,
                    trading_style,
                    copy_trading_advice,
                    improvement_suggestions,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                address,
                analysis.get('rating'),
                analysis.get('overall_score'),
                analysis.get('analysis_text'),
                analysis.get('summary'),
                analysis.get('strengths'),
                analysis.get('risks'),
                analysis.get('trading_style'),
                analysis.get('copy_trading_advice'),
                analysis.get('improvement_suggestions')
            ))

            logger.info(f"保存AI分析结果: {address}")

    def get_trader_ai_analysis(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取交易员AI分析结果

        Args:
            address: 交易员地址

        Returns:
            AI分析结果字典，如果不存在返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM trader_ai_analysis
                WHERE address = ?
            """, (address,))

            row = cursor.fetchone()
            if not row:
                return None

            return dict(row)
