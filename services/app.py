"""
Flask API Server 主入口
负责应用配置和路由注册
"""
from flask import Flask
from flask_cors import CORS
import logging

from services.routes import register_routes

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """创建并配置 Flask 应用"""
    app = Flask(__name__)
    CORS(app)  # 允许跨域请求

    # 注册所有路由
    register_routes(app)

    logger.info("Flask 应用初始化完成")
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
