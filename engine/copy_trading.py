"""
跟单机器人引擎
监控目标交易者的持仓变化并复制交易

改进版本包含:
- 并发安全锁
- 订单重试机制
- 每日统计自动重置
- 锁定超时机制
- 完善风控系统
- API 客户端复用和缓存
- 健康检查与监控
- 飞书通知集成
"""
import asyncio
from asyncio import Lock
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
import pendulum
from collections import deque

from hyperliquid.info import Info

from core.models import (
    Position, PositionSide, Trade, OrderSide
)
from clients.hyperliquid_client import HyperliquidClient

# 最小订单价值（USD）
MIN_ORDER_VALUE_USD = 11


@dataclass
class RiskControl:
    """风控配置"""
    # 仓位限制
    max_total_positions: int = 10
    max_daily_trades: int = 50
    
    # 单笔风控
    max_single_loss_usd: float = 100.0  # 单笔最大亏损
    
    # 累计风控
    max_daily_loss_usd: float = 500.0   # 每日最大亏损
    max_drawdown_pct: float = 10.0      # 最大回撤百分比
    
    # 资金使用率
    max_margin_usage_pct: float = 80.0  # 最大保证金使用率
    
    # 暂停条件
    pause_on_consecutive_losses: int = 5  # 连续亏损N次后暂停
    
    # 订单重试
    max_order_retries: int = 3  # 订单最大重试次数
    retry_base_delay: float = 1.0  # 重试基础延迟（秒）

    @classmethod
    def from_dict(cls, config: dict) -> 'RiskControl':
        """从字典创建配置实例"""
        return cls(
            max_total_positions=int(config.get('max_total_positions', 10)),
            max_daily_trades=int(config.get('max_daily_trades', 50)),
            max_single_loss_usd=float(config.get('max_single_loss_usd', 100.0)),
            max_daily_loss_usd=float(config.get('max_daily_loss_usd', 500.0)),
            max_drawdown_pct=float(config.get('max_drawdown_pct', 10.0)),
            max_margin_usage_pct=float(config.get('max_margin_usage_pct', 80.0)),
            pause_on_consecutive_losses=int(config.get('pause_on_consecutive_losses', 5)),
            max_order_retries=int(config.get('max_order_retries', 3)),
            retry_base_delay=float(config.get('retry_base_delay', 1.0)),
        )


@dataclass
class HealthMetrics:
    """健康指标"""
    last_successful_sync: Optional[pendulum.DateTime] = None
    consecutive_failures: int = 0
    consecutive_losses: int = 0  # 连续亏损次数
    api_error_count: int = 0
    total_syncs: int = 0
    successful_syncs: int = 0
    
    def get_success_rate(self) -> float:
        """获取同步成功率"""
        if self.total_syncs == 0:
            return 1.0
        return self.successful_syncs / self.total_syncs


@dataclass
class LockState:
    """锁定状态"""
    target_address: str
    locked_at: pendulum.DateTime
    max_lock_duration: float = 7200.0  # 默认最长锁定2小时
    reason: str = ""


@dataclass
class CopyTradingConfig: 
    """跟单配置"""
    # 目标交易者地址
    target_address: str = ""

    # 跟单设置
    copy_ratio: float = 1.0  # 跟单比例 (0.5 = 跟单50%仓位)
    max_position_size_usd: float = 1000.0  # 单个仓位最大价值
    min_position_size_usd: float = 10.0  # 最小仓位价值（过滤小仓位）
    sync_position: bool = True  # 是否同步现有仓位

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
    last_reset_date: Optional[str] = None  # 上次重置日期


class MultiTargetCopyTradingBot:
    """
    多目标跟单机器人

    从数据库加载跟单配置，支持同时跟单多个交易者
    
    改进特性:
    - 并发安全: 使用异步锁保护关键操作
    - 订单重试: 支持失败后自动重试
    - 每日重置: 自动重置每日统计
    - 锁定超时: 防止长时间锁定单一交易员
    - 风控系统: 完善的风险控制
    - 健康监控: 实时健康状态检查
    - 飞书通知: 重要事件通知
    """

    def __init__(
        self,
        client: HyperliquidClient,
        check_interval: float = 10.0,
        reload_interval: float = 60.0,
        risk_control: Optional[RiskControl] = None,
        feishu_webhook: Optional[str] = None
    ):
        """
        初始化多目标跟单机器人

        Args:
            client: Hyperliquid 客户端（需要已初始化钱包）
            check_interval: 检查间隔（秒）
            reload_interval: 配置重载间隔（秒）
            risk_control: 风控配置
            feishu_webhook: 飞书 webhook 地址
        """
        self.client = client
        self.check_interval = check_interval
        self.reload_interval = reload_interval
        # 如果没有传入风控配置，则从数据库加载
        self.risk_control = risk_control or self._load_risk_control_from_db()
        self.feishu_webhook = feishu_webhook

        # 目标交易者状态
        self.targets: Dict[str, TargetTraderState] = {}

        # 自己的持仓
        self.my_positions: Dict[str, Position] = {}

        # 锁定状态
        self.lock_state: Optional[LockState] = None

        # 运行状态
        self.is_running = False
        self.is_paused = False  # 风控暂停
        self.last_config_reload: Optional[pendulum.DateTime] = None

        # 健康指标
        self.health = HealthMetrics()
        self._sync_latencies: deque = deque(maxlen=100)  # 最近100次同步延迟

        # 并发锁
        self._order_lock = Lock()  # 订单操作锁
        self._position_lock = Lock()  # 持仓更新锁
        self._sync_lock = Lock()  # 同步锁

        # 缓存
        self._info_client: Optional[Info] = None
        self._meta_cache: Optional[Dict] = None
        self._meta_cache_time: Optional[pendulum.DateTime] = None
        self._symbol_decimals: Dict[str, int] = {}

        # 回调
        self._on_copy: Optional[Callable[[str, str, str, float], None]] = None
        self._on_close: Optional[Callable[[str, str, float], None]] = None
        self._on_adjust: Optional[Callable[[str, str, str, float, bool], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

        # 延迟加载数据库（避免循环导入）
        self._db = None
        self._feishu_client = None

    @property
    def db(self):
        """延迟加载数据库"""
        if self._db is None:
            from database import TraderDatabase
            self._db = TraderDatabase()
        return self._db

    @property
    def info_client(self) -> Info:
        """复用 Info 客户端"""
        if self._info_client is None:
            self._info_client = Info(self.client.api_url, skip_ws=True)
        return self._info_client

    @property
    def locked_target(self) -> Optional[str]:
        """兼容旧代码的锁定目标访问"""
        return self.lock_state.target_address if self.lock_state else None

    # ==================== 回调设置 ====================

    def set_on_copy(self, callback: Callable[[str, str, str, float], None]):
        """设置复制成功回调 (target_address, symbol, side, size)"""
        self._on_copy = callback

    def set_on_close(self, callback: Callable[[str, str, float], None]):
        """设置平仓回调 (target_address, symbol, pnl)"""
        self._on_close = callback

    def set_on_adjust(self, callback: Callable[[str, str, str, float, bool], None]):
        """设置调整仓位回调 (target_address, symbol, side, size, is_increase)"""
        self._on_adjust = callback

    def set_on_error(self, callback: Callable[[Exception], None]):
        """设置错误回调"""
        self._on_error = callback

    def _load_risk_control_from_db(self) -> RiskControl:
        """从数据库加载风控配置"""
        try:
            config = self.db.get_risk_control_config()
            logger.info(f"从数据库加载风控配置: {config}")
            return RiskControl.from_dict(config)
        except Exception as e:
            logger.warning(f"从数据库加载风控配置失败，使用默认值: {e}")
            return RiskControl()

    def reload_risk_control(self) -> RiskControl:
        """
        重新从数据库加载风控配置
        
        Returns:
            RiskControl: 新的风控配置
        """
        self.risk_control = self._load_risk_control_from_db()
        logger.info(f"风控配置已重新加载: 每日最大亏损 ${self.risk_control.max_daily_loss_usd}, "
                   f"连续亏损暂停 {self.risk_control.pause_on_consecutive_losses} 次")
        return self.risk_control

    # ==================== 通知系统 ====================

    async def _notify(self, message: str, level: str = 'info'):
        """发送飞书通知"""
        if not self.feishu_webhook:
            return
        
        try:
            import aiohttp
            
            emoji = {'info': 'ℹ️', 'success': '✅', 'warning': '⚠️', 'error': '❌'}.get(level, '')
            
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.feishu_webhook,
                    json={
                        "msg_type": "text",
                        "content": {"text": f"{emoji} 跟单机器人\n{message}"}
                    },
                    timeout=aiohttp.ClientTimeout(total=5)
                )
        except Exception as e:
            logger.warning(f"发送飞书通知失败: {e}")

    # ==================== 缓存和工具方法 ====================

    def _get_meta_cached(self) -> Dict:
        """获取元数据（带缓存，5分钟刷新）"""
        now = pendulum.now()
        if (self._meta_cache is None or 
            self._meta_cache_time is None or
            (now - self._meta_cache_time).total_seconds() > 300):
            self._meta_cache = self.client.get_meta()
            self._meta_cache_time = now
            # 刷新精度缓存
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

    # ==================== 每日重置 ====================

    def _check_daily_reset(self):
        """检查并重置每日统计"""
        today = pendulum.now().to_date_string()
        
        for state in self.targets.values():
            if state.last_reset_date != today:
                if state.last_reset_date is not None:
                    logger.info(
                        f"[{state.address[:8]}] 重置每日统计 "
                        f"(昨日交易: {state.copies_today}, PnL: {state.daily_pnl:.2f})"
                    )
                state.copies_today = 0
                state.daily_pnl = 0.0
                state.last_reset_date = today
        
        # 重置健康指标中的连续亏损
        if self.health.consecutive_losses > 0:
            self.health.consecutive_losses = 0
        
        # 取消风控暂停
        if self.is_paused:
            logger.info("新的一天，解除风控暂停")
            self.is_paused = False

    # ==================== 锁定机制 ====================

    def _lock_target(self, address: str, reason: str = "首次开仓"):
        """锁定交易员"""
        if self.lock_state is None:
            self.lock_state = LockState(
                target_address=address,
                locked_at=pendulum.now(),
                reason=reason
            )
            logger.info(f"🔒 锁定交易员: {address[:10]}... ({reason})")

    def _unlock_target(self, reason: str = ""):
        """解除锁定"""
        if self.lock_state:
            logger.info(f"🔓 解除锁定: {self.lock_state.target_address[:10]}... ({reason})")
            self.lock_state = None

    def _check_lock_timeout(self):
        """检查锁定是否超时"""
        if not self.lock_state:
            return
        
        elapsed = (pendulum.now() - self.lock_state.locked_at).total_seconds()
        if elapsed > self.lock_state.max_lock_duration:
            self._unlock_target(f"锁定超时 ({elapsed/3600:.1f}小时)")

    # ==================== 风控检查 ====================

    async def _check_risk_limits(self, target_state: TargetTraderState) -> bool:
        """
        检查风控限制
        
        Returns:
            bool: True 表示可以继续交易，False 表示应暂停
        """
        # 检查是否已暂停
        if self.is_paused:
            return False
        
        # 检查每日亏损
        if target_state.daily_pnl < -self.risk_control.max_daily_loss_usd:
            logger.warning(
                f"[{target_state.address[:8]}] 触发每日亏损限制: "
                f"{target_state.daily_pnl:.2f} < -{self.risk_control.max_daily_loss_usd}"
            )
            await self._notify(
                f"触发每日亏损限制\n亏损: ${abs(target_state.daily_pnl):.2f}",
                level='warning'
            )
            return False
        
        # 检查连续亏损
        if self.health.consecutive_losses >= self.risk_control.pause_on_consecutive_losses:
            logger.warning(
                f"触发连续亏损限制: {self.health.consecutive_losses} 次"
            )
            self.is_paused = True
            await self._notify(
                f"连续亏损 {self.health.consecutive_losses} 次，暂停跟单",
                level='error'
            )
            return False
        
        # 检查每日交易次数
        if target_state.copies_today >= self.risk_control.max_daily_trades:
            logger.info(f"[{target_state.address[:8]}] 达到每日交易次数上限")
            return False
        
        # 检查持仓数量
        if len(self.my_positions) >= self.risk_control.max_total_positions:
            logger.warning("持仓数量达到上限")
            return False
        
        return True

    # ==================== 订单重试机制 ====================

    async def _execute_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        max_retries: Optional[int] = None,
        base_delay: Optional[float] = None
    ) -> Dict:
        """
        带重试的订单执行
        
        Args:
            operation: 要执行的操作（返回 dict）
            operation_name: 操作名称（用于日志）
            max_retries: 最大重试次数
            base_delay: 重试基础延迟
            
        Returns:
            执行结果
        """
        max_retries = max_retries or self.risk_control.max_order_retries
        base_delay = base_delay or self.risk_control.retry_base_delay
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                result = operation()
                
                if result.get('status') == 'ok':
                    return result
                
                # API 返回失败
                error_response = result.get('response', {})
                error_msg = str(error_response)
                
                # 检查是否可重试的错误
                retryable_errors = ['rate limit', 'timeout', 'temporary', 'try again']
                is_retryable = any(err in error_msg.lower() for err in retryable_errors)
                
                if is_retryable and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} 失败，{delay:.1f}秒后重试 "
                        f"({attempt + 1}/{max_retries}): {error_msg}"
                    )
                    await asyncio.sleep(delay)
                    continue
                
                return result  # 不可重试的错误，直接返回
                
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"{operation_name} 异常，{delay:.1f}秒后重试 "
                        f"({attempt + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        
        # 所有重试都失败
        if last_error:
            raise last_error
        return {'status': 'error', 'message': 'Max retries exceeded'}

    # ==================== 配置加载 ====================

    def _load_configs_from_db(self) -> List[Dict]:
        """从数据库加载启用的跟单配置"""
        try:
            return self.db.get_enabled_copy_addresses()
        except Exception as e:
            logger.error(f"加载跟单配置失败: {e}")
            self.health.api_error_count += 1
            return []

    def _dict_to_config(self, data: Dict) -> CopyTradingConfig:
        """将数据库记录转换为 CopyTradingConfig"""
        return CopyTradingConfig(
            target_address=data.get('address', ''),
            copy_ratio=data.get('copy_ratio', 0.1),
            max_position_size_usd=data.get('max_position_size_usd', 100.0),
            min_position_size_usd=data.get('min_position_size_usd', 20.0),
            sync_position=data.get('sync_position', True),
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

    # ==================== 持仓获取 ====================

    def _should_copy_symbol(self, config: CopyTradingConfig, symbol: str) -> bool:
        """检查是否应该复制该币种"""
        if config.symbols_blacklist and symbol in config.symbols_blacklist:
            return False
        if config.symbols_whitelist:
            return symbol in config.symbols_whitelist
        return True

    def _get_target_positions(self, address: str) -> Optional[Dict[str, Dict]]:
        """获取目标交易者的当前持仓，失败时返回 None"""
        try:
            state = self.info_client.user_state(address)
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
            self.health.api_error_count += 1
            return None

    def _get_my_positions(self) -> Dict[str, Position]:
        """获取自己的当前持仓"""
        positions = {}
        try:
            for pos in self.client.get_positions():
                positions[pos.symbol] = pos
        except Exception as e:
            logger.error(f"获取自己持仓失败: {e}")
            self.health.api_error_count += 1
        return positions

    # ==================== 仓位计算 ====================

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

        return self._round_size(target_position['symbol'], size)

    def _calculate_leverage(
        self,
        config: CopyTradingConfig,
        target_leverage: int
    ) -> int:
        """计算杠杆"""
        if config.copy_leverage:
            return min(target_leverage, config.max_leverage)
        return config.default_leverage

    # ==================== 订单操作 ====================

    async def _open_position(
        self,
        target_state: TargetTraderState,
        symbol: str,
        is_long: bool,
        size: float,
        leverage: int,
        target_position: Dict = None
    ) -> bool:
        """开仓（带锁和重试）"""
        async with self._order_lock:
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
                # 设置杠杆
                self.client.set_leverage(symbol, leverage)
                await asyncio.sleep(0.3)

                # 带重试的下单
                result = await self._execute_with_retry(
                    lambda: self.client.market_order(symbol, is_long, size, slippage=config.slippage),
                    f"开仓 {symbol} {side}"
                )

                success = result.get('status') == 'ok'
                order_data['executed_at'] = pendulum.now().isoformat()

                if success:
                    logger.info(f"[{target_state.address[:8]}] 开仓成功: {symbol} {side} {size}")
                    order_data['status'] = 'success'
                    target_state.successful_copies += 1

                    # 锁定该交易员
                    self._lock_target(target_state.address, "谁先开仓跟谁")

                    # 发送通知
                    await self._notify(
                        f"开仓成功: {symbol} {side}\n"
                        f"数量: {size}\n"
                        f"目标: {target_state.address[:10]}...",
                        level='success'
                    )

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
        """调整仓位（加仓或减仓，带锁和重试）"""
        async with self._order_lock:
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

            # 使用精确计算
            current_price = self.client.get_mid_price(symbol)
            my_target_size = self._calculate_copy_size(config, target_position, current_price)
            my_current_size = abs(my_pos.size)
            adjustment_size = abs(my_target_size - my_current_size)
            adjustment_size = self._round_size(symbol, adjustment_size)

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

                # 带重试的下单
                if is_increase:
                    result = await self._execute_with_retry(
                        lambda: self.client.market_order(symbol, is_long, adjustment_size, slippage=config.slippage),
                        f"加仓 {symbol}"
                    )
                else:
                    result = await self._execute_with_retry(
                        lambda: self.client.market_order(symbol, not is_long, adjustment_size, slippage=config.slippage),
                        f"减仓 {symbol}"
                    )

                success = result.get('status') == 'ok'
                order_data['executed_at'] = pendulum.now().isoformat()

                if success:
                    logger.info(f"[{target_state.address[:8]}] {action_type}成功: {symbol} {adjustment_size}")
                    order_data['status'] = 'success'
                    if self._on_adjust:
                        side = 'long' if is_long else 'short'
                        self._on_adjust(target_state.address, symbol, side, adjustment_size, is_increase)
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
        """平仓（带锁和重试）"""
        async with self._order_lock:
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
                # 带重试的平仓
                result = await self._execute_with_retry(
                    lambda: self.client.close_position(symbol, slippage=config.slippage),
                    f"平仓 {symbol}"
                )
                
                success = result.get('status') == 'ok'
                order_data['executed_at'] = pendulum.now().isoformat()

                if success:
                    logger.info(f"[{target_state.address[:8]}] 平仓成功: {symbol}, PnL: {pnl:.2f}")
                    order_data['status'] = 'success'
                    target_state.daily_pnl += pnl
                    
                    # 更新连续亏损计数
                    if pnl < 0:
                        self.health.consecutive_losses += 1
                    else:
                        self.health.consecutive_losses = 0
                    
                    # 发送通知
                    level = 'success' if pnl >= 0 else 'warning'
                    await self._notify(
                        f"平仓: {symbol}\n"
                        f"PnL: ${pnl:.2f}\n"
                        f"今日PnL: ${target_state.daily_pnl:.2f}",
                        level=level
                    )
                    
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

    # ==================== 初始化和同步 ====================

    async def _initialize_target(
        self,
        target_state: TargetTraderState,
        target_positions: Dict[str, Dict]
    ):
        """初始化目标交易者状态"""
        config = target_state.config
        address = target_state.address
        
        # 尝试从数据库恢复已跟单仓位状态
        saved_positions = self.db.get_copied_positions(address)
        if saved_positions:
            logger.info(f"[{address[:8]}] 从数据库恢复 {len(saved_positions)} 个已跟单仓位状态")
            target_state.copied_positions = saved_positions
            target_state.initialized = True
            target_state.init_timestamp = pendulum.now()
            target_state.last_check = pendulum.now()

            # 恢复锁定状态
            self._lock_target(address, "已有跟单仓位")
            return
        
        target_state.init_timestamp = pendulum.now()
        
        if config.sync_position:
            logger.info(f"[{address[:8]}] 开始同步现有仓位...")
            for symbol, target_pos in target_positions.items():
                if not self._should_copy_symbol(config, symbol):
                    continue
                if target_pos['notional'] < config.min_position_size_usd:
                    continue
                
                my_pos = self.my_positions.get(symbol)
                current_price = self.client.get_mid_price(symbol)
                copy_size = self._calculate_copy_size(config, target_pos, current_price)
                leverage = self._calculate_leverage(config, target_pos['leverage'])
                is_long = target_pos['side'] == 'long'
                
                if my_pos is None:
                    logger.info(
                        f"[{address[:8]}] 同步仓位: {symbol} "
                        f"{target_pos['side']} {abs(target_pos['size'])} -> 开仓 {copy_size}"
                    )
                    await self._open_position(target_state, symbol, is_long, copy_size, leverage, target_pos)
                    target_state.copies_today += 1
                elif (my_pos.side == PositionSide.LONG) != is_long:
                    logger.warning(
                        f"[{address[:8]}] 跳过同步（方向不同）: {symbol} "
                        f"我方 {my_pos.side.value} vs 目标 {target_pos['side']}"
                    )
                else:
                    logger.info(
                        f"[{address[:8]}] 记录已有仓位: {symbol} "
                        f"{target_pos['side']} {abs(target_pos['size'])}"
                    )
                
                target_state.copied_positions[symbol] = target_pos
                await asyncio.sleep(config.order_delay)
            
            logger.info(
                f"[{address[:8]}] 初始化完成（同步模式），已同步 {len(target_state.copied_positions)} 个仓位"
            )
        else:
            for symbol, target_pos in target_positions.items():
                if self._should_copy_symbol(config, symbol):
                    target_state.copied_positions[symbol] = target_pos
                    logger.info(
                        f"[{address[:8]}] 初始化记录现有持仓: {symbol} "
                        f"{target_pos['side']} {abs(target_pos['size'])} (不跟单)"
                    )
            logger.info(
                f"[{address[:8]}] 初始化完成（不同步），已记录 {len(target_state.copied_positions)} 个现有持仓"
            )
        
        target_state.initialized = True
        target_state.last_check = pendulum.now()

    async def _sync_target(self, target_state: TargetTraderState):
        """同步单个目标的持仓"""
        config = target_state.config
        address = target_state.address

        # 检查锁定状态
        if self.lock_state and self.lock_state.target_address != address:
            return

        # 风控检查
        if not await self._check_risk_limits(target_state):
            return

        # 获取目标持仓
        target_positions = self._get_target_positions(address)

        if target_positions is None:
            logger.warning(f"[{address[:8]}] 获取持仓失败，跳过本次同步")
            self.health.consecutive_failures += 1
            return

        target_state.positions = target_positions

        # 首次初始化
        if not target_state.initialized:
            await self._initialize_target(target_state, target_positions)
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
                # 新仓位
                logger.info(f"[{address[:8]}] 发现新仓位: {symbol} {target_pos['side']} {abs(target_pos['size'])}")

                # 检查观察期
                if target_state.init_timestamp:
                    time_since_init = (pendulum.now() - target_state.init_timestamp).total_seconds()
                    if time_since_init < config.init_observation_period:
                        logger.warning(
                            f"[{address[:8]}] 观察期内（{time_since_init:.1f}s/{config.init_observation_period:.0f}s），"
                            f"跳过新仓位 {symbol}"
                        )
                        target_state.copied_positions[symbol] = target_pos
                        continue

                current_price = self.client.get_mid_price(symbol)
                copy_size = self._calculate_copy_size(config, target_pos, current_price)
                leverage = self._calculate_leverage(config, target_pos['leverage'])
                is_long = target_pos['side'] == 'long'

                if my_pos is None:
                    await self._open_position(target_state, symbol, is_long, copy_size, leverage, target_pos)
                elif (my_pos.side == PositionSide.LONG) != is_long:
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
                leverage = self._calculate_leverage(config, target_pos['leverage'])

                await self._open_position(target_state, symbol, target_pos['side'] == 'long', copy_size, leverage, target_pos)
                target_state.copies_today += 1

            elif abs(prev_target['size']) != abs(target_pos['size']):
                # 仓位大小变化
                size_change_pct = (abs(target_pos['size']) - abs(prev_target['size'])) / abs(prev_target['size']) * 100

                if abs(size_change_pct) >= 1.0:
                    await self._adjust_position(
                        target_state, symbol,
                        prev_target['size'], target_pos['size'],
                        target_pos
                    )
                    target_state.copies_today += 1

            target_state.copied_positions[symbol] = target_pos

        # 处理平仓：目标不再持有的仓位
        for symbol in list(target_state.copied_positions.keys()):
            if symbol not in target_positions:
                if symbol in self.my_positions:
                    logger.info(f"[{address[:8]}] 目标已平仓: {symbol}")
                    await self._close_position(target_state, symbol)
                    target_state.copies_today += 1

                del target_state.copied_positions[symbol]
                try:
                    self.db.delete_copied_position(address, symbol)
                except Exception as e:
                    logger.warning(f"[{address[:8]}] 删除仓位状态失败: {e}")

        # 锁定状态下：平掉目标没有但我们有的所有仓位
        # 这可以处理因仓位太小减仓失败的情况
        if self.lock_state and self.lock_state.target_address == address:
            for symbol in list(self.my_positions.keys()):
                # 目标没有这个仓位，但我们有
                if symbol not in target_positions:
                    logger.info(
                        f"[{address[:8]}] 锁定状态下发现目标无仓位，平掉我方仓位: {symbol}"
                    )
                    await self._close_position(target_state, symbol)
                    target_state.copies_today += 1
                    
                    # 同时清理 copied_positions（如果存在）
                    if symbol in target_state.copied_positions:
                        del target_state.copied_positions[symbol]
                        try:
                            self.db.delete_copied_position(address, symbol)
                        except Exception as e:
                            logger.warning(f"[{address[:8]}] 删除仓位状态失败: {e}")

        # 持久化状态
        try:
            self.db.save_copied_positions(address, target_state.copied_positions)
        except Exception as e:
            logger.warning(f"[{address[:8]}] 保存跟单状态失败: {e}")

        # 检查是否解除锁定
        if self.lock_state and self.lock_state.target_address == address and not target_state.copied_positions:
            self._unlock_target("仓位已全部平仓")

        target_state.last_check = pendulum.now()

    async def _sync_all_targets(self):
        """同步所有目标"""
        async with self._sync_lock:
            start_time = pendulum.now()
            
            # 每日重置检查
            self._check_daily_reset()
            
            # 锁定超时检查
            self._check_lock_timeout()
            
            # 更新自己的持仓
            async with self._position_lock:
                self.my_positions = self._get_my_positions()

            # 确定要同步的目标
            if self.lock_state and self.lock_state.target_address in self.targets:
                targets_to_sync = {self.lock_state.target_address: self.targets[self.lock_state.target_address]}
            else:
                targets_to_sync = self.targets

            # 健康指标
            self.health.total_syncs += 1

            # 串行同步（避免并发问题）
            for address, state in targets_to_sync.items():
                try:
                    await self._sync_target(state)
                except Exception as e:
                    logger.error(f"同步目标 {address[:10]}... 失败: {e}")
                    self.health.consecutive_failures += 1
                    if self._on_error:
                        self._on_error(e)

            # 更新健康指标
            latency = (pendulum.now() - start_time).total_milliseconds()
            self._sync_latencies.append(latency)
            self.health.last_successful_sync = pendulum.now()
            self.health.successful_syncs += 1
            self.health.consecutive_failures = 0

    # ==================== 运行控制 ====================

    async def run(self):
        """运行多目标跟单机器人"""
        self.is_running = True

        logger.info("=" * 60)
        logger.info("多目标跟单机器人启动 (改进版)")
        logger.info(f"检查间隔: {self.check_interval}秒")
        logger.info(f"配置重载间隔: {self.reload_interval}秒")
        logger.info(f"风控: 每日最大亏损 ${self.risk_control.max_daily_loss_usd}")
        logger.info(f"风控: 连续亏损暂停 {self.risk_control.pause_on_consecutive_losses} 次")
        logger.info("=" * 60)

        # 发送启动通知
        await self._notify("跟单机器人已启动", level='info')

        # 加载初始配置
        self.reload_configs()

        if not self.targets:
            logger.warning("没有启用的跟单目标，请先在跟单管理中添加并启用地址")

        try:
            while self.is_running:
                try:
                    # 检查是否需要重载配置
                    if (self.last_config_reload is None or
                        (pendulum.now() - self.last_config_reload).total_seconds() >= self.reload_interval):
                        self.reload_configs()

                    if self.targets:
                        await self._sync_all_targets()

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"同步时遇到错误，将在下一周期重试: {e}")
                    self.health.consecutive_failures += 1
                    if self._on_error:
                        self._on_error(e)

                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("多目标跟单机器人被取消")
        finally:
            self.is_running = False
            await self._notify("跟单机器人已停止", level='warning')
            logger.info("多目标跟单机器人停止")

    def stop(self):
        """停止机器人"""
        self.is_running = False
        logger.info("正在停止多目标跟单机器人...")

    # ==================== 状态和健康检查 ====================

    def is_healthy(self) -> bool:
        """检查机器人是否健康"""
        # 检查连续失败
        if self.health.consecutive_failures > 5:
            return False
        
        # 检查最后成功同步时间
        if self.health.last_successful_sync:
            elapsed = (pendulum.now() - self.health.last_successful_sync).total_seconds()
            if elapsed > 300:  # 5分钟无成功同步
                return False
        
        # 检查是否暂停
        if self.is_paused:
            return False
        
        return True

    def get_health_status(self) -> Dict[str, Any]:
        """获取健康状态详情"""
        avg_latency = sum(self._sync_latencies) / len(self._sync_latencies) if self._sync_latencies else 0
        
        return {
            'is_healthy': self.is_healthy(),
            'is_paused': self.is_paused,
            'consecutive_failures': self.health.consecutive_failures,
            'consecutive_losses': self.health.consecutive_losses,
            'api_error_count': self.health.api_error_count,
            'sync_success_rate': f"{self.health.get_success_rate() * 100:.1f}%",
            'avg_sync_latency_ms': round(avg_latency, 2),
            'last_successful_sync': self.health.last_successful_sync.isoformat() if self.health.last_successful_sync else None
        }

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
            'is_healthy': self.is_healthy(),
            'is_paused': self.is_paused,
            'target_count': len(self.targets),
            'locked_target': self.locked_target,
            'lock_info': {
                'address': self.lock_state.target_address if self.lock_state else None,
                'locked_at': self.lock_state.locked_at.isoformat() if self.lock_state else None,
                'reason': self.lock_state.reason if self.lock_state else None,
                'duration_seconds': (pendulum.now() - self.lock_state.locked_at).total_seconds() if self.lock_state else 0
            } if self.lock_state else None,
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
            'health': self.get_health_status(),
            'last_config_reload': self.last_config_reload.isoformat() if self.last_config_reload else None
        }
