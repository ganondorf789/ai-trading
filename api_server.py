"""
Flask API Server for Trader Analytics
提供交易者数据查询和分析接口

入口文件：调用模块化的服务
"""
from services.app import run_server

if __name__ == '__main__':
    run_server(host='0.0.0.0', port=5000, debug=True)
