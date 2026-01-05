"""
API Routes Package
将所有 API 路由模块化组织
"""
from flask import Blueprint

def register_routes(app):
    """注册所有路由到 Flask 应用"""
    from .traders import traders_bp
    from .copy_trading import copy_trading_bp
    from .group_comparison import group_comparison_bp
    from .system import system_bp

    app.register_blueprint(traders_bp)
    app.register_blueprint(copy_trading_bp)
    app.register_blueprint(group_comparison_bp)
    app.register_blueprint(system_bp)
