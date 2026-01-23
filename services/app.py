"""
Flask API Server 主入口
负责应用配置和路由注册
"""
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
import logging

from services.routes import register_routes

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """创建并配置 Flask 应用"""
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

    logger.info("Flask 应用初始化完成，Swagger 文档可访问: /docs")
    return app


def run_server(host='0.0.0.0', port=5000, debug=True):
    """启动服务器"""
    app = create_app()

    logger.info("启动 Trader Analytics API Server...")
    logger.info("API 文档:")
    logger.info("  GET  /api/traders - 获取交易者列表")
    logger.info("  GET  /api/traders/<address> - 获取交易者详情")
    logger.info("  POST /api/traders/<address>/refresh - 刷新分析")
    logger.info("  GET  /api/traders/<address>/fills - 获取历史交易")
    logger.info("  GET  /api/traders/<address>/positions - 获取当前持仓")
    logger.info("  GET  /api/traders/<address>/history - 获取历史图表数据")
    logger.info("  GET  /api/traders/rating/<rating> - 按评级筛选")
    logger.info("  GET  /api/coins - 获取币种列表")
    logger.info("  GET  /api/stats - 获取统计信息")
    logger.info("  GET  /api/sessions - 获取筛选会话")
    logger.info("  GET  /api/copy-trading/orders - 获取跟单订单")
    logger.info("  GET  /api/copy-trading/orders/stats - 订单统计")
    logger.info("  GET  /health - 健康检查")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server()
