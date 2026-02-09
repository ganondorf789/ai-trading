"""
数据库服务 gRPC 实现

处理所有仓位跟单相关的数据库操作
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import grpc
from loguru import logger

import trading_service_pb2 as pb2
import trading_service_pb2_grpc as pb2_grpc
from database import TraderDatabase


class DatabaseServiceServicer(pb2_grpc.DatabaseServiceServicer):
    """数据库服务 gRPC 实现"""
    
    def __init__(self, db: TraderDatabase = None):
        """
        初始化数据库服务
        
        Args:
            db: 数据库实例，如果为 None 则自动创建
        """
        self._db = db or TraderDatabase()
        logger.info("DatabaseService 初始化完成")
    
    def _resolve_user_ulid(self, user_id_int: int) -> str:
        """将用户整数 ID 解析为 ULID"""
        if not user_id_int:
            return ''
        try:
            user = self._db.get_user_by_id(user_id_int)
            return user.get('ulid', '') if user else ''
        except Exception:
            return ''

    def _resolve_address_ulid(self, address_id_int: int) -> str:
        """将跟单地址整数 ID 解析为 ULID"""
        if not address_id_int:
            return ''
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ulid FROM copy_trading_addresses WHERE id = %s", (address_id_int,))
                row = cursor.fetchone()
                return row[0] if row else ''
        except Exception:
            return ''
    
    def _resolve_user_int_id(self, user_ulid: str) -> int:
        """将用户 ULID 解析为整数 ID"""
        if not user_ulid:
            return 0
        try:
            user = self._db.get_user_by_ulid(user_ulid)
            return user.get('id', 0) if user else 0
        except Exception:
            return 0

    def _resolve_tracking_int_id(self, tracking_ulid: str) -> int:
        """将跟单记录 ULID 解析为整数 ID"""
        if not tracking_ulid:
            return 0
        try:
            tracking = self._db.get_position_tracking_by_ulid(tracking_ulid)
            return tracking.get('id', 0) if tracking else 0
        except Exception:
            return 0
    
    def _resolve_address_int_id(self, address_ulid: str) -> int:
        """将跟单地址 ULID 解析为整数 ID"""
        if not address_ulid:
            return 0
        try:
            with self._db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM copy_trading_addresses WHERE ulid = %s", (address_ulid,))
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def _tracking_to_proto(self, tracking: dict) -> pb2.PositionTracking:
        """将数据库记录转换为 proto 消息（使用 ULID 作为外部标识）"""
        # 解析关联的用户和地址 ULID
        user_ulid = tracking.get('user_ulid', '') or self._resolve_user_ulid(tracking.get('user_id'))
        address_ulid = tracking.get('address_ulid', '') or self._resolve_address_ulid(tracking.get('address_id'))
        
        return pb2.PositionTracking(
            id=tracking.get('ulid', ''),  # 使用 ULID 作为对外 ID
            target_address=tracking.get('target_address', ''),
            symbol=tracking.get('symbol', ''),
            target_side=tracking.get('target_side', ''),
            copy_ratio=float(tracking.get('copy_ratio', 1.0)),
            max_position_size=float(tracking.get('max_position_size_usd', 0) or tracking.get('max_position_size', 0)),
            slippage=float(tracking.get('slippage', 0.001)),
            is_enabled=tracking.get('is_enabled', True),
            status=tracking.get('status', 'pending'),
            my_size=float(tracking.get('my_size', 0) or 0),
            my_side=tracking.get('my_side', '') or '',
            my_entry_price=float(tracking.get('my_entry_price', 0) or 0),
            user_id=user_ulid,
            address_id=address_ulid,
            target_entry_price=float(tracking.get('target_entry_price', 0) or 0),
            target_size=float(tracking.get('target_size', 0) or 0),
            nickname=tracking.get('nickname', '') or tracking.get('target_name', '') or '',
            created_at=str(tracking.get('created_at', '')),
            updated_at=str(tracking.get('updated_at', '')),
            close_reason=tracking.get('close_reason', '') or '',
            closed_pnl=float(tracking.get('closed_pnl', 0) or 0),
            # 自动补仓配置
            auto_replenish=tracking.get('auto_replenish', False) or False,
            replenish_ratio=float(tracking.get('replenish_ratio', 0.5) or 0.5),
            replenish_min_value_usd=float(tracking.get('replenish_min_value_usd', 10.0) or 10.0),
            replenish_max_value_usd=float(tracking.get('replenish_max_value_usd', 100.0) or 100.0),
            # 其他配置
            target_name=tracking.get('target_name', '') or '',
            min_position_size=float(tracking.get('min_position_size_usd', 20.0) or tracking.get('min_position_size', 20.0)),
            copy_leverage=tracking.get('copy_leverage', True) if tracking.get('copy_leverage') is not None else True,
            max_leverage=tracking.get('max_leverage', 10) or 10,
            default_leverage=tracking.get('default_leverage', 5) or 5,
            # 目标初始仓位快照
            target_initial_size=float(tracking.get('target_initial_size', 0) or 0),
            target_initial_side=tracking.get('target_initial_side', '') or '',
            target_initial_entry_price=float(tracking.get('target_initial_entry_price', 0) or 0),
            target_initial_leverage=tracking.get('target_initial_leverage', 0) or 0,
            # 时间戳
            started_at=str(tracking.get('started_at', '') or ''),
            closed_at=str(tracking.get('closed_at', '') or ''),
            # 标记
            target_is_starred=tracking.get('target_is_starred', False) or False,
            # 交易员评分信息
            target_score=float(tracking.get('target_score', 0) or 0),
            target_rating=tracking.get('target_rating', '') or '',
        )
    
    def _address_to_proto(self, address: dict, user_ulid: str = '') -> pb2.CopyAddress:
        """将地址配置转换为 proto 消息（使用 ULID 作为外部标识）"""
        import json
        # 解析用户 ULID
        resolved_user_ulid = user_ulid or self._resolve_user_ulid(address.get('user_id'))
        return pb2.CopyAddress(
            id=address.get('ulid', ''),  # 使用 ULID 作为对外 ID
            user_id=resolved_user_ulid,
            address=address.get('address', ''),
            nickname=address.get('nickname', '') or '',
            copy_ratio=float(address.get('copy_ratio', 1.0)),
            max_position_size=float(address.get('max_position_size', 0)),
            slippage=float(address.get('slippage', 0.001)),
            is_enabled=address.get('is_enabled', True),
            auto_copy=address.get('auto_copy', False),
            whitelist_symbols=json.dumps(address.get('whitelist_symbols', []) or []),
            blacklist_symbols=json.dumps(address.get('blacklist_symbols', []) or []),
            created_at=str(address.get('created_at', '')),
            updated_at=str(address.get('updated_at', '')),
            copy_once=address.get('copy_once', False) or False,
        )
    
    def GetPositionTracking(self, request: pb2.GetPositionTrackingRequest, context) -> pb2.PositionTrackingResponse:
        """获取单个仓位跟单详情（通过 ULID）"""
        try:
            tracking = self._db.get_position_tracking_by_ulid(request.tracking_id)
            if tracking:
                return pb2.PositionTrackingResponse(
                    success=True,
                    tracking=self._tracking_to_proto(tracking)
                )
            else:
                return pb2.PositionTrackingResponse(
                    success=False,
                    error=f"跟单记录不存在: {request.tracking_id}"
                )
        except Exception as e:
            logger.error(f"GetPositionTracking 错误: {e}")
            return pb2.PositionTrackingResponse(
                success=False,
                error=str(e)
            )
    
    def GetActivePositionTrackings(self, request: pb2.GetActivePositionTrackingsRequest, context) -> pb2.PositionTrackingListResponse:
        """获取所有活跃的仓位跟单"""
        try:
            trackings = self._db.get_active_position_trackings()
            return pb2.PositionTrackingListResponse(
                success=True,
                trackings=[self._tracking_to_proto(t) for t in trackings]
            )
        except Exception as e:
            logger.error(f"GetActivePositionTrackings 错误: {e}")
            return pb2.PositionTrackingListResponse(
                success=False,
                error=str(e)
            )
    
    def SavePositionTracking(self, request: pb2.SavePositionTrackingRequest, context) -> pb2.SavePositionTrackingResponse:
        """保存仓位跟单记录（接收 ULID，返回 ULID）"""
        try:
            data = {
                'target_address': request.target_address,
                'symbol': request.symbol,
                'target_side': request.target_side,
                'copy_ratio': request.copy_ratio,
                'is_enabled': request.is_enabled,
                'status': request.status,
            }
            
            # 可选字段：id（ULID → 整数 ID）
            if request.HasField('id') and request.id:
                int_id = self._resolve_tracking_int_id(request.id)
                if int_id:
                    data['id'] = int_id
            if request.HasField('max_position_size'):
                data['max_position_size_usd'] = request.max_position_size
            if request.HasField('slippage'):
                data['slippage'] = request.slippage
            if request.HasField('my_size'):
                data['my_size'] = request.my_size
            if request.HasField('my_side'):
                data['my_side'] = request.my_side
            if request.HasField('my_entry_price'):
                data['my_entry_price'] = request.my_entry_price
            # user_id（ULID → 整数 ID）
            if request.HasField('user_id') and request.user_id:
                data['user_id'] = self._resolve_user_int_id(request.user_id)
            # address_id（ULID → 整数 ID）
            if request.HasField('address_id') and request.address_id:
                data['address_id'] = self._resolve_address_int_id(request.address_id)
            if request.HasField('target_entry_price'):
                data['target_entry_price'] = request.target_entry_price
            if request.HasField('target_size'):
                data['target_size'] = request.target_size
            if request.HasField('nickname'):
                data['target_name'] = request.nickname
            
            # 自动补仓配置
            if request.HasField('auto_replenish'):
                data['auto_replenish'] = request.auto_replenish
            if request.HasField('replenish_ratio'):
                data['replenish_ratio'] = request.replenish_ratio
            if request.HasField('replenish_min_value_usd'):
                data['replenish_min_value_usd'] = request.replenish_min_value_usd
            if request.HasField('replenish_max_value_usd'):
                data['replenish_max_value_usd'] = request.replenish_max_value_usd
            
            # 其他配置
            if request.HasField('target_name'):
                data['target_name'] = request.target_name
            if request.HasField('min_position_size'):
                data['min_position_size_usd'] = request.min_position_size
            if request.HasField('copy_leverage'):
                data['copy_leverage'] = request.copy_leverage
            if request.HasField('max_leverage'):
                data['max_leverage'] = request.max_leverage
            if request.HasField('default_leverage'):
                data['default_leverage'] = request.default_leverage
            
            # 目标初始仓位快照
            if request.HasField('target_initial_size'):
                data['target_initial_size'] = request.target_initial_size
            if request.HasField('target_initial_side'):
                data['target_initial_side'] = request.target_initial_side
            if request.HasField('target_initial_entry_price'):
                data['target_initial_entry_price'] = request.target_initial_entry_price
            if request.HasField('target_initial_leverage'):
                data['target_initial_leverage'] = request.target_initial_leverage
            
            # 时间戳
            if request.HasField('started_at'):
                data['started_at'] = request.started_at
            if request.HasField('closed_at'):
                data['closed_at'] = request.closed_at
            
            # 标记
            if request.HasField('target_is_starred'):
                data['target_is_starred'] = request.target_is_starred
            
            # 交易员评分信息
            if request.HasField('target_score'):
                data['target_score'] = request.target_score
            if request.HasField('target_rating'):
                data['target_rating'] = request.target_rating
            
            int_id = self._db.save_position_tracking(data)
            
            # 将返回的整数 ID 转换为 ULID
            tracking_ulid = ''
            if int_id:
                tracking = self._db.get_position_tracking(int_id)
                tracking_ulid = tracking.get('ulid', '') if tracking else ''
            
            return pb2.SavePositionTrackingResponse(
                success=bool(int_id),
                tracking_id=tracking_ulid
            )
        except Exception as e:
            logger.error(f"SavePositionTracking 错误: {e}")
            return pb2.SavePositionTrackingResponse(
                success=False,
                error=str(e)
            )
    
    def UpdateTrackingStatus(self, request: pb2.UpdateTrackingStatusRequest, context) -> pb2.UpdateTrackingResponse:
        """更新跟单状态（通过 ULID）"""
        try:
            close_reason = request.close_reason if request.HasField('close_reason') else None
            closed_pnl = request.closed_pnl if request.HasField('closed_pnl') else None
            
            success = self._db.update_tracking_status_by_ulid(
                ulid=request.tracking_id,
                status=request.status,
                close_reason=close_reason,
                closed_pnl=closed_pnl
            )
            return pb2.UpdateTrackingResponse(success=success)
        except Exception as e:
            logger.error(f"UpdateTrackingStatus 错误: {e}")
            return pb2.UpdateTrackingResponse(
                success=False,
                error=str(e)
            )
    
    def UpdateTrackingPosition(self, request: pb2.UpdateTrackingPositionRequest, context) -> pb2.UpdateTrackingResponse:
        """更新跟单仓位信息（通过 ULID）"""
        try:
            my_entry_price = request.my_entry_price if request.HasField('my_entry_price') else None
            
            success = self._db.update_tracking_position_by_ulid(
                ulid=request.tracking_id,
                my_size=request.my_size,
                my_side=request.my_side,
                my_entry_price=my_entry_price
            )
            return pb2.UpdateTrackingResponse(success=success)
        except Exception as e:
            logger.error(f"UpdateTrackingPosition 错误: {e}")
            return pb2.UpdateTrackingResponse(
                success=False,
                error=str(e)
            )
    
    def GetEnabledCopyAddresses(self, request: pb2.GetEnabledCopyAddressesRequest, context) -> pb2.CopyAddressListResponse:
        """获取启用的跟单地址配置（通过用户 ULID）"""
        try:
            # 将用户 ULID 解析为整数 ID
            user_int_id = self._resolve_user_int_id(request.user_id)
            if not user_int_id:
                return pb2.CopyAddressListResponse(
                    success=False,
                    error=f"用户不存在: {request.user_id}"
                )
            
            addresses = self._db.get_enabled_copy_addresses(user_int_id)
            return pb2.CopyAddressListResponse(
                success=True,
                addresses=[self._address_to_proto(a, user_ulid=request.user_id) for a in addresses]
            )
        except Exception as e:
            logger.error(f"GetEnabledCopyAddresses 错误: {e}")
            return pb2.CopyAddressListResponse(
                success=False,
                error=str(e)
            )
    
    def CheckPositionTrackingExists(self, request: pb2.CheckPositionTrackingExistsRequest, context) -> pb2.CheckPositionTrackingExistsResponse:
        """检查仓位跟单是否存在"""
        try:
            exists = self._db.check_position_tracking_exists(
                target_address=request.target_address,
                symbol=request.symbol
            )
            return pb2.CheckPositionTrackingExistsResponse(exists=exists)
        except Exception as e:
            logger.error(f"CheckPositionTrackingExists 错误: {e}")
            return pb2.CheckPositionTrackingExistsResponse(
                exists=False,
                error=str(e)
            )
    
    def ToggleCopyTradingAddress(self, request: pb2.ToggleCopyTradingAddressRequest, context) -> pb2.UpdateTrackingResponse:
        """启用/禁用跟单地址（通过用户 ULID）"""
        try:
            # 将用户 ULID 解析为整数 ID
            user_int_id = self._resolve_user_int_id(request.user_id)
            if not user_int_id:
                return pb2.UpdateTrackingResponse(
                    success=False,
                    error=f"用户不存在: {request.user_id}"
                )
            
            success = self._db.toggle_copy_trading_address(
                user_id=user_int_id,
                address=request.address,
                is_enabled=request.is_enabled
            )
            return pb2.UpdateTrackingResponse(success=success)
        except Exception as e:
            logger.error(f"ToggleCopyTradingAddress 错误: {e}")
            return pb2.UpdateTrackingResponse(
                success=False,
                error=str(e)
            )
