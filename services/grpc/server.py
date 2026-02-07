"""
gRPC 服务器

启动方式：
python -m services.grpc.server

或从项目根目录：
python grpc_server.py
"""
import sys
import os
from concurrent import futures
import signal

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import grpc
from loguru import logger

import trading_service_pb2_grpc as pb2_grpc
from config.settings import settings
from database import TraderDatabase

from .database_service import DatabaseServiceServicer
from .redis_service import RedisServiceServicer
from .auth_service import AuthServiceServicer


# 不需要认证的 gRPC 方法（白名单）
AUTH_WHITELIST = {
    '/trading.AuthService/VerifyApiKey',
}


class ApiKeyAuthInterceptor(grpc.ServerInterceptor):
    """
    gRPC 服务端 API Key 认证拦截器
    
    从请求 metadata 中提取 'x-api-key'，验证后将 user_id 注入 context。
    白名单中的方法（如 VerifyApiKey 自身）不需要认证。
    """
    
    def __init__(self, db: TraderDatabase):
        self._db = db
    
    def intercept_service(self, continuation, handler_call_details):
        """拦截 gRPC 请求，验证 API Key"""
        method = handler_call_details.method
        
        # 白名单方法不需要认证
        if method in AUTH_WHITELIST:
            return continuation(handler_call_details)
        
        # 从 metadata 中提取 API Key
        metadata = dict(handler_call_details.invocation_metadata or [])
        api_key = metadata.get('x-api-key', '')
        
        if not api_key:
            # 无 API Key，拒绝请求
            return self._unauthenticated_handler()
        
        # 验证 API Key
        user = self._db.verify_api_key(api_key)
        if not user:
            return self._unauthenticated_handler()
        
        # 认证通过，继续处理
        return continuation(handler_call_details)
    
    def _unauthenticated_handler(self):
        """返回一个拒绝请求的 handler"""
        def _abort(ignored_request, context):
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                'API Key 无效或未提供，请在 Trading 服务配置中设置有效的 API_KEY'
            )
        
        return grpc.unary_unary_rpc_method_handler(_abort)


class GRPCServer:
    """gRPC 服务器"""
    
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 50051,
        max_workers: int = 10,
        redis_host: str = None,
        redis_port: int = None,
        redis_password: str = None,
        redis_db: int = None,
    ):
        """
        初始化 gRPC 服务器
        
        Args:
            host: 监听地址
            port: 监听端口
            max_workers: 最大工作线程数
            redis_*: Redis 配置，如果为 None 则从 settings 读取
        """
        self.host = host
        self.port = port
        self.max_workers = max_workers
        
        # Redis 配置
        self.redis_host = redis_host or settings.redis.host
        self.redis_port = redis_port or settings.redis.port
        self.redis_password = redis_password or settings.redis.password
        self.redis_db = redis_db if redis_db is not None else settings.redis.db
        
        self._server = None
    
    def start(self, block: bool = True):
        """
        启动 gRPC 服务器
        
        Args:
            block: 是否阻塞等待
        """
        # 创建共享的数据库实例
        shared_db = TraderDatabase()
        
        # 创建 API Key 认证拦截器
        auth_interceptor = ApiKeyAuthInterceptor(db=shared_db)
        
        self._server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=self.max_workers),
            interceptors=[auth_interceptor]
        )
        
        # 注册认证服务（使用共享数据库实例）
        auth_servicer = AuthServiceServicer(db=shared_db)
        pb2_grpc.add_AuthServiceServicer_to_server(auth_servicer, self._server)
        logger.info("已注册 AuthService（API Key 认证拦截器已启用）")
        
        # 注册数据库服务（使用共享数据库实例）
        db_servicer = DatabaseServiceServicer(db=shared_db)
        pb2_grpc.add_DatabaseServiceServicer_to_server(db_servicer, self._server)
        logger.info("已注册 DatabaseService")
        
        # 注册 Redis 服务
        try:
            redis_servicer = RedisServiceServicer(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db
            )
            pb2_grpc.add_RedisServiceServicer_to_server(redis_servicer, self._server)
            logger.info("已注册 RedisService")
        except Exception as e:
            logger.warning(f"RedisService 注册失败: {e}")
        
        # 绑定端口
        address = f'{self.host}:{self.port}'
        self._server.add_insecure_port(address)
        
        # 启动服务器
        self._server.start()
        logger.info(f"gRPC 服务器已启动: {address}")
        
        if block:
            self._server.wait_for_termination()
    
    def stop(self, grace: float = 5.0):
        """
        停止 gRPC 服务器
        
        Args:
            grace: 优雅关闭超时时间（秒）
        """
        if self._server:
            logger.info("正在停止 gRPC 服务器...")
            self._server.stop(grace)
            logger.info("gRPC 服务器已停止")


def serve(
    host: str = None,
    port: int = None,
    max_workers: int = None,
):
    """
    启动 gRPC 服务器的便捷函数
    
    Args:
        host: 监听地址（默认从配置读取）
        port: 监听端口（默认从配置读取）
        max_workers: 最大工作线程数（默认从配置读取）
    """
    # 使用配置的默认值
    host = host or settings.grpc.host
    port = port or settings.grpc.port
    max_workers = max_workers or settings.grpc.max_workers
    
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    
    server = GRPCServer(host=host, port=port, max_workers=max_workers)
    
    # 注册信号处理
    def signal_handler(signum, frame):
        logger.info(f"\n收到信号 {signum}，正在关闭...")
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 60)
    logger.info("gRPC Trading Service")
    logger.info("=" * 60)
    logger.info(f"监听地址: {host}:{port}")
    logger.info(f"工作线程: {max_workers}")
    logger.info(f"PostgreSQL: {settings.postgres.host}:{settings.postgres.port}")
    logger.info(f"Redis: {settings.redis.host}:{settings.redis.port}")
    logger.info("按 Ctrl+C 停止")
    logger.info("")
    
    server.start(block=True)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='gRPC Trading Service')
    parser.add_argument('--host', default=None, help=f'监听地址 (默认: {settings.grpc.host})')
    parser.add_argument('--port', type=int, default=None, help=f'监听端口 (默认: {settings.grpc.port})')
    parser.add_argument('--workers', type=int, default=None, help=f'最大工作线程数 (默认: {settings.grpc.max_workers})')
    
    args = parser.parse_args()
    serve(host=args.host, port=args.port, max_workers=args.workers)
