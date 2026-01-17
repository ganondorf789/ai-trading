"""
工具函数模块
"""
import re
from typing import Tuple, List, Dict, Any, Optional
import pendulum
import numpy as np

# 上海时区
SHANGHAI_TZ = "Asia/Shanghai"


def timestamp_to_pendulum(ts_ms: int, tz: str = SHANGHAI_TZ) -> pendulum.DateTime:
    """
    毫秒时间戳转 pendulum 时间
    
    Args:
        ts_ms: 毫秒时间戳
        tz: 时区
    
    Returns:
        pendulum.DateTime 对象
    """
    return pendulum.from_timestamp(ts_ms / 1000, tz=tz)


def get_time_keys(trade_time: pendulum.DateTime) -> Tuple[str, str, str]:
    """
    获取日/周/月 key
    
    Args:
        trade_time: 交易时间
    
    Returns:
        (day_key, week_key, month_key) 元组
    """
    return (
        trade_time.format('YYYY-MM-DD'),
        trade_time.format('YYYY-[W]WW'),
        trade_time.format('YYYY-MM')
    )


def now_shanghai() -> pendulum.DateTime:
    """获取当前上海时间"""
    return pendulum.now(SHANGHAI_TZ)


def calculate_trade_type(dir_val: str, start_position: float) -> Optional[str]:
    """
    根据 dir 和 start_position 计算交易类型
    
    Args:
        dir_val: 方向字符串，如 'Open Long', 'Close Short' 等
        start_position: 开始仓位
    
    Returns:
        交易类型: open_long/add_long/close_long/open_short/add_short/close_short
    """
    if not dir_val:
        return None
    
    start_pos = start_position or 0
    
    if 'Open' in dir_val:
        if 'Long' in dir_val:
            return 'open_long' if start_pos == 0 else 'add_long'
        elif 'Short' in dir_val:
            return 'open_short' if start_pos == 0 else 'add_short'
    elif 'Close' in dir_val:
        if 'Long' in dir_val:
            return 'close_long'
        elif 'Short' in dir_val:
            return 'close_short'
    
    return None


def validate_address(address: str) -> bool:
    """
    验证以太坊地址格式
    
    Args:
        address: 交易者地址
    
    Returns:
        是否为有效地址
    """
    if not address:
        return False
    # 以太坊地址：0x 开头，后跟 40 个十六进制字符
    pattern = r'^0x[a-fA-F0-9]{40}$'
    return bool(re.match(pattern, address))


def short_address(address: str, prefix: int = 6, suffix: int = 4) -> str:
    """
    缩短地址显示
    
    Args:
        address: 完整地址
        prefix: 前缀长度
        suffix: 后缀长度
    
    Returns:
        缩短后的地址
    """
    if len(address) <= prefix + suffix + 3:
        return address
    return f"{address[:prefix]}...{address[-suffix:]}"


def format_pnl(pnl: float) -> str:
    """格式化 PnL 显示"""
    if pnl >= 0:
        return f"${pnl:,.2f}"
    return f"-${abs(pnl):,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """格式化百分比显示"""
    return f"{value * 100:.{decimals}f}%"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    安全除法，避免除零错误
    
    Args:
        numerator: 分子
        denominator: 分母
        default: 默认值（当分母为0时返回）
    
    Returns:
        除法结果或默认值
    """
    if denominator == 0:
        return default
    return numerator / denominator


def calculate_max_drawdown(pnl_series: List[float]) -> Tuple[float, float]:
    """
    计算最大回撤
    
    Args:
        pnl_series: PnL 序列
    
    Returns:
        (最大回撤比例, 最大回撤绝对值)
    """
    if len(pnl_series) < 2:
        return 0.0, 0.0
    
    pnl_array = np.array(pnl_series)
    cumulative_pnl = np.cumsum(pnl_array)
    peak = np.maximum.accumulate(cumulative_pnl)
    drawdown = peak - cumulative_pnl
    max_dd_abs = float(np.max(drawdown))
    
    max_peak = float(np.max(peak))
    if max_peak > 0:
        max_dd_ratio = max_dd_abs / max_peak
    else:
        max_dd_ratio = 0.0
    
    return max_dd_ratio, max_dd_abs


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    annualization_factor: float = 252
) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益序列
        risk_free_rate: 无风险利率
        annualization_factor: 年化因子（默认252个交易日）
    
    Returns:
        夏普比率
    """
    if len(returns) < 2:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    
    std = np.std(excess_returns)
    if std == 0:
        return 0.0
    
    return float(np.mean(excess_returns) / std * np.sqrt(annualization_factor))


def calculate_sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    annualization_factor: float = 252
) -> float:
    """
    计算索提诺比率（只考虑下行风险）
    
    Args:
        returns: 收益序列
        risk_free_rate: 无风险利率
        annualization_factor: 年化因子
    
    Returns:
        索提诺比率
    """
    if len(returns) < 2:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    negative_returns = excess_returns[excess_returns < 0]
    
    if len(negative_returns) == 0:
        # 没有负收益时返回一个较大的有限值，而不是Infinity
        return 999.0 if np.mean(excess_returns) > 0 else 0.0
    
    downside_std = np.std(negative_returns)
    if downside_std == 0:
        return 0.0
    
    return float(np.mean(excess_returns) / downside_std * np.sqrt(annualization_factor))


def calculate_calmar_ratio(
    total_return: float,
    max_drawdown: float,
    days: int
) -> float:
    """
    计算卡玛比率（年化收益率 / 最大回撤）
    
    Args:
        total_return: 总收益
        max_drawdown: 最大回撤（小数形式）
        days: 交易天数
    
    Returns:
        卡玛比率
    """
    if max_drawdown <= 0 or days <= 0:
        return 0.0
    
    annualized_return = (total_return / days) * 365
    return annualized_return / (max_drawdown * 100)


def calculate_var(
    pnl_list: List[float],
    confidence: float = 0.95
) -> float:
    """
    计算 Value at Risk (VaR)
    
    Args:
        pnl_list: PnL 列表
        confidence: 置信水平
    
    Returns:
        VaR 值（正数表示潜在损失）
    """
    if len(pnl_list) < 2:
        return 0.0
    return float(-np.percentile(pnl_list, (1 - confidence) * 100))


def calculate_expected_shortfall(
    pnl_list: List[float],
    confidence: float = 0.95
) -> float:
    """
    计算条件 VaR (CVaR/Expected Shortfall)
    
    Args:
        pnl_list: PnL 列表
        confidence: 置信水平
    
    Returns:
        CVaR 值
    """
    if len(pnl_list) < 2:
        return 0.0
    
    var = calculate_var(pnl_list, confidence)
    losses_beyond_var = [p for p in pnl_list if p <= -var]
    
    if not losses_beyond_var:
        return var
    
    return float(-np.mean(losses_beyond_var))


def calculate_consecutive_streaks(pnl_list: List[float]) -> Tuple[int, int]:
    """
    计算最大连续盈亏次数
    
    Args:
        pnl_list: PnL 列表
    
    Returns:
        (最大连续盈利, 最大连续亏损)
    """
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0
    
    for pnl in pnl_list:
        if pnl > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif pnl < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
        # pnl == 0 时不重置
    
    return max_wins, max_losses


def calculate_holding_time(fills: List[Dict[str, Any]]) -> float:
    """
    计算平均持仓时间（小时）
    
    Args:
        fills: 成交记录列表
    
    Returns:
        平均持仓时间（小时）
    """
    positions: Dict[str, Dict] = {}  # symbol -> {open_time, side}
    holding_times = []
    
    sorted_fills = sorted(fills, key=lambda x: x.get('time', 0))
    
    for fill in sorted_fills:
        symbol = fill.get('coin')
        trade_type = fill.get('trade_type', '')
        trade_time = fill.get('time', 0)
        
        if not symbol or not trade_type:
            continue
        
        if 'open' in trade_type:
            positions[symbol] = {'open_time': trade_time, 'side': trade_type}
        elif 'close' in trade_type and symbol in positions:
            open_time = positions[symbol]['open_time']
            holding_hours = (trade_time - open_time) / (1000 * 3600)
            if holding_hours > 0:
                holding_times.append(holding_hours)
            del positions[symbol]
    
    return float(np.mean(holding_times)) if holding_times else 0.0


def aggregate_by_period(
    fills: List[Dict[str, Any]],
    value_key: str = 'closedPnl'
) -> Tuple[Dict[str, float], Dict[str, float], Dict[str, float]]:
    """
    按日/周/月聚合数据
    
    Args:
        fills: 成交记录列表
        value_key: 要聚合的字段
    
    Returns:
        (daily_dict, weekly_dict, monthly_dict)
    """
    daily: Dict[str, float] = {}
    weekly: Dict[str, float] = {}
    monthly: Dict[str, float] = {}
    
    for fill in fills:
        value = float(fill.get(value_key, 0))
        trade_time = timestamp_to_pendulum(fill.get('time', 0))
        day_key, week_key, month_key = get_time_keys(trade_time)
        
        daily[day_key] = daily.get(day_key, 0) + value
        weekly[week_key] = weekly.get(week_key, 0) + value
        monthly[month_key] = monthly.get(month_key, 0) + value
    
    return daily, weekly, monthly


def rebuild_positions_from_fills(fills: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从成交记录重建仓位历史
    
    将多笔 fills 聚合成完整的仓位周期（开仓→平仓）。
    这样可以更准确地计算胜率、盈亏笔数等指标。
    
    Args:
        fills: 成交记录列表（需要包含 trade_type 字段）
    
    Returns:
        仓位历史列表，每个仓位包含：
        - coin: 交易对
        - direction: 方向 ('long' 或 'short')
        - open_time: 开仓时间（毫秒时间戳）
        - close_time: 平仓时间（毫秒时间戳，未平仓为 None）
        - max_size: 最大仓位
        - avg_entry_price: 平均开仓价格
        - avg_close_price: 平均平仓价格
        - total_volume: 总交易量
        - realized_pnl: 已实现盈亏
        - open_trades: 开仓交易次数
        - close_trades: 平仓交易次数
        - holding_hours: 持仓时长（小时）
        - status: 状态 ('open' 或 'closed')
    """
    if not fills:
        return []
    
    # 按时间排序
    sorted_fills = sorted(fills, key=lambda x: x.get('time', 0))
    
    # 按币种分组处理
    positions_by_coin: Dict[str, Dict] = {}  # 当前持仓状态
    position_history: List[Dict] = []
    
    for fill in sorted_fills:
        fill_coin = fill.get('coin', '')
        trade_type = fill.get('trade_type', '')
        time_ms = fill.get('time', 0)
        px = float(fill.get('px', 0) or 0)
        sz = float(fill.get('sz', 0) or 0)
        closed_pnl = float(fill.get('closedPnl', 0) or 0)
        
        if not trade_type or not fill_coin:
            continue
        
        volume = px * sz
        
        # 开仓（从零仓位）
        if trade_type in ('open_long', 'open_short'):
            # 如果有旧的未平仓仓位，先关闭它（异常情况）
            if fill_coin in positions_by_coin:
                old_pos = positions_by_coin[fill_coin]
                old_pos['status'] = 'closed'
                old_pos['close_time'] = time_ms
                if old_pos['open_time'] and time_ms:
                    old_pos['holding_hours'] = (time_ms - old_pos['open_time']) / (1000 * 3600)
                position_history.append(old_pos)
            
            # 创建新仓位
            direction = 'long' if 'long' in trade_type else 'short'
            positions_by_coin[fill_coin] = {
                'coin': fill_coin,
                'direction': direction,
                'open_time': time_ms,
                'close_time': None,
                'max_size': sz,
                'current_size': sz,
                'avg_entry_price': px,
                'total_entry_value': volume,
                'total_entry_size': sz,
                'avg_close_price': None,
                'total_close_value': 0,
                'total_close_size': 0,
                'total_volume': volume,
                'realized_pnl': closed_pnl,
                'open_trades': 1,
                'close_trades': 0,
                'holding_hours': None,
                'status': 'open'
            }
        
        # 加仓
        elif trade_type in ('add_long', 'add_short'):
            if fill_coin not in positions_by_coin:
                # 没有开仓记录，创建一个（可能是历史数据不完整）
                direction = 'long' if 'long' in trade_type else 'short'
                positions_by_coin[fill_coin] = {
                    'coin': fill_coin,
                    'direction': direction,
                    'open_time': time_ms,
                    'close_time': None,
                    'max_size': sz,
                    'current_size': sz,
                    'avg_entry_price': px,
                    'total_entry_value': volume,
                    'total_entry_size': sz,
                    'avg_close_price': None,
                    'total_close_value': 0,
                    'total_close_size': 0,
                    'total_volume': volume,
                    'realized_pnl': closed_pnl,
                    'open_trades': 1,
                    'close_trades': 0,
                    'holding_hours': None,
                    'status': 'open'
                }
            else:
                pos = positions_by_coin[fill_coin]
                pos['current_size'] += sz
                pos['max_size'] = max(pos['max_size'], pos['current_size'])
                pos['total_entry_value'] += volume
                pos['total_entry_size'] += sz
                pos['avg_entry_price'] = (
                    pos['total_entry_value'] / pos['total_entry_size'] 
                    if pos['total_entry_size'] > 0 else 0
                )
                pos['total_volume'] += volume
                pos['realized_pnl'] += closed_pnl
                pos['open_trades'] += 1
        
        # 平仓
        elif trade_type in ('close_long', 'close_short'):
            if fill_coin not in positions_by_coin:
                # 没有开仓记录，跳过（可能是历史数据不完整）
                continue
            
            pos = positions_by_coin[fill_coin]
            pos['current_size'] -= sz
            pos['total_close_value'] += volume
            pos['total_close_size'] += sz
            pos['avg_close_price'] = (
                pos['total_close_value'] / pos['total_close_size'] 
                if pos['total_close_size'] > 0 else None
            )
            pos['total_volume'] += volume
            pos['realized_pnl'] += closed_pnl
            pos['close_trades'] += 1
            
            # 检查是否完全平仓（仓位接近0）
            if abs(pos['current_size']) < 0.0001:
                pos['status'] = 'closed'
                pos['close_time'] = time_ms
                if pos['open_time'] and time_ms:
                    pos['holding_hours'] = (time_ms - pos['open_time']) / (1000 * 3600)
                position_history.append(pos)
                del positions_by_coin[fill_coin]
    
    # 添加未平仓的仓位
    for coin, pos in positions_by_coin.items():
        pos['status'] = 'open'
        position_history.append(pos)
    
    # 按开仓时间降序排列
    position_history.sort(key=lambda x: x.get('open_time', 0) or 0, reverse=True)
    
    return position_history


def calculate_position_based_metrics(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    基于仓位历史计算指标
    
    这些指标是基于完整的仓位周期（开仓→平仓）计算的，
    比基于单笔 fill 计算更加合理。
    
    Args:
        positions: 仓位历史列表（由 rebuild_positions_from_fills 生成）
    
    Returns:
        包含以下指标的字典：
        - winning_positions: 盈利仓位数
        - losing_positions: 亏损仓位数
        - total_closed_positions: 已平仓位数
        - total_open_positions: 未平仓位数
        - win_rate: 胜率（基于已平仓位）
        - total_pnl: 总盈亏
        - total_profit: 总盈利
        - total_loss: 总亏损
        - avg_win: 平均盈利
        - avg_loss: 平均亏损
        - profit_factor: 盈亏比
        - pnl_list: 已平仓位盈亏列表（用于计算风险指标）
        - avg_holding_hours: 平均持仓时长
    """
    if not positions:
        return {
            'winning_positions': 0,
            'losing_positions': 0,
            'total_closed_positions': 0,
            'total_open_positions': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'pnl_list': [],
            'avg_holding_hours': 0.0,
        }
    
    winning_positions = 0
    losing_positions = 0
    total_closed = 0
    total_open = 0
    total_pnl = 0.0
    total_profit = 0.0
    total_loss = 0.0
    win_amounts = []
    loss_amounts = []
    pnl_list = []  # 已平仓位的盈亏列表
    holding_hours_list = []
    
    for pos in positions:
        pnl = pos.get('realized_pnl', 0) or 0
        status = pos.get('status', 'open')
        holding_hours = pos.get('holding_hours')
        
        total_pnl += pnl
        
        if status == 'closed':
            total_closed += 1
            pnl_list.append(pnl)
            
            if pnl > 0:
                winning_positions += 1
                total_profit += pnl
                win_amounts.append(pnl)
            elif pnl < 0:
                losing_positions += 1
                total_loss += abs(pnl)
                loss_amounts.append(abs(pnl))
            
            if holding_hours is not None and holding_hours > 0:
                holding_hours_list.append(holding_hours)
        else:
            total_open += 1
    
    # 计算胜率（仅基于已平仓位）
    win_rate = winning_positions / total_closed if total_closed > 0 else 0.0
    
    # 计算平均盈亏
    avg_win = np.mean(win_amounts) if win_amounts else 0.0
    avg_loss = np.mean(loss_amounts) if loss_amounts else 0.0
    
    # 计算盈亏比
    profit_factor = total_profit / total_loss if total_loss > 0 else (
        float('inf') if total_profit > 0 else 0.0
    )
    
    # 平均持仓时长
    avg_holding_hours = np.mean(holding_hours_list) if holding_hours_list else 0.0
    
    return {
        'winning_positions': winning_positions,
        'losing_positions': losing_positions,
        'total_closed_positions': total_closed,
        'total_open_positions': total_open,
        'win_rate': float(win_rate),
        'total_pnl': float(total_pnl),
        'total_profit': float(total_profit),
        'total_loss': float(total_loss),
        'avg_win': float(avg_win),
        'avg_loss': float(avg_loss),
        'profit_factor': float(profit_factor) if profit_factor != float('inf') else float('inf'),
        'pnl_list': pnl_list,
        'avg_holding_hours': float(avg_holding_hours),
    }


def calculate_position_pnl_by_time(
    positions: List[Dict[str, Any]],
    days: int = 7
) -> float:
    """
    计算指定时间范围内平仓的仓位盈亏
    
    Args:
        positions: 仓位历史列表
        days: 时间范围（天数）
    
    Returns:
        该时间范围内已平仓位的总盈亏
    """
    if not positions:
        return 0.0
    
    cutoff_time = now_shanghai().subtract(days=days)
    cutoff_ms = cutoff_time.timestamp() * 1000
    
    total_pnl = 0.0
    for pos in positions:
        if pos.get('status') != 'closed':
            continue
        close_time = pos.get('close_time', 0) or 0
        if close_time >= cutoff_ms:
            total_pnl += pos.get('realized_pnl', 0) or 0
    
    return total_pnl