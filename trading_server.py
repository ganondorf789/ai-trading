"""
Trading API Server 入口文件
独立的交易服务，提供交易操作和日志查询 API

启动方式：
python trading_server.py --port 5001 --api-key your-secret-key

配置文件：trading/.env
- API_KEY: API Key（为空时禁用认证）
- API_PORT: 服务端口（默认 5001）
- HYPERLIQUID_PRIVATE_KEY: Hyperliquid 钱包私钥
- HYPERLIQUID_WALLET_ADDRESS: 钱包地址（可选）
- HYPERLIQUID_TESTNET: 是否使用测试网（默认 false）
"""
import argparse
import os

# 设置环境变量后再导入 settings
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Trading API Server')
    parser.add_argument('--host', default=None, help='监听地址')
    parser.add_argument('--port', type=int, default=None, help='监听端口')
    parser.add_argument('--api-key', default=None, help='API Key（覆盖配置文件）')
    parser.add_argument('--debug', action='store_true', default=None, help='调试模式')
    
    args = parser.parse_args()
    
    # 如果命令行提供了参数，设置环境变量（优先级高于 .env）
    if args.api_key:
        os.environ['API_KEY'] = args.api_key
    if args.host:
        os.environ['API_HOST'] = args.host
    if args.port:
        os.environ['API_PORT'] = str(args.port)
    if args.debug is not None:
        os.environ['API_DEBUG'] = str(args.debug).lower()
    
    # 导入时会加载 .env 配置
    from trading.app import run_server
    from trading.settings import settings
    
    run_server(
        host=settings.api.host,
        port=settings.api.port,
        debug=settings.api.debug
    )
