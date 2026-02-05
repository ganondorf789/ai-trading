"""
Trading API Server 主入口
独立的交易服务，提供交易操作和日志查询 API
使用 API Key 认证
"""
import sys
import os

# 添加项目根目录到路径（用于导入 clients）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from flask_cors import CORS
from flasgger import Swagger
import logging

from trading.routes import register_routes
from trading.settings import settings

# 配置日志
logging.basicConfig(level=getattr(logging, settings.log.level, logging.INFO))
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
            "title": "Trading API",
            "description": "交易操作和日志查询 API（API Key 认证）",
            "version": "1.0.0"
        },
        "securityDefinitions": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            }
        },
        "security": [{"ApiKeyAuth": []}],
        "tags": [
            {"name": "System", "description": "系统相关接口"},
            {"name": "Trading - Market", "description": "市场数据"},
            {"name": "Trading - Positions", "description": "交易仓位"},
            {"name": "Trading - Orders", "description": "交易订单"},
            {"name": "Trading - Account", "description": "账户信息"},
            {"name": "Logs", "description": "日志查询"}
        ]
    }

    # 注册所有路由
    register_routes(app)

    # 初始化 Swagger（在路由注册后）
    Swagger(app, config=swagger_config, template=swagger_template)

    logger.info("Trading API 应用初始化完成，Swagger 文档可访问: /docs")
    return app


def run_server(host='0.0.0.0', port=5001, debug=True):
    """启动服务器
    
    Args:
        host: 监听地址
        port: 监听端口
        debug: 是否启用调试模式
    """
    app = create_app()

    logger.info("启动 Trading API Server...")
    logger.info(f"监听地址: {host}:{port}")
    logger.info("")
    logger.info("API 端点:")
    logger.info("  GET  /api/trading/meta - 获取市场元数据")
    logger.info("  GET  /api/trading/mids - 获取所有中间价")
    logger.info("  GET  /api/trading/mids/<symbol> - 获取指定中间价")
    logger.info("  GET  /api/trading/positions - 获取所有仓位")
    logger.info("  GET  /api/trading/positions/<symbol> - 获取指定仓位")
    logger.info("  POST /api/trading/positions/<symbol>/add - 市价补仓")
    logger.info("  POST /api/trading/positions/<symbol>/add-limit - 限价补仓")
    logger.info("  POST /api/trading/positions/<symbol>/close - 市价平仓")
    logger.info("  POST /api/trading/positions/<symbol>/close-limit - 限价平仓")
    logger.info("  POST /api/trading/positions/close-all - 一键平仓")
    logger.info("  POST /api/trading/positions/<symbol>/tp-sl - 设置止盈止损")
    logger.info("  GET  /api/trading/orders - 获取未成交订单")
    logger.info("  DELETE /api/trading/orders/<symbol>/<order_id> - 取消订单")
    logger.info("  DELETE /api/trading/orders/<symbol> - 取消交易对订单")
    logger.info("  DELETE /api/trading/orders - 取消所有订单")
    logger.info("  GET  /api/trading/account - 获取账户信息")
    logger.info("")
    logger.info("日志端点:")
    logger.info("  GET  /api/logs/copy-trading - 获取日志文件列表")
    logger.info("  GET  /api/logs/copy-trading/<filename> - 获取日志内容")
    logger.info("  GET  /api/logs/copy-trading/latest - 获取最新日志")
    logger.info("")
    logger.info("认证方式: X-API-Key Header 或 ?api_key= Query Parameter")
    logger.info("  GET  /health - 健康检查（无需认证）")
    
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server()
