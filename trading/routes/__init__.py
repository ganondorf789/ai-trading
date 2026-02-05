"""
Trading Service Routes
"""


def register_routes(app):
    """注册交易服务路由"""
    # 系统路由（健康检查）
    from .system import system_bp
    app.register_blueprint(system_bp)
    
    # 交易路由
    from .trading import trading_bp
    app.register_blueprint(trading_bp)
    
    # 日志路由
    from .logs import logs_bp
    app.register_blueprint(logs_bp)
