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


class TargetSubscriptionManager:
    """
    目标交易者 WebSocket 订阅管理器

    管理多个目标的 WebSocket 订阅，实时接收成交通知
    """

    def __init__(self, api_url: str):
        self.api_url = api_url
        self.ws_info: Optional[Info] = None
        self._subscribed_addresses: set = set()
        self._pending_fills: Dict[str, List[Dict]] = {}  # {address: [fills]}
        self._lock = asyncio.Lock()

    def _ensure_ws(self):
        """确保 WebSocket 连接"""
        if self.ws_info is None:
            self.ws_info = Info(self.api_url, skip_ws=False)

    def subscribe(self, address: str):
        """订阅目标交易者的成交"""
        if address in self._subscribed_addresses:
            return

        self._ensure_ws()
        self._pending_fills[address] = []

        def on_fill(message: Dict[str, Any]):
            self._handle_fill(address, message)

        self.ws_info.subscribe(
            {"type": "userFills", "user": address},
            on_fill
        )
        self._subscribed_addresses.add(address)
        logger.info(f"已订阅目标: {address[:10]}...")

    def unsubscribe(self, address: str):
        """取消订阅（注意：hyperliquid SDK 可能不支持取消订阅）"""
        if address in self._subscribed_addresses:
            self._subscribed_addresses.discard(address)
            if address in self._pending_fills:
                del self._pending_fills[address]
            logger.info(f"已取消订阅: {address[:10]}...")

    def _handle_fill(self, address: str, message: Dict[str, Any]):
        """处理收到的成交通知"""
        data = message.get('data', {})

        if isinstance(data, list):
            for fill in data:
                fill_info = {
                    'symbol': fill.get('coin', ''),
                    'side': 'buy' if fill.get('side') == 'B' else 'sell',
                    'size': float(fill.get('sz', 0)),
                    'price': float(fill.get('px', 0)),
                    'time': fill.get('time', 0),
                    'oid': fill.get('oid', ''),
                    'closed_pnl': float(fill.get('closedPnl', 0))
                }

                if address in self._pending_fills:
                    self._pending_fills[address].append(fill_info)
                    logger.info(
                        f"[WS] [{address[:8]}] 成交: {fill_info['symbol']} "
                        f"{fill_info['side']} {fill_info['size']} @ {fill_info['price']}"
                    )

    def get_pending_fills(self, address: str) -> List[Dict]:
        """获取并清空待处理的成交"""
        if address not in self._pending_fills:
            return []
        fills = self._pending_fills[address]
        self._pending_fills[address] = []
        return fills

    def has_pending_fills(self, address: str) -> bool:
        """检查是否有待处理的成交"""
        return bool(self._pending_fills.get(address, []))

    def get_all_pending_addresses(self) -> List[str]:
        """获取所有有待处理成交的地址"""
        return [addr for addr, fills in self._pending_fills.items() if fills]

    @property
    def subscribed_count(self) -> int:
        return len(self._subscribed_addresses)


@dataclass
class TargetTraderState:
    """单个目标交易者的状态"""
    address: str
    config: CopyTradingConfig
    positions: Dict[str, Dict] = field(default_factory=dict)
    copied_positions: Dict[str, Dict] = field(default_factory=dict)
    last_check: Optional[datetime] = None
    copies_today: int = 0
    successful_copies: int = 0
    failed_copies: int = 0
    daily_pnl: float = 0.0


class MultiTargetCopyTradingBot:
    """
    多目标跟单机器人

    从数据库加载跟单配置，支持同时跟单多个交易者
    """

    def __init__(
        self,
        client: HyperliquidClient,
        db_path: str = "data/traders.db",
        global_dry_run: bool = True,
        check_interval: float = 10.0,
        reload_interval: float = 60.0
    ):
        """
        初始化多目标跟单机器人

        Args:
            client: Hyperliquid 客户端（需要已初始化钱包）
            db_path: 数据库路径
            global_dry_run: 全局模拟模式（覆盖数据库配置）
            check_interval: 检查间隔（秒）
            reload_interval: 配置重载间隔（秒）
        """
        self.client = client
        self.db_path = db_path
        self.global_dry_run = global_dry_run
        self.check_interval = check_interval
        self.reload_interval = reload_interval

        # 目标交易者状态
        self.targets: Dict[str, TargetTraderState] = {}

        # 自己的持仓
        self.my_positions: Dict[str, Position] = {}

        # 运行状态
        self.is_running = False
        self.last_config_reload: Optional[datetime] = None

        # 回调
        self._on_copy: Optional[Callable[[str, str, str, float], None]] = None
        self._on_close: Optional[Callable[[str, str, float], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

        # 延迟加载数据库（避免循环导入）
        self._db = None

    @property
    def db(self):
        """延迟加载数据库"""
        if self._db is None:
            from screener.database import TraderDatabase
            self._db = TraderDatabase(self.db_path)
        return self._db

    def set_on_copy(self, callback: Callable[[str, str, str, float], None]):
        """设置复制成功回调 (target_address, symbol, side, size)"""
        self._on_copy = callback

    def set_on_close(self, callback: Callable[[str, str, float], None]):
        """设置平仓回调 (target_address, symbol, pnl)"""
        self._on_close = callback

    def set_on_error(self, callback: Callable[[Exception], None]):
        """设置错误回调"""
        self._on_error = callback

    def _load_configs_from_db(self) -> List[Dict]:
        """从数据库加载启用的跟单配置"""
        try:
            return self.db.get_enabled_copy_addresses()
        except Exception as e:
            logger.error(f"加载跟单配置失败: {e}")
            return []

    def _dict_to_config(self, data: Dict) -> CopyTradingConfig:
        """将数据库记录转换为 CopyTradingConfig"""
        return CopyTradingConfig(
            target_address=data.get('address', ''),
            copy_ratio=data.get('copy_ratio', 0.1),
            max_position_size_usd=data.get('max_position_size_usd', 500.0),
            min_position_size_usd=data.get('min_position_size_usd', 20.0),
            symbols_whitelist=data.get('symbols_whitelist', []),
            symbols_blacklist=data.get('symbols_blacklist', []),
            copy_leverage=data.get('copy_leverage', True),
            max_leverage=data.get('max_leverage', 10),
            default_leverage=data.get('default_leverage', 5),
            check_interval=data.get('check_interval', 10.0),
            order_delay=0.5,
            max_total_positions=data.get('max_total_positions', 10),
            max_daily_trades=data.get('max_daily_trades', 50),
            slippage=data.get('slippage', 0.01),
            dry_run=self.global_dry_run or data.get('dry_run', True)
        )

    def reload_configs(self):
        """重新加载配置（添加新的、移除禁用的、更新已有的）"""
        configs = self._load_configs_from_db()
        current_addresses = set(self.targets.keys())
        new_addresses = set()

        for data in configs:
            address = data.get('address')
            if not address:
                continue

            new_addresses.add(address)
            config = self._dict_to_config(data)

            if address in self.targets:
                # 更新已有配置
                self.targets[address].config = config
                logger.debug(f"更新跟单配置: {address[:10]}...")
            else:
                # 添加新目标
                self.targets[address] = TargetTraderState(
                    address=address,
                    config=config
                )
                logger.info(f"添加跟单目标: {address[:10]}... (比例: {config.copy_ratio * 100}%)")

        # 移除已禁用的目标
        for address in current_addresses - new_addresses:
            del self.targets[address]
            logger.info(f"移除跟单目标: {address[:10]}...")

        self.last_config_reload = datetime.now()
        logger.info(f"配置加载完成: 共 {len(self.targets)} 个跟单目标")

    def _should_copy_symbol(self, config: CopyTradingConfig, symbol: str) -> bool:
        """检查是否应该复制该币种"""
        if config.symbols_blacklist and symbol in config.symbols_blacklist:
            return False
        if config.symbols_whitelist:
            return symbol in config.symbols_whitelist
        return True

    def _get_target_positions(self, address: str) -> Dict[str, Dict]:
        """获取目标交易者的当前持仓"""
        try:
            from hyperliquid.utils import constants
            # 使用 client 的 api_url，如果 client 为 None 则使用主网 API
            api_url = self.client.api_url if self.client else constants.MAINNET_API_URL
            info = Info(api_url, skip_ws=True)
            state = info.user_state(address)
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
                        'leverage': int(leverage_info.get('value', 1)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'notional': abs(size) * float(pos.get('entryPx', 0))
                    }

            return positions

        except Exception as e:
            logger.error(f"获取目标持仓失败 {address[:10]}...: {e}")
            return {}

    def _get_my_positions(self) -> Dict[str, Position]:
        """获取自己的当前持仓"""
        # 模拟模式下无需客户端
        if self.client is None:
            return {}
        positions = {}
        for pos in self.client.get_positions():
            positions[pos.symbol] = pos
        return positions

    def _calculate_copy_size(
        self,
        config: CopyTradingConfig,
        target_position: Dict,
        current_price: float
    ) -> float:
        """计算跟单仓位大小"""
        target_notional = target_position['notional']
        copy_notional = target_notional * config.copy_ratio

        copy_notional = max(copy_notional, config.min_position_size_usd)
        copy_notional = min(copy_notional, config.max_position_size_usd)

        size = copy_notional / current_price

        # 获取精度（模拟模式下使用默认精度）
        decimals = 4
        if self.client is not None:
            meta = self.client.get_meta()
            for asset in meta.get('universe', []):
                if asset['name'] == target_position['symbol']:
                    decimals = asset.get('szDecimals', 4)
                    break

        return round(size, decimals)

    async def _open_position(
        self,
        target_state: TargetTraderState,
        symbol: str,
        is_long: bool,
        size: float,
        leverage: int,
        target_position: Dict = None
    ) -> bool:
        """开仓"""
        config = target_state.config
        side = 'long' if is_long else 'short'
        # 模拟模式下使用目标持仓的入场价格
        if self.client is not None:
            price = self.client.get_mid_price(symbol)
        else:
            price = target_position.get('entry_price', 0) if target_position else 0

        # 创建订单记录
        order_data = {
            'target_address': target_state.address,
            'symbol': symbol,
            'side': side,
            'action': 'open',
            'size': size,
            'price': price,
            'leverage': leverage,
            'copy_ratio': config.copy_ratio,
            'target_size': abs(target_position['size']) if target_position else None,
            'target_entry_price': target_position['entry_price'] if target_position else None,
            'status': 'pending',
            'is_dry_run': config.dry_run,
            'created_at': datetime.now().isoformat()
        }

        try:
            if config.dry_run:
                logger.info(f"[模拟] [{target_state.address[:8]}] 开仓: {symbol} {side} {size} x{leverage}")
                order_data['status'] = 'success'
                order_data['executed_at'] = datetime.now().isoformat()
                self._save_order(order_data)
                target_state.successful_copies += 1
                if self._on_copy:
                    self._on_copy(target_state.address, symbol, side, size)
                return True

            self.client.set_leverage(symbol, leverage)
            await asyncio.sleep(0.5)

            result = self.client.market_order(
                symbol, is_long, size,
                slippage=config.slippage
            )

            success = result.get('status') == 'ok'
            order_data['executed_at'] = datetime.now().isoformat()

            if success:
                logger.info(f"[{target_state.address[:8]}] 开仓成功: {symbol} {side} {size}")
                order_data['status'] = 'success'
                target_state.successful_copies += 1
                if self._on_copy:
                    self._on_copy(target_state.address, symbol, side, size)
            else:
                logger.error(f"[{target_state.address[:8]}] 开仓失败: {result}")
                order_data['status'] = 'failed'
                order_data['error_message'] = str(result)
                target_state.failed_copies += 1

            self._save_order(order_data)
            return success

        except Exception as e:
            logger.error(f"[{target_state.address[:8]}] 开仓异常: {e}")
            order_data['status'] = 'failed'
            order_data['error_message'] = str(e)
            order_data['executed_at'] = datetime.now().isoformat()
            self._save_order(order_data)
            target_state.failed_copies += 1
            if self._on_error:
                self._on_error(e)
            return False

    async def _close_position(
        self,
        target_state: TargetTraderState,
        symbol: str
    ) -> bool:
        """平仓"""
        config = target_state.config
        my_pos = self.my_positions.get(symbol)
        pnl = my_pos.unrealized_pnl if my_pos else 0
        size = my_pos.size if my_pos else 0
        side = 'long' if my_pos and my_pos.side == PositionSide.LONG else 'short'
        # 模拟模式下使用 0 作为价格
        price = self.client.get_mid_price(symbol) if self.client is not None else 0

        # 创建订单记录
        order_data = {
            'target_address': target_state.address,
            'symbol': symbol,
            'side': side,
            'action': 'close',
            'size': abs(size),
            'price': price,
            'leverage': 1,
            'copy_ratio': config.copy_ratio,
            'pnl': pnl,
            'status': 'pending',
            'is_dry_run': config.dry_run,
            'created_at': datetime.now().isoformat()
        }

        try:
            if config.dry_run:
                logger.info(f"[模拟] [{target_state.address[:8]}] 平仓: {symbol}")
                order_data['status'] = 'success'
                order_data['executed_at'] = datetime.now().isoformat()
                self._save_order(order_data)
                target_state.daily_pnl += pnl
                if self._on_close:
                    self._on_close(target_state.address, symbol, pnl)
                return True

            result = self.client.close_position(symbol, slippage=config.slippage)
            success = result.get('status') == 'ok'
            order_data['executed_at'] = datetime.now().isoformat()

            if success:
                logger.info(f"[{target_state.address[:8]}] 平仓成功: {symbol}, PnL: {pnl:.2f}")
                order_data['status'] = 'success'
                target_state.daily_pnl += pnl
                if self._on_close:
                    self._on_close(target_state.address, symbol, pnl)
            else:
                logger.error(f"[{target_state.address[:8]}] 平仓失败: {result}")
                order_data['status'] = 'failed'
                order_data['error_message'] = str(result)

            self._save_order(order_data)
            return success

        except Exception as e:
            logger.error(f"[{target_state.address[:8]}] 平仓异常: {e}")
            order_data['status'] = 'failed'
            order_data['error_message'] = str(e)
            order_data['executed_at'] = datetime.now().isoformat()
            self._save_order(order_data)
            if self._on_error:
                self._on_error(e)
            return False

    def _save_order(self, order_data: Dict):
        """保存订单到数据库"""
        try:
            self.db.save_copy_order(order_data)
        except Exception as e:
            logger.error(f"保存订单记录失败: {e}")

    async def _sync_target(self, target_state: TargetTraderState):
        """同步单个目标的持仓"""
        config = target_state.config
        address = target_state.address

        # 检查每日交易次数限制
        if target_state.copies_today >= config.max_daily_trades:
            return

        # 获取目标持仓
        target_positions = self._get_target_positions(address)
        target_state.positions = target_positions

        # 处理新开仓/调整仓位
        for symbol, target_pos in target_positions.items():
            if not self._should_copy_symbol(config, symbol):
                continue

            if target_pos['notional'] < config.min_position_size_usd:
                continue

            my_pos = self.my_positions.get(symbol)
            prev_target = target_state.copied_positions.get(symbol)

            if prev_target is None:
                # 新仓位
                logger.info(f"[{address[:8]}] 发现新仓位: {symbol} {target_pos['side']} {abs(target_pos['size'])}")

                # 模拟模式下使用目标持仓的入场价格
                current_price = self.client.get_mid_price(symbol) if self.client else target_pos.get('entry_price', 1)
                copy_size = self._calculate_copy_size(config, target_pos, current_price)
                leverage = target_pos['leverage'] if config.copy_leverage else config.default_leverage
                leverage = min(leverage, config.max_leverage)

                is_long = target_pos['side'] == 'long'

                if my_pos is None:
                    await self._open_position(target_state, symbol, is_long, copy_size, leverage, target_pos)
                elif (my_pos.side == PositionSide.LONG) != is_long:
                    # 方向不同，先平后开
                    await self._close_position(target_state, symbol)
                    await asyncio.sleep(0.5)
                    await self._open_position(target_state, symbol, is_long, copy_size, leverage, target_pos)

                target_state.copies_today += 1

            elif prev_target['side'] != target_pos['side']:
                # 方向变化
                logger.info(f"[{address[:8]}] 仓位方向变化: {symbol} {prev_target['side']} -> {target_pos['side']}")

                await self._close_position(target_state, symbol)
                await asyncio.sleep(0.5)

                # 模拟模式下使用目标持仓的入场价格
                current_price = self.client.get_mid_price(symbol) if self.client else target_pos.get('entry_price', 1)
                copy_size = self._calculate_copy_size(config, target_pos, current_price)
                leverage = target_pos['leverage'] if config.copy_leverage else config.default_leverage
                leverage = min(leverage, config.max_leverage)

                await self._open_position(target_state, symbol, target_pos['side'] == 'long', copy_size, leverage, target_pos)
                target_state.copies_today += 1

            target_state.copied_positions[symbol] = target_pos

        # 处理平仓
        for symbol in list(target_state.copied_positions.keys()):
            if symbol not in target_positions:
                if symbol in self.my_positions:
                    logger.info(f"[{address[:8]}] 目标已平仓: {symbol}")
                    await self._close_position(target_state, symbol)
                    target_state.copies_today += 1

                del target_state.copied_positions[symbol]

        target_state.last_check = datetime.now()

    async def _sync_all_targets(self):
        """同步所有目标"""
        # 更新自己的持仓
        self.my_positions = self._get_my_positions()

        # 并发同步所有目标
        tasks = [self._sync_target(state) for state in self.targets.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run(self):
        """运行多目标跟单机器人"""
        self.is_running = True

        logger.info("=" * 60)
        logger.info("多目标跟单机器人启动")
        logger.info(f"全局模拟模式: {self.global_dry_run}")
        logger.info(f"检查间隔: {self.check_interval}秒")
        logger.info(f"配置重载间隔: {self.reload_interval}秒")
        logger.info("=" * 60)

        # 加载初始配置
        self.reload_configs()

        if not self.targets:
            logger.warning("没有启用的跟单目标，请先在跟单管理中添加并启用地址")

        try:
            while self.is_running:
                # 检查是否需要重载配置
                if (self.last_config_reload is None or
                    (datetime.now() - self.last_config_reload).seconds >= self.reload_interval):
                    self.reload_configs()

                if self.targets:
                    await self._sync_all_targets()

                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("多目标跟单机器人被取消")
        except Exception as e:
            logger.error(f"多目标跟单机器人异常: {e}")
            if self._on_error:
                self._on_error(e)
        finally:
            self.is_running = False
            logger.info("多目标跟单机器人停止")

    def stop(self):
        """停止机器人"""
        self.is_running = False
        logger.info("正在停止多目标跟单机器人...")

    def get_status(self) -> Dict[str, Any]:
        """获取机器人状态"""
        targets_status = []
        total_stats = {
            'total_copies_today': 0,
            'successful_copies': 0,
            'failed_copies': 0,
            'daily_pnl': 0.0
        }

        for address, state in self.targets.items():
            targets_status.append({
                'address': address,
                'name': state.config.target_address[:10] + '...',
                'copy_ratio': state.config.copy_ratio,
                'dry_run': state.config.dry_run,
                'last_check': state.last_check.isoformat() if state.last_check else None,
                'positions': list(state.positions.keys()),
                'copies_today': state.copies_today,
                'successful': state.successful_copies,
                'failed': state.failed_copies,
                'daily_pnl': state.daily_pnl
            })

            total_stats['total_copies_today'] += state.copies_today
            total_stats['successful_copies'] += state.successful_copies
            total_stats['failed_copies'] += state.failed_copies
            total_stats['daily_pnl'] += state.daily_pnl

        return {
            'is_running': self.is_running,
            'global_dry_run': self.global_dry_run,
            'target_count': len(self.targets),
            'targets': targets_status,
            'my_positions': [
                {
                    'symbol': p.symbol,
                    'side': p.side.value,
                    'size': p.size,
                    'unrealized_pnl': p.unrealized_pnl
                }
                for p in self.my_positions.values()
            ],
            'total_stats': total_stats,
            'last_config_reload': self.last_config_reload.isoformat() if self.last_config_reload else None
        }


class MultiTargetCopyTradingBotWithWebSocket(MultiTargetCopyTradingBot):
    """
    基于 WebSocket 的多目标跟单机器人

    通过 WebSocket 订阅目标交易者的实时成交，实现低延迟跟单
    特点：
    - 实时接收目标交易者的成交通知
    - 自动管理多个目标的 WebSocket 订阅
    - 配置热重载时自动更新订阅
    - 定期全量同步作为兜底
    """

    def __init__(
        self,
        client: HyperliquidClient,
        db_path: str = "data/traders.db",
        global_dry_run: bool = True,
        check_interval: float = 2.0,  # WebSocket 模式下可以更快检查
        reload_interval: float = 60.0,
        sync_interval: float = 30.0  # 全量同步间隔
    ):
        super().__init__(
            client=client,
            db_path=db_path,
            global_dry_run=global_dry_run,
            check_interval=check_interval,
            reload_interval=reload_interval
        )
        self.sync_interval = sync_interval
        self.last_full_sync: Optional[datetime] = None

        # WebSocket 订阅管理器
        from hyperliquid.utils import constants
        api_url = client.api_url if client else constants.MAINNET_API_URL
        self.subscription_manager = TargetSubscriptionManager(api_url)

    def reload_configs(self):
        """重新加载配置并更新订阅"""
        old_addresses = set(self.targets.keys())

        # 调用父类方法加载配置
        super().reload_configs()

        new_addresses = set(self.targets.keys())

        # 订阅新增的目标
        for address in new_addresses - old_addresses:
            self.subscription_manager.subscribe(address)

        # 取消已移除目标的订阅
        for address in old_addresses - new_addresses:
            self.subscription_manager.unsubscribe(address)

        logger.info(f"WebSocket 订阅数: {self.subscription_manager.subscribed_count}")

    async def _process_ws_fills(self, address: str, target_state: TargetTraderState):
        """处理 WebSocket 收到的成交"""
        fills = self.subscription_manager.get_pending_fills(address)
        if not fills:
            return

        config = target_state.config

        # 按 symbol 分组处理
        symbols_with_fills = set(f['symbol'] for f in fills)

        for symbol in symbols_with_fills:
            if not self._should_copy_symbol(config, symbol):
                continue

            # 检查每日交易次数限制
            if target_state.copies_today >= config.max_daily_trades:
                logger.warning(f"[{address[:8]}] 达到每日最大交易次数限制")
                continue

            # 获取目标当前持仓状态
            target_positions = self._get_target_positions(address)
            target_pos = target_positions.get(symbol)

            my_pos = self.my_positions.get(symbol)
            prev_target = target_state.copied_positions.get(symbol)

            if target_pos is None:
                # 目标已平仓
                if my_pos is not None:
                    logger.info(f"[WS] [{address[:8]}] 目标已平仓: {symbol}")
                    await self._close_position(target_state, symbol)
                    target_state.copies_today += 1

                if symbol in target_state.copied_positions:
                    del target_state.copied_positions[symbol]
            else:
                # 目标有仓位
                if target_pos['notional'] < config.min_position_size_usd:
                    continue

                is_new_position = prev_target is None
                is_direction_change = prev_target and prev_target['side'] != target_pos['side']

                if is_new_position or is_direction_change:
                    if is_direction_change:
                        logger.info(
                            f"[WS] [{address[:8]}] 仓位方向变化: {symbol} "
                            f"{prev_target['side']} -> {target_pos['side']}"
                        )
                        # 先平仓
                        if my_pos is not None:
                            await self._close_position(target_state, symbol)
                            await asyncio.sleep(0.5)
                            my_pos = None
                    else:
                        logger.info(
                            f"[WS] [{address[:8]}] 新仓位: {symbol} "
                            f"{target_pos['side']} {abs(target_pos['size'])}"
                        )

                    # 计算跟单参数
                    current_price = (
                        self.client.get_mid_price(symbol)
                        if self.client else target_pos.get('entry_price', 1)
                    )
                    copy_size = self._calculate_copy_size(config, target_pos, current_price)
                    leverage = (
                        target_pos['leverage'] if config.copy_leverage
                        else config.default_leverage
                    )
                    leverage = min(leverage, config.max_leverage)
                    is_long = target_pos['side'] == 'long'

                    # 开仓
                    if my_pos is None:
                        await self._open_position(
                            target_state, symbol, is_long,
                            copy_size, leverage, target_pos
                        )
                    elif (my_pos.side == PositionSide.LONG) != is_long:
                        # 方向不同，先平后开
                        await self._close_position(target_state, symbol)
                        await asyncio.sleep(0.5)
                        await self._open_position(
                            target_state, symbol, is_long,
                            copy_size, leverage, target_pos
                        )

                    target_state.copies_today += 1

                # 更新已复制仓位记录
                target_state.copied_positions[symbol] = target_pos

            target_state.positions = target_positions

        target_state.last_check = datetime.now()

    async def _process_all_ws_fills(self):
        """处理所有目标的 WebSocket 成交"""
        # 先更新自己的持仓
        self.my_positions = self._get_my_positions()

        addresses_with_fills = self.subscription_manager.get_all_pending_addresses()

        for address in addresses_with_fills:
            if address in self.targets:
                await self._process_ws_fills(address, self.targets[address])

    async def run(self):
        """运行 WebSocket 多目标跟单机器人"""
        self.is_running = True

        logger.info("=" * 60)
        logger.info("WebSocket 多目标跟单机器人启动")
        logger.info(f"全局模拟模式: {self.global_dry_run}")
        logger.info(f"WebSocket 检查间隔: {self.check_interval}秒")
        logger.info(f"全量同步间隔: {self.sync_interval}秒")
        logger.info(f"配置重载间隔: {self.reload_interval}秒")
        logger.info("=" * 60)

        # 加载初始配置并订阅
        self.reload_configs()

        if not self.targets:
            logger.warning("没有启用的跟单目标，请先在跟单管理中添加并启用地址")

        try:
            # 初始全量同步
            if self.targets:
                await self._sync_all_targets()
            self.last_full_sync = datetime.now()

            while self.is_running:
                # 检查是否需要重载配置
                if (self.last_config_reload is None or
                    (datetime.now() - self.last_config_reload).seconds >= self.reload_interval):
                    self.reload_configs()

                # 处理 WebSocket 收到的成交（低延迟）
                await self._process_all_ws_fills()

                # 定期全量同步（兜底）
                if self.targets and (
                    self.last_full_sync is None or
                    (datetime.now() - self.last_full_sync).seconds >= self.sync_interval
                ):
                    logger.debug("执行全量同步...")
                    await self._sync_all_targets()
                    self.last_full_sync = datetime.now()

                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("WebSocket 多目标跟单机器人被取消")
        except Exception as e:
            logger.error(f"WebSocket 多目标跟单机器人异常: {e}")
            import traceback
            traceback.print_exc()
            if self._on_error:
                self._on_error(e)
        finally:
            self.is_running = False
            logger.info("WebSocket 多目标跟单机器人停止")

    def get_status(self) -> Dict[str, Any]:
        """获取机器人状态"""
        status = super().get_status()
        status['websocket'] = {
            'subscribed_count': self.subscription_manager.subscribed_count,
            'last_full_sync': (
                self.last_full_sync.isoformat()
                if self.last_full_sync else None
            ),
            'sync_interval': self.sync_interval
        }
        return status

