"""
AI 分析管理模块 (PostgreSQL)
"""
import json
import hashlib
from typing import Dict, Any, Optional, List
from psycopg2 import extras
from loguru import logger


class AIAnalysisOps:
    """AI 分析相关操作"""

    # ==================== 持仓 AI 分析 ====================

    def _generate_positions_analysis_key(
        self,
        analysis_type: str,
        positions: List[Dict[str, Any]],
        coin: Optional[str] = None,
        address: Optional[str] = None
    ) -> str:
        """
        生成持仓分析的唯一标识符
        
        Args:
            analysis_type: 分析类型 (overall/coin/single)
            positions: 持仓数据列表
            coin: 币种（coin/single类型时需要）
            address: 地址（single类型时需要）
            
        Returns:
            唯一标识符字符串
        """
        if analysis_type == 'overall':
            # 整体分析：基于所有持仓的地址+币种组合生成哈希
            position_keys = sorted([
                f"{p.get('address', '')}_{p.get('coin', '')}"
                for p in positions
            ])
            content = '_'.join(position_keys)
            hash_suffix = hashlib.md5(content.encode()).hexdigest()[:12]
            return f"overall_{hash_suffix}"
        
        elif analysis_type == 'coin':
            # 币种分析：基于币种和持仓的地址列表生成哈希
            addresses = sorted([p.get('address', '') for p in positions])
            content = f"{coin}_{'_'.join(addresses)}"
            hash_suffix = hashlib.md5(content.encode()).hexdigest()[:12]
            return f"coin_{coin}_{hash_suffix}"
        
        elif analysis_type == 'single':
            # 单仓位分析：基于地址+币种+开仓价格生成
            if positions:
                p = positions[0]
                entry_px = p.get('entry_px', 0)
                szi = p.get('szi', 0)
                content = f"{address}_{coin}_{entry_px}_{szi}"
                hash_suffix = hashlib.md5(content.encode()).hexdigest()[:12]
                return f"single_{address[:10]}_{coin}_{hash_suffix}"
            return f"single_{address[:10]}_{coin}"
        
        return f"unknown_{analysis_type}"

    def save_positions_ai_analysis(
        self,
        analysis_type: str,
        analysis: Dict[str, Any],
        positions: List[Dict[str, Any]],
        stats: Optional[Dict[str, Any]] = None,
        coin: Optional[str] = None,
        address: Optional[str] = None,
        provider: Optional[str] = None
    ) -> int:
        """
        保存持仓 AI 分析结果
        
        Args:
            analysis_type: 分析类型 (overall/coin/single)
            analysis: AI 分析结果
            positions: 参与分析的持仓列表
            stats: 统计数据快照
            coin: 币种
            address: 地址
            provider: AI 提供商
            
        Returns:
            记录 ID
        """
        analysis_key = self._generate_positions_analysis_key(
            analysis_type, positions, coin, address
        )
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO positions_ai_analysis (
                    analysis_type,
                    analysis_key,
                    coin,
                    address,
                    position_count,
                    analysis_text,
                    sections,
                    stats_snapshot,
                    ai_provider,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(analysis_key) DO UPDATE SET
                    position_count = EXCLUDED.position_count,
                    analysis_text = EXCLUDED.analysis_text,
                    sections = EXCLUDED.sections,
                    stats_snapshot = EXCLUDED.stats_snapshot,
                    ai_provider = EXCLUDED.ai_provider,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                analysis_type,
                analysis_key,
                coin or analysis.get('coin'),
                address or analysis.get('address'),
                analysis.get('position_count', len(positions)),
                analysis.get('analysis_text'),
                json.dumps(analysis.get('sections', {})),
                json.dumps(stats) if stats else None,
                provider or 'default'
            ))
            
            result = cursor.fetchone()
            record_id = result[0] if result else None
            
            logger.info(f"保存持仓AI分析结果: type={analysis_type}, key={analysis_key}, id={record_id}")
            return record_id

    def get_positions_ai_analysis(
        self,
        analysis_type: str,
        positions: List[Dict[str, Any]],
        coin: Optional[str] = None,
        address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取已存在的持仓 AI 分析结果
        
        Args:
            analysis_type: 分析类型 (overall/coin/single)
            positions: 持仓数据列表（用于生成key）
            coin: 币种
            address: 地址
            
        Returns:
            AI 分析结果字典，如果不存在返回 None
        """
        analysis_key = self._generate_positions_analysis_key(
            analysis_type, positions, coin, address
        )
        
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT *
                FROM positions_ai_analysis
                WHERE analysis_key = %s
            """, (analysis_key,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            result = dict(row)
            # 解析 JSON 字段
            if result.get('sections'):
                if isinstance(result['sections'], str):
                    result['sections'] = json.loads(result['sections'])
            if result.get('stats_snapshot'):
                if isinstance(result['stats_snapshot'], str):
                    result['stats_snapshot'] = json.loads(result['stats_snapshot'])
            
            return result

    def get_positions_ai_analysis_by_key(self, analysis_key: str) -> Optional[Dict[str, Any]]:
        """
        通过 key 直接获取持仓 AI 分析结果
        
        Args:
            analysis_key: 分析唯一标识符
            
        Returns:
            AI 分析结果字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT *
                FROM positions_ai_analysis
                WHERE analysis_key = %s
            """, (analysis_key,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            result = dict(row)
            if result.get('sections'):
                if isinstance(result['sections'], str):
                    result['sections'] = json.loads(result['sections'])
            if result.get('stats_snapshot'):
                if isinstance(result['stats_snapshot'], str):
                    result['stats_snapshot'] = json.loads(result['stats_snapshot'])
            
            return result

    def delete_positions_ai_analysis(self, analysis_key: str) -> bool:
        """删除持仓 AI 分析结果"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM positions_ai_analysis
                WHERE analysis_key = %s
            """, (analysis_key,))
            return cursor.rowcount > 0

    def clear_positions_ai_analysis(self, analysis_type: Optional[str] = None) -> int:
        """
        清空持仓 AI 分析结果
        
        Args:
            analysis_type: 如果指定，只清空该类型的分析
            
        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if analysis_type:
                cursor.execute("""
                    DELETE FROM positions_ai_analysis
                    WHERE analysis_type = %s
                """, (analysis_type,))
            else:
                cursor.execute("DELETE FROM positions_ai_analysis")
            return cursor.rowcount

    # ==================== 交易员 AI 分析 ====================

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
                INSERT INTO trader_ai_analysis (
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
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(address) DO UPDATE SET
                    rating = EXCLUDED.rating,
                    overall_score = EXCLUDED.overall_score,
                    analysis_text = EXCLUDED.analysis_text,
                    summary = EXCLUDED.summary,
                    strengths = EXCLUDED.strengths,
                    risks = EXCLUDED.risks,
                    trading_style = EXCLUDED.trading_style,
                    copy_trading_advice = EXCLUDED.copy_trading_advice,
                    improvement_suggestions = EXCLUDED.improvement_suggestions,
                    updated_at = CURRENT_TIMESTAMP
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
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT *
                FROM trader_ai_analysis
                WHERE address = %s
            """, (address,))

            row = cursor.fetchone()
            if not row:
                return None

            return dict(row)
