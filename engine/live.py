"""
实盘交易引擎
使用 Hyperliquid 进行实时交易
"""
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger

from core.models import (
    Signal, SignalType, Position, Order, Trade,
    OrderSide, OrderType, PositionSide, OHLCVDataFrame
)
from clients.hyperliquid_client import HyperliquidClient
from strategies.base import BaseStrategy


@dataclass
class LiveEngineConfig:
    """实盘引擎配置"""
    symbols: List[str] = field(default_factory=lambda: ["ETH"])
    timeframe: str = "1h"
    update_interval: float = 60.0  # 更新间隔（秒）
    max_position_size_usd: float = 1000.0  # 最大仓位价值
    leverage: int = 5  # 杠杆倍数
    dry_run: bool = True  # 模拟运行（不实际下单）


@dataclass
class LiveEngineState:
    """实盘引擎状态"""
    is_running: bool = False
    last_update: Optional[datetime] = None
    current_positions: Dict[str, Position] = field(default_factory=dict)
    pending_orders: Dict[str, Order] = field(default_factory=dict)
    daily_pnl: float = 0.0
    total_trades_today: int = 0


class LiveEngine:
    """
    实盘交易引擎
    
    连接 Hyperliquid 进行实时交易
    """
    
    def __init__(
        self,
        client: HyperliquidClient,
        strategy: BaseStrategy,
        config: Optional[LiveEngineConfig] = None
    ):
        """
        初始化实盘引擎
        
        Args:
            client: Hyperliquid 客户端
            strategy: 交易策略
            config: 引擎配置
        """
        self.client = client
        self.strategy = strategy
        self.config = config or LiveEngineConfig()
        self.state = LiveEngineState()
        
        # 风险管理回调
        self._risk_check: Optional[Callable[[Signal], bool]] = None
        
        # 事件回调
        self._on_signal: Optional[Callable[[Signal], None]] = None
        self._on_trade: Optional[Callable[[Trade], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        
        logger.info(f"实盘引擎初始化: {strategy.name}")
    
    def set_risk_check(self, callback: Callable[[Signal], bool]):
        """
        设置风险检查回调
        
        Args:
            callback: 风险检查函数，返回 True 表示通过
        """
        self._risk_check = callback
    
    def set_on_signal(self, callback: Callable[[Signal], None]):
        """设置信号回调"""
        self._on_signal = callback
    
    def set_on_trade(self, callback: Callable[[Trade], None]):
        """设置成交回调"""
        self._on_trade = callback
    
    def set_on_error(self, callback: Callable[[Exception], None]):
        """设置错误回调"""
        self._on_error = callback
    
    def _get_current_position(self, symbol: str) -> Optional[Position]:
        """获取当前持仓"""
        positions = self.client.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    def _calculate_position_size(
        self,
        symbol: str,
        price: float,
        account_value: float
    ) -> float:
        """
        计算仓位大小
        
        Args:
            symbol: 交易对
            price: 当前价格
            account_value: 账户价值
        
        Returns:
            仓位大小
        """
        # 使用策略配置的仓位比例
        position_value = account_value * self.strategy.config.position_size_pct
        
        # 不超过最大仓位限制
        position_value = min(position_value, self.config.max_position_size_usd)
        
        # 计算数量
        size = position_value / price
        
        # 获取精度信息
        meta = self.client.get_meta()
        for asset in meta.get('universe', []):
            if asset['name'] == symbol:
                decimals = asset.get('szDecimals', 4)
                size = round(size, decimals)
                break
        
        return size
    
    async def _process_signal(self, symbol: str, signal: Signal):
        """
        处理交易信号
        
        Args:
            symbol: 交易对
            signal: 交易信号
        """
        # 风险检查
        if self._risk_check and not self._risk_check(signal):
            logger.warning(f"信号未通过风险检查: {signal}")
            return
        
        # 触发信号回调
        if self._on_signal:
            self._on_signal(signal)
        
        # 模拟运行不实际下单
        if self.config.dry_run:
            logger.info(f"[模拟] 信号: {signal.signal_type.value} @ {signal.price}")
            return
        
        current_position = self._get_current_position(symbol)
        account = self.client.get_account_info()
        
        try:
            if signal.signal_type == SignalType.BUY:
                # 如果有空仓，先平仓
                if current_position and current_position.side == PositionSide.SHORT:
                    self.client.close_position(symbol)
                    logger.info(f"平掉空仓: {symbol}")
                
                # 开多仓
                if not current_position or current_position.side == PositionSide.SHORT:
                    size = self._calculate_position_size(
                        symbol, signal.price, account.equity
                    )
                    
                    # 设置杠杆
                    self.client.set_leverage(symbol, self.config.leverage)
                    
                    # 市价买入
                    result = self.client.market_order(symbol, True, size)
                    
                    if result.get('status') == 'ok':
                        logger.info(f"开多仓成功: {symbol} {size}")
                        self.state.total_trades_today += 1
                        
                        # 设置止损止盈
                        if signal.stop_loss:
                            self.client.stop_order(
                                symbol, False, size, signal.stop_loss
                            )
                        if signal.take_profit:
                            self.client.stop_order(
                                symbol, False, size, signal.take_profit
                            )
            
            elif signal.signal_type == SignalType.SELL:
                # 如果有多仓，先平仓
                if current_position and current_position.side == PositionSide.LONG:
                    self.client.close_position(symbol)
                    logger.info(f"平掉多仓: {symbol}")
                
                # 开空仓
                if not current_position or current_position.side == PositionSide.LONG:
                    size = self._calculate_position_size(
                        symbol, signal.price, account.equity
                    )
                    
                    # 设置杠杆
                    self.client.set_leverage(symbol, self.config.leverage)
                    
                    # 市价卖出
                    result = self.client.market_order(symbol, False, size)
                    
                    if result.get('status') == 'ok':
                        logger.info(f"开空仓成功: {symbol} {size}")
                        self.state.total_trades_today += 1
                        
                        # 设置止损止盈
                        if signal.stop_loss:
                            self.client.stop_order(
                                symbol, True, size, signal.stop_loss
                            )
                        if signal.take_profit:
                            self.client.stop_order(
                                symbol, True, size, signal.take_profit
                            )
            
            elif signal.signal_type == SignalType.CLOSE:
                if current_position:
                    result = self.client.close_position(symbol)
                    if result.get('status') == 'ok':
                        logger.info(f"平仓成功: {symbol}")
                        self.state.total_trades_today += 1
        
        except Exception as e:
            logger.error(f"执行交易失败: {e}")
            if self._on_error:
                self._on_error(e)
    
    async def _update_cycle(self, symbol: str):
        """
        单次更新循环
        
        Args:
            symbol: 交易对
        """
        try:
            # 获取最新数据
            end_time = datetime.now()
            start_time = end_time - timedelta(days=7)  # 获取7天数据
            
            data = self.client.get_candles_dataframe(
                symbol,
                self.config.timeframe,
                start_time,
                end_time
            )
            
            if len(data) < 30:
                logger.warning(f"数据不足: {len(data)} 条")
                return
            
            # 获取当前持仓
            current_position = self._get_current_position(symbol)
            
            # 更新策略并获取信号
            signal = self.strategy.update(symbol, data, current_position)
            
            # 更新状态
            self.state.last_update = datetime.now()
            
            # 处理信号
            if signal.signal_type != SignalType.HOLD:
                await self._process_signal(symbol, signal)
            
            logger.debug(f"更新完成: {symbol}, 信号: {signal.signal_type.value}")
        
        except Exception as e:
            logger.error(f"更新循环错误: {e}")
            if self._on_error:
                self._on_error(e)
    
    async def run(self):
        """
        运行实盘引擎
        
        主循环，持续运行直到停止
        """
        self.state.is_running = True
        self.strategy.on_init()
        self.strategy.on_start()
        
        logger.info(f"实盘引擎启动: {self.strategy.name}")
        logger.info(f"交易对: {self.config.symbols}")
        logger.info(f"时间周期: {self.config.timeframe}")
        logger.info(f"模拟模式: {self.config.dry_run}")
        
        try:
            while self.state.is_running:
                for symbol in self.config.symbols:
                    await self._update_cycle(symbol)
                
                # 等待下一次更新
                await asyncio.sleep(self.config.update_interval)
        
        except asyncio.CancelledError:
            logger.info("引擎被取消")
        except Exception as e:
            logger.error(f"引擎运行错误: {e}")
            if self._on_error:
                self._on_error(e)
        finally:
            self.state.is_running = False
            self.strategy.on_stop()
            logger.info("实盘引擎停止")
    
    def stop(self):
        """停止引擎"""
        self.state.is_running = False
        logger.info("正在停止实盘引擎...")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取引擎状态
        
        Returns:
            状态信息字典
        """
        positions = self.client.get_positions() if not self.config.dry_run else []
        account = self.client.get_account_info() if not self.config.dry_run else None
        
        return {
            "is_running": self.state.is_running,
            "strategy": self.strategy.name,
            "symbols": self.config.symbols,
            "timeframe": self.config.timeframe,
            "dry_run": self.config.dry_run,
            "last_update": self.state.last_update.isoformat() if self.state.last_update else None,
            "trades_today": self.state.total_trades_today,
            "daily_pnl": self.state.daily_pnl,
            "positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side.value,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "unrealized_pnl": p.unrealized_pnl
                }
                for p in positions
            ],
            "account": {
                "equity": account.equity if account else 0,
                "available_margin": account.available_margin if account else 0,
                "margin_ratio": account.margin_ratio if account else 0
            } if account else None
        }


class LiveEngineWithWebSocket(LiveEngine):
    """
    使用 WebSocket 的实盘引擎
    
    通过 WebSocket 订阅实时数据，降低延迟
    """
    
    def __init__(
        self,
        client: HyperliquidClient,
        strategy: BaseStrategy,
        config: Optional[LiveEngineConfig] = None
    ):
        super().__init__(client, strategy, config)
        
        # 实时数据缓存
        self._price_cache: Dict[str, float] = {}
        self._candle_cache: Dict[str, List] = {}
    
    def _on_price_update(self, message: Dict[str, Any]):
        """价格更新回调"""
        if 'mids' in message.get('data', {}):
            mids = message['data']['mids']
            for symbol, price in mids.items():
                self._price_cache[symbol] = float(price)
    
    def _on_candle_update(self, message: Dict[str, Any]):
        """K线更新回调"""
        data = message.get('data', {})
        symbol = data.get('s', '')
        
        if symbol:
            if symbol not in self._candle_cache:
                self._candle_cache[symbol] = []
            
            candle = {
                't': data.get('t'),
                'o': data.get('o'),
                'h': data.get('h'),
                'l': data.get('l'),
                'c': data.get('c'),
                'v': data.get('v')
            }
            
            # 更新或添加K线
            if self._candle_cache[symbol] and \
               self._candle_cache[symbol][-1]['t'] == candle['t']:
                self._candle_cache[symbol][-1] = candle
            else:
                self._candle_cache[symbol].append(candle)
                # 保留最近500根K线
                if len(self._candle_cache[symbol]) > 500:
                    self._candle_cache[symbol] = self._candle_cache[symbol][-500:]
    
    async def run(self):
        """运行带 WebSocket 的实盘引擎"""
        self.state.is_running = True
        self.strategy.on_init()
        self.strategy.on_start()
        
        logger.info(f"WebSocket 实盘引擎启动: {self.strategy.name}")
        
        # 订阅实时数据
        self.client.subscribe_all_mids(self._on_price_update)
        
        for symbol in self.config.symbols:
            self.client.subscribe_candles(
                symbol,
                self.config.timeframe,
                self._on_candle_update
            )
        
        try:
            while self.state.is_running:
                for symbol in self.config.symbols:
                    await self._update_cycle(symbol)
                
                await asyncio.sleep(self.config.update_interval)
        
        except asyncio.CancelledError:
            logger.info("WebSocket 引擎被取消")
        except Exception as e:
            logger.error(f"WebSocket 引擎错误: {e}")
            if self._on_error:
                self._on_error(e)
        finally:
            self.state.is_running = False
            self.strategy.on_stop()
            logger.info("WebSocket 实盘引擎停止")

