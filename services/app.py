"""
Flask API Server 主入口
负责应用配置和路由注册
支持 WebSocket 实时推送新仓位通知
"""
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
import logging

from services.routes import register_routes

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(enable_websocket=True):
    """创建并配置 Flask 应用
    
    Args:
        enable_websocket: 是否启用 WebSocket 支持
    """
    app = Flask(__name__)
    CORS(app)  # 允许跨域请求

    # Swagger 配置
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": 'apispec',
                "route": '/apispec.json',
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs"
    }

    swagger_template = {
        "info": {
            "title": "Trader Analytics API",
            "description": "交易者分析和跟单交易 API",
            "version": "1.0.0"
        },
        "tags": [
            {"name": "System", "description": "系统相关接口"},
            {"name": "Traders", "description": "交易者管理"},
            {"name": "Traders - Positions", "description": "交易者持仓管理"},
            {"name": "Traders - New Positions", "description": "新仓位检测记录"},
            {"name": "Traders - Analysis", "description": "交易者分析"},
            {"name": "Traders - Stats", "description": "交易者统计"},
            {"name": "Copy Trading - Groups", "description": "跟单分组管理"},
            {"name": "Copy Trading - Addresses", "description": "跟单地址管理"},
            {"name": "Copy Trading - Orders", "description": "跟单订单管理"},
            {"name": "Copy Trading - Positions", "description": "跟单仓位管理"},
            {"name": "Copy Trading - Tracking", "description": "仓位级别跟单"},
            {"name": "Copy Trading - Config", "description": "跟单配置管理"},
            {"name": "Trading - Market", "description": "市场数据"},
            {"name": "Trading - Positions", "description": "交易仓位"},
            {"name": "Trading - Orders", "description": "交易订单"},
            {"name": "Trading - Account", "description": "账户信息"}
        ]
    }

    # 注册所有路由
    register_routes(app)

    # 初始化 Swagger（在路由注册后）
    Swagger(app, config=swagger_config, template=swagger_template)

    # 初始化 WebSocket
    if enable_websocket:
        from services.websocket import init_socketio
        init_socketio(app)
        logger.info("WebSocket 支持已启用")

    logger.info("Flask 应用初始化完成，Swagger 文档可访问: /docs")
    return app


def run_server(host='0.0.0.0', port=5000, debug=True, enable_websocket=True):
    """启动服务器
    
    Args:
        host: 监听地址
        port: 监听端口
        debug: 是否启用调试模式
        enable_websocket: 是否启用 WebSocket 支持
    """
    app = create_app(enable_websocket=enable_websocket)

    logger.info("启动 Trader Analytics API Server...")
    logger.info("API 文档:")
    logger.info("  GET  /api/traders - 获取交易者列表")
    logger.info("  GET  /api/traders/<address> - 获取交易者详情")
    logger.info("  POST /api/traders/<address>/refresh - 刷新分析")
    logger.info("  GET  /api/traders/<address>/fills - 获取历史交易")
    logger.info("  GET  /api/traders/<address>/positions - 获取当前持仓")
    logger.info("  GET  /api/traders/<address>/history - 获取历史图表数据")
    logger.info("  GET  /api/traders/rating/<rating> - 按评级筛选")
    logger.info("  GET  /api/new-positions - 获取新仓位记录")
    logger.info("  GET  /api/coins - 获取币种列表")
    logger.info("  GET  /api/stats - 获取统计信息")
    logger.info("  GET  /api/sessions - 获取筛选会话")
    logger.info("  GET  /api/copy-trading/orders - 获取跟单订单")
    logger.info("  GET  /api/copy-trading/orders/stats - 订单统计")
    logger.info("  GET  /health - 健康检查")
    
    if enable_websocket:
        logger.info("")
        logger.info("WebSocket 端点:")
        logger.info(f"  ws://{host}:{port}/socket.io - 新仓位实时推送")
        logger.info("  事件: 'new_position' - 接收新仓位通知")
        logger.info("  Redis 订阅将在首个客户端连接时自动启动")
        
        from services.websocket import socketio
        
        # 使用 SocketIO 运行（支持 WebSocket）
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    else:
        # 普通 Flask 运行
        app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server()
