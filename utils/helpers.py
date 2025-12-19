"""
辅助工具函数
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np


def format_number(value: float, decimals: int = 2) -> str:
    """
    格式化数字
    
    Args:
        value: 数值
        decimals: 小数位数
    
    Returns:
        格式化后的字符串
    """
    if abs(value) >= 1_000_000:
        return f"{value/1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.{decimals}f}K"
    else:
        return f"{value:.{decimals}f}"


def format_percent(value: float, decimals: int = 2) -> str:
    """
    格式化百分比
    
    Args:
        value: 数值 (0-1)
        decimals: 小数位数
    
    Returns:
        格式化后的字符串
    """
    return f"{value * 100:.{decimals}f}%"


def format_usd(value: float, decimals: int = 2) -> str:
    """
    格式化美元金额
    
    Args:
        value: 金额
        decimals: 小数位数
    
    Returns:
        格式化后的字符串
    """
    if value >= 0:
        return f"${value:,.{decimals}f}"
    else:
        return f"-${abs(value):,.{decimals}f}"


def timestamp_to_datetime(ts: int) -> datetime:
    """
    时间戳转 datetime
    
    Args:
        ts: 时间戳（毫秒或秒）
    
    Returns:
        datetime 对象
    """
    if ts > 1e12:  # 毫秒
        return datetime.fromtimestamp(ts / 1000)
    return datetime.fromtimestamp(ts)


def datetime_to_timestamp(dt: datetime, milliseconds: bool = True) -> int:
    """
    datetime 转时间戳
    
    Args:
        dt: datetime 对象
        milliseconds: 是否返回毫秒
    
    Returns:
        时间戳
    """
    ts = dt.timestamp()
    if milliseconds:
        return int(ts * 1000)
    return int(ts)


def round_to_tick(value: float, tick_size: float) -> float:
    """
    按照 tick size 取整
    
    Args:
        value: 原始值
        tick_size: tick size
    
    Returns:
        取整后的值
    """
    return round(value / tick_size) * tick_size


def calculate_pnl_percent(
    entry_price: float,
    exit_price: float,
    is_long: bool,
    leverage: int = 1
) -> float:
    """
    计算盈亏百分比
    
    Args:
        entry_price: 入场价
        exit_price: 出场价
        is_long: 是否做多
        leverage: 杠杆
    
    Returns:
        盈亏百分比
    """
    if is_long:
        pnl_pct = (exit_price - entry_price) / entry_price
    else:
        pnl_pct = (entry_price - exit_price) / entry_price
    
    return pnl_pct * leverage


def calculate_liquidation_price(
    entry_price: float,
    leverage: int,
    is_long: bool,
    maintenance_margin_rate: float = 0.005
) -> float:
    """
    计算清算价格
    
    Args:
        entry_price: 入场价
        leverage: 杠杆
        is_long: 是否做多
        maintenance_margin_rate: 维持保证金率
    
    Returns:
        清算价格
    """
    if is_long:
        # 多仓清算价 = 入场价 * (1 - 1/杠杆 + 维持保证金率)
        liq_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)
    else:
        # 空仓清算价 = 入场价 * (1 + 1/杠杆 - 维持保证金率)
        liq_price = entry_price * (1 + 1/leverage - maintenance_margin_rate)
    
    return liq_price


def resample_ohlcv(
    df: pd.DataFrame,
    target_timeframe: str
) -> pd.DataFrame:
    """
    重采样 OHLCV 数据
    
    Args:
        df: OHLCV DataFrame
        target_timeframe: 目标时间周期 (e.g., '4h', '1d')
    
    Returns:
        重采样后的 DataFrame
    """
    resampled = df.resample(target_timeframe).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    return resampled


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率
        periods_per_year: 每年交易周期数
    
    Returns:
        夏普比率
    """
    if len(returns) < 2:
        return 0.0
    
    excess_returns = returns - risk_free_rate / periods_per_year
    
    if excess_returns.std() == 0:
        return 0.0
    
    sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)
    return sharpe


def calculate_max_drawdown(equity_curve: pd.Series) -> tuple:
    """
    计算最大回撤
    
    Args:
        equity_curve: 权益曲线
    
    Returns:
        (最大回撤, 回撤开始索引, 回撤结束索引)
    """
    cummax = equity_curve.cummax()
    drawdown = (equity_curve - cummax) / cummax
    
    max_dd = drawdown.min()
    end_idx = drawdown.idxmin()
    
    # 找到回撤开始点
    peak_equity = equity_curve[:end_idx].max()
    start_idx = equity_curve[:end_idx][equity_curve[:end_idx] == peak_equity].index[-1]
    
    return abs(max_dd), start_idx, end_idx


def calculate_win_rate(trades: List[Dict[str, Any]]) -> float:
    """
    计算胜率
    
    Args:
        trades: 交易记录列表
    
    Returns:
        胜率 (0-1)
    """
    if not trades:
        return 0.0
    
    wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
    return wins / len(trades)


def calculate_profit_factor(trades: List[Dict[str, Any]]) -> float:
    """
    计算盈亏比
    
    Args:
        trades: 交易记录列表
    
    Returns:
        盈亏比
    """
    if not trades:
        return 0.0
    
    gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
    gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
    
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
    
    return gross_profit / gross_loss

