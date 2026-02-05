"""
Redis 服务 gRPC 实现

处理 Pub/Sub 和缓存操作
"""
import sys
import os
import asyncio
import threading
from typing import Optional
from queue import Queue, Empty

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import grpc
from loguru import logger

import trading_service_pb2 as pb2
import trading_service_pb2_grpc as pb2_grpc

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisServiceServicer(pb2_grpc.RedisServiceServicer):
    """Redis 服务 gRPC 实现"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, password: str = None, db: int = 0):
        """
        初始化 Redis 服务
        
        Args:
            host: Redis 主机地址
            port: Redis 端口
            password: Redis 密码
            db: Redis 数据库索引
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis 库未安装，请运行: pip install redis")
        
        self._redis = redis.Redis(
            host=host,
            port=port,
            password=password or None,
            db=db,
            decode_responses=True
        )
        
        # 测试连接
        self._redis.ping()
        logger.info(f"RedisService 初始化完成: {host}:{port}")
    
    def Publish(self, request: pb2.PublishRequest, context) -> pb2.PublishResponse:
        """发布消息到指定 channel"""
        try:
            receivers = self._redis.publish(request.channel, request.message)
            logger.debug(f"Publish to {request.channel}: {request.message[:100]}... -> {receivers} receivers")
            return pb2.PublishResponse(
                success=True,
                receivers=receivers
            )
        except Exception as e:
            logger.error(f"Publish 错误: {e}")
            return pb2.PublishResponse(
                success=False,
                error=str(e)
            )
    
    def Subscribe(self, request: pb2.SubscribeRequest, context):
        """
        订阅 channel（服务端流式 RPC）
        
        客户端调用此方法后会持续接收消息，直到客户端断开连接
        """
        channels = list(request.channels)
        if not channels:
            logger.warning("Subscribe: 没有指定 channel")
            return
        
        logger.info(f"Subscribe: 开始订阅 {channels}")
        
        try:
            pubsub = self._redis.pubsub()
            pubsub.subscribe(*channels)
            
            # 持续监听消息
            while context.is_active():
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message and message['type'] == 'message':
                        yield pb2.SubscribeMessage(
                            channel=message['channel'],
                            message=message['data']
                        )
                except Exception as e:
                    logger.warning(f"Subscribe 消息接收错误: {e}")
                    break
            
            logger.info(f"Subscribe: 客户端断开连接，停止订阅 {channels}")
            
        except Exception as e:
            logger.error(f"Subscribe 错误: {e}")
        finally:
            try:
                pubsub.unsubscribe(*channels)
                pubsub.close()
            except:
                pass
    
    def SetEx(self, request: pb2.SetExRequest, context) -> pb2.SetExResponse:
        """设置带过期时间的键值"""
        try:
            self._redis.setex(
                name=request.key,
                time=request.expire_seconds,
                value=request.value
            )
            logger.debug(f"SetEx: {request.key} (expire: {request.expire_seconds}s)")
            return pb2.SetExResponse(success=True)
        except Exception as e:
            logger.error(f"SetEx 错误: {e}")
            return pb2.SetExResponse(
                success=False,
                error=str(e)
            )
    
    def Get(self, request: pb2.GetRequest, context) -> pb2.GetResponse:
        """获取键值"""
        try:
            value = self._redis.get(request.key)
            if value is not None:
                return pb2.GetResponse(
                    success=True,
                    value=value
                )
            else:
                return pb2.GetResponse(
                    success=True,
                    value=None
                )
        except Exception as e:
            logger.error(f"Get 错误: {e}")
            return pb2.GetResponse(
                success=False,
                error=str(e)
            )
