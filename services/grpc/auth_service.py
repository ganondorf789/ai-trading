"""
认证服务 gRPC 实现

提供 API Key 验证功能
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


class AuthServiceServicer(pb2_grpc.AuthServiceServicer):
    """认证服务 gRPC 实现"""
    
    def __init__(self, db: TraderDatabase = None):
        """
        初始化认证服务
        
        Args:
            db: 数据库实例，如果为 None 则自动创建
        """
        self._db = db or TraderDatabase()
        logger.info("AuthService 初始化完成")
    
    def VerifyApiKey(self, request: pb2.VerifyApiKeyRequest, context) -> pb2.VerifyApiKeyResponse:
        """验证 API Key"""
        try:
            if not request.api_key:
                return pb2.VerifyApiKeyResponse(
                    valid=False,
                    error="API Key 不能为空"
                )
            
            user = self._db.verify_api_key(request.api_key)
            
            if user:
                return pb2.VerifyApiKeyResponse(
                    valid=True,
                    user_id=user['id'],
                    account=user['account'],
                    role=user.get('role', 'user')
                )
            else:
                return pb2.VerifyApiKeyResponse(
                    valid=False,
                    error="API Key 无效、已过期或账户已被禁用"
                )
                
        except Exception as e:
            logger.error(f"VerifyApiKey 错误: {e}")
            return pb2.VerifyApiKeyResponse(
                valid=False,
                error=str(e)
            )
