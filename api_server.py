"""
Flask API Server for Trader Analytics
提供交易者数据查询和分析接口

入口文件：调用模块化的服务

WebSocket 使用说明：
1. 启动服务器后，WebSocket 端点: ws://localhost:5000/socket.io
2. 客户端连接后监听 'new_position' 事件接收新仓位通知
3. 监控脚本 monitor_s_traders_positions.py 需要带 --redis 参数运行

示例（JavaScript）：
    const socket = io('http://localhost:5000');
    socket.on('new_position', (data) => {
        console.log('新仓位:', data);
        // data 包含: id, trader_address, coin, direction, position_value, ...
    });
"""
import argparse
from services.app import run_server

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Trader Analytics API Server')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=5000, help='监听端口')
    parser.add_argument('--no-websocket', action='store_true', help='禁用 WebSocket 支持')
    parser.add_argument('--debug', action='store_true', default=True, help='调试模式')
    
    args = parser.parse_args()
    
    run_server(
        host=args.host,
        port=args.port,
        debug=args.debug,
        enable_websocket=not args.no_websocket
    )
