"""
gRPC 客户端

为 trading 服务提供数据库和 Redis 操作的 gRPC 客户端
替代直接的数据库和 Redis 连接
"""
import sys
import os
import json
import asyncio
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import grpc
from loguru import logger

import trading_service_pb2 as pb2
import trading_service_pb2_grpc as pb2_grpc


class GRPCDatabaseClient:
    """数据库 gRPC 客户端"""
    
    def __init__(self, host: str = 'localhost', port: int = 50051, api_key: str = ''):
        """
        初始化数据库客户端
        
        Args:
            host: gRPC 服务器地址
            port: gRPC 服务器端口
            api_key: API Key（用于 gRPC 认证）
        """
        self._address = f'{host}:{port}'
        self._api_key = api_key
        self._channel = None
        self._stub = None
    
    def _get_metadata(self):
        """获取携带 API Key 的 metadata"""
        if self._api_key:
            return [('x-api-key', self._api_key)]
        return []
    
    def _ensure_connected(self):
        """确保已连接"""
        if self._channel is None:
            self._channel = grpc.insecure_channel(self._address)
            self._stub = pb2_grpc.DatabaseServiceStub(self._channel)
    
    def close(self):
        """关闭连接"""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
    
    def _tracking_to_dict(self, tracking: pb2.PositionTracking) -> Dict:
        """将 proto 消息转换为字典"""
        return {
            'id': tracking.id,
            'target_address': tracking.target_address,
            'symbol': tracking.symbol,
            'target_side': tracking.target_side,
            'copy_ratio': tracking.copy_ratio,
            'max_position_size': tracking.max_position_size,
            'max_position_size_usd': tracking.max_position_size,  # 兼容字段名
            'slippage': tracking.slippage,
            'is_enabled': tracking.is_enabled,
            'status': tracking.status,
            'my_size': tracking.my_size if tracking.my_size else None,
            'my_side': tracking.my_side if tracking.my_side else None,
            'my_entry_price': tracking.my_entry_price if tracking.my_entry_price else None,
            'user_id': tracking.user_id if tracking.user_id else None,
            'address_id': tracking.address_id if tracking.address_id else None,
            'target_entry_price': tracking.target_entry_price if tracking.target_entry_price else None,
            'target_size': tracking.target_size if tracking.target_size else None,
            'nickname': tracking.nickname if tracking.nickname else None,
            'target_name': tracking.target_name if tracking.target_name else tracking.nickname if tracking.nickname else None,
            'created_at': tracking.created_at if tracking.created_at else None,
            'updated_at': tracking.updated_at if tracking.updated_at else None,
            'close_reason': tracking.close_reason if tracking.close_reason else None,
            'closed_pnl': tracking.closed_pnl if tracking.closed_pnl else None,
            # 自动补仓配置
            'auto_replenish': tracking.auto_replenish,
            'replenish_ratio': tracking.replenish_ratio if tracking.replenish_ratio else 0.5,
            'replenish_min_value_usd': tracking.replenish_min_value_usd if tracking.replenish_min_value_usd else 10.0,
            'replenish_max_value_usd': tracking.replenish_max_value_usd if tracking.replenish_max_value_usd else 100.0,
            # 其他配置
            'min_position_size': tracking.min_position_size if tracking.min_position_size else 20.0,
            'min_position_size_usd': tracking.min_position_size if tracking.min_position_size else 20.0,
            'copy_leverage': tracking.copy_leverage,
            'max_leverage': tracking.max_leverage if tracking.max_leverage else 10,
            'default_leverage': tracking.default_leverage if tracking.default_leverage else 5,
            # 目标初始仓位快照
            'target_initial_size': tracking.target_initial_size if tracking.target_initial_size else None,
            'target_initial_side': tracking.target_initial_side if tracking.target_initial_side else None,
            'target_initial_entry_price': tracking.target_initial_entry_price if tracking.target_initial_entry_price else None,
            'target_initial_leverage': tracking.target_initial_leverage if tracking.target_initial_leverage else None,
            # 时间戳
            'started_at': tracking.started_at if tracking.started_at else None,
            'closed_at': tracking.closed_at if tracking.closed_at else None,
            # 标记
            'target_is_starred': tracking.target_is_starred,
            # 交易员评分信息
            'target_score': tracking.target_score if tracking.target_score else None,
            'target_rating': tracking.target_rating if tracking.target_rating else None,
            # 仓位模式
            'position_mode': tracking.position_mode or 'cross',
        }
    
    def _address_to_dict(self, address: pb2.CopyAddress) -> Dict:
        """将地址配置 proto 消息转换为字典"""
        return {
            'id': address.id,
            'user_id': address.user_id,
            'address': address.address,
            'nickname': address.nickname if address.nickname else None,
            'copy_ratio': address.copy_ratio,
            'max_position_size': address.max_position_size,
            'slippage': address.slippage,
            'is_enabled': address.is_enabled,
            'auto_copy': address.auto_copy,
            'whitelist_symbols': json.loads(address.whitelist_symbols) if address.whitelist_symbols else [],
            'blacklist_symbols': json.loads(address.blacklist_symbols) if address.blacklist_symbols else [],
            'created_at': address.created_at if address.created_at else None,
            'updated_at': address.updated_at if address.updated_at else None,
            'copy_once': address.copy_once,
        }
    
    def get_position_tracking(self, tracking_id: str) -> Optional[Dict]:
        """获取单个仓位跟单详情（通过 ULID）"""
        self._ensure_connected()
        try:
            response = self._stub.GetPositionTracking(
                pb2.GetPositionTrackingRequest(tracking_id=tracking_id),
                metadata=self._get_metadata()
            )
            if response.success and response.HasField('tracking'):
                return self._tracking_to_dict(response.tracking)
            return None
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (GetPositionTracking): {e}")
            return None
    
    def get_active_position_trackings(self) -> List[Dict]:
        """获取所有活跃的仓位跟单"""
        self._ensure_connected()
        try:
            response = self._stub.GetActivePositionTrackings(
                pb2.GetActivePositionTrackingsRequest(),
                metadata=self._get_metadata()
            )
            if response.success:
                return [self._tracking_to_dict(t) for t in response.trackings]
            return []
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (GetActivePositionTrackings): {e}")
            return []
    
    def save_position_tracking(self, data: Dict) -> str:
        """保存仓位跟单记录，返回 ULID"""
        self._ensure_connected()
        try:
            request = pb2.SavePositionTrackingRequest(
                target_address=data['target_address'],
                symbol=data['symbol'],
                target_side=data['target_side'],
                copy_ratio=data.get('copy_ratio', 1.0),
                is_enabled=data.get('is_enabled', True),
                status=data.get('status', 'pending'),
            )
            
            # 可选字段（id 现在是 ULID 字符串）
            if 'id' in data and data['id']:
                request.id = str(data['id'])
            # 支持两种字段名
            max_pos = data.get('max_position_size') or data.get('max_position_size_usd')
            if max_pos:
                request.max_position_size = max_pos
            if 'slippage' in data and data['slippage']:
                request.slippage = data['slippage']
            if 'my_size' in data and data['my_size']:
                request.my_size = data['my_size']
            if 'my_side' in data and data['my_side']:
                request.my_side = data['my_side']
            if 'my_entry_price' in data and data['my_entry_price']:
                request.my_entry_price = data['my_entry_price']
            if 'user_id' in data and data['user_id']:
                request.user_id = str(data['user_id'])
            if 'address_id' in data and data['address_id']:
                request.address_id = str(data['address_id'])
            if 'target_entry_price' in data and data['target_entry_price']:
                request.target_entry_price = data['target_entry_price']
            if 'target_size' in data and data['target_size']:
                request.target_size = data['target_size']
            # 支持两种字段名
            nickname = data.get('nickname') or data.get('target_name')
            if nickname:
                request.nickname = nickname
            
            # 自动补仓配置
            if 'auto_replenish' in data:
                request.auto_replenish = data['auto_replenish']
            if 'replenish_ratio' in data and data['replenish_ratio']:
                request.replenish_ratio = data['replenish_ratio']
            if 'replenish_min_value_usd' in data and data['replenish_min_value_usd']:
                request.replenish_min_value_usd = data['replenish_min_value_usd']
            if 'replenish_max_value_usd' in data and data['replenish_max_value_usd']:
                request.replenish_max_value_usd = data['replenish_max_value_usd']
            
            # 其他配置
            target_name = data.get('target_name') or data.get('nickname')
            if target_name:
                request.target_name = target_name
            min_pos = data.get('min_position_size') or data.get('min_position_size_usd')
            if min_pos:
                request.min_position_size = min_pos
            if 'copy_leverage' in data:
                request.copy_leverage = data['copy_leverage']
            if 'max_leverage' in data and data['max_leverage']:
                request.max_leverage = data['max_leverage']
            if 'default_leverage' in data and data['default_leverage']:
                request.default_leverage = data['default_leverage']
            
            # 目标初始仓位快照
            if 'target_initial_size' in data and data['target_initial_size']:
                request.target_initial_size = data['target_initial_size']
            if 'target_initial_side' in data and data['target_initial_side']:
                request.target_initial_side = data['target_initial_side']
            if 'target_initial_entry_price' in data and data['target_initial_entry_price']:
                request.target_initial_entry_price = data['target_initial_entry_price']
            if 'target_initial_leverage' in data and data['target_initial_leverage']:
                request.target_initial_leverage = data['target_initial_leverage']
            
            # 时间戳
            if 'started_at' in data and data['started_at']:
                request.started_at = str(data['started_at'])
            if 'closed_at' in data and data['closed_at']:
                request.closed_at = str(data['closed_at'])
            
            # 标记
            if 'target_is_starred' in data:
                request.target_is_starred = data['target_is_starred']
            
            # 交易员评分信息
            if 'target_score' in data and data['target_score'] is not None:
                request.target_score = float(data['target_score'])
            if 'target_rating' in data and data['target_rating']:
                request.target_rating = data['target_rating']

            # 仓位模式
            if 'position_mode' in data and data['position_mode']:
                request.position_mode = data['position_mode']

            response = self._stub.SavePositionTracking(request, metadata=self._get_metadata())
            if response.success:
                return response.tracking_id  # 返回 ULID 字符串
            else:
                logger.error(f"SavePositionTracking 失败: {response.error}")
                return ''
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (SavePositionTracking): {e}")
            return ''
    
    def update_tracking_status(
        self,
        tracking_id: str,
        status: str,
        close_reason: Optional[str] = None,
        closed_pnl: Optional[float] = None
    ) -> bool:
        """更新跟单状态（通过 ULID）"""
        self._ensure_connected()
        try:
            request = pb2.UpdateTrackingStatusRequest(
                tracking_id=tracking_id,
                status=status
            )
            if close_reason:
                request.close_reason = close_reason
            if closed_pnl is not None:
                request.closed_pnl = closed_pnl
            
            response = self._stub.UpdateTrackingStatus(request, metadata=self._get_metadata())
            return response.success
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (UpdateTrackingStatus): {e}")
            return False
    
    def update_tracking_position(
        self,
        tracking_id: str,
        my_size: float,
        my_side: str,
        my_entry_price: Optional[float] = None
    ) -> bool:
        """更新跟单仓位信息（通过 ULID）"""
        self._ensure_connected()
        try:
            request = pb2.UpdateTrackingPositionRequest(
                tracking_id=tracking_id,
                my_size=my_size,
                my_side=my_side
            )
            if my_entry_price is not None:
                request.my_entry_price = my_entry_price
            
            response = self._stub.UpdateTrackingPosition(request, metadata=self._get_metadata())
            return response.success
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (UpdateTrackingPosition): {e}")
            return False
    
    def get_enabled_copy_addresses(self, user_id: str) -> List[Dict]:
        """获取启用的跟单地址配置（通过用户 ULID）"""
        self._ensure_connected()
        try:
            response = self._stub.GetEnabledCopyAddresses(
                pb2.GetEnabledCopyAddressesRequest(user_id=user_id),
                metadata=self._get_metadata()
            )
            if response.success:
                return [self._address_to_dict(a) for a in response.addresses]
            return []
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (GetEnabledCopyAddresses): {e}")
            return []
    
    def check_position_tracking_exists(self, target_address: str, symbol: str) -> bool:
        """检查仓位跟单是否存在"""
        self._ensure_connected()
        try:
            response = self._stub.CheckPositionTrackingExists(
                pb2.CheckPositionTrackingExistsRequest(
                    target_address=target_address,
                    symbol=symbol
                ),
                metadata=self._get_metadata()
            )
            return response.exists
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (CheckPositionTrackingExists): {e}")
            return False
    
    def toggle_copy_trading_address(self, user_id: str, address: str, is_enabled: bool) -> bool:
        """启用/禁用跟单地址（通过用户 ULID）"""
        self._ensure_connected()
        try:
            response = self._stub.ToggleCopyTradingAddress(
                pb2.ToggleCopyTradingAddressRequest(
                    user_id=user_id,
                    address=address,
                    is_enabled=is_enabled
                ),
                metadata=self._get_metadata()
            )
            return response.success
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (ToggleCopyTradingAddress): {e}")
            return False
    
    def toggle_config_rule(self, rule_id: str, is_enabled: bool) -> bool:
        """启用/禁用跟单配置规则（立即跟单等）"""
        self._ensure_connected()
        try:
            response = self._stub.ToggleConfigRule(
                pb2.ToggleConfigRuleRequest(
                    rule_id=rule_id,
                    is_enabled=is_enabled
                ),
                metadata=self._get_metadata()
            )
            return response.success
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (ToggleConfigRule): {e}")
            return False
    
    def get_enabled_address_trackings(self, user_id: str) -> List[Dict]:
        """
        获取启用的地址跟踪配置（通过用户 ULID）
        
        Args:
            user_id: 用户 ULID
        
        Returns:
            启用的地址跟踪配置列表，每项包含:
            - id: 记录ID
            - tracking_address: 跟踪地址
            - address_remark: 地址备注
            - monitor_events: 监控事件列表 (open/close/add/reduce)
            - is_enabled: 是否启用
            - enable_notification: 是否开启通知
        """
        self._ensure_connected()
        try:
            response = self._stub.GetEnabledAddressTrackings(
                pb2.GetEnabledAddressTrackingsRequest(user_id=user_id),
                metadata=self._get_metadata()
            )
            if response.success:
                results = []
                for item in response.trackings:
                    # 解析 monitor_events JSON 字符串
                    try:
                        events = json.loads(item.monitor_events) if item.monitor_events else []
                    except (json.JSONDecodeError, TypeError):
                        events = []
                    
                    results.append({
                        'id': item.id,
                        'tracking_address': item.tracking_address,
                        'address_remark': item.address_remark,
                        'monitor_events': events,
                        'is_enabled': item.is_enabled,
                        'enable_notification': item.enable_notification,
                    })
                return results
            return []
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (GetEnabledAddressTrackings): {e}")
            return []


class GRPCRedisClient:
    """Redis gRPC 客户端"""
    
    def __init__(self, host: str = 'localhost', port: int = 50051, api_key: str = ''):
        """
        初始化 Redis 客户端
        
        Args:
            host: gRPC 服务器地址
            port: gRPC 服务器端口
            api_key: API Key（用于 gRPC 认证）
        """
        self._address = f'{host}:{port}'
        self._api_key = api_key
        self._channel = None
        self._stub = None
        self._subscriptions: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
    
    def _get_metadata(self):
        """获取携带 API Key 的 metadata"""
        if self._api_key:
            return [('x-api-key', self._api_key)]
        return []
    
    def _ensure_connected(self):
        """确保已连接"""
        if self._channel is None:
            self._channel = grpc.insecure_channel(self._address)
            self._stub = pb2_grpc.RedisServiceStub(self._channel)
    
    def close(self):
        """关闭连接"""
        # 停止所有订阅
        for key, stop_event in self._stop_events.items():
            stop_event.set()
        
        # 等待所有订阅线程结束
        for thread in self._subscriptions.values():
            thread.join(timeout=2.0)
        
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
    
    def publish(self, channel: str, message: str) -> int:
        """发布消息到指定 channel"""
        self._ensure_connected()
        try:
            response = self._stub.Publish(
                pb2.PublishRequest(channel=channel, message=message),
                metadata=self._get_metadata()
            )
            if response.success:
                return response.receivers
            return 0
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (Publish): {e}")
            return 0
    
    def setex(self, key: str, expire_seconds: int, value: str) -> bool:
        """设置带过期时间的键值"""
        self._ensure_connected()
        try:
            response = self._stub.SetEx(
                pb2.SetExRequest(
                    key=key,
                    value=value,
                    expire_seconds=expire_seconds
                ),
                metadata=self._get_metadata()
            )
            return response.success
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (SetEx): {e}")
            return False
    
    def get(self, key: str) -> Optional[str]:
        """获取键值"""
        self._ensure_connected()
        try:
            response = self._stub.Get(pb2.GetRequest(key=key), metadata=self._get_metadata())
            if response.success and response.HasField('value'):
                return response.value
            return None
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (Get): {e}")
            return None
    
    def subscribe_async(
        self,
        channels: List[str],
        callback: Callable[[str, str], None],
        subscription_key: str = None
    ) -> str:
        """
        异步订阅 channel
        
        Args:
            channels: 要订阅的 channel 列表
            callback: 收到消息时的回调函数，参数为 (channel, message)
            subscription_key: 订阅标识符，用于后续取消订阅
        
        Returns:
            订阅标识符
        """
        key = subscription_key or f"sub_{id(callback)}"
        
        if key in self._subscriptions:
            logger.warning(f"订阅已存在: {key}")
            return key
        
        stop_event = threading.Event()
        self._stop_events[key] = stop_event
        
        def subscription_thread():
            try:
                # 创建新的 channel 用于订阅
                channel = grpc.insecure_channel(self._address)
                stub = pb2_grpc.RedisServiceStub(channel)
                
                request = pb2.SubscribeRequest(channels=channels)
                
                logger.info(f"开始订阅 {channels}")
                
                for message in stub.Subscribe(request, metadata=self._get_metadata()):
                    if stop_event.is_set():
                        break
                    try:
                        callback(message.channel, message.message)
                    except Exception as e:
                        logger.error(f"订阅回调错误: {e}")
                
                channel.close()
                logger.info(f"订阅结束 {channels}")
                
            except grpc.RpcError as e:
                if not stop_event.is_set():
                    logger.error(f"订阅错误: {e}")
            except Exception as e:
                logger.error(f"订阅线程异常: {e}")
        
        thread = threading.Thread(target=subscription_thread, daemon=True)
        self._subscriptions[key] = thread
        thread.start()
        
        return key
    
    def unsubscribe(self, subscription_key: str):
        """取消订阅"""
        if subscription_key in self._stop_events:
            self._stop_events[subscription_key].set()
            del self._stop_events[subscription_key]
        
        if subscription_key in self._subscriptions:
            thread = self._subscriptions[subscription_key]
            thread.join(timeout=2.0)
            del self._subscriptions[subscription_key]


class GRPCPubSub:
    """
    Redis PubSub 兼容接口
    
    用于替代原有的 redis.pubsub() 接口，保持 API 兼容性
    """
    
    def __init__(self, redis_client: GRPCRedisClient):
        """
        初始化 PubSub
        
        Args:
            redis_client: GRPCRedisClient 实例
        """
        self._client = redis_client
        self._channels: List[str] = []
        self._messages: asyncio.Queue = None
        self._subscription_key: str = None
        self._running = False
    
    def subscribe(self, *channels: str):
        """订阅 channel"""
        self._channels.extend(channels)
    
    def unsubscribe(self, *channels: str):
        """取消订阅"""
        for ch in channels:
            if ch in self._channels:
                self._channels.remove(ch)
    
    def _start_subscription(self):
        """启动订阅"""
        if self._running or not self._channels:
            return
        
        self._messages = asyncio.Queue()
        self._running = True
        
        def on_message(channel: str, message: str):
            try:
                # 使用线程安全的方式添加消息
                asyncio.get_event_loop().call_soon_threadsafe(
                    self._messages.put_nowait,
                    {'type': 'message', 'channel': channel, 'data': message}
                )
            except:
                pass
        
        self._subscription_key = self._client.subscribe_async(
            channels=self._channels,
            callback=on_message
        )
    
    def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0) -> Optional[Dict]:
        """
        获取消息（同步接口，用于兼容原有代码）
        
        注意：此方法在 gRPC 模式下不直接可用，需要使用 async_get_message
        """
        raise NotImplementedError("请使用 async_get_message 或 GRPCRedisClient.subscribe_async")
    
    async def async_get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0) -> Optional[Dict]:
        """异步获取消息"""
        if not self._running:
            self._start_subscription()
        
        try:
            message = await asyncio.wait_for(self._messages.get(), timeout=timeout)
            return message
        except asyncio.TimeoutError:
            return None
    
    def close(self):
        """关闭订阅"""
        self._running = False
        if self._subscription_key:
            self._client.unsubscribe(self._subscription_key)
            self._subscription_key = None


class GRPCClient:
    """
    统一的 gRPC 客户端
    
    提供数据库和 Redis 操作的统一接口
    所有请求通过 API Key 进行认证
    """
    
    def __init__(self, host: str = 'localhost', port: int = 50051, api_key: str = ''):
        """
        初始化 gRPC 客户端
        
        Args:
            host: gRPC 服务器地址
            port: gRPC 服务器端口
            api_key: API Key（用于 gRPC 认证）
        """
        self.host = host
        self.port = port
        self._api_key = api_key
        self._db = GRPCDatabaseClient(host, port, api_key=api_key)
        self._redis = GRPCRedisClient(host, port, api_key=api_key)
        self._auth_channel = None
        self._auth_stub = None
    
    @property
    def db(self) -> GRPCDatabaseClient:
        """获取数据库客户端"""
        return self._db
    
    @property
    def redis(self) -> GRPCRedisClient:
        """获取 Redis 客户端"""
        return self._redis
    
    def close(self):
        """关闭所有连接"""
        self._db.close()
        self._redis.close()
        if self._auth_channel:
            self._auth_channel.close()
            self._auth_channel = None
            self._auth_stub = None
    
    def _ensure_auth_connected(self):
        """确保认证 channel 已连接"""
        if self._auth_channel is None:
            self._auth_channel = grpc.insecure_channel(f'{self.host}:{self.port}')
            self._auth_stub = pb2_grpc.AuthServiceStub(self._auth_channel)
    
    def verify_api_key(self, api_key: str = None) -> Optional[Dict]:
        """
        验证 API Key（通过 gRPC 调用服务端验证）
        
        Args:
            api_key: 要验证的 API Key，为空则使用自身的 API Key
            
        Returns:
            验证成功返回用户信息 dict，失败返回 None
        """
        key_to_verify = api_key or self._api_key
        if not key_to_verify:
            return None
        
        self._ensure_auth_connected()
        try:
            response = self._auth_stub.VerifyApiKey(
                pb2.VerifyApiKeyRequest(api_key=key_to_verify)
            )
            if response.valid:
                return {
                    'user_id': response.user_id,
                    'account': response.account,
                    'role': response.role,
                }
            return None
        except grpc.RpcError as e:
            logger.error(f"gRPC 错误 (VerifyApiKey): {e}")
            return None
    
    def ping(self) -> bool:
        """测试连接（同时验证 API Key）"""
        try:
            if self._api_key:
                # 有 API Key 时通过认证接口验证连接
                result = self.verify_api_key()
                if result:
                    logger.info(f"gRPC 认证成功: user={result['account']}, role={result['role']}")
                    return True
                else:
                    logger.error("gRPC 认证失败: API Key 无效")
                    return False
            else:
                # 无 API Key 时尝试直接连接（会被拦截器拒绝）
                self._db.get_active_position_trackings()
                return True
        except Exception as e:
            logger.error(f"gRPC 连接测试失败: {e}")
            return False
