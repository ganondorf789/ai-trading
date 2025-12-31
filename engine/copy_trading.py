"""
跟单机器人引擎
监控目标交易者的持仓变化并复制交易
"""
import asyncio
import threading
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
import pendulum

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
    init_observation_period: float = 10.0  # 初始化后观察期（秒），期间不跟单新仓位

    # 风控
    max_total_positions: int = 10  # 最大持仓数
    max_daily_trades: int = 50  # 每日最大交易次数
    slippage: float = 0.01  # 滑点容忍度

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
        self._lock = threading.Lock()  # 使用线程锁保护 WebSocket 回调访问

    def _ensure_ws(self):
        """确保 WebSocket 连接"""
        if self.ws_info is None:
            self.ws_info = Info(self.api_url, skip_ws=False)

    def subscribe(self, address: str):
        """订阅目标交易者的成交"""
        if address in self._subscribed_addresses:
            return

        self._ensure_ws()
        with self._lock:
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
            with self._lock:
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

                with self._lock:
                    if address in self._pending_fills:
                        self._pending_fills[address].append(fill_info)
                        logger.info(
                            f"[WS] [{address[:8]}] 成交: {fill_info['symbol']} "
                            f"{fill_info['side']} {fill_info['size']} @ {fill_info['price']}"
                        )

    def get_pending_fills(self, address: str) -> List[Dict]:
        """获取并清空待处理的成交"""
        with self._lock:
            if address not in self._pending_fills:
                return []
            fills = self._pending_fills[address]
            self._pending_fills[address] = []
            return fills

    def has_pending_fills(self, address: str) -> bool:
        """检查是否有待处理的成交"""
        with self._lock:
            return bool(self._pending_fills.get(address, []))

    def get_all_pending_addresses(self) -> List[str]:
        """获取所有有待处理成交的地址"""
        with self._lock:
            return [addr for addr, fills in self._pending_fills.items() if fills]

    @property
    def subscribed_count(self) -> int:
        return len(self._subscribed_addresses)

    def close(self):
        """关闭 WebSocket 连接"""
        if self.ws_info is not None:
            try:
                # 清理订阅
                self._subscribed_addresses.clear()
                with self._lock:
                    self._pending_fills.clear()
                # 关闭 WebSocket
                if hasattr(self.ws_info, 'ws') and self.ws_info.ws is not None:
                    try:
                        self.ws_info.ws.close()
                    except Exception:
                        pass
                # 尝试关闭 WebSocket 管理器
                if hasattr(self.ws_info, 'ws_manager') and self.ws_info.ws_manager is not None:
                    try:
                        self.ws_info.ws_manager.close()
                    except Exception:
                        pass
                self.ws_info = None
                logger.info("WebSocket 连接已关闭")
            except Exception as e:
                logger.warning(f"关闭 WebSocket 时出错: {e}")


@dataclass
class TargetTraderState:
    """单个目标交易者的状态"""
    address: str
    config: CopyTradingConfig
    positions: Dict[str, Dict] = field(default_factory=dict)
    copied_positions: Dict[str, Dict] = field(default_factory=dict)
    last_check: Optional[pendulum.DateTime] = None
    copies_today: int = 0
    successful_copies: int = 0
    failed_copies: int = 0
    daily_pnl: float = 0.0
    initialized: bool = False  # 是否已完成初始化（记录现有持仓）
    init_timestamp: Optional[pendulum.DateTime] = None  # 初始化时间戳


class MultiTargetCopyTradingBot:
    """
    多目标跟单机器人

    从数据库加载跟单配置，支持同时跟单多个交易者
    """

    def __init__(
        self,
        client: HyperliquidClient,
        db_path: str = "data/traders.db",
        check_interval: float = 10.0,
        reload_interval: float = 60.0
    ):
        """
        初始化多目标跟单机器人

        Args:
            client: Hyperliquid 客户端（需要已初始化钱包）
            db_path: 数据库路径
            check_interval: 检查间隔（秒）
            reload_interval: 配置重载间隔（秒）
        """
        self.client = client
        self.db_path = db_path
        self.check_interval = check_interval
        self.reload_interval = reload_interval

        # 目标交易者状态
        self.targets: Dict[str, TargetTraderState] = {}

        # 自己的持仓
        self.my_positions: Dict[str, Position] = {}

        # 运行状态
        self.is_running = False
        self.last_config_reload: Optional[pendulum.DateTime] = None

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
            max_position_size_usd=data.get('max_position_size_usd', 100.0),
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
            slippage=data.get('slippage', 0.01)
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

        self.last_config_reload = pendulum.now()
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
            info = Info(self.client.api_url, skip_ws=True)
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

        # 获取精度
        decimals = 4
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
        price = self.client.get_mid_price(symbol)

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
            'created_at': pendulum.now().isoformat()
        }

        try:
            self.client.set_leverage(symbol, leverage)
            await asyncio.sleep(0.5)

            result = self.client.market_order(
                symbol, is_long, size,
                slippage=config.slippage
            )

            success = result.get('status') == 'ok'
            order_data['executed_at'] = pendulum.now().isoformat()

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
            order_data['executed_at'] = pendulum.now().isoformat()
            self._save_order(order_data)
            target_state.failed_copies += 1
            if self._on_error:
                self._on_error(e)
            return False

    async def _adjust_position(
        self,
        target_state: TargetTraderState,
        symbol: str,
        prev_size: float,
        new_size: float,
        target_position: Dict
    ) -> bool:
        """调整仓位（加仓或减仓）"""
        config = target_state.config
        my_pos = self.my_positions.get(symbol)

        if my_pos is None:
            logger.warning(f"[{target_state.address[:8]}] 无法调整仓位: {symbol} (本地无持仓)")
            return False

        # 判断是加仓还是减仓
        prev_abs_size = abs(prev_size)
        new_abs_size = abs(new_size)
        is_increase = new_abs_size > prev_abs_size
        action_type = "加仓" if is_increase else "减仓"

        # 使用精确计算：根据目标的新仓位和 copy_ratio 重新计算我们的目标仓位
        current_price = self.client.get_mid_price(symbol)
        my_target_size = self._calculate_copy_size(config, target_position, current_price)
        my_current_size = abs(my_pos.size)
        adjustment_size = abs(my_target_size - my_current_size)

        # 获取精度
        decimals = 4
        meta = self.client.get_meta()
        for asset in meta.get('universe', []):
            if asset['name'] == symbol:
                decimals = asset.get('szDecimals', 4)
                break
        adjustment_size = round(adjustment_size, decimals)

        if adjustment_size == 0:
            logger.debug(f"[{target_state.address[:8]}] {symbol} 调整数量太小，跳过")
            return True

        is_long = my_pos.side == PositionSide.LONG

        # 创建订单记录
        order_data = {
            'target_address': target_state.address,
            'symbol': symbol,
            'side': 'long' if is_long else 'short',
            'action': 'increase' if is_increase else 'reduce',
            'size': adjustment_size,
            'price': current_price,
            'leverage': my_pos.leverage,
            'copy_ratio': config.copy_ratio,
            'target_size': new_abs_size,
            'target_prev_size': prev_abs_size,
            'my_target_size': my_target_size,
            'my_current_size': my_current_size,
            'status': 'pending',
            'created_at': pendulum.now().isoformat()
        }

        try:
            change_pct = ((new_abs_size - prev_abs_size) / prev_abs_size * 100) if prev_abs_size > 0 else 0
            logger.info(
                f"[{target_state.address[:8]}] {action_type}: {symbol} "
                f"目标 {prev_abs_size:.4f} → {new_abs_size:.4f} ({change_pct:+.1f}%), "
                f"我们 {my_current_size:.4f} → {my_target_size:.4f} (调整 {adjustment_size:.4f})"
            )

            if is_increase:
                # 加仓：与当前方向相同的市价单
                result = self.client.market_order(
                    symbol, is_long, adjustment_size,
                    slippage=config.slippage
                )
            else:
                # 减仓：反向的市价单（部分平仓）
                result = self.client.market_order(
                    symbol, not is_long, adjustment_size,
                    slippage=config.slippage
                )

            success = result.get('status') == 'ok'
            order_data['executed_at'] = pendulum.now().isoformat()

            if success:
                logger.info(f"[{target_state.address[:8]}] {action_type}成功: {symbol} {adjustment_size}")
                order_data['status'] = 'success'
            else:
                logger.error(f"[{target_state.address[:8]}] {action_type}失败: {result}")
                order_data['status'] = 'failed'
                order_data['error_message'] = str(result)

            self._save_order(order_data)
            return success

        except Exception as e:
            logger.error(f"[{target_state.address[:8]}] {action_type}异常: {e}")
            order_data['status'] = 'failed'
            order_data['error_message'] = str(e)
            order_data['executed_at'] = pendulum.now().isoformat()
            self._save_order(order_data)
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
        price = self.client.get_mid_price(symbol)

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
            'created_at': pendulum.now().isoformat()
        }

        try:
            result = self.client.close_position(symbol, slippage=config.slippage)
            success = result.get('status') == 'ok'
            order_data['executed_at'] = pendulum.now().isoformat()

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
            order_data['executed_at'] = pendulum.now().isoformat()
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

        # 首次初始化：只记录现有持仓，不跟单
        if not target_state.initialized:
            target_state.init_timestamp = pendulum.now()
            for symbol, target_pos in target_positions.items():
                if self._should_copy_symbol(config, symbol):
                    target_state.copied_positions[symbol] = target_pos
                    logger.info(
                        f"[{address[:8]}] 初始化记录现有持仓: {symbol} "
                        f"{target_pos['side']} {abs(target_pos['size'])} (不跟单)"
                    )
            target_state.initialized = True
            target_state.last_check = pendulum.now()
            logger.info(
                f"[{address[:8]}] 初始化完成，已记录 {len(target_state.copied_positions)} 个现有持仓，"
                f"后续将只跟单新开仓位"
            )
            return

        # 处理新开仓/调整仓位
        for symbol, target_pos in target_positions.items():
            if not self._should_copy_symbol(config, symbol):
                continue

            if target_pos['notional'] < config.min_position_size_usd:
                continue

            my_pos = self.my_positions.get(symbol)
            prev_target = target_state.copied_positions.get(symbol)

            if prev_target is None:
                # 新仓位（初始化后新开的）
                logger.info(f"[{address[:8]}] 发现新仓位: {symbol} {target_pos['side']} {abs(target_pos['size'])}")

                # 检查是否在观察期内
                if target_state.init_timestamp:
                    time_since_init = (pendulum.now() - target_state.init_timestamp).total_seconds()
                    if time_since_init < config.init_observation_period:
                        logger.warning(
                            f"[{address[:8]}] 初始化后观察期内（{time_since_init:.1f}s/{config.init_observation_period:.0f}s），"
                            f"跳过新仓位 {symbol}，避免误跟单初始化前的仓位"
                        )
                        # 记录这个仓位，下次如果还在就不会再提示
                        target_state.copied_positions[symbol] = target_pos
                        continue

                current_price = self.client.get_mid_price(symbol)
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

                current_price = self.client.get_mid_price(symbol)
                copy_size = self._calculate_copy_size(config, target_pos, current_price)
                leverage = target_pos['leverage'] if config.copy_leverage else config.default_leverage
                leverage = min(leverage, config.max_leverage)

                await self._open_position(target_state, symbol, target_pos['side'] == 'long', copy_size, leverage, target_pos)
                target_state.copies_today += 1

            elif abs(prev_target['size']) != abs(target_pos['size']):
                # 仓位大小变化（加仓或减仓）
                size_change_pct = (abs(target_pos['size']) - abs(prev_target['size'])) / abs(prev_target['size']) * 100

                # 只有当变化超过 1% 时才调整（避免微小波动）
                if abs(size_change_pct) >= 1.0:
                    await self._adjust_position(
                        target_state, symbol,
                        prev_target['size'], target_pos['size'],
                        target_pos
                    )
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

        target_state.last_check = pendulum.now()

    async def _sync_all_targets(self):
        """同步所有目标"""
        # 更新自己的持仓
        self.my_positions = self._get_my_positions()

        # 并发同步所有目标
        tasks = [self._sync_target(state) for state in self.targets.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查并记录异常
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                target_address = list(self.targets.keys())[i]
                logger.error(f"同步目标 {target_address[:10]}... 失败: {result}")
                if self._on_error:
                    self._on_error(result)

    async def run(self):
        """运行多目标跟单机器人"""
        self.is_running = True

        logger.info("=" * 60)
        logger.info("多目标跟单机器人启动")
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
                    (pendulum.now() - self.last_config_reload).total_seconds() >= self.reload_interval):
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
    - 每次循环全量同步确保状态一致
    """

    def __init__(
        self,
        client: HyperliquidClient,
        db_path: str = "data/traders.db",
        check_interval: float = 2.0,  # WebSocket 模式下可以更快检查
        reload_interval: float = 60.0
    ):
        super().__init__(
            client=client,
            db_path=db_path,
            check_interval=check_interval,
            reload_interval=reload_interval
        )

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
        # 如果尚未初始化，不处理 WebSocket 成交
        if not target_state.initialized:
            return

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
                    # 如果是新仓位（不是方向变化），检查观察期
                    if is_new_position and target_state.init_timestamp:
                        time_since_init = (pendulum.now() - target_state.init_timestamp).total_seconds()
                        if time_since_init < config.init_observation_period:
                            logger.warning(
                                f"[WS] [{address[:8]}] 初始化后观察期内（{time_since_init:.1f}s/{config.init_observation_period:.0f}s），"
                                f"跳过新仓位 {symbol}，避免误跟单初始化前的仓位"
                            )
                            # 记录这个仓位，下次如果还在就不会再提示
                            target_state.copied_positions[symbol] = target_pos
                            continue

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
                    current_price = self.client.get_mid_price(symbol)
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

                elif prev_target and abs(prev_target['size']) != abs(target_pos['size']):
                    # 仓位大小变化（加仓或减仓）
                    size_change_pct = (
                        (abs(target_pos['size']) - abs(prev_target['size'])) /
                        abs(prev_target['size']) * 100
                    )

                    # 只有当变化超过 1% 时才调整（避免微小波动）
                    if abs(size_change_pct) >= 1.0:
                        logger.info(
                            f"[WS] [{address[:8]}] 仓位大小变化: {symbol} "
                            f"{abs(prev_target['size']):.4f} -> {abs(target_pos['size']):.4f} "
                            f"({size_change_pct:+.1f}%)"
                        )
                        await self._adjust_position(
                            target_state, symbol,
                            prev_target['size'], target_pos['size'],
                            target_pos
                        )
                        target_state.copies_today += 1

                # 更新已复制仓位记录
                target_state.copied_positions[symbol] = target_pos

            target_state.positions = target_positions

        target_state.last_check = pendulum.now()

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
        logger.info(f"检查/同步间隔: {self.check_interval}秒")
        logger.info(f"配置重载间隔: {self.reload_interval}秒")
        logger.info("=" * 60)

        # 加载初始配置并订阅
        self.reload_configs()

        if not self.targets:
            logger.warning("没有启用的跟单目标，请先在跟单管理中添加并启用地址")

        try:
            while self.is_running:
                # 检查是否需要重载配置
                if (self.last_config_reload is None or
                    (pendulum.now() - self.last_config_reload).total_seconds() >= self.reload_interval):
                    self.reload_configs()

                # 处理 WebSocket 收到的成交（低延迟）
                await self._process_all_ws_fills()

                # 全量同步
                if self.targets:
                    await self._sync_all_targets()

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

    def stop(self):
        """停止机器人并关闭 WebSocket 连接"""
        super().stop()
        # 关闭 WebSocket 连接
        if hasattr(self, 'subscription_manager'):
            self.subscription_manager.close()

    def get_status(self) -> Dict[str, Any]:
        """获取机器人状态"""
        status = super().get_status()
        status['websocket'] = {
            'subscribed_count': self.subscription_manager.subscribed_count
        }
        return status

