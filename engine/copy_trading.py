"""
跟单机器人引擎
监控目标交易者的持仓变化并复制交易
"""
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger

from hyperliquid.info import Info

from core.models import (
    Position, PositionSide, Trade, OrderSide
)
from clients.hyperliquid_client import HyperliquidClient


@dataclass
class CopyTradingConfig:
    """跟单配置"""
    # 目标交易者地址
    target_address: str = ""
    
    # 跟单设置
    copy_ratio: float = 1.0  # 跟单比例 (0.5 = 跟单50%仓位)
    max_position_size_usd: float = 1000.0  # 单个仓位最大价值
    min_position_size_usd: float = 10.0  # 最小仓位价值（过滤小仓位）
    
    # 白名单/黑名单
    symbols_whitelist: List[str] = field(default_factory=list)  # 只跟单这些币
    symbols_blacklist: List[str] = field(default_factory=list)  # 不跟单这些币
    
    # 杠杆设置
    copy_leverage: bool = True  # 是否复制杠杆
    max_leverage: int = 10  # 最大杠杆限制
    default_leverage: int = 5  # 默认杠杆
    
    # 延迟设置
    check_interval: float = 5.0  # 检查间隔（秒）
    order_delay: float = 0.5  # 下单延迟（秒）
    
    # 风控
    max_total_positions: int = 10  # 最大持仓数
    max_daily_trades: int = 50  # 每日最大交易次数
    slippage: float = 0.01  # 滑点容忍度
    
    # 模式
    dry_run: bool = True  # 模拟模式


@dataclass
class CopyTradingState:
    """跟单状态"""
    is_running: bool = False
    last_check: Optional[datetime] = None
    
    # 目标交易者状态
    target_positions: Dict[str, Dict] = field(default_factory=dict)
    
    # 本地状态
    my_positions: Dict[str, Position] = field(default_factory=dict)
    copied_positions: Dict[str, Dict] = field(default_factory=dict)  # 已复制的仓位记录
    
    # 统计
    total_copies_today: int = 0
    successful_copies: int = 0
    failed_copies: int = 0
    daily_pnl: float = 0.0


class CopyTradingBot:
    """
    跟单机器人
    
    监控目标交易者的持仓变化并自动复制交易
    """
    
    def __init__(
        self,
        client: HyperliquidClient,
        config: Optional[CopyTradingConfig] = None
    ):
        """
        初始化跟单机器人
        
        Args:
            client: Hyperliquid 客户端（需要已初始化钱包）
            config: 跟单配置
        """
        self.client = client
        self.config = config or CopyTradingConfig()
        self.state = CopyTradingState()
        
        # 用于读取目标交易者数据的 Info 客户端
        self.target_info = Info(client.api_url, skip_ws=True)
        
        # 事件回调
        self._on_copy: Optional[Callable[[str, str, float], None]] = None
        self._on_close: Optional[Callable[[str, float], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        
        if not self.config.target_address:
            logger.warning("未配置目标交易者地址")
    
    def set_on_copy(self, callback: Callable[[str, str, float], None]):
        """设置复制成功回调 (symbol, side, size)"""
        self._on_copy = callback
    
    def set_on_close(self, callback: Callable[[str, float], None]):
        """设置平仓回调 (symbol, pnl)"""
        self._on_close = callback
    
    def set_on_error(self, callback: Callable[[Exception], None]):
        """设置错误回调"""
        self._on_error = callback
    
    def _should_copy_symbol(self, symbol: str) -> bool:
        """检查是否应该复制该币种"""
        # 黑名单检查
        if self.config.symbols_blacklist and symbol in self.config.symbols_blacklist:
            return False
        
        # 白名单检查
        if self.config.symbols_whitelist:
            return symbol in self.config.symbols_whitelist
        
        return True
    
    def _get_target_positions(self) -> Dict[str, Dict]:
        """
        获取目标交易者的当前持仓
        
        Returns:
            {symbol: position_info} 字典
        """
        try:
            state = self.target_info.user_state(self.config.target_address)
            positions = {}
            
            for pos_data in state.get('assetPositions', []):
                pos = pos_data.get('position', {})
                size = float(pos.get('szi', 0))
                
                if size != 0:
                    symbol = pos.get('coin', '')
                    leverage_info = pos.get('leverage', {})
                    
                    positions[symbol] = {
                        'symbol': symbol,
                        'size': size,
                        'side': 'long' if size > 0 else 'short',
                        'entry_price': float(pos.get('entryPx', 0)),
                        'mark_price': float(pos.get('markPx', 0)) if 'markPx' in pos else 0,
                        'leverage': int(leverage_info.get('value', 1)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'notional': abs(size) * float(pos.get('entryPx', 0))
                    }
            
            return positions
        
        except Exception as e:
            logger.error(f"获取目标持仓失败: {e}")
            return {}
    
    def _get_my_positions(self) -> Dict[str, Position]:
        """获取自己的当前持仓"""
        positions = {}
        for pos in self.client.get_positions():
            positions[pos.symbol] = pos
        return positions
    
    def _calculate_copy_size(
        self,
        target_position: Dict,
        current_price: float
    ) -> float:
        """
        计算跟单仓位大小
        
        Args:
            target_position: 目标持仓信息
            current_price: 当前价格
        
        Returns:
            跟单数量
        """
        # 目标仓位价值
        target_notional = target_position['notional']
        
        # 按比例计算
        copy_notional = target_notional * self.config.copy_ratio
        
        # 限制最大最小值
        copy_notional = max(copy_notional, self.config.min_position_size_usd)
        copy_notional = min(copy_notional, self.config.max_position_size_usd)
        
        # 计算数量
        size = copy_notional / current_price
        
        # 获取精度
        meta = self.client.get_meta()
        for asset in meta.get('universe', []):
            if asset['name'] == target_position['symbol']:
                decimals = asset.get('szDecimals', 4)
                size = round(size, decimals)
                break
        
        return size
    
    async def _open_position(
        self,
        symbol: str,
        is_long: bool,
        size: float,
        leverage: int
    ) -> bool:
        """
        开仓
        
        Args:
            symbol: 交易对
            is_long: 是否做多
            size: 数量
            leverage: 杠杆
        
        Returns:
            是否成功
        """
        try:
            if self.config.dry_run:
                logger.info(f"[模拟] 开仓: {symbol} {'多' if is_long else '空'} {size} x{leverage}")
                return True
            
            # 设置杠杆
            self.client.set_leverage(symbol, leverage)
            
            # 延迟
            await asyncio.sleep(self.config.order_delay)
            
            # 市价开仓
            result = self.client.market_order(
                symbol,
                is_long,
                size,
                slippage=self.config.slippage
            )
            
            success = result.get('status') == 'ok'
            
            if success:
                logger.info(f"开仓成功: {symbol} {'多' if is_long else '空'} {size}")
                self.state.successful_copies += 1
                
                if self._on_copy:
                    self._on_copy(symbol, 'long' if is_long else 'short', size)
            else:
                logger.error(f"开仓失败: {result}")
                self.state.failed_copies += 1
            
            return success
        
        except Exception as e:
            logger.error(f"开仓异常: {e}")
            self.state.failed_copies += 1
            if self._on_error:
                self._on_error(e)
            return False
    
    async def _close_position(self, symbol: str) -> bool:
        """
        平仓
        
        Args:
            symbol: 交易对
        
        Returns:
            是否成功
        """
        try:
            if self.config.dry_run:
                logger.info(f"[模拟] 平仓: {symbol}")
                return True
            
            # 获取当前仓位 PnL
            my_pos = self.state.my_positions.get(symbol)
            pnl = my_pos.unrealized_pnl if my_pos else 0
            
            result = self.client.close_position(symbol, slippage=self.config.slippage)
            
            success = result.get('status') == 'ok'
            
            if success:
                logger.info(f"平仓成功: {symbol}, PnL: {pnl:.2f}")
                self.state.daily_pnl += pnl
                
                if self._on_close:
                    self._on_close(symbol, pnl)
            else:
                logger.error(f"平仓失败: {result}")
            
            return success
        
        except Exception as e:
            logger.error(f"平仓异常: {e}")
            if self._on_error:
                self._on_error(e)
            return False
    
    async def _adjust_position(
        self,
        symbol: str,
        target_position: Dict,
        my_position: Optional[Position]
    ) -> bool:
        """
        调整仓位（增加或减少）
        
        Args:
            symbol: 交易对
            target_position: 目标仓位
            my_position: 我的当前仓位
        
        Returns:
            是否成功
        """
        try:
            target_is_long = target_position['side'] == 'long'
            target_size = abs(target_position['size'])
            
            current_price = self.client.get_mid_price(symbol)
            copy_size = self._calculate_copy_size(target_position, current_price)
            
            if my_position is None:
                # 没有仓位，直接开仓
                leverage = target_position['leverage'] if self.config.copy_leverage else self.config.default_leverage
                leverage = min(leverage, self.config.max_leverage)
                return await self._open_position(symbol, target_is_long, copy_size, leverage)
            
            my_is_long = my_position.side == PositionSide.LONG
            my_size = my_position.size
            
            # 方向不同，先平仓再反向开仓
            if target_is_long != my_is_long:
                await self._close_position(symbol)
                await asyncio.sleep(self.config.order_delay)
                leverage = target_position['leverage'] if self.config.copy_leverage else self.config.default_leverage
                leverage = min(leverage, self.config.max_leverage)
                return await self._open_position(symbol, target_is_long, copy_size, leverage)
            
            # 方向相同，调整仓位大小（如果变化超过10%）
            size_diff_ratio = abs(copy_size - my_size) / my_size if my_size > 0 else 1
            
            if size_diff_ratio > 0.1:
                if copy_size > my_size:
                    # 加仓
                    add_size = round(copy_size - my_size, 6)
                    if add_size * current_price >= self.config.min_position_size_usd:
                        if self.config.dry_run:
                            logger.info(f"[模拟] 加仓: {symbol} +{add_size}")
                            return True
                        result = self.client.market_order(symbol, target_is_long, add_size)
                        return result.get('status') == 'ok'
                else:
                    # 减仓
                    reduce_size = round(my_size - copy_size, 6)
                    if reduce_size * current_price >= self.config.min_position_size_usd:
                        if self.config.dry_run:
                            logger.info(f"[模拟] 减仓: {symbol} -{reduce_size}")
                            return True
                        result = self.client.market_order(symbol, not target_is_long, reduce_size)
                        return result.get('status') == 'ok'
            
            return True
        
        except Exception as e:
            logger.error(f"调整仓位异常: {e}")
            if self._on_error:
                self._on_error(e)
            return False
    
    async def _sync_positions(self):
        """
        同步持仓（核心逻辑）
        
        比较目标交易者和自己的持仓，执行必要的交易
        """
        # 获取目标和自己的持仓
        target_positions = self._get_target_positions()
        my_positions = self._get_my_positions()
        
        self.state.target_positions = target_positions
        self.state.my_positions = my_positions
        
        # 检查每日交易次数限制
        if self.state.total_copies_today >= self.config.max_daily_trades:
            logger.warning("达到每日最大交易次数限制")
            return
        
        # 检查最大持仓数
        if len(my_positions) >= self.config.max_total_positions:
            logger.warning("达到最大持仓数限制")
        
        # 处理目标新开的仓位（开仓/调整）
        for symbol, target_pos in target_positions.items():
            if not self._should_copy_symbol(symbol):
                continue
            
            # 过滤小仓位
            if target_pos['notional'] < self.config.min_position_size_usd:
                continue
            
            my_pos = my_positions.get(symbol)
            
            # 检查是否是新仓位或需要调整
            prev_target = self.state.copied_positions.get(symbol)
            
            if prev_target is None:
                # 新仓位
                logger.info(f"发现新仓位: {symbol} {target_pos['side']} {abs(target_pos['size'])}")
                await self._adjust_position(symbol, target_pos, my_pos)
                self.state.total_copies_today += 1
            else:
                # 检查是否需要调整
                if prev_target['side'] != target_pos['side']:
                    # 方向变化
                    logger.info(f"仓位方向变化: {symbol} {prev_target['side']} -> {target_pos['side']}")
                    await self._adjust_position(symbol, target_pos, my_pos)
                    self.state.total_copies_today += 1
            
            # 更新已复制仓位记录
            self.state.copied_positions[symbol] = target_pos
        
        # 处理目标已平的仓位（平仓）
        for symbol in list(self.state.copied_positions.keys()):
            if symbol not in target_positions:
                # 目标已平仓
                if symbol in my_positions:
                    logger.info(f"目标已平仓: {symbol}")
                    await self._close_position(symbol)
                    self.state.total_copies_today += 1
                
                del self.state.copied_positions[symbol]
    
    async def run(self):
        """
        运行跟单机器人
        
        主循环，持续监控并复制交易
        """
        if not self.config.target_address:
            raise ValueError("请配置目标交易者地址")
        
        self.state.is_running = True
        
        logger.info("=" * 50)
        logger.info("跟单机器人启动")
        logger.info(f"目标地址: {self.config.target_address}")
        logger.info(f"跟单比例: {self.config.copy_ratio * 100}%")
        logger.info(f"最大仓位: ${self.config.max_position_size_usd}")
        logger.info(f"检查间隔: {self.config.check_interval}秒")
        logger.info(f"模拟模式: {self.config.dry_run}")
        logger.info("=" * 50)
        
        try:
            while self.state.is_running:
                await self._sync_positions()
                self.state.last_check = datetime.now()
                await asyncio.sleep(self.config.check_interval)
        
        except asyncio.CancelledError:
            logger.info("跟单机器人被取消")
        except Exception as e:
            logger.error(f"跟单机器人异常: {e}")
            if self._on_error:
                self._on_error(e)
        finally:
            self.state.is_running = False
            logger.info("跟单机器人停止")
    
    def stop(self):
        """停止机器人"""
        self.state.is_running = False
        logger.info("正在停止跟单机器人...")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取机器人状态
        
        Returns:
            状态信息字典
        """
        return {
            "is_running": self.state.is_running,
            "target_address": self.config.target_address,
            "copy_ratio": self.config.copy_ratio,
            "dry_run": self.config.dry_run,
            "last_check": self.state.last_check.isoformat() if self.state.last_check else None,
            
            "target_positions": [
                {
                    "symbol": p['symbol'],
                    "side": p['side'],
                    "size": abs(p['size']),
                    "entry_price": p['entry_price'],
                    "unrealized_pnl": p['unrealized_pnl']
                }
                for p in self.state.target_positions.values()
            ],
            
            "my_positions": [
                {
                    "symbol": p.symbol,
                    "side": p.side.value,
                    "size": p.size,
                    "entry_price": p.entry_price,
                    "unrealized_pnl": p.unrealized_pnl
                }
                for p in self.state.my_positions.values()
            ],
            
            "stats": {
                "total_copies_today": self.state.total_copies_today,
                "successful_copies": self.state.successful_copies,
                "failed_copies": self.state.failed_copies,
                "daily_pnl": self.state.daily_pnl
            }
        }
    
    def get_target_fills(self, limit: int = 20) -> List[Dict]:
        """
        获取目标交易者的最近成交
        
        Args:
            limit: 返回数量
        
        Returns:
            成交记录列表
        """
        try:
            fills = self.target_info.user_fills(self.config.target_address)[:limit]
            return [
                {
                    "symbol": f.get('coin', ''),
                    "side": 'buy' if f.get('side') == 'B' else 'sell',
                    "price": float(f.get('px', 0)),
                    "size": float(f.get('sz', 0)),
                    "time": datetime.fromtimestamp(f.get('time', 0) / 1000).isoformat(),
                    "pnl": float(f.get('closedPnl', 0))
                }
                for f in fills
            ]
        except Exception as e:
            logger.error(f"获取目标成交失败: {e}")
            return []


class CopyTradingBotWithWebSocket(CopyTradingBot):
    """
    使用 WebSocket 的跟单机器人
    
    通过 WebSocket 订阅目标交易者的实时交易，降低延迟
    """
    
    def __init__(
        self,
        client: HyperliquidClient,
        config: Optional[CopyTradingConfig] = None
    ):
        super().__init__(client, config)
        
        # WebSocket Info 客户端
        self.ws_info = None
        self._pending_trades: List[Dict] = []
    
    def _on_target_trade(self, message: Dict[str, Any]):
        """目标交易者成交回调"""
        data = message.get('data', {})
        
        if isinstance(data, list):
            for fill in data:
                self._pending_trades.append({
                    'symbol': fill.get('coin', ''),
                    'side': 'buy' if fill.get('side') == 'B' else 'sell',
                    'size': float(fill.get('sz', 0)),
                    'price': float(fill.get('px', 0)),
                    'time': fill.get('time', 0)
                })
                logger.info(f"检测到目标交易: {fill.get('coin')} {fill.get('side')}")
    
    async def _process_pending_trades(self):
        """处理待执行的交易"""
        while self._pending_trades:
            trade = self._pending_trades.pop(0)
            symbol = trade['symbol']
            
            if not self._should_copy_symbol(symbol):
                continue
            
            # 获取目标当前持仓
            target_positions = self._get_target_positions()
            my_positions = self._get_my_positions()
            
            target_pos = target_positions.get(symbol)
            my_pos = my_positions.get(symbol)
            
            if target_pos:
                await self._adjust_position(symbol, target_pos, my_pos)
            elif my_pos:
                # 目标已无仓位，平仓
                await self._close_position(symbol)
            
            self.state.total_copies_today += 1
    
    async def run(self):
        """运行带 WebSocket 的跟单机器人"""
        if not self.config.target_address:
            raise ValueError("请配置目标交易者地址")
        
        self.state.is_running = True
        
        logger.info("=" * 50)
        logger.info("WebSocket 跟单机器人启动")
        logger.info(f"目标地址: {self.config.target_address}")
        logger.info("=" * 50)
        
        # 初始化 WebSocket
        self.ws_info = Info(self.client.api_url, skip_ws=False)
        
        # 订阅目标交易者的成交
        self.ws_info.subscribe(
            {"type": "userFills", "user": self.config.target_address},
            self._on_target_trade
        )
        
        logger.info(f"已订阅目标交易者: {self.config.target_address}")
        
        try:
            # 先同步一次现有仓位
            await self._sync_positions()
            
            while self.state.is_running:
                # 处理 WebSocket 收到的交易
                if self._pending_trades:
                    await self._process_pending_trades()
                
                # 定期全量同步（防止遗漏）
                await self._sync_positions()
                self.state.last_check = datetime.now()
                
                await asyncio.sleep(self.config.check_interval)
        
        except asyncio.CancelledError:
            logger.info("WebSocket 跟单机器人被取消")
        except Exception as e:
            logger.error(f"WebSocket 跟单机器人异常: {e}")
            if self._on_error:
                self._on_error(e)
        finally:
            self.state.is_running = False
            logger.info("WebSocket 跟单机器人停止")

