"""
回测引擎
使用 Birdeye 历史数据进行策略回测
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Type
import pandas as pd
import numpy as np
from loguru import logger

from core.models import (
    OHLCV, OHLCVDataFrame, Signal, SignalType, Position, Trade,
    Order, OrderSide, OrderType, OrderStatus, PositionSide
)
from strategies.base import BaseStrategy


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 10000.0  # 初始资金
    commission_rate: float = 0.0006  # 手续费率 (0.06%)
    slippage: float = 0.0001  # 滑点 (0.01%)
    leverage: int = 1  # 杠杆倍数
    margin_ratio: float = 0.1  # 保证金率
    allow_short: bool = True  # 是否允许做空


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    strategy_name: str
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    
    # 收益指标
    total_return: float = 0.0  # 总收益率
    annual_return: float = 0.0  # 年化收益率
    max_drawdown: float = 0.0  # 最大回撤
    max_drawdown_duration: int = 0  # 最大回撤持续天数
    
    # 风险指标
    sharpe_ratio: float = 0.0  # 夏普比率
    sortino_ratio: float = 0.0  # 索提诺比率
    calmar_ratio: float = 0.0  # 卡尔玛比率
    volatility: float = 0.0  # 波动率
    
    # 交易统计
    total_trades: int = 0  # 总交易次数
    winning_trades: int = 0  # 盈利交易次数
    losing_trades: int = 0  # 亏损交易次数
    win_rate: float = 0.0  # 胜率
    avg_win: float = 0.0  # 平均盈利
    avg_loss: float = 0.0  # 平均亏损
    profit_factor: float = 0.0  # 盈亏比
    
    # 详细数据
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "period": f"{self.start_date.date()} - {self.end_date.date()}",
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "total_return": f"{self.total_return * 100:.2f}%",
            "annual_return": f"{self.annual_return * 100:.2f}%",
            "max_drawdown": f"{self.max_drawdown * 100:.2f}%",
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "total_trades": self.total_trades,
            "win_rate": f"{self.win_rate * 100:.2f}%",
            "profit_factor": round(self.profit_factor, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2)
        }
    
    def summary(self) -> str:
        """生成摘要报告"""
        return f"""
========== 回测报告 ==========
策略: {self.strategy_name}
交易对: {self.symbol}
回测期间: {self.start_date.date()} - {self.end_date.date()}

【收益指标】
初始资金: ${self.initial_capital:,.2f}
最终资金: ${self.final_capital:,.2f}
总收益率: {self.total_return * 100:.2f}%
年化收益率: {self.annual_return * 100:.2f}%
最大回撤: {self.max_drawdown * 100:.2f}%

【风险指标】
夏普比率: {self.sharpe_ratio:.2f}
索提诺比率: {self.sortino_ratio:.2f}
卡尔玛比率: {self.calmar_ratio:.2f}
波动率: {self.volatility * 100:.2f}%

【交易统计】
总交易次数: {self.total_trades}
盈利交易: {self.winning_trades}
亏损交易: {self.losing_trades}
胜率: {self.win_rate * 100:.2f}%
平均盈利: ${self.avg_win:.2f}
平均亏损: ${self.avg_loss:.2f}
盈亏比: {self.profit_factor:.2f}
================================
"""


class BacktestEngine:
    """
    回测引擎
    
    使用历史数据对策略进行回测，计算各项绩效指标
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
        """
        self.config = config or BacktestConfig()
        
        # 状态变量
        self._capital = 0.0
        self._position: Optional[Position] = None
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._signals: List[Signal] = []
    
    def _reset(self):
        """重置状态"""
        self._capital = self.config.initial_capital
        self._position = None
        self._trades = []
        self._equity_curve = []
        self._signals = []
    
    def _calculate_commission(self, size: float, price: float) -> float:
        """计算手续费"""
        return size * price * self.config.commission_rate
    
    def _calculate_slippage(self, price: float, is_buy: bool) -> float:
        """计算滑点"""
        slippage_amount = price * self.config.slippage
        return price + slippage_amount if is_buy else price - slippage_amount
    
    def _open_position(
        self,
        symbol: str,
        is_long: bool,
        price: float,
        size: float,
        timestamp: datetime,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> Position:
        """开仓"""
        # 计算实际成交价（考虑滑点）
        fill_price = self._calculate_slippage(price, is_long)
        
        # 计算手续费
        commission = self._calculate_commission(size, fill_price)
        self._capital -= commission
        
        # 创建仓位
        self._position = Position(
            symbol=symbol,
            side=PositionSide.LONG if is_long else PositionSide.SHORT,
            size=size,
            entry_price=fill_price,
            current_price=fill_price,
            leverage=self.config.leverage,
            created_at=timestamp
        )
        
        logger.debug(f"开仓: {self._position.side.value} {size} @ {fill_price}, 手续费: {commission:.4f}")
        return self._position
    
    def _close_position(self, price: float, timestamp: datetime) -> Trade:
        """平仓"""
        if self._position is None:
            raise ValueError("没有持仓")
        
        is_long = self._position.side == PositionSide.LONG
        
        # 计算实际成交价（考虑滑点）
        fill_price = self._calculate_slippage(price, not is_long)
        
        # 计算盈亏
        if is_long:
            pnl = (fill_price - self._position.entry_price) * self._position.size
        else:
            pnl = (self._position.entry_price - fill_price) * self._position.size
        
        # 考虑杠杆
        pnl *= self.config.leverage
        
        # 计算手续费
        commission = self._calculate_commission(self._position.size, fill_price)
        
        # 更新资金
        self._capital += pnl - commission
        
        # 创建成交记录
        trade = Trade(
            id=str(len(self._trades) + 1),
            symbol=self._position.symbol,
            side=OrderSide.SELL if is_long else OrderSide.BUY,
            price=fill_price,
            size=self._position.size,
            pnl=pnl,
            fee=commission,
            timestamp=timestamp
        )
        self._trades.append(trade)
        
        logger.debug(f"平仓: {fill_price}, PnL: {pnl:.4f}, 手续费: {commission:.4f}")
        
        self._position = None
        return trade
    
    def _check_stop_loss_take_profit(
        self,
        candle: OHLCV,
        stop_loss: Optional[float],
        take_profit: Optional[float]
    ) -> bool:
        """检查止损止盈"""
        if self._position is None:
            return False
        
        is_long = self._position.side == PositionSide.LONG
        
        # 检查止损
        if stop_loss:
            if is_long and candle.low <= stop_loss:
                self._close_position(stop_loss, candle.timestamp)
                logger.debug(f"触发止损: {stop_loss}")
                return True
            elif not is_long and candle.high >= stop_loss:
                self._close_position(stop_loss, candle.timestamp)
                logger.debug(f"触发止损: {stop_loss}")
                return True
        
        # 检查止盈
        if take_profit:
            if is_long and candle.high >= take_profit:
                self._close_position(take_profit, candle.timestamp)
                logger.debug(f"触发止盈: {take_profit}")
                return True
            elif not is_long and candle.low <= take_profit:
                self._close_position(take_profit, candle.timestamp)
                logger.debug(f"触发止盈: {take_profit}")
                return True
        
        return False
    
    def _calculate_equity(self, current_price: float) -> float:
        """计算当前权益"""
        equity = self._capital
        
        if self._position:
            if self._position.side == PositionSide.LONG:
                unrealized_pnl = (current_price - self._position.entry_price) * self._position.size
            else:
                unrealized_pnl = (self._position.entry_price - current_price) * self._position.size
            
            unrealized_pnl *= self.config.leverage
            equity += unrealized_pnl
        
        return equity
    
    def _calculate_metrics(
        self,
        result: BacktestResult,
        risk_free_rate: float = 0.02
    ) -> BacktestResult:
        """计算绩效指标"""
        if not result.equity_curve:
            return result
        
        equity_series = pd.Series(result.equity_curve)
        returns = equity_series.pct_change().dropna()
        
        # 总收益率
        result.total_return = (result.final_capital - result.initial_capital) / result.initial_capital
        
        # 年化收益率
        days = (result.end_date - result.start_date).days
        if days > 0:
            result.annual_return = (1 + result.total_return) ** (365 / days) - 1
        
        # 最大回撤
        cummax = equity_series.cummax()
        drawdown = (equity_series - cummax) / cummax
        result.max_drawdown = abs(drawdown.min())
        result.drawdown_curve = drawdown.tolist()
        
        # 波动率（年化）
        if len(returns) > 1:
            result.volatility = returns.std() * np.sqrt(252)
        
        # 夏普比率
        if result.volatility > 0:
            excess_return = result.annual_return - risk_free_rate
            result.sharpe_ratio = excess_return / result.volatility
        
        # 索提诺比率（只考虑下行风险）
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = downside_returns.std() * np.sqrt(252)
            if downside_std > 0:
                result.sortino_ratio = (result.annual_return - risk_free_rate) / downside_std
        
        # 卡尔玛比率
        if result.max_drawdown > 0:
            result.calmar_ratio = result.annual_return / result.max_drawdown
        
        # 交易统计
        if result.trades:
            result.total_trades = len(result.trades)
            
            wins = [t for t in result.trades if t.pnl > 0]
            losses = [t for t in result.trades if t.pnl <= 0]
            
            result.winning_trades = len(wins)
            result.losing_trades = len(losses)
            
            if result.total_trades > 0:
                result.win_rate = result.winning_trades / result.total_trades
            
            if wins:
                result.avg_win = sum(t.pnl for t in wins) / len(wins)
            if losses:
                result.avg_loss = abs(sum(t.pnl for t in losses) / len(losses))
            
            total_profit = sum(t.pnl for t in wins) if wins else 0
            total_loss = abs(sum(t.pnl for t in losses)) if losses else 0
            
            if total_loss > 0:
                result.profit_factor = total_profit / total_loss
        
        return result
    
    def run(
        self,
        strategy: BaseStrategy,
        data: OHLCVDataFrame,
        symbol: str = "ETH"
    ) -> BacktestResult:
        """
        运行回测 (优化版 - 预计算指标)

        Args:
            strategy: 交易策略
            data: OHLCV 历史数据
            symbol: 交易对符号

        Returns:
            回测结果
        """
        self._reset()

        df = data.df
        if df.empty:
            raise ValueError("数据为空")

        logger.info(f"开始回测: {strategy.name}, 数据量: {len(df)}")

        # 初始化策略
        strategy.on_init()
        strategy.on_start()

        # ===== 优化：预计算所有指标 =====
        logger.debug("预计算指标...")
        all_indicators = strategy.calculate_indicators(data)

        # 预先转换为 numpy 数组加速访问
        close_prices = df['close'].values
        high_prices = df['high'].values
        low_prices = df['low'].values
        timestamps = df.index.tolist()

        # 用于追踪止损止盈
        current_stop_loss: Optional[float] = None
        current_take_profit: Optional[float] = None

        warmup_period = max(30, strategy.config.params.get('slow_period', 30),
                           strategy.config.params.get('atr_period', 10) + 10)

        # 遍历历史数据 (使用 numpy 数组加速)
        for i in range(len(df)):
            current_price = close_prices[i]

            # 构造当前 K 线
            candle = OHLCV(
                timestamp=timestamps[i],
                open=df['open'].iloc[i],
                high=high_prices[i],
                low=low_prices[i],
                close=current_price,
                volume=df['volume'].iloc[i]
            )

            # 检查止损止盈
            if self._position:
                if self._check_stop_loss_take_profit(
                    candle, current_stop_loss, current_take_profit
                ):
                    current_stop_loss = None
                    current_take_profit = None

            # 需要足够的数据才能生成信号
            if i < warmup_period:
                self._equity_curve.append(self._calculate_equity(current_price))
                continue

            # ===== 优化：使用预计算的指标生成信号 =====
            # 截取到当前位置的指标
            current_indicators = {
                name: series.iloc[:i+1] for name, series in all_indicators.items()
            }

            # 创建轻量级数据对象 (只包含最新数据用于信号生成)
            current_data = OHLCVDataFrame.from_dataframe(df.iloc[max(0, i-100):i+1])

            signal = strategy.generate_signal(current_data, current_indicators, self._position)
            self._signals.append(signal)
            
            # 处理信号
            if signal.signal_type == SignalType.BUY:
                # 如果有空仓，先平仓
                if self._position and self._position.side == PositionSide.SHORT:
                    self._close_position(candle.close, candle.timestamp)
                
                # 开多仓
                if self._position is None:
                    # 计算仓位大小
                    position_value = self._capital * strategy.config.position_size_pct
                    size = position_value / candle.close
                    
                    self._open_position(
                        symbol, True, candle.close, size, candle.timestamp,
                        signal.stop_loss, signal.take_profit
                    )
                    current_stop_loss = signal.stop_loss
                    current_take_profit = signal.take_profit
            
            elif signal.signal_type == SignalType.SELL:
                # 如果有多仓，先平仓
                if self._position and self._position.side == PositionSide.LONG:
                    self._close_position(candle.close, candle.timestamp)
                
                # 开空仓（如果允许）
                if self._position is None and self.config.allow_short:
                    position_value = self._capital * strategy.config.position_size_pct
                    size = position_value / candle.close
                    
                    self._open_position(
                        symbol, False, candle.close, size, candle.timestamp,
                        signal.stop_loss, signal.take_profit
                    )
                    current_stop_loss = signal.stop_loss
                    current_take_profit = signal.take_profit
            
            elif signal.signal_type == SignalType.CLOSE:
                if self._position:
                    self._close_position(candle.close, candle.timestamp)
                    current_stop_loss = None
                    current_take_profit = None
            
            # 记录权益
            self._equity_curve.append(self._calculate_equity(candle.close))
        
        # 回测结束，平掉所有仓位
        if self._position:
            last_candle = data.latest
            self._close_position(last_candle.close, last_candle.timestamp)
        
        strategy.on_stop()
        
        # 创建结果
        result = BacktestResult(
            strategy_name=strategy.name,
            symbol=symbol,
            start_date=df.index[0] if isinstance(df.index[0], datetime) else datetime.now(),
            end_date=df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now(),
            initial_capital=self.config.initial_capital,
            final_capital=self._capital,
            trades=self._trades,
            equity_curve=self._equity_curve,
            signals=self._signals
        )
        
        # 计算指标
        result = self._calculate_metrics(result)
        
        logger.info(f"回测完成: 总收益率 {result.total_return * 100:.2f}%")
        
        return result
    
    def run_multiple(
        self,
        strategies: List[BaseStrategy],
        data: OHLCVDataFrame,
        symbol: str = "ETH"
    ) -> List[BacktestResult]:
        """
        批量运行多个策略的回测
        
        Args:
            strategies: 策略列表
            data: OHLCV 历史数据
            symbol: 交易对符号
        
        Returns:
            回测结果列表
        """
        results = []
        for strategy in strategies:
            result = self.run(strategy, data, symbol)
            results.append(result)
        
        return results
    
    def compare_strategies(self, results: List[BacktestResult]) -> pd.DataFrame:
        """
        比较多个策略的回测结果
        
        Args:
            results: 回测结果列表
        
        Returns:
            比较结果 DataFrame
        """
        comparison_data = []
        
        for result in results:
            comparison_data.append({
                "策略": result.strategy_name,
                "总收益率": f"{result.total_return * 100:.2f}%",
                "年化收益率": f"{result.annual_return * 100:.2f}%",
                "最大回撤": f"{result.max_drawdown * 100:.2f}%",
                "夏普比率": round(result.sharpe_ratio, 2),
                "胜率": f"{result.win_rate * 100:.2f}%",
                "交易次数": result.total_trades,
                "盈亏比": round(result.profit_factor, 2)
            })
        
        return pd.DataFrame(comparison_data)

