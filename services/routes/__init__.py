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
    
    # 用户认证路由
    from .auth import auth_bp
    app.register_blueprint(auth_bp)
    
    # 交易者管理路由（拆分后）
    from .traders_core import traders_core_bp
    from .traders_positions import traders_positions_bp
    from .traders_stats import traders_stats_bp

    app.register_blueprint(traders_core_bp)
    app.register_blueprint(traders_positions_bp)
    app.register_blueprint(traders_stats_bp)
    
    # 跟单交易路由（拆分后）
    from .copy_trading_addresses import copy_trading_addresses_bp
    from .copy_trading_positions import copy_trading_positions_bp
    from .copy_trading_tracking import copy_trading_tracking_bp
    
    app.register_blueprint(copy_trading_addresses_bp)
    app.register_blueprint(copy_trading_positions_bp)
    app.register_blueprint(copy_trading_tracking_bp)
    
    # 通知路由
    from .notifications import notifications_bp
    app.register_blueprint(notifications_bp)
    
    # 应用版本管理路由
    from .app_versions import app_versions_bp
    app.register_blueprint(app_versions_bp)
    
    # 公告管理路由
    from .announcements import announcements_bp
    app.register_blueprint(announcements_bp)
    
    # 地址跟踪路由
    from .address_tracking import address_tracking_bp
    app.register_blueprint(address_tracking_bp)
    
    # 巨鲸锚点路由
    from .whale_anchor import whale_anchor_bp
    app.register_blueprint(whale_anchor_bp)

    # 交易数据代理路由
    from .trading import trading_bp
    app.register_blueprint(trading_bp)
