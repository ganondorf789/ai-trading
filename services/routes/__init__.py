"""
API Routes Package
将所有 API 路由模块化组织
"""
from flask import Blueprint


def register_routes(app):
    """注册所有路由到 Flask 应用"""
    # 系统路由
    from .system import system_bp
    app.register_blueprint(system_bp)
    
    # 交易者管理路由（拆分后）
    from .traders_core import traders_core_bp
    from .traders_positions import traders_positions_bp
    from .traders_analysis import traders_analysis_bp
    from .traders_stats import traders_stats_bp
    
    app.register_blueprint(traders_core_bp)
    app.register_blueprint(traders_positions_bp)
    app.register_blueprint(traders_analysis_bp)
    app.register_blueprint(traders_stats_bp)
    
    # 跟单交易路由（拆分后）
    from .copy_trading_addresses import copy_trading_addresses_bp
    from .copy_trading_orders import copy_trading_orders_bp
    from .copy_trading_positions import copy_trading_positions_bp
    from .copy_trading_tracking import copy_trading_tracking_bp
    
    app.register_blueprint(copy_trading_addresses_bp)
    app.register_blueprint(copy_trading_orders_bp)
    app.register_blueprint(copy_trading_positions_bp)
    app.register_blueprint(copy_trading_tracking_bp)
    
    # C端交易 API 路由
    from .trading import trading_bp
    app.register_blueprint(trading_bp)
    
    # 通知路由
    from .notifications import notifications_bp
    app.register_blueprint(notifications_bp)