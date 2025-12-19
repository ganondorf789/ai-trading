"""
风险管理模块
负责风险控制、仓位管理和资金保护
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
from loguru import logger

from core.models import Signal, SignalType, Position, PositionSide, Trade


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskConfig:
    """风险管理配置"""
    # 最大回撤限制
    max_drawdown_percent: float = 0.1  # 10%
    
    # 每日亏损限制
    max_daily_loss_percent: float = 0.05  # 5%
    max_daily_loss_usd: float = 500.0
    
    # 单笔交易风险
    max_trade_risk_percent: float = 0.02  # 2%
    
    # 仓位限制
    max_position_size_usd: float = 1000.0
    max_positions: int = 3
    max_leverage: int = 10
    
    # 连续亏损限制
    max_consecutive_losses: int = 5
    
    # 交易频率限制
    min_trade_interval_seconds: int = 60
    max_trades_per_hour: int = 10
    max_trades_per_day: int = 50
    
    # 价格波动限制
    max_price_deviation_percent: float = 0.05  # 5% 价格偏离限制


@dataclass
class RiskState:
    """风险状态"""
    # 账户状态
    initial_equity: float = 0.0
    current_equity: float = 0.0
    peak_equity: float = 0.0
    
    # 回撤
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    
    # 每日统计
    daily_pnl: float = 0.0
    daily_trades: int = 0
    daily_start_equity: float = 0.0
    
    # 交易统计
    consecutive_losses: int = 0
    last_trade_time: Optional[datetime] = None
    trades_this_hour: int = 0
    hour_start: Optional[datetime] = None
    
    # 风险等级
    risk_level: RiskLevel = RiskLevel.LOW
    
    # 警告消息
    warnings: List[str] = field(default_factory=list)
    
    # 是否暂停交易
    trading_paused: bool = False
    pause_reason: str = ""


class RiskManager:
    """
    风险管理器
    
    负责：
    - 监控账户风险
    - 检查交易信号是否符合风险控制要求
    - 计算适当的仓位大小
    - 在风险过高时暂停交易
    """
    
    def __init__(self, config: Optional[RiskConfig] = None):
        """
        初始化风险管理器
        
        Args:
            config: 风险配置
        """
        self.config = config or RiskConfig()
        self.state = RiskState()
        
        logger.info("风险管理器初始化")
    
    def initialize(self, initial_equity: float):
        """
        初始化风险状态
        
        Args:
            initial_equity: 初始资金
        """
        self.state.initial_equity = initial_equity
        self.state.current_equity = initial_equity
        self.state.peak_equity = initial_equity
        self.state.daily_start_equity = initial_equity
        self.state.hour_start = datetime.now()
        
        logger.info(f"风险管理器初始化，初始资金: {initial_equity}")
    
    def update_equity(self, equity: float):
        """
        更新账户权益
        
        Args:
            equity: 当前权益
        """
        self.state.current_equity = equity
        
        # 更新峰值
        if equity > self.state.peak_equity:
            self.state.peak_equity = equity
        
        # 计算回撤
        if self.state.peak_equity > 0:
            self.state.current_drawdown = (
                self.state.peak_equity - equity
            ) / self.state.peak_equity
            
            if self.state.current_drawdown > self.state.max_drawdown:
                self.state.max_drawdown = self.state.current_drawdown
        
        # 计算每日盈亏
        self.state.daily_pnl = equity - self.state.daily_start_equity
        
        # 更新风险等级
        self._update_risk_level()
    
    def _update_risk_level(self):
        """更新风险等级"""
        warnings = []
        
        # 检查回撤
        if self.state.current_drawdown >= self.config.max_drawdown_percent:
            self.state.risk_level = RiskLevel.CRITICAL
            warnings.append(f"回撤达到最大限制: {self.state.current_drawdown * 100:.2f}%")
        elif self.state.current_drawdown >= self.config.max_drawdown_percent * 0.8:
            self.state.risk_level = RiskLevel.HIGH
            warnings.append(f"回撤接近限制: {self.state.current_drawdown * 100:.2f}%")
        elif self.state.current_drawdown >= self.config.max_drawdown_percent * 0.5:
            self.state.risk_level = RiskLevel.MEDIUM
        
        # 检查每日亏损
        daily_loss_percent = abs(min(self.state.daily_pnl, 0)) / self.state.daily_start_equity if self.state.daily_start_equity > 0 else 0
        
        if daily_loss_percent >= self.config.max_daily_loss_percent:
            self.state.risk_level = RiskLevel.CRITICAL
            warnings.append(f"每日亏损达到限制: {daily_loss_percent * 100:.2f}%")
        
        if abs(self.state.daily_pnl) >= self.config.max_daily_loss_usd and self.state.daily_pnl < 0:
            self.state.risk_level = RiskLevel.CRITICAL
            warnings.append(f"每日亏损达到USD限制: ${abs(self.state.daily_pnl):.2f}")
        
        # 检查连续亏损
        if self.state.consecutive_losses >= self.config.max_consecutive_losses:
            self.state.risk_level = RiskLevel.HIGH
            warnings.append(f"连续亏损次数: {self.state.consecutive_losses}")
        
        self.state.warnings = warnings
        
        # 检查是否需要暂停交易
        if self.state.risk_level == RiskLevel.CRITICAL:
            self.state.trading_paused = True
            self.state.pause_reason = "; ".join(warnings)
            logger.warning(f"交易已暂停: {self.state.pause_reason}")
    
    def on_trade(self, trade: Trade):
        """
        交易完成回调
        
        Args:
            trade: 成交记录
        """
        self.state.last_trade_time = trade.timestamp
        self.state.daily_trades += 1
        
        # 更新每小时交易计数
        now = datetime.now()
        if self.state.hour_start is None or \
           (now - self.state.hour_start) > timedelta(hours=1):
            self.state.hour_start = now
            self.state.trades_this_hour = 0
        
        self.state.trades_this_hour += 1
        
        # 更新连续亏损
        if trade.pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
        
        logger.debug(f"交易记录: PnL={trade.pnl:.4f}, 连续亏损={self.state.consecutive_losses}")
    
    def reset_daily_stats(self):
        """重置每日统计"""
        self.state.daily_pnl = 0.0
        self.state.daily_trades = 0
        self.state.daily_start_equity = self.state.current_equity
        self.state.trading_paused = False
        self.state.pause_reason = ""
        
        logger.info("每日统计已重置")
    
    def check_signal(self, signal: Signal, current_positions: List[Position]) -> bool:
        """
        检查交易信号是否符合风险要求
        
        Args:
            signal: 交易信号
            current_positions: 当前持仓列表
        
        Returns:
            是否通过风险检查
        """
        # 如果交易已暂停
        if self.state.trading_paused:
            logger.warning(f"交易已暂停，拒绝信号: {self.state.pause_reason}")
            return False
        
        # 如果是持有信号，直接通过
        if signal.signal_type == SignalType.HOLD:
            return True
        
        # 如果是平仓信号，通常允许
        if signal.signal_type == SignalType.CLOSE:
            return True
        
        # 检查风险等级
        if self.state.risk_level == RiskLevel.CRITICAL:
            logger.warning("风险等级为 CRITICAL，拒绝新开仓")
            return False
        
        # 检查仓位数量
        if len(current_positions) >= self.config.max_positions:
            logger.warning(f"已达最大仓位数量: {len(current_positions)}")
            return False
        
        # 检查交易频率
        if not self._check_trade_frequency():
            logger.warning("交易频率超限")
            return False
        
        # 检查每日交易次数
        if self.state.daily_trades >= self.config.max_trades_per_day:
            logger.warning(f"每日交易次数已达上限: {self.state.daily_trades}")
            return False
        
        return True
    
    def _check_trade_frequency(self) -> bool:
        """检查交易频率"""
        now = datetime.now()
        
        # 检查最小交易间隔
        if self.state.last_trade_time:
            elapsed = (now - self.state.last_trade_time).total_seconds()
            if elapsed < self.config.min_trade_interval_seconds:
                return False
        
        # 检查每小时交易次数
        if self.state.trades_this_hour >= self.config.max_trades_per_hour:
            return False
        
        return True
    
    def calculate_position_size(
        self,
        account_value: float,
        entry_price: float,
        stop_loss_price: float,
        leverage: int = 1
    ) -> float:
        """
        基于风险计算仓位大小
        
        使用固定风险百分比法：
        仓位大小 = (账户价值 * 风险百分比) / (入场价 - 止损价)
        
        Args:
            account_value: 账户价值
            entry_price: 入场价格
            stop_loss_price: 止损价格
            leverage: 杠杆倍数
        
        Returns:
            建议的仓位大小
        """
        # 计算每单位风险
        risk_per_unit = abs(entry_price - stop_loss_price)
        
        if risk_per_unit <= 0:
            # 如果没有止损，使用默认风险
            risk_per_unit = entry_price * self.config.max_trade_risk_percent
        
        # 计算可承受的风险金额
        risk_amount = account_value * self.config.max_trade_risk_percent
        
        # 计算仓位大小
        position_size = risk_amount / risk_per_unit
        
        # 考虑杠杆
        position_size = position_size / leverage
        
        # 检查最大仓位限制
        max_size_by_value = self.config.max_position_size_usd / entry_price
        position_size = min(position_size, max_size_by_value)
        
        # 根据风险等级调整仓位
        if self.state.risk_level == RiskLevel.HIGH:
            position_size *= 0.5
        elif self.state.risk_level == RiskLevel.MEDIUM:
            position_size *= 0.75
        
        return position_size
    
    def get_stop_loss_price(
        self,
        entry_price: float,
        is_long: bool,
        atr: Optional[float] = None
    ) -> float:
        """
        计算建议的止损价格
        
        Args:
            entry_price: 入场价格
            is_long: 是否做多
            atr: ATR 值（可选）
        
        Returns:
            建议的止损价格
        """
        if atr:
            # 使用 2 倍 ATR 作为止损距离
            stop_distance = atr * 2
        else:
            # 使用固定百分比
            stop_distance = entry_price * self.config.max_trade_risk_percent
        
        if is_long:
            return entry_price - stop_distance
        else:
            return entry_price + stop_distance
    
    def get_take_profit_price(
        self,
        entry_price: float,
        stop_loss_price: float,
        is_long: bool,
        risk_reward_ratio: float = 2.0
    ) -> float:
        """
        计算建议的止盈价格
        
        Args:
            entry_price: 入场价格
            stop_loss_price: 止损价格
            is_long: 是否做多
            risk_reward_ratio: 风险回报比
        
        Returns:
            建议的止盈价格
        """
        risk = abs(entry_price - stop_loss_price)
        reward = risk * risk_reward_ratio
        
        if is_long:
            return entry_price + reward
        else:
            return entry_price - reward
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取风险状态
        
        Returns:
            状态字典
        """
        return {
            "risk_level": self.state.risk_level.value,
            "trading_paused": self.state.trading_paused,
            "pause_reason": self.state.pause_reason,
            "current_drawdown": f"{self.state.current_drawdown * 100:.2f}%",
            "max_drawdown": f"{self.state.max_drawdown * 100:.2f}%",
            "daily_pnl": f"${self.state.daily_pnl:.2f}",
            "daily_trades": self.state.daily_trades,
            "consecutive_losses": self.state.consecutive_losses,
            "current_equity": self.state.current_equity,
            "peak_equity": self.state.peak_equity,
            "warnings": self.state.warnings
        }
    
    def resume_trading(self):
        """手动恢复交易"""
        if self.state.trading_paused:
            self.state.trading_paused = False
            self.state.pause_reason = ""
            logger.info("交易已手动恢复")


class PositionSizer:
    """
    仓位计算器
    
    提供多种仓位计算方法
    """
    
    @staticmethod
    def fixed_amount(
        amount: float,
        price: float
    ) -> float:
        """
        固定金额法
        
        Args:
            amount: 固定金额
            price: 当前价格
        
        Returns:
            仓位大小
        """
        return amount / price
    
    @staticmethod
    def fixed_percent(
        account_value: float,
        percent: float,
        price: float
    ) -> float:
        """
        固定百分比法
        
        Args:
            account_value: 账户价值
            percent: 百分比 (0-1)
            price: 当前价格
        
        Returns:
            仓位大小
        """
        amount = account_value * percent
        return amount / price
    
    @staticmethod
    def fixed_risk(
        account_value: float,
        risk_percent: float,
        entry_price: float,
        stop_loss_price: float
    ) -> float:
        """
        固定风险法
        
        Args:
            account_value: 账户价值
            risk_percent: 风险百分比 (0-1)
            entry_price: 入场价格
            stop_loss_price: 止损价格
        
        Returns:
            仓位大小
        """
        risk_amount = account_value * risk_percent
        risk_per_unit = abs(entry_price - stop_loss_price)
        
        if risk_per_unit <= 0:
            return 0
        
        return risk_amount / risk_per_unit
    
    @staticmethod
    def kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        凯利公式法
        
        计算最优仓位比例
        
        Args:
            win_rate: 胜率
            avg_win: 平均盈利
            avg_loss: 平均亏损（正数）
        
        Returns:
            建议的仓位比例 (0-1)
        """
        if avg_loss <= 0:
            return 0
        
        win_loss_ratio = avg_win / avg_loss
        
        # 凯利公式: f = (bp - q) / b
        # b = 赔率，p = 胜率，q = 败率
        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # 限制在 0-0.5 之间（半凯利）
        return max(0, min(kelly * 0.5, 0.5))

