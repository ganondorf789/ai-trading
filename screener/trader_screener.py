"""
Hyperliquid 优质交易者筛选器
自动分析交易者表现并筛选优质地址
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import requests
from loguru import logger
import pandas as pd
import numpy as np
import pendulum

from hyperliquid.info import Info
from hyperliquid.utils import constants

# 上海时区
SHANGHAI_TZ = "Asia/Shanghai"


class QualityRating(Enum):
    """交易者质量评级"""
    S_TIER = "S"  # 顶级交易者
    A_TIER = "A"  # 优秀交易者
    B_TIER = "B"  # 良好交易者
    C_TIER = "C"  # 一般交易者
    D_TIER = "D"  # 较差交易者
    F_TIER = "F"  # 不推荐


@dataclass
class TraderMetrics:
    """交易者指标"""
    address: str
    
    # 基础统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # 盈亏指标
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_volume: float = 0.0
    
    # 收益率指标
    roi: float = 0.0  # 投资回报率
    avg_profit_per_trade: float = 0.0
    
    # 风险指标
    win_rate: float = 0.0  # 胜率
    profit_factor: float = 0.0  # 盈亏比
    max_drawdown: float = 0.0  # 最大回撤
    sharpe_ratio: float = 0.0  # 夏普比率
    sortino_ratio: float = 0.0  # 索提诺比率
    calmar_ratio: float = 0.0  # 卡玛比率
    
    # 交易特征
    avg_holding_time_hours: float = 0.0  # 平均持仓时间
    trade_frequency_per_day: float = 0.0  # 日均交易频率
    avg_leverage: float = 1.0  # 平均杠杆
    
    # 活跃度
    active_days: int = 0
    last_trade_time: Optional[datetime] = None
    first_trade_time: Optional[datetime] = None
    
    # 持仓信息
    current_positions: int = 0
    current_equity: float = 0.0
    
    # 综合评分
    overall_score: float = 0.0
    rating: QualityRating = QualityRating.F_TIER

    # 分项评分
    profitability_score: float = 0.0
    risk_score: float = 0.0
    consistency_score: float = 0.0
    activity_score: float = 0.0

    # 新增分析字段
    avg_trade_price: float = 0.0  # 平均交易价格
    avg_trade_size: float = 0.0  # 平均交易规模（USD）
    max_single_win: float = 0.0  # 最大单笔盈利
    max_single_loss: float = 0.0  # 最大单笔亏损
    max_consecutive_wins: int = 0  # 最大连续盈利次数
    max_consecutive_losses: int = 0  # 最大连续亏损次数
    avg_win_amount: float = 0.0  # 盈利交易平均收益
    avg_loss_amount: float = 0.0  # 亏损交易平均损失
    unique_symbols: int = 0  # 交易品种数量
    favorite_symbol: str = ""  # 最常交易的品种
    recent_7d_pnl: float = 0.0  # 最近7天PnL
    recent_7d_win_rate: float = 0.0  # 最近7天胜率
    long_short_ratio: float = 0.0  # 多空比例（多单占比）

    # 时间段统计
    daily_pnl: float = 0.0  # 日均PnL
    weekly_pnl: float = 0.0  # 周均PnL
    monthly_pnl: float = 0.0  # 月均PnL
    daily_roi: float = 0.0  # 日均ROI
    weekly_roi: float = 0.0  # 周均ROI
    monthly_roi: float = 0.0  # 月均ROI
    daily_volume: float = 0.0  # 日均交易量
    weekly_volume: float = 0.0  # 周均交易量
    monthly_volume: float = 0.0  # 月均交易量

    # 原始交易记录（可选，用于保存到数据库）
    fills: List[Dict] = field(default_factory=list)

    # 当前持仓（来自 assetPositions）
    asset_positions: List[Dict] = field(default_factory=list)

    def to_dict(self, include_fills: bool = False, include_positions: bool = False) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result['rating'] = self.rating.value
        if self.last_trade_time:
            result['last_trade_time'] = self.last_trade_time.to_iso8601_string()
        if self.first_trade_time:
            result['first_trade_time'] = self.first_trade_time.to_iso8601_string()
        # 默认不包含 fills（数据量可能很大）
        if not include_fills:
            result.pop('fills', None)
        # 默认不包含 asset_positions
        if not include_positions:
            result.pop('asset_positions', None)
        return result


@dataclass
class ScreenerConfig:
    """筛选器配置"""
    # API 配置
    api_url: str = constants.MAINNET_API_URL
    testnet: bool = False
    
    # 数据获取配置
    max_fills_per_trader: int = 0  # 每个交易者最大获取成交数 (0=不限制)
    lookback_days: int = 30  # 回溯天数
    
    # 筛选条件
    min_total_trades: int = 10  # 最小交易次数
    min_win_rate: float = 0.45  # 最小胜率
    min_profit_factor: float = 1.0  # 最小盈亏比
    min_total_pnl: float = 0.0  # 最小总盈利
    max_drawdown: float = 0.5  # 最大回撤限制
    min_active_days: int = 5  # 最小活跃天数
    min_sharpe_ratio: float = 0.0  # 最小夏普比率
    
    # 评分权重
    profitability_weight: float = 0.35  # 盈利能力权重
    risk_weight: float = 0.30  # 风险控制权重
    consistency_weight: float = 0.20  # 稳定性权重
    activity_weight: float = 0.15  # 活跃度权重
    
    # 输出配置
    top_n: int = 20  # 输出前 N 名
    output_file: str = "qualified_traders.json"
    
    # 并发配置
    max_concurrent_requests: int = 3
    request_delay: float = 0.5  # 请求间隔（秒）
    api_call_delay: float = 0.3  # API调用之间的延迟（秒）
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 2.0  # 重试延迟（秒）


class TraderScreener:
    """
    Hyperliquid 优质交易者筛选器
    
    功能：
    - 获取和分析交易者历史数据
    - 计算多维度质量指标
    - 综合评分和排名
    - 输出优质交易者地址列表
    """
    
    def __init__(self, config: Optional[ScreenerConfig] = None):
        """
        初始化筛选器
        
        Args:
            config: 筛选器配置
        """
        self.config = config or ScreenerConfig()
        self.api_url = constants.TESTNET_API_URL if self.config.testnet else self.config.api_url
        self.info = Info(self.api_url, skip_ws=True)
        
        self._analyzed_traders: Dict[str, TraderMetrics] = {}
        self._failed_addresses: List[str] = []
        
        logger.info(f"交易者筛选器初始化完成，API: {self.api_url}")
    
    def _api_call_with_retry(self, func, *args, **kwargs):
        """带重试的 API 调用"""
        for attempt in range(self.config.max_retries):
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error_str = str(e)
                # 检查是否是 429 错误
                if "429" in error_str:
                    wait_time = self.config.retry_delay * (attempt + 1)
                    logger.warning(f"请求频率过高，等待 {wait_time} 秒后重试... (尝试 {attempt + 1}/{self.config.max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.debug(f"API 调用失败: {e}")
                    if attempt < self.config.max_retries - 1:
                        time.sleep(self.config.retry_delay)
                    else:
                        raise
        return None

    def _get_user_state(self, address: str) -> Optional[Dict[str, Any]]:
        """获取用户状态"""
        try:
            return self._api_call_with_retry(self.info.user_state, address)
        except Exception as e:
            logger.debug(f"获取用户状态失败 {address[:10]}...: {e}")
            return None

    def _get_user_fills(self, address: str, limit: int = None) -> List[Dict]:
        """获取用户成交记录"""
        try:
            limit = limit if limit is not None else self.config.max_fills_per_trader
            fills = self._api_call_with_retry(self.info.user_fills, address)
            if fills is None:
                return []
            # limit=0 表示不限制
            return fills[:limit] if limit > 0 and len(fills) > limit else fills
        except Exception as e:
            logger.debug(f"获取用户成交记录失败 {address[:10]}...: {e}")
            return []

    def _get_user_fills_by_time(
        self,
        address: str,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """按时间范围获取用户成交记录"""
        try:
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int((end_time or pendulum.now(SHANGHAI_TZ)).timestamp() * 1000)

            fills = self._api_call_with_retry(
                self.info.user_fills_by_time, address, start_ms, end_ms
            )
            return fills if fills else []
        except Exception as e:
            logger.debug(f"按时间获取成交记录失败 {address[:10]}...: {e}")
            # 回退到普通方法
            time.sleep(self.config.api_call_delay)
            return self._get_user_fills(address)
    
    def _calculate_metrics_from_fills(
        self,
        address: str,
        fills: List[Dict],
        user_state: Optional[Dict] = None
    ) -> TraderMetrics:
        """
        从成交记录计算交易者指标
        
        Args:
            address: 交易者地址
            fills: 成交记录列表
            user_state: 用户状态
        
        Returns:
            TraderMetrics 对象
        """
        metrics = TraderMetrics(address=address)
        
        if not fills:
            return metrics
        
        # 基础统计
        metrics.total_trades = len(fills)
        
        # 按时间排序
        fills_sorted = sorted(fills, key=lambda x: x.get('time', 0))
        
        # 时间范围（使用上海时区）
        if fills_sorted:
            metrics.first_trade_time = pendulum.from_timestamp(
                fills_sorted[0].get('time', 0) / 1000,
                tz=SHANGHAI_TZ
            )
            metrics.last_trade_time = pendulum.from_timestamp(
                fills_sorted[-1].get('time', 0) / 1000,
                tz=SHANGHAI_TZ
            )
        
        # 盈亏计算
        total_profit = 0.0
        total_loss = 0.0
        pnl_list = []
        daily_pnl_dict: Dict[str, float] = {}
        weekly_pnl_dict: Dict[str, float] = {}
        monthly_pnl_dict: Dict[str, float] = {}
        daily_volume_dict: Dict[str, float] = {}
        weekly_volume_dict: Dict[str, float] = {}
        monthly_volume_dict: Dict[str, float] = {}

        # 新增统计变量
        total_price = 0.0
        total_size_usd = 0.0
        symbol_counts: Dict[str, int] = {}
        long_count = 0
        short_count = 0
        win_amounts = []
        loss_amounts = []
        recent_7d_start = pendulum.now(SHANGHAI_TZ).subtract(days=7)
        recent_7d_pnl = 0.0
        recent_7d_wins = 0
        recent_7d_trades = 0

        for fill in fills:
            pnl = float(fill.get('closedPnl', 0))
            price = float(fill.get('px', 0))
            size = float(fill.get('sz', 0))
            volume = price * size

            metrics.total_volume += volume
            metrics.realized_pnl += pnl
            pnl_list.append(pnl)

            # 新增：价格和规模统计
            total_price += price
            total_size_usd += volume

            # 新增：品种统计
            symbol = fill.get('coin', '')
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

            # 新增：多空统计
            side = fill.get('side', '').upper()
            if side == 'B' or side == 'BUY':
                long_count += 1
            elif side == 'A' or side == 'SELL':
                short_count += 1

            if pnl > 0:
                metrics.winning_trades += 1
                total_profit += pnl
                win_amounts.append(pnl)
            elif pnl < 0:
                metrics.losing_trades += 1
                total_loss += abs(pnl)
                loss_amounts.append(abs(pnl))

            # 按天/周/月统计（使用上海时区）
            trade_time = pendulum.from_timestamp(fill.get('time', 0) / 1000, tz=SHANGHAI_TZ)
            day_key = trade_time.format('YYYY-MM-DD')
            week_key = trade_time.format('YYYY-[W]WW')  # ISO周格式
            month_key = trade_time.format('YYYY-MM')

            daily_pnl_dict[day_key] = daily_pnl_dict.get(day_key, 0) + pnl
            weekly_pnl_dict[week_key] = weekly_pnl_dict.get(week_key, 0) + pnl
            monthly_pnl_dict[month_key] = monthly_pnl_dict.get(month_key, 0) + pnl

            daily_volume_dict[day_key] = daily_volume_dict.get(day_key, 0) + volume
            weekly_volume_dict[week_key] = weekly_volume_dict.get(week_key, 0) + volume
            monthly_volume_dict[month_key] = monthly_volume_dict.get(month_key, 0) + volume

            # 新增：最近7天统计
            if trade_time >= recent_7d_start:
                recent_7d_trades += 1
                recent_7d_pnl += pnl
                if pnl > 0:
                    recent_7d_wins += 1
        
        # 活跃天数
        metrics.active_days = len(daily_pnl_dict)

        # 计算日/周/月均值
        if len(daily_pnl_dict) > 0:
            metrics.daily_pnl = sum(daily_pnl_dict.values()) / len(daily_pnl_dict)
            metrics.daily_volume = sum(daily_volume_dict.values()) / len(daily_volume_dict)
        if len(weekly_pnl_dict) > 0:
            metrics.weekly_pnl = sum(weekly_pnl_dict.values()) / len(weekly_pnl_dict)
            metrics.weekly_volume = sum(weekly_volume_dict.values()) / len(weekly_volume_dict)
        if len(monthly_pnl_dict) > 0:
            metrics.monthly_pnl = sum(monthly_pnl_dict.values()) / len(monthly_pnl_dict)
            metrics.monthly_volume = sum(monthly_volume_dict.values()) / len(monthly_volume_dict)

        # 新增指标计算
        if metrics.total_trades > 0:
            metrics.avg_trade_price = total_price / metrics.total_trades
            metrics.avg_trade_size = total_size_usd / metrics.total_trades

        # 最大单笔盈亏
        if pnl_list:
            metrics.max_single_win = max(pnl_list) if max(pnl_list) > 0 else 0
            metrics.max_single_loss = abs(min(pnl_list)) if min(pnl_list) < 0 else 0

        # 平均盈亏金额
        if win_amounts:
            metrics.avg_win_amount = sum(win_amounts) / len(win_amounts)
        if loss_amounts:
            metrics.avg_loss_amount = sum(loss_amounts) / len(loss_amounts)

        # 连续盈亏计算
        current_wins = 0
        current_losses = 0
        for pnl in pnl_list:
            if pnl > 0:
                current_wins += 1
                current_losses = 0
                metrics.max_consecutive_wins = max(metrics.max_consecutive_wins, current_wins)
            elif pnl < 0:
                current_losses += 1
                current_wins = 0
                metrics.max_consecutive_losses = max(metrics.max_consecutive_losses, current_losses)

        # 品种统计
        metrics.unique_symbols = len(symbol_counts)
        if symbol_counts:
            metrics.favorite_symbol = max(symbol_counts, key=symbol_counts.get)

        # 多空比例
        total_sides = long_count + short_count
        if total_sides > 0:
            metrics.long_short_ratio = long_count / total_sides

        # 最近7天统计
        metrics.recent_7d_pnl = recent_7d_pnl
        if recent_7d_trades > 0:
            metrics.recent_7d_win_rate = recent_7d_wins / recent_7d_trades

        # 胜率
        if metrics.total_trades > 0:
            metrics.win_rate = metrics.winning_trades / metrics.total_trades
            metrics.avg_profit_per_trade = metrics.realized_pnl / metrics.total_trades
        
        # 盈亏比
        if total_loss > 0:
            metrics.profit_factor = total_profit / total_loss
        elif total_profit > 0:
            metrics.profit_factor = float('inf')
        
        # 总 PnL
        metrics.total_pnl = metrics.realized_pnl
        
        # 计算交易频率
        if metrics.first_trade_time and metrics.last_trade_time:
            days_active = (metrics.last_trade_time - metrics.first_trade_time).days + 1
            if days_active > 0:
                metrics.trade_frequency_per_day = metrics.total_trades / days_active
        
        # 计算风险指标
        if len(pnl_list) > 1:
            pnl_array = np.array(pnl_list)
            
            # 累积 PnL 曲线
            cumulative_pnl = np.cumsum(pnl_array)
            
            # 最大回撤
            peak = np.maximum.accumulate(cumulative_pnl)
            drawdown = (peak - cumulative_pnl)
            max_dd_abs = np.max(drawdown)
            if np.max(peak) > 0:
                metrics.max_drawdown = max_dd_abs / np.max(peak)
            
            # 夏普比率（假设无风险利率为0）
            if np.std(pnl_array) > 0:
                metrics.sharpe_ratio = np.mean(pnl_array) / np.std(pnl_array) * np.sqrt(252)
            
            # 索提诺比率（只考虑下行风险）
            negative_returns = pnl_array[pnl_array < 0]
            if len(negative_returns) > 0 and np.std(negative_returns) > 0:
                metrics.sortino_ratio = np.mean(pnl_array) / np.std(negative_returns) * np.sqrt(252)

            # Calmar Ratio（年化收益率 / 最大回撤）
            if metrics.max_drawdown > 0 and metrics.first_trade_time and metrics.last_trade_time:
                days_active = (metrics.last_trade_time - metrics.first_trade_time).days + 1
                if days_active > 0:
                    annualized_return = (metrics.total_pnl / days_active) * 365
                    metrics.calmar_ratio = annualized_return / (metrics.max_drawdown * 100)  # 转换为百分比

        # 从用户状态获取当前信息
        if user_state:
            margin = user_state.get('marginSummary', {})
            metrics.current_equity = float(margin.get('accountValue', 0))
            
            positions = user_state.get('assetPositions', [])
            metrics.current_positions = sum(
                1 for p in positions 
                if float(p.get('position', {}).get('szi', 0)) != 0
            )
            
            # 未实现盈亏
            for pos_data in positions:
                pos = pos_data.get('position', {})
                metrics.unrealized_pnl += float(pos.get('unrealizedPnl', 0))
                
                # 平均杠杆
                leverage = pos.get('leverage', {}).get('value', 1)
                if leverage:
                    metrics.avg_leverage = max(metrics.avg_leverage, int(leverage))
            
            # ROI 计算（总ROI和日/周/月ROI）
            if metrics.current_equity > 0:
                metrics.roi = metrics.total_pnl / metrics.current_equity
                metrics.daily_roi = metrics.daily_pnl / metrics.current_equity if metrics.daily_pnl else 0
                metrics.weekly_roi = metrics.weekly_pnl / metrics.current_equity if metrics.weekly_pnl else 0
                metrics.monthly_roi = metrics.monthly_pnl / metrics.current_equity if metrics.monthly_pnl else 0

        return metrics
    
    def _calculate_scores(self, metrics: TraderMetrics) -> TraderMetrics:
        """
        计算综合评分
        
        Args:
            metrics: 交易者指标
        
        Returns:
            更新后的 TraderMetrics
        """
        # 1. 盈利能力评分 (0-100)
        profitability_score = 0.0
        
        # 胜率贡献 (0-30分)
        profitability_score += min(metrics.win_rate * 50, 30)
        
        # 盈亏比贡献 (0-30分)
        if metrics.profit_factor != float('inf'):
            profitability_score += min(metrics.profit_factor * 10, 30)
        else:
            profitability_score += 30
        
        # 总盈利贡献 (0-40分)
        if metrics.total_pnl > 0:
            # 使用对数缩放
            pnl_score = min(np.log10(metrics.total_pnl + 1) * 10, 40)
            profitability_score += pnl_score
        
        metrics.profitability_score = min(profitability_score, 100)
        
        # 2. 风险控制评分 (0-100)
        risk_score = 100.0
        
        # 最大回撤惩罚
        risk_score -= min(metrics.max_drawdown * 100, 50)
        
        # 夏普比率加分
        if metrics.sharpe_ratio > 0:
            risk_score += min(metrics.sharpe_ratio * 10, 30)
        elif metrics.sharpe_ratio < 0:
            risk_score += metrics.sharpe_ratio * 10  # 负分
        
        metrics.risk_score = max(0, min(risk_score, 100))
        
        # 3. 稳定性评分 (0-100)
        consistency_score = 50.0
        
        # 交易次数加分
        consistency_score += min(metrics.total_trades / 10, 20)
        
        # 活跃天数加分
        consistency_score += min(metrics.active_days, 20)
        
        # 盈亏比稳定性
        if metrics.profit_factor > 1.5:
            consistency_score += 10
        
        metrics.consistency_score = min(consistency_score, 100)
        
        # 4. 活跃度评分 (0-100)
        activity_score = 0.0
        
        # 日均交易频率
        activity_score += min(metrics.trade_frequency_per_day * 20, 40)
        
        # 最近交易时间
        if metrics.last_trade_time:
            days_since_last = (pendulum.now(SHANGHAI_TZ) - metrics.last_trade_time).days
            if days_since_last <= 1:
                activity_score += 30
            elif days_since_last <= 7:
                activity_score += 20
            elif days_since_last <= 30:
                activity_score += 10
        
        # 当前持仓
        if metrics.current_positions > 0:
            activity_score += 30
        
        metrics.activity_score = min(activity_score, 100)
        
        # 5. 综合评分
        metrics.overall_score = (
            metrics.profitability_score * self.config.profitability_weight +
            metrics.risk_score * self.config.risk_weight +
            metrics.consistency_score * self.config.consistency_weight +
            metrics.activity_score * self.config.activity_weight
        )
        
        # 6. 确定评级
        if metrics.overall_score >= 85:
            metrics.rating = QualityRating.S_TIER
        elif metrics.overall_score >= 70:
            metrics.rating = QualityRating.A_TIER
        elif metrics.overall_score >= 55:
            metrics.rating = QualityRating.B_TIER
        elif metrics.overall_score >= 40:
            metrics.rating = QualityRating.C_TIER
        elif metrics.overall_score >= 25:
            metrics.rating = QualityRating.D_TIER
        else:
            metrics.rating = QualityRating.F_TIER
        
        return metrics
    
    def _passes_filters(self, metrics: TraderMetrics) -> bool:
        """
        检查交易者是否通过筛选条件
        
        Args:
            metrics: 交易者指标
        
        Returns:
            是否通过筛选
        """
        if metrics.total_trades < self.config.min_total_trades:
            return False
        
        if metrics.win_rate < self.config.min_win_rate:
            return False
        
        if metrics.profit_factor < self.config.min_profit_factor:
            return False
        
        if metrics.total_pnl < self.config.min_total_pnl:
            return False
        
        if metrics.max_drawdown > self.config.max_drawdown:
            return False
        
        if metrics.active_days < self.config.min_active_days:
            return False
        
        if metrics.sharpe_ratio < self.config.min_sharpe_ratio:
            return False
        
        return True
    
    def analyze_trader(self, address: str, store_fills: bool = True) -> Optional[TraderMetrics]:
        """
        分析单个交易者

        Args:
            address: 交易者地址
            store_fills: 是否在 metrics 中存储原始交易记录

        Returns:
            TraderMetrics 或 None
        """
        logger.debug(f"分析交易者: {address[:10]}...")

        try:
            # 获取用户状态
            user_state = self._get_user_state(address)

            # API 调用间延迟
            time.sleep(self.config.api_call_delay)

            # 获取成交记录（使用上海时区）
            start_time = pendulum.now(SHANGHAI_TZ).subtract(days=self.config.lookback_days)
            fills = self._get_user_fills_by_time(address, start_time)

            if not fills:
                logger.debug(f"交易者 {address[:10]}... 无成交记录")
                return None

            # 计算指标
            metrics = self._calculate_metrics_from_fills(address, fills, user_state)

            # 计算评分
            metrics = self._calculate_scores(metrics)

            # 存储原始交易记录
            if store_fills:
                metrics.fills = fills

            # 存储当前持仓（来自 assetPositions）
            if user_state:
                metrics.asset_positions = user_state.get('assetPositions', [])

            # 缓存结果
            self._analyzed_traders[address] = metrics

            return metrics

        except Exception as e:
            logger.error(f"分析交易者失败 {address[:10]}...: {e}")
            self._failed_addresses.append(address)
            return None
    
    async def analyze_traders_async(
        self,
        addresses: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[TraderMetrics]:
        """
        异步分析多个交易者
        
        Args:
            addresses: 交易者地址列表
            progress_callback: 进度回调函数
        
        Returns:
            TraderMetrics 列表
        """
        results = []
        total = len(addresses)
        
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        async def analyze_with_limit(address: str, index: int):
            async with semaphore:
                # 使用线程池执行同步 API 调用
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.analyze_trader, address)
                
                if progress_callback:
                    progress_callback(index + 1, total, address, result)
                
                await asyncio.sleep(self.config.request_delay)
                return result
        
        tasks = [
            analyze_with_limit(addr, i)
            for i, addr in enumerate(addresses)
        ]
        
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results_raw:
            if isinstance(result, TraderMetrics):
                results.append(result)
        
        return results
    
    def analyze_traders(
        self,
        addresses: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[TraderMetrics]:
        """
        同步分析多个交易者
        
        Args:
            addresses: 交易者地址列表
            progress_callback: 进度回调函数
        
        Returns:
            TraderMetrics 列表
        """
        results = []
        total = len(addresses)

        for i, address in enumerate(addresses):
            metrics = self.analyze_trader(address)

            if metrics:
                results.append(metrics)

            if progress_callback:
                progress_callback(i + 1, total, address, metrics)

            # 每个交易者分析完后等待，避免 API 频率限制
            if i < total - 1:  # 最后一个不需要等待
                time.sleep(self.config.request_delay)

        return results
    
    def screen_traders(
        self,
        addresses: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[TraderMetrics]:
        """
        筛选优质交易者
        
        Args:
            addresses: 候选交易者地址列表
            progress_callback: 进度回调
        
        Returns:
            符合条件的交易者列表（按评分排序）
        """
        logger.info(f"开始筛选 {len(addresses)} 个交易者...")
        
        # 分析所有交易者
        all_metrics = self.analyze_traders(addresses, progress_callback)
        
        # 筛选符合条件的
        qualified = [m for m in all_metrics if self._passes_filters(m)]
        
        # 按评分排序
        qualified.sort(key=lambda x: x.overall_score, reverse=True)
        
        # 取前 N 名
        top_traders = qualified[:self.config.top_n]
        
        logger.info(f"筛选完成: {len(top_traders)}/{len(addresses)} 个优质交易者")
        
        return top_traders
    
    async def screen_traders_async(
        self,
        addresses: List[str],
        progress_callback: Optional[callable] = None
    ) -> List[TraderMetrics]:
        """异步筛选优质交易者"""
        logger.info(f"开始异步筛选 {len(addresses)} 个交易者...")
        
        all_metrics = await self.analyze_traders_async(addresses, progress_callback)
        
        qualified = [m for m in all_metrics if self._passes_filters(m)]
        qualified.sort(key=lambda x: x.overall_score, reverse=True)
        
        top_traders = qualified[:self.config.top_n]
        
        logger.info(f"筛选完成: {len(top_traders)}/{len(addresses)} 个优质交易者")
        
        return top_traders
    
    def save_results(
        self,
        traders: List[TraderMetrics],
        filepath: Optional[str] = None
    ):
        """
        保存筛选结果
        
        Args:
            traders: 交易者列表
            filepath: 输出文件路径
        """
        filepath = filepath or self.config.output_file

        output = {
            "timestamp": pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
            "config": {
                "lookback_days": self.config.lookback_days,
                "min_total_trades": self.config.min_total_trades,
                "min_win_rate": self.config.min_win_rate,
                "min_profit_factor": self.config.min_profit_factor,
            },
            "total_analyzed": len(self._analyzed_traders),
            "qualified_count": len(traders),
            "traders": [t.to_dict() for t in traders]
        }
        
        # 确保目录存在
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"结果已保存至: {filepath}")
    
    def print_summary(self, traders: List[TraderMetrics], detailed: bool = False):
        """
        打印筛选结果摘要

        Args:
            traders: 交易者列表
            detailed: 是否显示详细信息
        """
        print("\n" + "=" * 120)
        print("Hyperliquid 优质交易者筛选结果")
        print("=" * 120)
        print(f"分析时间 (上海时区): {pendulum.now(SHANGHAI_TZ).format('YYYY-MM-DD HH:mm:ss')}")
        print(f"筛选条件: 胜率≥{self.config.min_win_rate:.0%}, "
              f"盈亏比≥{self.config.min_profit_factor:.1f}, "
              f"交易次数≥{self.config.min_total_trades}")
        print("-" * 120)

        if not traders:
            print("未找到符合条件的交易者")
            return

        # 主要指标表格
        print(f"{'#':<3} {'等级':<3} {'地址':<14} {'评分':<6} {'胜率':<7} "
              f"{'盈亏比':<7} {'总PnL':<11} {'交易数':<6} {'回撤':<6} "
              f"{'Sharpe':<7} {'活跃天':<6} {'杠杆':<5} {'持仓':<4}")
        print("-" * 120)

        for i, t in enumerate(traders, 1):
            addr_short = f"{t.address[:6]}...{t.address[-4:]}"
            pnl_str = f"${t.total_pnl:,.0f}" if t.total_pnl >= 0 else f"-${abs(t.total_pnl):,.0f}"
            pf_str = f"{t.profit_factor:.2f}" if t.profit_factor != float('inf') else "∞"
            sharpe_str = f"{t.sharpe_ratio:.2f}" if t.sharpe_ratio else "N/A"

            print(f"{i:<3} {t.rating.value:<3} {addr_short:<14} "
                  f"{t.overall_score:>5.1f} {t.win_rate:>6.1%} "
                  f"{pf_str:>6} {pnl_str:>10} {t.total_trades:>5} "
                  f"{t.max_drawdown:>5.1%} {sharpe_str:>6} "
                  f"{t.active_days:>5} {t.avg_leverage:>4.0f}x {t.current_positions:>3}")

        print("=" * 120)

        # 详细信息（可选）
        if detailed:
            print("\n详细指标:")
            print("-" * 120)
            for i, t in enumerate(traders, 1):
                last_trade = t.last_trade_time.format('MM-DD HH:mm') if t.last_trade_time else "N/A"
                print(f"\n[{i}] {t.address}")
                print(f"    基础: 胜率={t.win_rate:.1%}, 盈亏比={t.profit_factor:.2f}, "
                      f"总PnL=${t.total_pnl:,.2f}, 交易数={t.total_trades}")
                print(f"    风险: Sharpe={t.sharpe_ratio:.2f}, Sortino={t.sortino_ratio:.2f}, "
                      f"回撤={t.max_drawdown:.1%}, 最大单亏=${t.max_single_loss:,.2f}")
                print(f"    活跃: 活跃天={t.active_days}, 最后交易={last_trade}, "
                      f"杠杆={t.avg_leverage:.0f}x, 持仓数={t.current_positions}")
                print(f"    交易: 平均价格=${t.avg_trade_price:,.2f}, 平均规模=${t.avg_trade_size:,.2f}, "
                      f"连赢={t.max_consecutive_wins}, 连亏={t.max_consecutive_losses}")
                print(f"    偏好: 品种数={t.unique_symbols}, 最爱={t.favorite_symbol or 'N/A'}, "
                      f"多空比={t.long_short_ratio:.1%}")
                print(f"    近7天: PnL=${t.recent_7d_pnl:,.2f}, 胜率={t.recent_7d_win_rate:.1%}")
                print(f"    平均盈利=${t.avg_win_amount:,.2f}, 平均亏损=${t.avg_loss_amount:,.2f}")

        # 推荐列表
        print(f"\n建议跟单的交易者地址 (评级 A 及以上):")
        for trader in traders:
            if trader.rating in [QualityRating.S_TIER, QualityRating.A_TIER]:
                last_trade = trader.last_trade_time.format('MM-DD') if trader.last_trade_time else "N/A"
                print(f"  [{trader.rating.value}] {trader.address} "
                      f"(胜率:{trader.win_rate:.0%}, PnL:${trader.total_pnl:,.0f}, 最后:{last_trade})")

        print()
    
    def get_sample_addresses(self) -> List[str]:
        """
        获取一些示例交易者地址（用于测试）
        
        实际使用时应从以下来源获取地址：
        - Hyperliquid 公开排行榜
        - 社区分享的优质交易者
        - 链上分析工具
        
        Returns:
            示例地址列表
        """
        # 这些是公开的测试地址，实际使用时需要替换
        return [
            # 可以从 Hyperliquid 排行榜或社区获取真实地址
            # 以下为占位符，需要替换为真实地址
        ]


def discover_active_traders(
    info: Info,
    sample_symbols: List[str] = None,
    limit_per_symbol: int = 50
) -> List[str]:
    """
    发现活跃交易者
    
    通过监控最近交易来发现活跃的交易者地址
    
    Args:
        info: Hyperliquid Info 客户端
        sample_symbols: 要监控的交易对
        limit_per_symbol: 每个交易对获取的交易数
    
    Returns:
        活跃交易者地址列表
    """
    sample_symbols = sample_symbols or ['BTC', 'ETH', 'SOL', 'ARB', 'DOGE']
    traders = set()
    
    logger.info(f"发现活跃交易者，监控交易对: {sample_symbols}")
    
    # 注意：Hyperliquid 的公共交易流 API 有限制
    # 这里只是示例逻辑，实际可能需要其他数据源
    
    return list(traders)

