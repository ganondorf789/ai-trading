"""
仓位级别跟单机器人引擎
第二种跟单模式：跟单特定交易员的特定仓位

与第一种模式 (MultiTargetCopyTradingBot) 的区别：
- 第一种：跟单交易员的所有仓位
- 第二种：只跟单交易员的特定仓位（本模块）

通过 gRPC 服务访问数据库和 Redis
"""
import sys
import os

# 添加项目根目录到路径（用于导入 clients, core, database）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from asyncio import Lock
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
import pendulum

from hyperliquid.info import Info

from core.models import Position, PositionSide
from core.tracking_utils import build_tracking_data_from_dataclass
from clients.hyperliquid_client import HyperliquidClient
from trading.settings import settings
from trading.grpc_client import GRPCClient, GRPCDatabaseClient, GRPCRedisClient

# Redis 开仓通知 channel
REDIS_OPEN_CHANNEL = "position_tracking_open"
# Redis 补仓通知 channel
REDIS_ADJUST_CHANNEL = "position_tracking_adjust"
# Redis 平仓通知 channel
REDIS_CLOSE_CHANNEL = "position_tracking_close"
# Redis 配置重载通知 channel
REDIS_CONFIG_RELOAD_CHANNEL = "copy_trading:config:reload"
# Redis 通知 channel（用于 WebSocket 推送和数据库保存）
REDIS_NOTIFICATIONS_CHANNEL = "notifications"
# Redis 账户缓存 key
REDIS_MY_POSITIONS_KEY = "copy_trading:my_positions"
REDIS_MY_BALANCE_KEY = "copy_trading:my_balance"


@dataclass
class TrackingState:
    """单个仓位跟单的状态"""
    tracking_id: str  # ULID 字符串
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
    
    # 自动补仓配置
    auto_replenish: bool = False  # 是否启用自动补仓
    replenish_ratio: float = 0.5  # 补仓比例（按目标补仓量的比例）
    replenish_min_value_usd: float = 10.0  # 单次补仓最小金额
    replenish_max_value_usd: float = 100.0  # 单次补仓最大金额
    
    # 目标仓位快照
    target_initial_size: Optional[float] = None
    target_initial_side: Optional[str] = None
    target_initial_entry_price: Optional[float] = None
    
    # 当前目标仓位
    target_current_size: Optional[float] = None
    target_current_side: Optional[str] = None
    target_current_notional: Optional[float] = None  # 目标的当前 notional
    
    # 我方仓位
    my_size: float = 0.0
    my_side: Optional[str] = None
    my_entry_price: Optional[float] = None
    
    # 状态
    status: str = 'pending'  # pending/active/closed/stopped
    last_sync: Optional[pendulum.DateTime] = None
    
    # 上次补仓失败时的目标仓位大小（用于避免重复尝试）
    last_failed_adjust_target_size: Optional[float] = None
    
    # 交易员标记
    target_is_starred: bool = False
    
    # 交易员评分信息
    target_score: Optional[float] = None
    target_rating: Optional[str] = None

    # 仓位模式
    position_mode: str = 'cross'  # 仓位模式: cross(全仓) / isolated(逐仓)


@dataclass
class AddressTrackingConfig:
    """地址跟踪配置（用于监控特定地址的交易活动并发送通知）"""
    id: int
    tracking_address: str
    address_remark: str = ''
    monitor_events: List[str] = field(default_factory=lambda: ['open', 'close', 'add', 'reduce'])
    is_enabled: bool = True
    enable_notification: bool = True


@dataclass
class AddressConfig:
    """跟单地址配置（用于自动跟单）"""
    address: str
    name: str
    is_enabled: bool = True
    
    # 跟单配置
    copy_ratio: float = 0.1
    max_position_size_usd: float = 500.0
    min_position_size_usd: float = 20.0
    copy_leverage: bool = True
    max_leverage: int = 10
    default_leverage: int = 5
    slippage: float = 0.01
    
    # 只跟一次
    copy_once: bool = False  # 开启后只跟第一个新仓位，跟完自动禁用该地址

    # 仓位模式
    position_mode: str = 'cross'  # 仓位模式: cross(全仓) / isolated(逐仓)
    
    # 自动补仓配置
    auto_replenish: bool = False  # 是否启用自动补仓
    replenish_ratio: float = 0.5  # 补仓比例（按目标补仓量的比例）
    replenish_min_value_usd: float = 10.0  # 单次补仓最小金额
    replenish_max_value_usd: float = 100.0  # 单次补仓最大金额
    
    # 币种限制
    symbols_whitelist: List[str] = field(default_factory=list)  # 白名单（空表示不限制）
    symbols_blacklist: List[str] = field(default_factory=list)  # 黑名单


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
        grpc_client: 'GRPCClient' = None,
        max_positions: int = 0
    ):
        """
        初始化仓位跟单机器人

        Args:
            client: Hyperliquid 客户端（需要已初始化钱包）
            check_interval: 检查间隔（秒）
            reload_interval: 配置重载间隔（秒）
            grpc_client: gRPC 客户端
            max_positions: 最大仓位数量限制，0表示不限制
        """
        self.client = client
        self.check_interval = check_interval
        self.reload_interval = reload_interval
        self.max_positions = max_positions
        
        # gRPC 客户端
        self._grpc_client = grpc_client
        
        # 跟单状态 (tracking_id(ULID) -> TrackingState)
        self.trackings: Dict[str, TrackingState] = {}
        
        # 自己的持仓
        self.my_positions: Dict[str, Position] = {}
        
        # 账户余额（可用保证金）
        self.available_balance: float = 0.0
        
        # 运行状态
        self.is_running = False
        self.last_config_reload: Optional[pendulum.DateTime] = None
        
        # 并发锁
        self._order_locks: Dict[str, Lock] = {}  # 按 symbol 分离的订单锁
        self._order_locks_lock = Lock()  # 保护 _order_locks 字典的锁
        self._sync_lock = Lock()
        
        # 缓存
        self._info_client: Optional[Info] = None
        self._meta_cache: Optional[Dict] = None
        self._meta_cache_time: Optional[pendulum.DateTime] = None
        self._symbol_decimals: Dict[str, int] = {}
        
        # 正在处理中的 tracking_id（防止并发重复处理）
        self._processing_tracking_ids: set = set()
        
        # 通知去重（避免重复发送相同通知）
        self._recent_notifications: Dict[str, float] = {}  # notification_key -> timestamp
        self._notification_cooldown: float = 10.0  # 10秒内相同通知不重复发送
        
        # 自动跟单相关
        self._user_id: str = settings.bot.user_id  # 用户 ULID（从配置读取）
        self.address_configs: Dict[str, AddressConfig] = {}  # 地址配置缓存 (address -> AddressConfig)
        self._address_positions: Dict[str, Dict[str, Dict]] = {}  # 地址仓位缓存 (address -> {symbol -> position})
        
        # 地址跟踪相关（仅监控，不交易）
        self.tracking_configs: Dict[str, AddressTrackingConfig] = {}  # 跟踪配置缓存 (address -> config)
        self._tracked_positions: Dict[str, Dict[str, Dict]] = {}  # 跟踪地址的仓位缓存 (address -> {symbol -> position})
        
        logger.info("使用 gRPC 模式连接数据库和 Redis")

    @property
    def db(self) -> GRPCDatabaseClient:
        """获取数据库客户端"""
        if self._grpc_client is None:
            self._grpc_client = GRPCClient(
                host=settings.grpc.host,
                port=settings.grpc.port,
                api_key=settings.api.key
            )
            logger.info(f"gRPC 客户端已连接: {settings.grpc.host}:{settings.grpc.port}")
        return self._grpc_client.db
    
    @property
    def redis(self) -> GRPCRedisClient:
        """获取 Redis 客户端"""
        if self._grpc_client is None:
            self._grpc_client = GRPCClient(
                host=settings.grpc.host,
                port=settings.grpc.port,
                api_key=settings.api.key
            )
        return self._grpc_client.redis

    async def _listen_redis_open(self):
        """监听 Redis 开仓通知，收到后立即执行开仓"""
        await self._listen_redis_grpc(
            channels=[REDIS_OPEN_CHANNEL],
            handler=self._on_redis_open_message,
            name="开仓"
        )
    
    async def _on_redis_open_message(self, channel: str, data: str):
        """
        处理开仓通知消息
        
        消息格式（JSON）：
            {"tracking_id": "<ULID>", "user_ulid": "<ULID>"}
        兼容旧格式（纯字符串 tracking ULID，不含 user_ulid 校验）
        
        注意: 支持 user_ulid 和 user_id 两种 key，以兼容新旧消息格式。
        user_ulid 的值现在是用户的 ULID 主键（来自 user.id）。
        """
        try:
            stripped = data.strip()
            if not stripped:
                logger.warning(f"无效的开仓通知格式: {data}")
                return
            
            # 尝试解析 JSON 格式
            tracking_id = ''
            user_ulid = ''
            try:
                msg = json.loads(stripped)
                tracking_id = msg.get('tracking_id', '')
                user_ulid = msg.get('user_ulid') or msg.get('user_id', '')
            except (json.JSONDecodeError, TypeError):
                # 兼容旧格式：纯 tracking ULID 字符串
                tracking_id = stripped
            
            if not tracking_id:
                logger.warning(f"无效的开仓通知格式（缺少 tracking_id）: {data}")
                return
            
            # 校验 user_ulid 是否与本 bot 的 BOT_USER_ID 一致
            my_user_id = settings.bot.user_id
            if user_ulid and my_user_id:
                if user_ulid != my_user_id:
                    logger.debug(
                        f"跳过开仓通知: user_ulid={user_ulid[:8]}... "
                        f"与本机 BOT_USER_ID={my_user_id[:8]}... 不匹配"
                    )
                    return
            elif not my_user_id:
                logger.warning("BOT_USER_ID 未配置，无法校验用户归属，跳过开仓通知")
                return
            
            logger.info(f"收到开仓通知: tracking_id={tracking_id}, user={user_ulid[:8] if user_ulid else 'N/A'}...")
            await self._handle_open_notification(tracking_id)
        except Exception:
            logger.warning(f"无效的开仓通知格式: {data}")

    async def _handle_open_notification(self, tracking_id: str):
        """处理开仓通知，立即执行开仓"""
        # 防止并发重复处理
        if tracking_id in self._processing_tracking_ids:
            logger.debug(f"[立即开仓] tracking_id={tracking_id} 正在处理中，跳过")
            return
        
        self._processing_tracking_ids.add(tracking_id)
        try:
            # 从数据库加载跟单配置
            tracking_data = self.db.get_position_tracking(tracking_id)
            if not tracking_data:
                logger.warning(f"[立即开仓] tracking_id={tracking_id} 不存在")
                return
            
            if tracking_data.get('status') != 'pending':
                logger.warning(f"[立即开仓] tracking_id={tracking_id} 状态不是 pending")
                return
            
            # 转换为 TrackingState
            state = self._dict_to_state(tracking_data)
            
            # 获取目标仓位
            target_pos = self._get_target_position(state.target_address, state.symbol)
            if target_pos is None:
                logger.warning(f"[立即开仓] {state.symbol} 目标暂无仓位")
                return
            
            logger.info(f"[立即开仓] tracking_id={tracking_id} {state.symbol} 目标仓位: {target_pos['side']} {abs(target_pos['size'])}")
            
            # 记录初始快照
            state.target_initial_size = abs(target_pos['size'])
            state.target_initial_side = target_pos['side']
            state.target_initial_entry_price = target_pos['entry_price']
            state.target_current_size = abs(target_pos['size'])
            state.target_current_side = target_pos['side']
            
            # 保存初始快照到数据库（保留原有配置参数，避免被默认值覆盖）
            self.db.save_position_tracking({
                'id': state.tracking_id,
                'target_address': state.target_address,
                'target_name': state.target_name,
                'symbol': state.symbol,
                'is_enabled': tracking_data.get('is_enabled', True),
                'copy_ratio': state.copy_ratio,
                'max_position_size_usd': state.max_position_size_usd,
                'min_position_size_usd': state.min_position_size_usd,
                'copy_leverage': state.copy_leverage,
                'max_leverage': state.max_leverage,
                'default_leverage': state.default_leverage,
                'slippage': state.slippage,
                'target_initial_size': state.target_initial_size,
                'target_initial_side': state.target_initial_side,
                'target_initial_entry_price': state.target_initial_entry_price,
                'target_initial_leverage': target_pos.get('leverage'),
                'target_is_starred': state.target_is_starred,
                'target_score': state.target_score,
                'target_rating': state.target_rating,
                'status': 'pending'
            })
            
            # 计算跟单仓位
            current_price = self.client.get_mid_price(state.symbol)
            copy_size = self._calculate_copy_size(state, target_pos['notional'], current_price)
            leverage = self._calculate_leverage(state, target_pos['leverage'])
            is_long = target_pos['side'] == 'long'
            
            # 更新自己的持仓和余额
            if not self._update_my_account():
                logger.warning(f"[立即开仓] 获取账户信息失败，跳过")
                return
            my_pos = self.my_positions.get(state.symbol)
            
            # 检查是否已有仓位
            if my_pos is None:
                # 执行开仓
                success = await self._open_position(state, is_long, copy_size, leverage, target_pos)
                if success:
                    # 添加到跟单列表
                    self.trackings[tracking_id] = state
                    logger.success(f"[立即开仓] 成功: {state.symbol} {target_pos['side']} {copy_size}")
                else:
                    # 开仓失败，标记为 stopped，不再重试
                    state.status = 'stopped'
                    self.db.update_tracking_status(state.tracking_id, 'stopped', '开仓失败')
                    self.trackings[tracking_id] = state
                    logger.error(f"[立即开仓] 失败: {state.symbol}，已停止")
            elif (my_pos.side == PositionSide.LONG) == is_long:
                # 方向相同，标记为 closed
                state.status = 'closed'
                self.db.update_tracking_status(state.tracking_id, 'closed', '已有同向仓位，需要手动处理')
                logger.warning(f"[立即开仓] 已有同向仓位，标记为 closed")
            else:
                # 已有反向仓位，标记为 closed
                state.status = 'closed'
                self.db.update_tracking_status(state.tracking_id, 'closed', '已有反向仓位，需要手动处理')
                logger.warning(f"[立即开仓] 已有反向仓位，标记为 closed")
                
        except Exception as e:
            logger.error(f"[立即开仓] 处理 tracking_id={tracking_id} 失败: {e}")
        finally:
            # 处理完成，移除标记
            self._processing_tracking_ids.discard(tracking_id)

    async def _listen_redis_adjust(self):
        """监听 Redis 补仓通知，收到后立即执行补仓"""
        await self._listen_redis_grpc(
            channels=[REDIS_ADJUST_CHANNEL],
            handler=self._on_redis_adjust_message,
            name="补仓"
        )
    
    async def _on_redis_adjust_message(self, channel: str, data: str):
        """处理补仓通知消息"""
        try:
            msg_data = json.loads(data)
            tracking_id = str(msg_data.get('tracking_id', ''))
            ratio = msg_data.get('ratio')
            size = msg_data.get('size')
            direction = msg_data.get('direction')
            
            logger.info(f"收到调仓通知: tracking_id={tracking_id}, ratio={ratio}, size={size}, direction={direction}")
            await self._handle_adjust_notification(tracking_id, ratio=ratio, size=size, direction=direction)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"无效的补仓通知格式: {data}, error: {e}")

    async def _handle_adjust_notification(
        self, 
        tracking_id: str, 
        ratio: float = None, 
        size: float = None,
        direction: str = None
    ):
        """
        处理加仓/减仓通知，立即执行
        
        Args:
            tracking_id: 跟单记录ID
            ratio: 调整比例（百分比），如 50 表示调整当前仓位的 50%
            size: 调整数量（直接指定数量）
            direction: 下单方向 ('long' 或 'short')
                       - 与当前持仓同向 = 加仓
                       - 与当前持仓反向 = 减仓
        """
        # 防止并发重复处理
        adjust_key = f"adjust_{tracking_id}"
        if adjust_key in self._processing_tracking_ids:
            logger.debug(f"[调仓] tracking_id={tracking_id} 正在处理中，跳过")
            return
        
        self._processing_tracking_ids.add(adjust_key)
        try:
            # 检查跟单状态
            state = self.trackings.get(tracking_id)
            if state is None:
                # 尝试从数据库加载
                tracking_data = self.db.get_position_tracking(tracking_id)
                if not tracking_data:
                    logger.warning(f"[调仓] tracking_id={tracking_id} 不存在")
                    return
                state = self._dict_to_state(tracking_data)
                self.trackings[tracking_id] = state
            
            if state.status != 'active':
                logger.warning(f"[调仓] tracking_id={tracking_id} 状态不是 active (当前: {state.status})")
                return
            
            symbol = state.symbol
            
            # 更新自己的持仓和余额
            if not self._update_my_account():
                logger.warning(f"[调仓] 获取账户信息失败，跳过")
                return
            my_pos = self.my_positions.get(symbol)
            
            if my_pos is None:
                logger.warning(f"[调仓] {symbol} 本地无持仓，无法调仓")
                return
            
            current_is_long = my_pos.side == PositionSide.LONG
            current_price = self.client.get_mid_price(symbol)
            my_current_size = abs(my_pos.size)
            
            # 确定下单方向
            if direction is not None:
                order_is_long = (direction == 'long')
            else:
                # 未指定方向，默认与当前持仓同向（加仓）
                order_is_long = current_is_long
            
            # 判断是加仓还是减仓
            is_add = (order_is_long == current_is_long)  # 同向=加仓，反向=减仓
            action_name = "加仓" if is_add else "减仓"
            
            # 计算调整数量
            if size is not None:
                # 直接指定数量
                adjust_size = abs(size)
            elif ratio is not None:
                # 按比例计算（ratio 是百分比，如 50 表示调整 50%）
                adjust_size = my_current_size * (ratio / 100.0)
            else:
                logger.warning(f"[调仓] tracking_id={tracking_id} 未指定比例或数量")
                return
            
            adjust_size = self._round_size(symbol, adjust_size)
            
            if adjust_size <= 0:
                logger.warning(f"[调仓] tracking_id={tracking_id} 计算的调整数量为 0")
                return
            
            # 减仓时检查数量不能超过当前仓位
            if not is_add and adjust_size > my_current_size:
                logger.warning(f"[减仓] {symbol} 减仓数量 {adjust_size:.4f} 超过当前仓位 {my_current_size:.4f}，调整为全部平仓")
                adjust_size = my_current_size
            
            # 加仓时检查余额是否足够
            if is_add:
                notional_value = adjust_size * current_price
                leverage = my_pos.leverage if my_pos.leverage else state.default_leverage
                required_margin = notional_value / leverage
                if not self._check_balance_sufficient(required_margin, "加仓", symbol):
                    return
            
            order_direction = "做多" if order_is_long else "做空"
            logger.info(
                f"[{action_name}] tracking_id={tracking_id} {symbol} "
                f"当前: {my_current_size:.4f}, {action_name}: {adjust_size:.4f}, 方向: {order_direction}"
            )
            
            # 执行下单
            order_lock = await self._get_order_lock(symbol)
            async with order_lock:
                try:
                    # 获取锁后重新检查仓位，防止并发问题
                    if not self._update_my_account():
                        logger.warning(f"[{action_name}] 获取账户信息失败，跳过")
                        return
                    my_pos = self.my_positions.get(symbol)
                    if my_pos is None:
                        logger.warning(f"[{action_name}] {symbol} 已无持仓，跳过")
                        return
                    
                    # 重新计算当前仓位大小（可能已被其他操作修改）
                    my_current_size = abs(my_pos.size)
                    current_is_long = my_pos.side == PositionSide.LONG
                    
                    # 重新判断加仓还是减仓
                    is_add = (order_is_long == current_is_long)
                    action_name = "加仓" if is_add else "减仓"
                    
                    # 减仓时重新检查数量
                    if not is_add and adjust_size > my_current_size:
                        adjust_size = my_current_size
                    
                    result = self.client.market_order(
                        symbol, order_is_long, adjust_size, slippage=state.slippage
                    )
                    
                    if result.get('status') == 'ok':
                        if is_add:
                            new_size = my_current_size + adjust_size
                        else:
                            new_size = my_current_size - adjust_size
                        
                        logger.success(
                            f"[{action_name}] 成功: {symbol} {my_current_size:.4f} → {new_size:.4f}"
                        )
                        
                        # 更新状态
                        if new_size > 0:
                            state.my_size = new_size
                            self.db.update_tracking_position(
                                state.tracking_id, new_size, state.my_side, state.my_entry_price
                            )
                        else:
                            # 完全平仓
                            state.my_size = 0
                            state.status = 'closed'
                            self.db.update_tracking_status(state.tracking_id, 'closed')
                        
                        # 发送通知
                        side = 'long' if order_is_long else 'short'
                        self._notify_copy_adjust(state.target_address, symbol, side, adjust_size, is_add)
                    else:
                        logger.error(f"[{action_name}] 失败: {result}")
                        
                except Exception as e:
                    logger.error(f"[{action_name}] 下单异常: {e}")
                        
        except Exception as e:
            logger.error(f"[调仓] 处理 tracking_id={tracking_id} 失败: {e}")
        finally:
            # 处理完成，移除标记
            self._processing_tracking_ids.discard(adjust_key)

    async def _listen_redis_close(self):
        """监听 Redis 平仓通知，收到后立即执行平仓"""
        await self._listen_redis_grpc(
            channels=[REDIS_CLOSE_CHANNEL],
            handler=self._on_redis_close_message,
            name="平仓"
        )
    
    async def _on_redis_close_message(self, channel: str, data: str):
        """处理平仓通知消息"""
        try:
            msg_data = json.loads(data)
            symbol = msg_data.get('symbol')
            tracking_id = msg_data.get('tracking_id')  # ULID 字符串
            
            logger.info(f"收到平仓通知: symbol={symbol}, tracking_id={tracking_id}")
            await self._handle_close_notification(symbol=symbol, tracking_id=tracking_id)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"无效的平仓通知格式: {data}, error: {e}")

    async def _listen_redis_config_reload(self):
        """监听 Redis 配置重载通知，收到后立即重载配置"""
        await self._listen_redis_grpc(
            channels=[REDIS_CONFIG_RELOAD_CHANNEL],
            handler=self._on_redis_config_reload_message,
            name="配置重载"
        )
    
    async def _on_redis_config_reload_message(self, channel: str, data: str):
        """
        处理配置重载通知消息
        
        消息格式（JSON）：{"user_ulid": "<ULID>"}
        兼容旧格式（纯字符串 "reload"，不含 user_ulid 校验）
        
        注意: 支持 user_ulid 和 user_id 两种 key，以兼容新旧消息格式。
        user_ulid 的值现在是用户的 ULID 主键（来自 user.id）。
        """
        try:
            # 尝试解析 JSON 格式
            user_ulid = ''
            try:
                msg = json.loads(data.strip())
                user_ulid = msg.get('user_ulid') or msg.get('user_id', '')
            except (json.JSONDecodeError, TypeError):
                pass  # 兼容旧格式
            
            # 校验 user_ulid 是否与本 bot 的 BOT_USER_ID 一致
            my_user_id = settings.bot.user_id
            if user_ulid and my_user_id:
                if user_ulid != my_user_id:
                    logger.debug(
                        f"跳过配置重载通知: user_ulid={user_ulid[:8]}... "
                        f"与本机 BOT_USER_ID={my_user_id[:8]}... 不匹配"
                    )
                    return
            
            logger.info(f"收到配置重载通知 (user={user_ulid[:8] + '...' if user_ulid else 'N/A'})，立即重载配置...")
            self.reload_configs()
        except Exception as e:
            logger.warning(f"处理配置重载通知失败: {e}")
    
    async def _listen_redis_grpc(self, channels: List[str], handler, name: str):
        """
        使用 gRPC 订阅 Redis channels
        
        Args:
            channels: 要订阅的 channel 列表
            handler: 消息处理函数 (channel, data) -> None
            name: 订阅名称（用于日志）
        """
        import grpc as grpc_module
        import trading_service_pb2 as pb2
        import trading_service_pb2_grpc as pb2_grpc
        
        address = f"{settings.grpc.host}:{settings.grpc.port}"
        logger.info(f"开始监听{name}通知 (gRPC: {address}, channels: {channels})")
        
        # 构造认证 metadata
        api_key_metadata = [('x-api-key', settings.api.key)] if settings.api.key else []
        
        while self.is_running:
            try:
                channel = grpc_module.insecure_channel(address)
                stub = pb2_grpc.RedisServiceStub(channel)
                
                request = pb2.SubscribeRequest(channels=channels)
                
                for message in stub.Subscribe(request, metadata=api_key_metadata):
                    if not self.is_running:
                        break
                    try:
                        await handler(message.channel, message.message)
                    except Exception as e:
                        logger.error(f"处理{name}消息错误: {e}")
                
                channel.close()
                
            except grpc_module.RpcError as e:
                if self.is_running:
                    logger.warning(f"gRPC {name}订阅断开: {e}, 5秒后重连...")
                    await asyncio.sleep(5)
            except Exception as e:
                if self.is_running:
                    logger.error(f"gRPC {name}订阅异常: {e}, 5秒后重连...")
                    await asyncio.sleep(5)

    async def _handle_close_notification(
        self, 
        symbol: str = None, 
        tracking_id: str = None
    ):
        """
        处理平仓通知，立即执行平仓
        
        Args:
            symbol: 币种（直接指定要平仓的币种）
            tracking_id: 跟单记录ID（根据跟单记录平仓）
        """
        # 确定要平仓的 symbol
        target_symbol = symbol
        state = None
        
        if tracking_id:
            state = self.trackings.get(tracking_id)
            if state is None:
                # 尝试从数据库加载
                tracking_data = self.db.get_position_tracking(tracking_id)
                if tracking_data:
                    state = self._dict_to_state(tracking_data)
                    target_symbol = state.symbol
            else:
                target_symbol = state.symbol
        
        if not target_symbol:
            logger.warning(f"[立即平仓] 未指定币种或跟单ID")
            return
        
        # 防止并发重复处理
        close_key = f"close_{target_symbol}"
        if close_key in self._processing_tracking_ids:
            logger.debug(f"[立即平仓] {target_symbol} 正在处理中，跳过")
            return
        
        self._processing_tracking_ids.add(close_key)
        try:
            # 更新自己的持仓
            if not self._update_my_account():
                logger.warning(f"[立即平仓] 获取账户信息失败，跳过")
                return
            my_pos = self.my_positions.get(target_symbol)
            
            if my_pos is None:
                logger.warning(f"[立即平仓] {target_symbol} 本地无持仓")
                return
            
            pnl = my_pos.unrealized_pnl
            
            logger.info(f"[立即平仓] {target_symbol} 当前持仓: {my_pos.size:.4f}, 未实现盈亏: ${pnl:.2f}")
            
            # 执行平仓
            order_lock = await self._get_order_lock(target_symbol)
            async with order_lock:
                try:
                    # 获取锁后重新检查仓位，防止并发重复平仓
                    if not self._update_my_account():
                        logger.warning(f"[立即平仓] 获取账户信息失败，跳过")
                        return
                    my_pos = self.my_positions.get(target_symbol)
                    if my_pos is None:
                        logger.info(f"[立即平仓] {target_symbol} 已无持仓，跳过")
                        return
                    pnl = my_pos.unrealized_pnl  # 重新获取最新 pnl
                    
                    result = self.client.close_position(target_symbol)
                    
                    if result is None:
                        logger.warning(f"[立即平仓] {target_symbol} 未找到持仓")
                        return
                    
                    if result.get('status') == 'ok':
                        logger.success(f"[立即平仓] 成功: {target_symbol}, PnL: ${pnl:.2f}")
                        
                        # 如果有关联的跟单状态，更新状态
                        if state:
                            state.status = 'closed'
                            state.my_size = 0
                            self.db.update_tracking_status(
                                state.tracking_id, 'closed', '手动平仓', pnl
                            )
                        
                        # 发送通知
                        target_address = state.target_address if state else ""
                        self._notify_copy_close(target_address, target_symbol, pnl)
                    else:
                        logger.error(f"[立即平仓] 失败: {result}")
                        
                except Exception as e:
                    logger.error(f"[立即平仓] 下单异常: {e}")
                        
        except Exception as e:
            logger.error(f"[立即平仓] 处理 {target_symbol} 失败: {e}")
        finally:
            # 处理完成，移除标记
            self._processing_tracking_ids.discard(close_key)

    def _should_notify(self, notification_key: str) -> bool:
        """
        检查是否应该发送通知（避免重复发送）
        
        Args:
            notification_key: 通知唯一标识（如 "open:BTC:long" 或 "close:BTC"）
            
        Returns:
            True 表示应该发送，False 表示应该跳过（冷却中）
        """
        import time
        now = time.time()
        last_time = self._recent_notifications.get(notification_key, 0)
        if now - last_time < self._notification_cooldown:
            logger.debug(f"跳过重复通知: {notification_key} (冷却中)")
            return False
        self._recent_notifications[notification_key] = now
        # 清理过期的通知记录（避免内存泄漏）
        expired_keys = [k for k, t in self._recent_notifications.items() if now - t > 60]
        for k in expired_keys:
            del self._recent_notifications[k]
        return True

    def _publish_notification(self, notification_data: Dict[str, Any]):
        """
        发布通知到 Redis（用于 WebSocket 推送和数据库保存）
        
        Args:
            notification_data: 通知数据，包含 type, title, content, target_address, symbol 等字段
        """
        # 添加时间戳
        notification_data['timestamp'] = pendulum.now().to_iso8601_string()
        # 添加用户ID（用于定向发送通知）
        notification_data['user_id'] = self._user_id
        
        message = json.dumps(notification_data, ensure_ascii=False)
        
        try:
            self.redis.publish(REDIS_NOTIFICATIONS_CHANNEL, message)
            logger.debug(f"通知已发布: type={notification_data.get('type')}, symbol={notification_data.get('symbol')}, user_id={self._user_id}")
        except Exception as e:
            logger.warning(f"发布通知失败: {e}")

    def _notify_copy_open(self, target_address: str, symbol: str, side: str, size: float):
        """发送开仓通知（通过 Redis 发布）"""
        # 去重检查：相同币种、方向的开仓通知在冷却时间内只发一次
        notification_key = f"open:{symbol}:{side}"
        if not self._should_notify(notification_key):
            return
        
        side_emoji = "🟢" if side.lower() == "long" else "🔴"
        side_cn = "做多" if side.lower() == "long" else "做空"
        
        # 构建 Markdown 格式内容
        content = f"**目标**: {target_address[:10]}...\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**方向**: {side_cn}\n"
        content += f"**数量**: {size}"
        
        notification_data = {
            'type': 'open',
            'title': f'{side_emoji} 复制开仓',
            'content': content,
            'target_address': target_address,
            'symbol': symbol,
            'side': side,
            'size': size,
            'pnl': None
        }
        
        self._publish_notification(notification_data)

    def _notify_copy_close(self, target_address: str, symbol: str, pnl: float):
        """发送平仓通知（通过 Redis 发布）"""
        # 去重检查：相同币种的平仓通知在冷却时间内只发一次
        notification_key = f"close:{symbol}"
        if not self._should_notify(notification_key):
            return
        
        pnl_emoji = "💰" if pnl >= 0 else "💸"
        
        # 构建 Markdown 格式内容
        content = f"**目标**: {target_address[:10]}...\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**盈亏**: ${pnl:+,.2f}"
        
        notification_data = {
            'type': 'close',
            'title': f'{pnl_emoji} 平仓',
            'content': content,
            'target_address': target_address,
            'symbol': symbol,
            'side': None,
            'size': None,
            'pnl': pnl
        }
        
        self._publish_notification(notification_data)

    def _notify_copy_adjust(self, target_address: str, symbol: str, side: str, size: float, is_increase: bool):
        """发送调整仓位通知（通过 Redis 发布）"""
        # 去重检查：相同币种、方向、加减仓类型的通知在冷却时间内只发一次
        action = "increase" if is_increase else "decrease"
        notification_key = f"adjust:{symbol}:{side}:{action}"
        if not self._should_notify(notification_key):
            return
        
        action_cn = "加仓" if is_increase else "减仓"
        action_emoji = "📈" if is_increase else "📉"
        side_cn = "做多" if side.lower() == "long" else "做空"
        
        # 构建 Markdown 格式内容
        content = f"**目标**: {target_address[:10]}...\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**方向**: {side_cn}\n"
        content += f"**数量**: {size}"
        
        notification_data = {
            'type': 'adjust',
            'title': f'{action_emoji} {action_cn}',
            'content': content,
            'target_address': target_address,
            'symbol': symbol,
            'side': side,
            'size': size,
            'pnl': None
        }
        
        self._publish_notification(notification_data)

    def _notify_error(self, error: str):
        """发送错误通知（通过 Redis 发布）"""
        # 构建 Markdown 格式内容
        content = f"**错误**: {error}"
        
        notification_data = {
            'type': 'error',
            'title': '跟单错误',
            'content': content,
            'target_address': None,
            'symbol': None,
            'side': None,
            'size': None,
            'pnl': None
        }

        self._publish_notification(notification_data)

    def _notify_max_positions_reached(self, symbol: str, current_count: int, max_count: int):
        """发送仓位数量已达上限通知（通过 Redis 发布）"""
        # 去重检查：相同币种的仓位上限通知在冷却时间内只发一次
        notification_key = f"max_positions_reached:{symbol}"
        if not self._should_notify(notification_key):
            return
        
        # 构建 Markdown 格式内容
        content = f"**币种**: {symbol}\n"
        content += f"**当前仓位数**: {current_count}\n"
        content += f"**最大限制**: {max_count}\n"
        content += "**状态**: 跳过开仓"
        
        notification_data = {
            'type': 'warning',
            'title': '⚠️ 仓位数量已达上限',
            'content': content,
            'target_address': None,
            'symbol': symbol,
            'side': None,
            'size': None,
            'pnl': None
        }

        self._publish_notification(notification_data)

    def _notify_balance_insufficient(self, action: str, required_margin: float, available_balance: float, symbol: str = ""):
        """发送余额不足通知（通过 Redis 发布）"""
        # 去重检查：相同操作的余额不足通知在冷却时间内只发一次
        notification_key = f"balance_insufficient:{symbol}:{action}" if symbol else f"balance_insufficient:{action}"
        if not self._should_notify(notification_key):
            return
        
        # 构建 Markdown 格式内容
        content = f"**币种**: {symbol}\n" if symbol else ""
        content += f"**操作**: {action}\n"
        content += f"**所需保证金**: ${required_margin:,.2f}\n"
        content += f"**可用余额**: ${available_balance:,.2f}\n"
        content += f"**缺口**: ${required_margin - available_balance:,.2f}"
        
        notification_data = {
            'type': 'error',
            'title': '余额不足',
            'content': content,
            'target_address': None,
            'symbol': symbol if symbol else None,
            'side': None,
            'size': None,
            'pnl': None
        }

        self._publish_notification(notification_data)

    @property
    def info_client(self) -> Info:
        """复用 Info 客户端"""
        if self._info_client is None:
            self._info_client = Info(self.client.api_url, skip_ws=True)
        return self._info_client

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

    async def _get_order_lock(self, symbol: str) -> Lock:
        """获取指定 symbol 的订单锁（线程安全）"""
        async with self._order_locks_lock:
            if symbol not in self._order_locks:
                self._order_locks[symbol] = Lock()
            return self._order_locks[symbol]

    # ==================== 配置加载 ====================

    def _load_trackings_from_db(self) -> List[Dict]:
        """从数据库加载启用的仓位跟单配置"""
        try:
            return self.db.get_active_position_trackings()
        except Exception as e:
            logger.error(f"加载仓位跟单配置失败: {e}")
            return []

    def _dict_to_state(self, data: Dict) -> TrackingState:
        """将数据库记录（通过 gRPC 返回的字典）转换为 TrackingState"""
        return TrackingState(
            tracking_id=data['id'],  # 现在是 ULID 字符串
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
            auto_replenish=data.get('auto_replenish', False),
            replenish_ratio=data.get('replenish_ratio', 0.5),
            replenish_min_value_usd=data.get('replenish_min_value_usd', 10.0),
            replenish_max_value_usd=data.get('replenish_max_value_usd', 100.0),
            target_initial_size=data.get('target_initial_size'),
            target_initial_side=data.get('target_initial_side'),
            target_initial_entry_price=data.get('target_initial_entry_price'),
            my_size=data.get('my_size', 0.0),
            my_side=data.get('my_side'),
            my_entry_price=data.get('my_entry_price'),
            status=data.get('status', 'pending'),
            target_is_starred=data.get('target_is_starred', False),
            target_score=data.get('target_score'),
            target_rating=data.get('target_rating'),
            position_mode=data.get('position_mode', 'cross'),
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
                state.target_current_notional = old_state.target_current_notional
                state.last_sync = old_state.last_sync
                state.last_failed_adjust_target_size = old_state.last_failed_adjust_target_size
                
                # 保留运行时状态（内存中的状态可能比数据库更新）
                # 如果内存中已经是 active/closed，不要被数据库中的 pending 覆盖
                if old_state.status in ('active', 'closed') and state.status == 'pending':
                    state.status = old_state.status
                    state.my_size = old_state.my_size
                    state.my_side = old_state.my_side
                    state.my_entry_price = old_state.my_entry_price
                
            self.trackings[tracking_id] = state
            logger.debug(f"加载仓位跟单: {state.symbol} <- {state.target_address[:10]}...")

        # 移除已删除/禁用的配置
        for tracking_id in current_ids - new_ids:
            del self.trackings[tracking_id]
            logger.info(f"移除仓位跟单: {tracking_id}")

        self.last_config_reload = pendulum.now()
        logger.info(f"仓位跟单配置加载完成: 共 {len(self.trackings)} 个")
        
        # 加载自动跟单地址配置
        self._load_address_configs()
        
        # 加载地址跟踪配置（仅监控，不交易）
        self._load_tracking_configs()

    def _load_address_configs(self):
        """从数据库加载启用的跟单地址配置（用于自动跟单）"""
        try:
            configs = self.db.get_enabled_copy_addresses(self._user_id)
            
            current_addresses = set(self.address_configs.keys())
            new_addresses = set()
            
            for data in configs:
                address = data['address']
                new_addresses.add(address)
                
                config = AddressConfig(
                    address=address,
                    name=data.get('name', ''),
                    is_enabled=data.get('is_enabled', True),
                    copy_ratio=data.get('copy_ratio', 0.1),
                    max_position_size_usd=data.get('max_position_size_usd', 500.0),
                    min_position_size_usd=data.get('min_position_size_usd', 20.0),
                    copy_leverage=data.get('copy_leverage', True),
                    max_leverage=data.get('max_leverage', 10),
                    default_leverage=data.get('default_leverage', 5),
                    slippage=data.get('slippage', 0.01),
                    copy_once=data.get('copy_once', False),
                    auto_replenish=data.get('auto_replenish', False),
                    replenish_ratio=data.get('replenish_ratio', 0.5),
                    replenish_min_value_usd=data.get('replenish_min_value_usd', 10.0),
                    replenish_max_value_usd=data.get('replenish_max_value_usd', 100.0),
                    symbols_whitelist=data.get('symbols_whitelist', []) or [],
                    symbols_blacklist=data.get('symbols_blacklist', []) or []
                )
                
                self.address_configs[address] = config
                logger.debug(f"加载自动跟单地址: {address[:10]}... ({config.name})")
            
            # 移除已删除/禁用的配置
            for address in current_addresses - new_addresses:
                del self.address_configs[address]
                # 同时清理仓位缓存
                if address in self._address_positions:
                    del self._address_positions[address]
                logger.info(f"移除自动跟单地址: {address[:10]}...")
            
            if self.address_configs:
                logger.info(f"自动跟单地址配置加载完成: 共 {len(self.address_configs)} 个")
            
        except Exception as e:
            logger.error(f"加载自动跟单地址配置失败: {e}")

    def _load_tracking_configs(self):
        """
        从 Redis 加载启用的地址跟踪配置（仅监控，不交易）
        
        通过 gRPC 读取 Redis 中由 API 服务器缓存的配置
        """
        try:
            configs = self.db.get_enabled_address_trackings(self._user_id)
            
            current_addresses = set(self.tracking_configs.keys())
            new_addresses = set()
            
            for data in configs:
                address = data.get('tracking_address', '')
                if not address:
                    continue
                
                new_addresses.add(address)
                
                config = AddressTrackingConfig(
                    id=data.get('id', 0),
                    tracking_address=address,
                    address_remark=data.get('address_remark', ''),
                    monitor_events=data.get('monitor_events', ['open', 'close', 'add', 'reduce']),
                    is_enabled=data.get('is_enabled', True),
                    enable_notification=data.get('enable_notification', True),
                )
                
                self.tracking_configs[address] = config
                logger.debug(f"加载地址跟踪: {address[:10]}... ({config.address_remark})")
            
            # 移除已删除/禁用的配置
            for address in current_addresses - new_addresses:
                del self.tracking_configs[address]
                if address in self._tracked_positions:
                    del self._tracked_positions[address]
                logger.info(f"移除地址跟踪: {address[:10]}...")
            
            if self.tracking_configs:
                logger.info(f"地址跟踪配置加载完成: 共 {len(self.tracking_configs)} 个")
            
        except Exception as e:
            logger.error(f"加载地址跟踪配置失败: {e}")

    # ==================== 自动跟单 ====================

    def _should_copy_symbol(self, config: AddressConfig, symbol: str) -> bool:
        """
        根据白名单/黑名单判断是否应该跟单该币种
        
        Args:
            config: 地址配置
            symbol: 币种符号
            
        Returns:
            是否应该跟单
        """
        # 黑名单优先：在黑名单中则不跟
        if symbol in config.symbols_blacklist:
            return False
        
        # 白名单为空表示不限制，否则必须在白名单中
        if config.symbols_whitelist:
            return symbol in config.symbols_whitelist
        
        return True

    def _detect_new_positions(
        self,
        address: str,
        old_positions: Dict[str, Dict],
        new_positions: Dict[str, Dict]
    ) -> List[Dict]:
        """
        检测新开的仓位
        
        Args:
            address: 交易员地址
            old_positions: 上次缓存的仓位 {symbol: position_dict}
            new_positions: 当前的仓位 {symbol: position_dict}
            
        Returns:
            新仓位列表
        """
        old_symbols = set(old_positions.keys())
        new_symbols = set(new_positions.keys())
        
        # 新出现的币种就是新仓位
        new_coin_set = new_symbols - old_symbols
        
        new_positions_list = []
        for symbol in new_coin_set:
            pos = new_positions[symbol]
            new_positions_list.append(pos)
            
        return new_positions_list

    def _auto_create_tracking(
        self,
        config: AddressConfig,
        position: Dict
    ) -> Optional[int]:
        """
        自动创建跟单记录
        
        Args:
            config: 地址配置
            position: 目标仓位信息
            
        Returns:
            创建的 tracking_id，如果创建失败或已存在则返回 None
        """
        symbol = position['symbol']
        address = config.address
        
        # 检查是否已存在活跃的跟单记录
        if self.db.check_position_tracking_exists(address, symbol):
            logger.debug(f"[自动跟单] 跳过 {symbol}: 已有活跃跟单记录")
            return None
        
        # 使用公共方法创建跟单记录
        tracking_data = build_tracking_data_from_dataclass(
            config_obj=config,
            target_address=address,
            symbol=symbol,
            target_position=position,
            target_is_starred=False,
            status='pending'
        )
        
        try:
            tracking_id = self.db.save_position_tracking(tracking_data)
            
            if tracking_id:
                side = position.get('side', 'unknown')
                logger.success(
                    f"[自动跟单] 创建跟单记录: {symbol} {side} "
                    f"(tracking_id={tracking_id}, 来自 {config.name or address[:10]}...)"
                )
                
                # 发送 Redis 通知触发开仓
                try:
                    self.redis.publish(REDIS_OPEN_CHANNEL, str(tracking_id))
                    logger.info(f"[自动跟单] 已发送开仓通知 (tracking_id={tracking_id})")
                except Exception as e:
                    logger.warning(f"[自动跟单] Redis 开仓通知发送失败: {e}")
                
                return tracking_id
            else:
                logger.error(f"[自动跟单] 创建跟单记录失败: {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"[自动跟单] 创建跟单记录异常: {symbol} - {e}")
            return None

    async def _sync_auto_copy(self, target_positions_cache: Dict[str, Dict[str, Dict]]):
        """
        自动跟单主循环

        检测配置地址的新仓位，根据白名单/黑名单筛选后自动创建跟单
        """
        if not self.address_configs:
            return

        new_trackings_count = 0

        for address, config in self.address_configs.items():
            if not config.is_enabled:
                continue

            try:
                # 获取当前仓位（从缓存中获取）
                current_positions = target_positions_cache.get(address, {})
                
                # 获取上次缓存的仓位
                old_positions = self._address_positions.get(address, {})
                
                # 检测新仓位
                new_positions = self._detect_new_positions(address, old_positions, current_positions)
                
                for position in new_positions:
                    symbol = position['symbol']
                    
                    # 检查白名单/黑名单
                    if not self._should_copy_symbol(config, symbol):
                        logger.debug(
                            f"[自动跟单] 跳过 {symbol}: 不在白名单或在黑名单中 "
                            f"(白名单: {config.symbols_whitelist}, 黑名单: {config.symbols_blacklist})"
                        )
                        continue
                    
                    # 创建跟单记录
                    tracking_id = self._auto_create_tracking(config, position)
                    if tracking_id:
                        new_trackings_count += 1
                    
                    # 只跟一次：不管跟单成功还是失败都自动禁用该地址
                    if config.copy_once:
                        result_text = f"跟单{'成功' if tracking_id else '失败'}"
                        logger.info(
                            f"[自动跟单] 只跟一次模式: {symbol} {result_text}，自动禁用地址 "
                            f"{address[:10]}... ({config.name})"
                        )
                        self.db.toggle_copy_trading_address(self._user_id, address, False)
                        config.is_enabled = False
                        break  # 跳出当前地址的仓位循环
                
                # 更新仓位缓存
                self._address_positions[address] = current_positions
                
            except Exception as e:
                logger.error(f"[自动跟单] 检测 {address[:10]}... 新仓位失败: {e}")
        
        if new_trackings_count > 0:
            logger.info(f"[自动跟单] 本轮创建了 {new_trackings_count} 个新跟单")
            # 重载配置以加载新创建的跟单
            self.reload_configs()

    # ==================== 地址跟踪监控 ====================

    async def _sync_address_tracking(self, target_positions_cache: Dict[str, Dict[str, Dict]]):
        """
        地址跟踪主循环

        检测被跟踪地址的仓位变化（开仓、平仓、加仓、减仓），
        并通过 Redis 发送通知给对应用户
        """
        if not self.tracking_configs:
            return

        for address, config in self.tracking_configs.items():
            if not config.is_enabled or not config.enable_notification:
                continue

            try:
                # 获取当前仓位（从缓存中获取）
                current_positions = target_positions_cache.get(address, {})
                
                # 获取上次缓存的仓位
                old_positions = self._tracked_positions.get(address, {})
                
                # 检测仓位变化并发送通知
                self._detect_and_notify_tracking_changes(config, old_positions, current_positions)
                
                # 更新仓位缓存
                self._tracked_positions[address] = current_positions
                
            except Exception as e:
                logger.error(f"[地址跟踪] 检测 {address[:10]}... 仓位变化失败: {e}")

    def _detect_and_notify_tracking_changes(
        self,
        config: AddressTrackingConfig,
        old_positions: Dict[str, Dict],
        new_positions: Dict[str, Dict]
    ):
        """
        检测仓位变化并发送跟踪通知
        
        Args:
            config: 跟踪配置
            old_positions: 上次的仓位快照 {symbol: position_dict}
            new_positions: 当前的仓位 {symbol: position_dict}
        """
        address = config.tracking_address
        remark = config.address_remark or address[:10] + '...'
        monitor_events = set(config.monitor_events)
        
        old_symbols = set(old_positions.keys())
        new_symbols = set(new_positions.keys())
        
        # 1. 新开仓：新出现的币种
        if 'open' in monitor_events:
            for symbol in new_symbols - old_symbols:
                pos = new_positions[symbol]
                self._notify_tracking_open(address, remark, symbol, pos)
        
        # 2. 平仓：消失的币种
        if 'close' in monitor_events:
            for symbol in old_symbols - new_symbols:
                old_pos = old_positions[symbol]
                self._notify_tracking_close(address, remark, symbol, old_pos)
        
        # 3. 加仓/减仓：仍存在的币种，但仓位大小变化
        for symbol in old_symbols & new_symbols:
            old_pos = old_positions[symbol]
            new_pos = new_positions[symbol]
            
            old_size = abs(old_pos.get('size', 0))
            new_size = abs(new_pos.get('size', 0))
            
            # 忽略微小变化（< 1%）
            if old_size > 0 and abs(new_size - old_size) / old_size < 0.01:
                continue
            
            if new_size > old_size and 'add' in monitor_events:
                self._notify_tracking_add(address, remark, symbol, new_pos, new_size - old_size)
            elif new_size < old_size and 'reduce' in monitor_events:
                self._notify_tracking_reduce(address, remark, symbol, new_pos, old_size - new_size)

    def _notify_tracking_open(self, address: str, remark: str, symbol: str, pos: Dict):
        """发送跟踪开仓通知"""
        notification_key = f"tracking_open:{address}:{symbol}"
        if not self._should_notify(notification_key):
            return
        
        side = pos.get('side', 'unknown')
        side_cn = "做多" if side == 'long' else "做空"
        size = abs(pos.get('size', 0))
        
        content = f"**跟踪地址**: {remark}\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**方向**: {side_cn}\n"
        content += f"**数量**: {size}"
        
        self._publish_notification({
            'type': 'tracking_open',
            'title': f'🔔 [{remark}] 新开仓 {symbol}',
            'content': content,
            'target_address': address,
            'symbol': symbol,
            'side': side,
            'size': size,
            'pnl': None,
        })

    def _notify_tracking_close(self, address: str, remark: str, symbol: str, old_pos: Dict):
        """发送跟踪平仓通知"""
        notification_key = f"tracking_close:{address}:{symbol}"
        if not self._should_notify(notification_key):
            return
        
        side = old_pos.get('side', 'unknown')
        side_cn = "做多" if side == 'long' else "做空"
        
        content = f"**跟踪地址**: {remark}\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**方向**: {side_cn}\n"
        content += f"**已全部平仓**"
        
        self._publish_notification({
            'type': 'tracking_close',
            'title': f'🔕 [{remark}] 平仓 {symbol}',
            'content': content,
            'target_address': address,
            'symbol': symbol,
            'side': side,
            'size': None,
            'pnl': None,
        })

    def _notify_tracking_add(self, address: str, remark: str, symbol: str, pos: Dict, added_size: float):
        """发送跟踪加仓通知"""
        notification_key = f"tracking_add:{address}:{symbol}"
        if not self._should_notify(notification_key):
            return
        
        side = pos.get('side', 'unknown')
        side_cn = "做多" if side == 'long' else "做空"
        total_size = abs(pos.get('size', 0))
        
        content = f"**跟踪地址**: {remark}\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**方向**: {side_cn}\n"
        content += f"**加仓数量**: +{added_size:.4f}\n"
        content += f"**当前总量**: {total_size}"
        
        self._publish_notification({
            'type': 'tracking_add',
            'title': f'📈 [{remark}] 加仓 {symbol}',
            'content': content,
            'target_address': address,
            'symbol': symbol,
            'side': side,
            'size': total_size,
            'pnl': None,
        })

    def _notify_tracking_reduce(self, address: str, remark: str, symbol: str, pos: Dict, reduced_size: float):
        """发送跟踪减仓通知"""
        notification_key = f"tracking_reduce:{address}:{symbol}"
        if not self._should_notify(notification_key):
            return
        
        side = pos.get('side', 'unknown')
        side_cn = "做多" if side == 'long' else "做空"
        total_size = abs(pos.get('size', 0))
        
        content = f"**跟踪地址**: {remark}\n"
        content += f"**交易对**: {symbol}\n"
        content += f"**方向**: {side_cn}\n"
        content += f"**减仓数量**: -{reduced_size:.4f}\n"
        content += f"**当前总量**: {total_size}"
        
        self._publish_notification({
            'type': 'tracking_reduce',
            'title': f'📉 [{remark}] 减仓 {symbol}',
            'content': content,
            'target_address': address,
            'symbol': symbol,
            'side': side,
            'size': total_size,
            'pnl': None,
        })

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

    def _get_target_positions(self, address: str) -> Dict[str, Dict]:
        """获取目标交易者的所有仓位，返回 {symbol: position_dict}"""
        try:
            state = self.info_client.user_state(address)
            positions = {}
            for pos_data in state.get('assetPositions', []):
                pos = pos_data.get('position', {})
                symbol = pos.get('coin', '')
                size = float(pos.get('szi', 0))
                if size != 0 and symbol:
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

    def _update_my_account(self) -> bool:
        """
        更新自己的持仓和余额（单次 API 调用），并缓存到 Redis
        
        Returns:
            是否更新成功
        """
        try:
            account_info = self.client.get_account_info()
            # 更新余额
            self.available_balance = account_info.available_margin
            # 更新持仓
            self.my_positions = {pos.symbol: pos for pos in account_info.positions}
            logger.debug(f"账户可用余额: {self.available_balance:.2f} USD, 持仓数: {len(self.my_positions)}")
            
            # 写入 Redis 缓存（供外部使用）
            try:
                # 序列化仓位数据
                positions_data = []
                for pos in account_info.positions:
                    positions_data.append({
                        'symbol': pos.symbol,
                        'side': pos.side.value,
                        'size': pos.size,
                        'entry_price': pos.entry_price,
                        'current_price': pos.current_price,
                        'leverage': pos.leverage,
                        'unrealized_pnl': pos.unrealized_pnl,
                        'liquidation_price': pos.liquidation_price,
                        'margin_used': pos.margin_used,
                    })
                
                # 写入 Redis（设置 60 秒过期，防止数据过期）
                self.redis.setex(REDIS_MY_POSITIONS_KEY, 60, json.dumps(positions_data))
                self.redis.setex(REDIS_MY_BALANCE_KEY, 60, str(self.available_balance))
            except Exception as e:
                logger.debug(f"写入 Redis 缓存失败: {e}")
            return True
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            return False

    def _check_balance_sufficient(self, required_margin: float, action: str = "开仓", symbol: str = "") -> bool:
        """
        检查余额是否足够
        
        Args:
            required_margin: 所需保证金
            action: 操作类型（用于日志）
            symbol: 币种（用于日志）
            
        Returns:
            余额是否足够
        """
        if self.available_balance < required_margin:
            symbol_info = f"[{symbol}] " if symbol else ""
            logger.warning(
                f"{symbol_info}余额不足，无法{action}: 需要 {required_margin:.2f} USD, "
                f"可用 {self.available_balance:.2f} USD"
            )
            # 发送余额不足通知
            self._notify_balance_insufficient(action, required_margin, self.available_balance, symbol)
            return False
        return True

    # ==================== 仓位计算 ====================

    def _calculate_copy_size(
        self,
        state: TrackingState,
        target_notional: float,
        current_price: float,
        is_opening: bool = True
    ) -> float:
        """
        计算跟单仓位大小
        
        Args:
            state: 跟单状态
            target_notional: 目标的 notional 价值
            current_price: 当前价格
            is_opening: 是否是开仓操作（开仓时应用 max_position_size_usd 限制，补仓时不限制）
        """
        copy_notional = target_notional * state.copy_ratio
        copy_notional = max(copy_notional, state.min_position_size_usd)
        
        # 只在开仓时应用最大仓位限制，补仓时不限制
        if is_opening:
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
        symbol = state.symbol
        
        # 检查仓位数量是否已达上限
        if self.max_positions > 0:
            current_position_count = len(self.my_positions)
            # 如果当前币种已有仓位，不计入新开仓检查
            if symbol not in self.my_positions and current_position_count >= self.max_positions:
                logger.warning(
                    f"[{state.tracking_id}] 仓位数量已达上限 ({current_position_count}/{self.max_positions})，"
                    f"跳过开仓: {symbol}"
                )
                self._notify_max_positions_reached(symbol, current_position_count, self.max_positions)
                return False
        
        order_lock = await self._get_order_lock(symbol)
        async with order_lock:
            # 获取锁后重新检查状态，防止并发重复开仓
            if state.status == 'active':
                logger.debug(f"[{state.tracking_id}] 状态已为 active，跳过开仓")
                return False
            
            # 重新获取持仓信息，检查是否已有仓位
            if not self._update_my_account():
                logger.warning(f"[{state.tracking_id}] 获取账户信息失败，跳过开仓")
                return False
            
            # 获取锁后再次检查仓位数量（防止并发开仓超限）
            if self.max_positions > 0:
                current_position_count = len(self.my_positions)
                if symbol not in self.my_positions and current_position_count >= self.max_positions:
                    logger.warning(
                        f"[{state.tracking_id}] 仓位数量已达上限 ({current_position_count}/{self.max_positions})，"
                        f"跳过开仓: {symbol}"
                    )
                    self._notify_max_positions_reached(symbol, current_position_count, self.max_positions)
                    return False
            
            my_pos = self.my_positions.get(symbol)
            if my_pos is not None:
                existing_is_long = my_pos.side == PositionSide.LONG
                # 检查方向是否一致
                if existing_is_long == is_long:
                    logger.info(f"[{state.tracking_id}] 已有同向仓位 {symbol}，跳过开仓")
                    # 更新状态为 active（防止重复处理）
                    state.status = 'active'
                    state.my_size = abs(my_pos.size)
                    state.my_side = 'long' if existing_is_long else 'short'
                    state.my_entry_price = my_pos.entry_price
                    # 记录目标的 notional，用于后续判断是否需要减仓
                    state.target_current_notional = target_position.get('notional')
                    self.db.update_tracking_status(state.tracking_id, 'active')
                    self.db.update_tracking_position(
                        state.tracking_id, state.my_size, state.my_side, state.my_entry_price
                    )
                    return True  # 返回 True，仓位已存在算作成功
                else:
                    logger.warning(f"[{state.tracking_id}] 已有反向仓位 {symbol}，无法开仓")
                    return False  # 方向不一致，真正的失败
            
            side = 'long' if is_long else 'short'
            price = self.client.get_mid_price(symbol)
            
            # 检查余额是否足够
            notional_value = size * price
            required_margin = notional_value / leverage
            if not self._check_balance_sufficient(required_margin, "开仓", symbol):
                return False

            try:
                # 设置杠杆
                is_cross = state.position_mode != 'isolated'
                self.client.set_leverage(symbol, leverage, is_cross=is_cross)
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
                    # 记录目标的 notional，用于后续判断是否需要减仓
                    state.target_current_notional = target_position.get('notional')
                    
                    # 更新数据库
                    self.db.update_tracking_status(state.tracking_id, 'active')
                    self.db.update_tracking_position(
                        state.tracking_id, size, side, price
                    )
                    
                    # 发送通知
                    self._notify_copy_open(state.target_address, symbol, side, size)
                    return True
                else:
                    logger.error(f"[{state.tracking_id}] 开仓失败: {result}")
                    return False

            except Exception as e:
                logger.error(f"[{state.tracking_id}] 开仓异常: {e}")
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
        
        order_lock = await self._get_order_lock(symbol)
        async with order_lock:
            # 获取锁后重新获取持仓信息，防止并发重复调整
            if not self._update_my_account():
                logger.warning(f"[{state.tracking_id}] 获取账户信息失败，跳过调仓")
                return False
            my_pos = self.my_positions.get(symbol)

            if my_pos is None:
                logger.warning(f"[{state.tracking_id}] 无法调整仓位: {symbol} (本地无持仓)")
                return False

            # 计算目标仓位
            current_price = self.client.get_mid_price(symbol)
            target_notional = target_position['notional']
            prev_target_notional = state.target_current_notional
            my_current_size = abs(my_pos.size)
            my_current_notional = my_current_size * current_price
            
            # 检测目标是否在加仓（notional 增加）
            target_is_increasing = prev_target_notional is not None and target_notional > prev_target_notional
            target_notional_increase = target_notional - prev_target_notional if target_is_increasing else 0
            
            # 自动补仓逻辑：当目标加仓且启用了自动补仓
            if target_is_increasing and state.auto_replenish:
                # 按目标加仓量的比例计算补仓金额
                replenish_value = target_notional_increase * state.replenish_ratio
                
                # 限制在配置的范围内
                if replenish_value < state.replenish_min_value_usd:
                    logger.debug(
                        f"[{state.tracking_id}] [{symbol}] 自动补仓: 计算补仓金额 ${replenish_value:.2f} "
                        f"< 最小限制 ${state.replenish_min_value_usd:.2f}，跳过"
                    )
                    state.target_current_notional = target_notional
                    return True
                
                if replenish_value > state.replenish_max_value_usd:
                    logger.info(
                        f"[{state.tracking_id}] [{symbol}] 自动补仓: 计算补仓金额 ${replenish_value:.2f} "
                        f"> 最大限制 ${state.replenish_max_value_usd:.2f}，限制为 ${state.replenish_max_value_usd:.2f}"
                    )
                    replenish_value = state.replenish_max_value_usd
                
                adjustment_size = self._round_size(symbol, replenish_value / current_price)
                adjustment_value = adjustment_size * current_price
                
                logger.info(
                    f"[{state.tracking_id}] [{symbol}] 自动补仓: 目标加仓 ${target_notional_increase:.2f} "
                    f"(ratio={state.replenish_ratio:.0%})，补仓 ${adjustment_value:.2f}"
                )
                
                is_increase = True
                action_type = "自动补仓"
                my_target_size = my_current_size + adjustment_size
            else:
                # 原有逻辑：按 copy_ratio 计算目标仓位
                my_target_size = self._calculate_copy_size(
                    state, target_notional, current_price, is_opening=False
                )
                
                # 判断是加仓还是减仓
                is_increase = my_target_size > my_current_size
                
                # 如果需要减仓，检查目标交易员是否真的减仓了
                # 避免因为手动补仓超过 max_position_size_usd 而被自动减仓
                if not is_increase:
                    if prev_target_notional is not None and target_notional >= prev_target_notional:
                        # 目标交易员没有减仓（notional 没有减少），但本地仓位超过了计算的目标
                        # 这通常是因为手动补仓超过了 max_position_size_usd，不应自动减仓
                        logger.debug(
                            f"[{state.tracking_id}] [{symbol}] 本地仓位 ${my_current_notional:.2f} "
                            f"超过计算目标 ${my_target_size * current_price:.2f}，但目标未减仓 "
                            f"(notional: {prev_target_notional:.2f} -> {target_notional:.2f})，跳过自动减仓"
                        )
                        # 更新目标 notional 记录
                        state.target_current_notional = target_notional
                        return True
                
                adjustment_size = abs(my_target_size - my_current_size)
                adjustment_size = self._round_size(symbol, adjustment_size)
                
                # 检查调整价值
                adjustment_value = adjustment_size * current_price
                action_type = "加仓" if is_increase else "减仓"
                
                # 加仓时限制单次补仓价值不超过 max_position_size_usd
                if is_increase and adjustment_value > state.max_position_size_usd:
                    logger.info(
                        f"[{state.tracking_id}] [{symbol}] 补仓价值 ${adjustment_value:.2f} "
                        f"超过限制 ${state.max_position_size_usd:.2f}，限制为 ${state.max_position_size_usd:.2f}"
                    )
                    adjustment_value = state.max_position_size_usd
                    adjustment_size = self._round_size(symbol, adjustment_value / current_price)
                    my_target_size = my_current_size + adjustment_size
            
            # 更新目标 notional 记录
            state.target_current_notional = target_notional
            
            # 检查调整价值是否太小（小于10 USD则跳过）
            if adjustment_value < 10:
                msg = f"[{symbol}] {action_type}调整价值 ${adjustment_value:.2f} < $10，跳过调整"
                logger.debug(f"[{state.tracking_id}] {msg}")
                return True

            is_long = my_pos.side == PositionSide.LONG
            
            # 加仓时检查余额是否足够
            if is_increase:
                notional_value = adjustment_size * current_price
                # 获取当前仓位的杠杆
                leverage = my_pos.leverage if my_pos.leverage else state.default_leverage
                required_margin = notional_value / leverage
                if not self._check_balance_sufficient(required_margin, action_type, symbol):
                    return False

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
                    
                    # 发送通知
                    side = 'long' if is_long else 'short'
                    self._notify_copy_adjust(state.target_address, symbol, side, adjustment_size, is_increase)
                    return True
                else:
                    logger.error(f"[{state.tracking_id}] {action_type}失败: {result}")
                    return False

            except Exception as e:
                logger.error(f"[{state.tracking_id}] {action_type}异常: {e}")
                return False

    async def _close_position(
        self,
        state: TrackingState,
        reason: str = "目标平仓"
    ) -> bool:
        """平仓"""
        symbol = state.symbol
        order_lock = await self._get_order_lock(symbol)
        async with order_lock:
            # 获取锁后重新检查状态，防止并发重复平仓
            if state.status == 'closed':
                logger.debug(f"[{state.tracking_id}] 状态已为 closed，跳过平仓")
                return False
            
            # 重新获取持仓信息
            if not self._update_my_account():
                logger.warning(f"[{state.tracking_id}] 获取账户信息失败，跳过平仓")
                return False
            my_pos = self.my_positions.get(symbol)
            
            # 如果已经没有仓位，直接标记为关闭（不发送通知，因为可能已经发过了）
            if my_pos is None:
                logger.info(f"[{state.tracking_id}] 平仓 {symbol}: 已无持仓，仅更新状态")
                state.status = 'closed'
                state.my_size = 0
                self.db.update_tracking_status(
                    state.tracking_id, 'closed', reason, 0
                )
                return True  # 返回 True，目标已达成（无需平仓）
            
            pnl = my_pos.unrealized_pnl

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
                    
                    # 发送通知
                    self._notify_copy_close(state.target_address, symbol, pnl)
                    return True
                else:
                    logger.error(f"[{state.tracking_id}] 平仓失败: {result}")
                    return False

            except Exception as e:
                logger.error(f"[{state.tracking_id}] 平仓异常: {e}")
                return False

    # ==================== 同步逻辑 ====================

    async def _sync_tracking(self, state: TrackingState, target_positions_cache: Dict[str, Dict[str, Dict]] = None):
        """同步单个仓位跟单"""
        symbol = state.symbol
        target_address = state.target_address
        
        # 如果正在被 Redis 通知处理，跳过（检查所有相关的 key）
        if state.tracking_id in self._processing_tracking_ids:
            return
        if f"adjust_{state.tracking_id}" in self._processing_tracking_ids:
            return
        if f"close_{symbol}" in self._processing_tracking_ids:
            return
        
        # 获取目标仓位（优先使用缓存）
        if target_positions_cache and target_address in target_positions_cache:
            target_pos = target_positions_cache[target_address].get(symbol)
        else:
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
                state.target_current_notional = target_pos.get('notional')
                
                # 保存初始快照到数据库（保留原有配置参数，避免被默认值覆盖）
                self.db.save_position_tracking({
                    'id': state.tracking_id,
                    'target_address': state.target_address,
                    'target_name': state.target_name,
                    'symbol': state.symbol,
                    'is_enabled': True,  # 进入同步逻辑的都是启用状态
                    'copy_ratio': state.copy_ratio,
                    'max_position_size_usd': state.max_position_size_usd,
                    'min_position_size_usd': state.min_position_size_usd,
                    'copy_leverage': state.copy_leverage,
                    'max_leverage': state.max_leverage,
                    'default_leverage': state.default_leverage,
                    'slippage': state.slippage,
                    'target_initial_size': state.target_initial_size,
                    'target_initial_side': state.target_initial_side,
                    'target_initial_entry_price': state.target_initial_entry_price,
                    'target_initial_leverage': target_pos.get('leverage'),
                    'target_is_starred': state.target_is_starred,
                    'target_score': state.target_score,
                    'target_rating': state.target_rating,
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
                    # 记录目标的 notional，用于后续判断是否需要减仓
                    state.target_current_notional = target_pos.get('notional')
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
            # 检查我方仓位是否已不存在（可能被手动平仓或止损）
            if my_pos is None:
                logger.warning(f"[{state.tracking_id}] [{symbol}] 跟单状态为 active 但本地无持仓，标记为 closed")
                state.status = 'closed'
                self.db.update_tracking_status(state.tracking_id, 'closed', '本地仓位已不存在')
                return
            
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
                    # 检查是否和上次失败时的目标仓位一样（避免重复尝试）
                    if (state.last_failed_adjust_target_size is not None and 
                        abs(new_size - state.last_failed_adjust_target_size) < 0.0001):
                        logger.debug(f"[{state.tracking_id}] 目标仓位未变化，跳过补仓重试")
                    else:
                        success = await self._adjust_position(state, target_pos)
                        if success:
                            # 补仓成功，清除失败记录
                            state.last_failed_adjust_target_size = None
                        else:
                            # 补仓失败，记录当前目标仓位大小
                            state.last_failed_adjust_target_size = new_size
        
        state.last_sync = pendulum.now()

    async def _sync_all_trackings(self, target_positions_cache: Dict[str, Dict[str, Dict]]):
        """同步所有仓位跟单"""
        async with self._sync_lock:
            # 过滤出活跃的跟单
            active_trackings = [
                s for s in self.trackings.values()
                if s.status in ('pending', 'active')
            ]

            # 异步并行同步所有仓位
            async def sync_with_error_handling(state):
                try:
                    await self._sync_tracking(state, target_positions_cache)
                except Exception as e:
                    logger.error(f"同步仓位跟单 {state.tracking_id} 失败: {e}")

            await asyncio.gather(*[
                sync_with_error_handling(state) for state in active_trackings
            ])

    # ==================== 运行控制 ====================

    async def run(self):
        """运行仓位跟单机器人"""
        self.is_running = True

        logger.info("=" * 60)
        logger.info("仓位级别跟单机器人启动")
        logger.info(f"检查间隔: {self.check_interval}秒")
        logger.info(f"配置重载间隔: {self.reload_interval}秒")
        logger.info(f"自动跟单用户ID: {self._user_id}")
        logger.info("=" * 60)

        # 加载初始配置
        self.reload_configs()

        if not self.trackings and not self.address_configs and not self.tracking_configs:
            logger.warning("没有启用的仓位跟单、自动跟单地址和地址跟踪，等待添加...")
        else:
            if self.trackings:
                logger.info(f"已加载 {len(self.trackings)} 个手动跟单")
            if self.address_configs:
                logger.info(f"已加载 {len(self.address_configs)} 个自动跟单地址")
            if self.tracking_configs:
                logger.info(f"已加载 {len(self.tracking_configs)} 个地址跟踪")

        # 启动 Redis 通知监听任务
        redis_open_task = asyncio.create_task(self._listen_redis_open())
        redis_adjust_task = asyncio.create_task(self._listen_redis_adjust())
        redis_close_task = asyncio.create_task(self._listen_redis_close())
        redis_config_reload_task = asyncio.create_task(self._listen_redis_config_reload())

        try:
            while self.is_running:
                try:
                    # 定时重载配置
                    if (self.last_config_reload is None or
                        (pendulum.now() - self.last_config_reload).total_seconds() >= self.reload_interval):
                        self.reload_configs()

                    # 同步现有跟单
                    # 更新自己的持仓和余额
                    if not self._update_my_account():
                        logger.warning("获取账户信息失败，跳过本轮同步")
                        await asyncio.sleep(self.check_interval)
                        continue

                    # 收集所有需要获取仓位的目标地址
                    all_target_addresses: set = set()
                    if self.trackings:
                        all_target_addresses.update(
                            s.target_address for s in self.trackings.values()
                            if s.status in ('pending', 'active')
                        )
                    if self.address_configs:
                        all_target_addresses.update(
                            addr for addr, cfg in self.address_configs.items() if cfg.is_enabled
                        )
                    if self.tracking_configs:
                        all_target_addresses.update(
                            addr for addr, cfg in self.tracking_configs.items()
                            if cfg.is_enabled and cfg.enable_notification
                        )

                    # 每个地址只获取一次仓位
                    target_positions_cache: Dict[str, Dict[str, Dict]] = {}
                    for address in all_target_addresses:
                        target_positions_cache[address] = self._get_target_positions(address)

                    # 同步
                    if self.trackings:
                        await self._sync_all_trackings(target_positions_cache)
                    if self.address_configs:
                        await self._sync_auto_copy(target_positions_cache)
                    if self.tracking_configs:
                        await self._sync_address_tracking(target_positions_cache)

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"同步时遇到错误，将在下一周期重试: {e}")

                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("仓位跟单机器人被取消")
        finally:
            self.is_running = False
            # 清理 Redis 任务
            for task in [redis_open_task, redis_adjust_task, redis_close_task, redis_config_reload_task]:
                if task:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
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
            'available_balance': self.available_balance,
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
