"""
评分系统模块

负责计算交易者的综合评分和评级
"""
from typing import Optional
import numpy as np
from loguru import logger

from .models import TraderMetrics, QualityRating, ScoreMetrics
from .config import ScoringConfig
from .utils import now_shanghai


class TraderScorer:
    """
    交易者评分器
    
    基于多维度指标计算综合评分和评级
    """
    
    def __init__(self, config: Optional[ScoringConfig] = None):
        """
        初始化评分器
        
        Args:
            config: 评分配置
        """
        self.config = config or ScoringConfig()
    
    def calculate_scores(self, metrics: TraderMetrics) -> TraderMetrics:
        """
        计算综合评分
        
        Args:
            metrics: 交易者指标
        
        Returns:
            更新后的 TraderMetrics
        """
        score = metrics.score
        
        # 1. 盈利能力评分
        score.profitability_score = self._calculate_profitability_score(metrics)
        
        # 2. 风险控制评分
        score.risk_score = self._calculate_risk_score(metrics)
        
        # 3. 稳定性评分
        score.consistency_score = self._calculate_consistency_score(metrics)
        
        # 4. 活跃度评分
        score.activity_score = self._calculate_activity_score(metrics)
        
        # 5. 择时能力评分（技术面）
        score.timing_score = self._calculate_timing_score(metrics)
        
        # 6. 综合评分
        score.overall_score = self._calculate_overall_score(score)
        
        # 7. 确定评级
        score.rating = self._determine_rating(score.overall_score)
        
        return metrics
    
    def _calculate_profitability_score(self, metrics: TraderMetrics) -> float:
        """
        计算盈利能力评分 (0-100)
        
        评分因素:
        - 胜率
        - 盈亏比
        - 总盈利
        """
        config = self.config
        score = 0.0
        
        # 胜率贡献
        win_rate_score = min(
            metrics.trade.win_rate * config.win_rate_multiplier,
            config.win_rate_max_score
        )
        score += win_rate_score
        
        # 盈亏比贡献
        pf = metrics.trade.profit_factor
        if pf != float('inf'):
            pf_score = min(
                pf * config.profit_factor_multiplier,
                config.profit_factor_max_score
            )
        else:
            pf_score = config.profit_factor_max_score
        score += pf_score
        
        # 总盈利贡献（对数缩放）
        if metrics.pnl.total_pnl > 0:
            pnl_score = min(
                np.log10(metrics.pnl.total_pnl + 1) * config.pnl_log_multiplier,
                config.pnl_max_score
            )
            score += pnl_score
        
        return min(score, 100.0)
    
    def _calculate_risk_score(self, metrics: TraderMetrics) -> float:
        """
        计算风险控制评分 (0-100)
        
        评分因素:
        - 最大回撤（惩罚）
        - 夏普比率（加分）
        - 索提诺比率（加分）
        - VaR 指标
        """
        config = self.config
        score = 100.0
        
        # 最大回撤惩罚
        dd_penalty = min(
            metrics.risk.max_drawdown * config.drawdown_penalty_multiplier,
            config.drawdown_max_penalty
        )
        score -= dd_penalty
        
        # 夏普比率加分/减分
        if metrics.risk.sharpe_ratio > 0:
            sharpe_bonus = min(
                metrics.risk.sharpe_ratio * config.sharpe_bonus_multiplier,
                config.sharpe_max_bonus
            )
            score += sharpe_bonus
        elif metrics.risk.sharpe_ratio < 0:
            # 负夏普比率惩罚
            score += metrics.risk.sharpe_ratio * config.sharpe_bonus_multiplier
        
        # 索提诺比率额外加分
        if metrics.risk.sortino_ratio > 0 and metrics.risk.sortino_ratio != float('inf'):
            sortino_bonus = min(metrics.risk.sortino_ratio * 3, 10)
            score += sortino_bonus
        
        # VaR 考虑（高 VaR 轻微惩罚）
        if metrics.risk.var_95 > 0:
            var_penalty = min(np.log10(metrics.risk.var_95 + 1) * 2, 10)
            score -= var_penalty
        
        return max(0.0, min(score, 100.0))
    
    def _calculate_consistency_score(self, metrics: TraderMetrics) -> float:
        """
        计算稳定性评分 (0-100)
        
        评分因素:
        - 交易次数
        - 活跃天数
        - 盈亏比稳定性
        - 连续亏损次数
        """
        config = self.config
        score = 50.0
        
        # 交易次数加分
        trades_bonus = min(
            metrics.trade.total_trades / config.trades_bonus_divisor,
            config.trades_max_bonus
        )
        score += trades_bonus
        
        # 活跃天数加分
        days_bonus = min(metrics.activity.active_days, config.active_days_max_bonus)
        score += days_bonus
        
        # 盈亏比稳定性
        if metrics.trade.profit_factor > config.profit_factor_threshold:
            score += config.profit_factor_bonus
        
        # 连续亏损惩罚
        if metrics.risk.max_consecutive_losses > 5:
            consecutive_loss_penalty = min(
                (metrics.risk.max_consecutive_losses - 5) * 2,
                15
            )
            score -= consecutive_loss_penalty
        
        # 品种多样性加分
        if metrics.trade.unique_symbols >= 3:
            score += 5
        
        return min(score, 100.0)
    
    def _calculate_activity_score(self, metrics: TraderMetrics) -> float:
        """
        计算活跃度评分 (0-100)
        
        评分因素:
        - 日均交易频率
        - 最近交易时间
        - 当前持仓
        """
        config = self.config
        score = 0.0
        
        # 日均交易频率
        freq_score = min(
            metrics.activity.trade_frequency_per_day * config.frequency_multiplier,
            config.frequency_max_score
        )
        score += freq_score
        
        # 最近交易时间
        if metrics.activity.last_trade_time:
            days_since_last = (now_shanghai() - metrics.activity.last_trade_time).days
            
            if days_since_last <= 1:
                score += config.recent_trade_1d_bonus
            elif days_since_last <= 7:
                score += config.recent_trade_7d_bonus
            elif days_since_last <= 30:
                score += config.recent_trade_30d_bonus
        
        # 当前持仓
        if metrics.position.current_positions > 0:
            score += config.has_position_bonus
        
        return min(score, 100.0)
    
    def _calculate_timing_score(self, metrics: TraderMetrics) -> float:
        """
        计算择时能力评分 (0-100)
        
        评分因素（基于技术面分析）:
        - 入场时机质量
        - 趋势顺应能力
        - 波动率择时
        - 持仓健康度
        """
        tech = metrics.technical
        score = 0.0
        weights_sum = 0.0
        
        # 入场时机评分 (权重 40%)
        if tech.entry_timing_score > 0:
            score += tech.entry_timing_score * 0.40
            weights_sum += 0.40
        
        # 趋势顺应率 (权重 25%)
        if tech.trend_trades > 0:
            trend_score = tech.trend_alignment_rate * 100
            score += trend_score * 0.25
            weights_sum += 0.25
        
        # 波动率择时 (权重 20%)
        if tech.volatility_timing_score > 0:
            score += tech.volatility_timing_score * 0.20
            weights_sum += 0.20
        
        # 持仓健康度 (权重 15%)
        if tech.position_health_score > 0:
            score += tech.position_health_score * 0.15
            weights_sum += 0.15
        
        # 归一化
        if weights_sum > 0:
            return score / weights_sum
        
        # 没有技术面数据时返回默认分数
        return 50.0
    
    def _calculate_overall_score(self, score: ScoreMetrics) -> float:
        """
        计算综合评分
        
        Args:
            score: 评分指标对象
        
        Returns:
            综合评分
        """
        config = self.config
        
        overall = (
            score.profitability_score * config.profitability_weight +
            score.risk_score * config.risk_weight +
            score.consistency_score * config.consistency_weight +
            score.activity_score * config.activity_weight +
            score.timing_score * config.timing_weight
        )
        
        return overall
    
    def _determine_rating(self, overall_score: float) -> QualityRating:
        """
        确定质量等级
        
        Args:
            overall_score: 综合评分
        
        Returns:
            QualityRating 枚举值
        """
        thresholds = self.config.rating_thresholds
        
        if overall_score >= thresholds['S']:
            return QualityRating.S_TIER
        elif overall_score >= thresholds['A']:
            return QualityRating.A_TIER
        elif overall_score >= thresholds['B']:
            return QualityRating.B_TIER
        elif overall_score >= thresholds['C']:
            return QualityRating.C_TIER
        elif overall_score >= thresholds['D']:
            return QualityRating.D_TIER
        else:
            return QualityRating.F_TIER


class CustomScorer(TraderScorer):
    """
    自定义评分器
    
    允许通过回调函数自定义评分逻辑
    """
    
    def __init__(
        self,
        config: Optional[ScoringConfig] = None,
        profitability_scorer=None,
        risk_scorer=None,
        consistency_scorer=None,
        activity_scorer=None
    ):
        """
        初始化自定义评分器
        
        Args:
            config: 评分配置
            profitability_scorer: 盈利能力评分函数
            risk_scorer: 风险控制评分函数
            consistency_scorer: 稳定性评分函数
            activity_scorer: 活跃度评分函数
        """
        super().__init__(config)
        self._profitability_scorer = profitability_scorer
        self._risk_scorer = risk_scorer
        self._consistency_scorer = consistency_scorer
        self._activity_scorer = activity_scorer
    
    def _calculate_profitability_score(self, metrics: TraderMetrics) -> float:
        if self._profitability_scorer:
            return self._profitability_scorer(metrics, self.config)
        return super()._calculate_profitability_score(metrics)
    
    def _calculate_risk_score(self, metrics: TraderMetrics) -> float:
        if self._risk_scorer:
            return self._risk_scorer(metrics, self.config)
        return super()._calculate_risk_score(metrics)
    
    def _calculate_consistency_score(self, metrics: TraderMetrics) -> float:
        if self._consistency_scorer:
            return self._consistency_scorer(metrics, self.config)
        return super()._calculate_consistency_score(metrics)
    
    def _calculate_activity_score(self, metrics: TraderMetrics) -> float:
        if self._activity_scorer:
            return self._activity_scorer(metrics, self.config)
        return super()._calculate_activity_score(metrics)


# 便捷函数
def calculate_scores(
    metrics: TraderMetrics,
    config: Optional[ScoringConfig] = None
) -> TraderMetrics:
    """
    计算评分（便捷函数）
    
    Args:
        metrics: 交易者指标
        config: 评分配置
    
    Returns:
        更新后的 TraderMetrics
    """
    scorer = TraderScorer(config)
    return scorer.calculate_scores(metrics)


def get_rating_description(rating: QualityRating) -> str:
    """
    获取评级描述
    
    Args:
        rating: 质量评级
    
    Returns:
        评级描述字符串
    """
    descriptions = {
        QualityRating.S_TIER: "顶级交易者 - 强烈推荐跟单",
        QualityRating.A_TIER: "优秀交易者 - 推荐跟单",
        QualityRating.B_TIER: "良好交易者 - 可以考虑跟单",
        QualityRating.C_TIER: "一般交易者 - 谨慎跟单",
        QualityRating.D_TIER: "较差交易者 - 不建议跟单",
        QualityRating.F_TIER: "不推荐 - 风险较高",
    }
    return descriptions.get(rating, "未知评级")


def get_score_breakdown(metrics: TraderMetrics) -> dict:
    """
    获取评分细分
    
    Args:
        metrics: 交易者指标
    
    Returns:
        评分细分字典
    """
    score = metrics.score
    tech = metrics.technical
    
    return {
        'overall': {
            'score': score.overall_score,
            'rating': score.rating.value,
            'description': get_rating_description(score.rating),
        },
        'breakdown': {
            'profitability': {
                'score': score.profitability_score,
                'weight': 0.30,
                'weighted_score': score.profitability_score * 0.30,
            },
            'risk': {
                'score': score.risk_score,
                'weight': 0.25,
                'weighted_score': score.risk_score * 0.25,
            },
            'consistency': {
                'score': score.consistency_score,
                'weight': 0.20,
                'weighted_score': score.consistency_score * 0.20,
            },
            'activity': {
                'score': score.activity_score,
                'weight': 0.15,
                'weighted_score': score.activity_score * 0.15,
            },
            'timing': {
                'score': score.timing_score,
                'weight': 0.10,
                'weighted_score': score.timing_score * 0.10,
            },
        },
        'key_factors': {
            'win_rate': f"{metrics.trade.win_rate:.1%}",
            'profit_factor': (
                f"{metrics.trade.profit_factor:.2f}"
                if metrics.trade.profit_factor != float('inf')
                else "∞"
            ),
            'max_drawdown': f"{metrics.risk.max_drawdown:.1%}",
            'sharpe_ratio': f"{metrics.risk.sharpe_ratio:.2f}",
            'total_trades': metrics.trade.total_trades,
            'active_days': metrics.activity.active_days,
        },
        'technical_factors': {
            'entry_timing_score': f"{tech.entry_timing_score:.1f}",
            'trend_alignment_rate': f"{tech.trend_alignment_rate:.1%}",
            'trend_win_rate': f"{tech.trend_win_rate:.1%}",
            'counter_trend_win_rate': f"{tech.counter_trend_win_rate:.1%}",
            'position_health_score': f"{tech.position_health_score:.1f}",
            'volatility_timing_score': f"{tech.volatility_timing_score:.1f}",
            'atr_normalized_pnl': f"{tech.atr_normalized_pnl:.2f}",
        }
    }
