#!/usr/bin/env python
"""
gRPC 服务器启动入口

启动方式：
python grpc_server.py
python grpc_server.py --port 50051

配置优先级：命令行参数 > 环境变量 > .env 文件 > 默认值

依赖：
- grpcio
- grpcio-tools (仅生成代码时需要)
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import settings
from services.grpc.server import serve

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='gRPC Trading Service')
    parser.add_argument('--host', default=None, help=f'监听地址 (默认: {settings.grpc.host})')
    parser.add_argument('--port', type=int, default=None, help=f'监听端口 (默认: {settings.grpc.port})')
    parser.add_argument('--workers', type=int, default=None, help=f'最大工作线程数 (默认: {settings.grpc.max_workers})')
    
    args = parser.parse_args()
    serve(host=args.host, port=args.port, max_workers=args.workers)
