"""
仓位级别跟单机器人引擎
第二种跟单模式：跟单特定交易员的特定仓位

与第一种模式 (MultiTargetCopyTradingBot) 的区别：
- 第一种：跟单交易员的所有仓位
- 第二种：只跟单交易员的特定仓位（本模块）
"""
import asyncio
from asyncio import Lock
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
import pendulum

from hyperliquid.info import Info

from core.models import Position, PositionSide
from clients.hyperliquid_client import HyperliquidClient
from clients.feishu_client import FeishuClient, CopyTradingNotifier
from config.settings import settings


# 最小订单价值（USD）
MIN_ORDER_VALUE_USD = 11


@dataclass
class TrackingState:
    """单个仓位跟单的状态"""
    tracking_id: int
    target_address: str
    target_name: str
    symbol: str
    
    # 配置
    copy_ratio: float = 0.1
    max_position_size_usd: float = 500.0
    min_position_size_usd: float = 20.0
    copy_leverage: bool = True
    max_leverage: int = 10
    default_leverage: int = 5
    slippage: float = 0.01
    
    # 目标仓位快照
    target_initial_size: Optional[float] = None
    target_initial_side: Optional[str] = None
    target_initial_entry_price: Optional[float] = None
    
    # 当前目标仓位
    target_current_size: Optional[float] = None
    target_current_side: Optional[str] = None
    
    # 我方仓位
    my_size: float = 0.0
    my_side: Optional[str] = None
    my_entry_price: Optional[float] = None
    
    # 状态
    status: str = 'pending'  # pending/active/closed/stopped
    last_sync: Optional[pendulum.DateTime] = None


class PositionCopyTradingBot:
    """
    仓位级别跟单机器人
    
    只跟单特定交易员的特定仓位，而非交易员的所有仓位
    """
    
    def __init__(
        self,
        client: HyperliquidClient,
        check_interval: float = 10.0,
        reload_interval: float = 60.0,
        enable_feishu_notify: bool = True
    ):
        """
        初始化仓位跟单机器人

        Args:
            client: Hyperliquid 客户端（需要已初始化钱包）
            check_interval: 检查间隔（秒）
            reload_interval: 配置重载间隔（秒）
            enable_feishu_notify: 是否启用飞书通知
        """
        self.client = client
        self.check_interval = check_interval
        self.reload_interval = reload_interval
        
        # 跟单状态 (tracking_id -> TrackingState)
        self.trackings: Dict[int, TrackingState] = {}
        
        # 自己的持仓
        self.my_positions: Dict[str, Position] = {}
        
        # 运行状态
        self.is_running = False
        self.last_config_reload: Optional[pendulum.DateTime] = None
        
        # 并发锁
        self._order_lock = Lock()
        self._sync_lock = Lock()
        
        # 缓存
        self._info_client: Optional[Info] = None
        self._meta_cache: Optional[Dict] = None
        self._meta_cache_time: Optional[pendulum.DateTime] = None
        self._symbol_decimals: Dict[str, int] = {}
        
        # 回调
        self._on_copy: Optional[Callable[[int, str, str, str, float], None]] = None
        self._on_close: Optional[Callable[[int, str, str, float], None]] = None
        self._on_adjust: Optional[Callable[[int, str, str, str, float, bool], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        
        # 延迟加载数据库
        self._db = None
        
        # 飞书通知器（使用 FeishuSettings 配置）
        self._notifier: Optional[CopyTradingNotifier] = None
        if enable_feishu_notify:
            self._init_feishu_notifier()

    @property
    def db(self):
        """延迟加载数据库"""
        if self._db is None:
            from database import TraderDatabase
            self._db = TraderDatabase()
        return self._db

    def _init_feishu_notifier(self):
        """初始化飞书通知器（使用 FeishuSettings 配置）"""
        try:
            if not settings.feishu.app_id:
                logger.warning("飞书未配置，通知功能将不可用")
                return
            
            feishu_client = FeishuClient(
                app_id=settings.feishu.app_id,
                app_secret=settings.feishu.app_secret,
                default_user_id=settings.feishu.default_user_id
            )
            self._notifier = CopyTradingNotifier(feishu_client)
            logger.info("飞书通知器初始化成功")
        except Exception as e:
            logger.warning(f"飞书通知器初始化失败: {e}")
            self._notifier = None

    def _notify_copy_open(self, target_address: str, symbol: str, side: str, size: float):
        """发送开仓通知"""
        if self._notifier:
            try:
                self._notifier.notify_copy_open(
                    target_address=target_address,
                    symbol=symbol,
                    side=side,
                    size=size
                )
            except Exception as e:
                logger.warning(f"飞书通知失败: {e}")

    def _notify_copy_close(self, target_address: str, symbol: str, pnl: float):
        """发送平仓通知"""
        if self._notifier:
            try:
                self._notifier.notify_copy_close(
                    target_address=target_address,
                    symbol=symbol,
                    pnl=pnl
                )
            except Exception as e:
                logger.warning(f"飞书通知失败: {e}")

    def _notify_copy_adjust(self, target_address: str, symbol: str, side: str, size: float, is_increase: bool):
        """发送调整仓位通知"""
        if self._notifier:
            try:
                self._notifier.notify_copy_adjust(
                    target_address=target_address,
                    symbol=symbol,
                    side=side,
                    size=size,
                    is_increase=is_increase
                )
            except Exception as e:
                logger.warning(f"飞书通知失败: {e}")

    def _notify_error(self, error: str):
        """发送错误通知"""
        if self._notifier:
            try:
                self._notifier.notify_error(error)
            except Exception as e:
                logger.warning(f"飞书通知失败: {e}")

    @property
    def info_client(self) -> Info:
        """复用 Info 客户端"""
        if self._info_client is None:
            self._info_client = Info(self.client.api_url, skip_ws=True)
        return self._info_client

    # ==================== 回调设置 ====================

    def set_on_copy(self, callback: Callable[[int, str, str, str, float], None]):
        """设置复制成功回调 (tracking_id, target_address, symbol, side, size)"""
        self._on_copy = callback

    def set_on_close(self, callback: Callable[[int, str, str, float], None]):
        """设置平仓回调 (tracking_id, target_address, symbol, pnl)"""
        self._on_close = callback

    def set_on_adjust(self, callback: Callable[[int, str, str, str, float, bool], None]):
        """设置调整仓位回调 (tracking_id, target_address, symbol, side, size, is_increase)"""
        self._on_adjust = callback

    def set_on_error(self, callback: Callable[[Exception], None]):
        """设置错误回调"""
        self._on_error = callback

    # ==================== 缓存和工具方法 ====================

    def _get_meta_cached(self) -> Dict:
        """获取元数据（带缓存，5分钟刷新）"""
        now = pendulum.now()
        if (self._meta_cache is None or 
            self._meta_cache_time is None or
            (now - self._meta_cache_time).total_seconds() > 300):
            self._meta_cache = self.client.get_meta()
            self._meta_cache_time = now
            self._symbol_decimals.clear()
        return self._meta_cache

    def _get_symbol_decimals(self, symbol: str) -> int:
        """获取币种精度（带缓存）"""
        if symbol in self._symbol_decimals:
            return self._symbol_decimals[symbol]
        
        meta = self._get_meta_cached()
        for asset in meta.get('universe', []):
            if asset['name'] == symbol:
                decimals = asset.get('szDecimals', 4)
                self._symbol_decimals[symbol] = decimals
                return decimals
        
        return 4  # 默认精度

    def _round_size(self, symbol: str, size: float) -> float:
        """根据币种精度四舍五入"""
        decimals = self._get_symbol_decimals(symbol)
        return round(size, decimals)

    # ==================== 配置加载 ====================

    def _load_trackings_from_db(self) -> List[Dict]:
        """从数据库加载启用的仓位跟单配置"""
        try:
            return self.db.get_active_position_trackings()
        except Exception as e:
            logger.error(f"加载仓位跟单配置失败: {e}")
            return []

    def _dict_to_state(self, data: Dict) -> TrackingState:
        """将数据库记录转换为 TrackingState"""
        return TrackingState(
            tracking_id=data['id'],
            target_address=data['target_address'],
            target_name=data.get('target_name', ''),
            symbol=data['symbol'],
            copy_ratio=data.get('copy_ratio', 0.1),
            max_position_size_usd=data.get('max_position_size_usd', 500.0),
            min_position_size_usd=data.get('min_position_size_usd', 20.0),
            copy_leverage=data.get('copy_leverage', True),
            max_leverage=data.get('max_leverage', 10),
            default_leverage=data.get('default_leverage', 5),
            slippage=data.get('slippage', 0.01),
            target_initial_size=data.get('target_initial_size'),
            target_initial_side=data.get('target_initial_side'),
            target_initial_entry_price=data.get('target_initial_entry_price'),
            my_size=data.get('my_size', 0.0),
            my_side=data.get('my_side'),
            my_entry_price=data.get('my_entry_price'),
            status=data.get('status', 'pending')
        )

    def reload_configs(self):
        """重新加载配置"""
        configs = self._load_trackings_from_db()
        current_ids = set(self.trackings.keys())
        new_ids = set()

        for data in configs:
            tracking_id = data['id']
            new_ids.add(tracking_id)
            state = self._dict_to_state(data)

            if tracking_id in self.trackings:
                # 更新已有配置（保留运行时状态）
                old_state = self.trackings[tracking_id]
                state.target_current_size = old_state.target_current_size
                state.target_current_side = old_state.target_current_side
                state.last_sync = old_state.last_sync
                
            self.trackings[tracking_id] = state
            logger.debug(f"加载仓位跟单: {state.symbol} <- {state.target_address[:10]}...")

        # 移除已删除/禁用的配置
        for tracking_id in current_ids - new_ids:
            del self.trackings[tracking_id]
            logger.info(f"移除仓位跟单: {tracking_id}")

        self.last_config_reload = pendulum.now()
        logger.info(f"仓位跟单配置加载完成: 共 {len(self.trackings)} 个")

    # ==================== 持仓获取 ====================

    def _get_target_position(self, address: str, symbol: str) -> Optional[Dict]:
        """获取目标交易者的特定仓位"""
        try:
            state = self.info_client.user_state(address)
            
            for pos_data in state.get('assetPositions', []):
                pos = pos_data.get('position', {})
                if pos.get('coin', '') == symbol:
                    size = float(pos.get('szi', 0))
                    if size != 0:
                        leverage_info = pos.get('leverage', {})
                        return {
                            'symbol': symbol,
                            'size': size,
                            'side': 'long' if size > 0 else 'short',
                            'entry_price': float(pos.get('entryPx', 0)),
                            'leverage': int(leverage_info.get('value', 1)),
                            'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                            'notional': abs(size) * float(pos.get('entryPx', 0))
                        }
            
            return None  # 目标没有该仓位

        except Exception as e:
            logger.error(f"获取目标持仓失败 {address[:10]}... {symbol}: {e}")
            return None

    def _get_my_positions(self) -> Dict[str, Position]:
        """获取自己的当前持仓"""
        positions = {}
        try:
            for pos in self.client.get_positions():
                positions[pos.symbol] = pos
        except Exception as e:
            logger.error(f"获取自己持仓失败: {e}")
        return positions

    # ==================== 仓位计算 ====================

    def _calculate_copy_size(
        self,
        state: TrackingState,
        target_notional: float,
        current_price: float
    ) -> float:
        """计算跟单仓位大小"""
        copy_notional = target_notional * state.copy_ratio
        copy_notional = max(copy_notional, state.min_position_size_usd)
        copy_notional = min(copy_notional, state.max_position_size_usd)
        
        size = copy_notional / current_price
        return self._round_size(state.symbol, size)

    def _calculate_leverage(self, state: TrackingState, target_leverage: int) -> int:
        """计算杠杆"""
        if state.copy_leverage:
            return min(target_leverage, state.max_leverage)
        return state.default_leverage

    # ==================== 订单操作 ====================

    async def _open_position(
        self,
        state: TrackingState,
        is_long: bool,
        size: float,
        leverage: int,
        target_position: Dict
    ) -> bool:
        """开仓"""
        async with self._order_lock:
            symbol = state.symbol
            side = 'long' if is_long else 'short'
            price = self.client.get_mid_price(symbol)

            try:
                # 设置杠杆
                self.client.set_leverage(symbol, leverage)
                await asyncio.sleep(0.3)

                # 下单
                result = self.client.market_order(
                    symbol, is_long, size, slippage=state.slippage
                )

                if result.get('status') == 'ok':
                    logger.info(
                        f"[{state.tracking_id}] 开仓成功: {symbol} {side} {size} "
                        f"(目标: {state.target_address[:8]}...)"
                    )
                    
                    # 更新状态
                    state.my_size = size
                    state.my_side = side
                    state.my_entry_price = price
                    state.status = 'active'
                    
                    # 更新数据库
                    self.db.update_tracking_status(state.tracking_id, 'active')
                    self.db.update_tracking_position(
                        state.tracking_id, size, side, price
                    )
                    
                    # 发送飞书通知
                    self._notify_copy_open(state.target_address, symbol, side, size)
                    
                    if self._on_copy:
                        self._on_copy(
                            state.tracking_id, state.target_address,
                            symbol, side, size
                        )
                    return True
                else:
                    logger.error(f"[{state.tracking_id}] 开仓失败: {result}")
                    return False

            except Exception as e:
                logger.error(f"[{state.tracking_id}] 开仓异常: {e}")
                if self._on_error:
                    self._on_error(e)
                return False

    async def _adjust_position(
        self,
        state: TrackingState,
        target_position: Dict
    ) -> bool:
        """调整仓位（加仓或减仓）"""
        symbol = state.symbol
        
        # 检查目标交易员是否已经清仓（size == 0）
        target_size = abs(target_position.get('size', 0))
        if target_size == 0:
            my_pos = self.my_positions.get(symbol)
            if my_pos:
                logger.info(f"[{state.tracking_id}] 目标交易员已清仓，执行完全平仓: {symbol}")
                return await self._close_position(state, "目标清仓")
            return True
        
        async with self._order_lock:
            my_pos = self.my_positions.get(symbol)

            if my_pos is None:
                logger.warning(f"[{state.tracking_id}] 无法调整仓位: {symbol} (本地无持仓)")
                return False

            # 计算目标仓位
            current_price = self.client.get_mid_price(symbol)
            my_target_size = self._calculate_copy_size(
                state, target_position['notional'], current_price
            )
            my_current_size = abs(my_pos.size)
            
            # 判断是加仓还是减仓
            is_increase = my_target_size > my_current_size
            adjustment_size = abs(my_target_size - my_current_size)
            adjustment_size = self._round_size(symbol, adjustment_size)

            is_long = my_pos.side == PositionSide.LONG
            action_type = "加仓" if is_increase else "减仓"

            try:
                logger.info(
                    f"[{state.tracking_id}] {action_type}: {symbol} "
                    f"{my_current_size:.4f} → {my_target_size:.4f} (调整 {adjustment_size:.4f})"
                )

                if is_increase:
                    result = self.client.market_order(
                        symbol, is_long, adjustment_size, slippage=state.slippage
                    )
                else:
                    result = self.client.market_order(
                        symbol, not is_long, adjustment_size, slippage=state.slippage
                    )

                if result.get('status') == 'ok':
                    logger.info(f"[{state.tracking_id}] {action_type}成功: {symbol} {adjustment_size}")
                    
                    # 更新状态
                    state.my_size = my_target_size
                    self.db.update_tracking_position(
                        state.tracking_id, my_target_size, state.my_side, state.my_entry_price
                    )
                    
                    # 发送飞书通知
                    side = 'long' if is_long else 'short'
                    self._notify_copy_adjust(state.target_address, symbol, side, adjustment_size, is_increase)
                    
                    if self._on_adjust:
                        self._on_adjust(
                            state.tracking_id, state.target_address,
                            symbol, side, adjustment_size, is_increase
                        )
                    return True
                else:
                    logger.error(f"[{state.tracking_id}] {action_type}失败: {result}")
                    return False

            except Exception as e:
                logger.error(f"[{state.tracking_id}] {action_type}异常: {e}")
                if self._on_error:
                    self._on_error(e)
                return False

    async def _close_position(
        self,
        state: TrackingState,
        reason: str = "目标平仓"
    ) -> bool:
        """平仓"""
        async with self._order_lock:
            symbol = state.symbol
            my_pos = self.my_positions.get(symbol)
            pnl = my_pos.unrealized_pnl if my_pos else 0

            try:
                result = self.client.close_position(symbol, slippage=state.slippage)

                if result is None:
                    logger.warning(f"[{state.tracking_id}] 平仓 {symbol}: 未找到持仓")
                    # 仍然标记为已关闭
                    state.status = 'closed'
                    self.db.update_tracking_status(
                        state.tracking_id, 'closed', reason, 0
                    )
                    return False

                if result.get('status') == 'ok':
                    logger.info(f"[{state.tracking_id}] 平仓成功: {symbol}, PnL: {pnl:.2f}")
                    
                    # 更新状态
                    state.status = 'closed'
                    state.my_size = 0
                    
                    self.db.update_tracking_status(
                        state.tracking_id, 'closed', reason, pnl
                    )
                    
                    # 发送飞书通知
                    self._notify_copy_close(state.target_address, symbol, pnl)
                    
                    if self._on_close:
                        self._on_close(
                            state.tracking_id, state.target_address, symbol, pnl
                        )
                    return True
                else:
                    logger.error(f"[{state.tracking_id}] 平仓失败: {result}")
                    return False

            except Exception as e:
                logger.error(f"[{state.tracking_id}] 平仓异常: {e}")
                if self._on_error:
                    self._on_error(e)
                return False

    # ==================== 同步逻辑 ====================

    async def _sync_tracking(self, state: TrackingState):
        """同步单个仓位跟单"""
        symbol = state.symbol
        target_address = state.target_address
        
        # 获取目标仓位
        target_pos = self._get_target_position(target_address, symbol)
        
        # 获取我方仓位
        my_pos = self.my_positions.get(symbol)
        
        if state.status == 'pending':
            # 等待开仓状态
            if target_pos is not None:
                # 目标有仓位，开始跟单
                logger.info(
                    f"[{state.tracking_id}] 目标有仓位 {symbol} {target_pos['side']} "
                    f"{abs(target_pos['size'])}，开始跟单"
                )
                
                # 记录初始快照
                state.target_initial_size = abs(target_pos['size'])
                state.target_initial_side = target_pos['side']
                state.target_initial_entry_price = target_pos['entry_price']
                state.target_current_size = abs(target_pos['size'])
                state.target_current_side = target_pos['side']
                
                # 保存初始快照到数据库
                self.db.save_position_tracking({
                    'id': state.tracking_id,
                    'target_initial_size': state.target_initial_size,
                    'target_initial_side': state.target_initial_side,
                    'target_initial_entry_price': state.target_initial_entry_price,
                    'status': 'pending'
                })
                
                # 计算跟单仓位
                current_price = self.client.get_mid_price(symbol)
                copy_size = self._calculate_copy_size(state, target_pos['notional'], current_price)
                leverage = self._calculate_leverage(state, target_pos['leverage'])
                is_long = target_pos['side'] == 'long'
                
                # 开仓
                if my_pos is None:
                    await self._open_position(state, is_long, copy_size, leverage, target_pos)
                elif (my_pos.side == PositionSide.LONG) == is_long:
                    # 方向相同，直接标记为 active
                    state.status = 'active'
                    state.my_size = abs(my_pos.size)
                    state.my_side = 'long' if my_pos.side == PositionSide.LONG else 'short'
                    state.my_entry_price = my_pos.entry_price
                    self.db.update_tracking_status(state.tracking_id, 'active')
                    self.db.update_tracking_position(
                        state.tracking_id, state.my_size, state.my_side, state.my_entry_price
                    )
                    logger.info(f"[{state.tracking_id}] 已有同向仓位，标记为 active")
                else:
                    # 方向不同，需要先平仓再开仓
                    logger.warning(f"[{state.tracking_id}] 已有反向仓位，需要手动处理")
            else:
                # 目标没有仓位，继续等待
                logger.debug(f"[{state.tracking_id}] 目标暂无 {symbol} 仓位，继续等待")
                
        elif state.status == 'active':
            # 活跃跟单状态
            if target_pos is None:
                # 目标已平仓，我们也平仓
                logger.info(f"[{state.tracking_id}] 目标已平仓 {symbol}，执行平仓")
                await self._close_position(state, "目标平仓")
                
            else:
                # 目标仓位变化
                prev_size = state.target_current_size or 0
                new_size = abs(target_pos['size'])
                
                state.target_current_size = new_size
                state.target_current_side = target_pos['side']
                
                # 检查方向变化
                if state.target_initial_side != target_pos['side']:
                    # 方向变化，平仓并重新开仓
                    logger.info(
                        f"[{state.tracking_id}] 目标方向变化: "
                        f"{state.target_initial_side} -> {target_pos['side']}"
                    )
                    await self._close_position(state, "目标方向变化")
                    # 注意：平仓后状态变为 closed，下次需要重新创建跟单
                    return
                
                # 检查仓位大小变化
                if prev_size > 0:
                    size_change_pct = (new_size - prev_size) / prev_size * 100
                    
                    if abs(size_change_pct) >= 1.0:  # 变化超过1%才调整
                        await self._adjust_position(state, target_pos)
        
        state.last_sync = pendulum.now()

    async def _sync_all_trackings(self):
        """同步所有仓位跟单"""
        async with self._sync_lock:
            # 更新自己的持仓
            self.my_positions = self._get_my_positions()
            
            # 过滤出活跃的跟单
            active_trackings = [
                s for s in self.trackings.values()
                if s.status in ('pending', 'active')
            ]
            
            for state in active_trackings:
                try:
                    await self._sync_tracking(state)
                except Exception as e:
                    logger.error(f"同步仓位跟单 {state.tracking_id} 失败: {e}")
                    if self._on_error:
                        self._on_error(e)

    # ==================== 运行控制 ====================

    async def run(self):
        """运行仓位跟单机器人"""
        self.is_running = True

        logger.info("=" * 60)
        logger.info("仓位级别跟单机器人启动")
        logger.info(f"检查间隔: {self.check_interval}秒")
        logger.info(f"配置重载间隔: {self.reload_interval}秒")
        logger.info("=" * 60)

        # 加载初始配置
        self.reload_configs()

        if not self.trackings:
            logger.warning("没有启用的仓位跟单，等待添加...")

        try:
            while self.is_running:
                try:
                    # 检查是否需要重载配置
                    if (self.last_config_reload is None or
                        (pendulum.now() - self.last_config_reload).total_seconds() >= self.reload_interval):
                        self.reload_configs()

                    if self.trackings:
                        await self._sync_all_trackings()

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"同步时遇到错误，将在下一周期重试: {e}")
                    if self._on_error:
                        self._on_error(e)

                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("仓位跟单机器人被取消")
        finally:
            self.is_running = False
            logger.info("仓位跟单机器人停止")

    def stop(self):
        """停止机器人"""
        self.is_running = False
        logger.info("正在停止仓位跟单机器人...")

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取机器人状态"""
        trackings_status = []
        
        for state in self.trackings.values():
            trackings_status.append({
                'tracking_id': state.tracking_id,
                'target_address': state.target_address,
                'target_name': state.target_name,
                'symbol': state.symbol,
                'status': state.status,
                'copy_ratio': state.copy_ratio,
                'target_initial_size': state.target_initial_size,
                'target_initial_side': state.target_initial_side,
                'target_current_size': state.target_current_size,
                'my_size': state.my_size,
                'my_side': state.my_side,
                'last_sync': state.last_sync.isoformat() if state.last_sync else None
            })

        return {
            'is_running': self.is_running,
            'tracking_count': len(self.trackings),
            'active_count': len([s for s in self.trackings.values() if s.status == 'active']),
            'pending_count': len([s for s in self.trackings.values() if s.status == 'pending']),
            'trackings': trackings_status,
            'my_positions': [
                {
                    'symbol': p.symbol,
                    'side': p.side.value,
                    'size': p.size,
                    'unrealized_pnl': p.unrealized_pnl
                }
                for p in self.my_positions.values()
            ],
            'last_config_reload': self.last_config_reload.isoformat() if self.last_config_reload else None
        }
