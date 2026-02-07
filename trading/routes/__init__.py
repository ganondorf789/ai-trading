"""
Trading Service Routes
"""


def register_routes(app):
    """注册交易服务路由"""
    # 系统路由（健康检查）
    from .system import system_bp
    app.register_blueprint(system_bp)
    
    # 交易路由
    from .trading import trading_bp, get_grpc_client
    app.register_blueprint(trading_bp)
    
    # 日志路由
    from .logs import logs_bp
    app.register_blueprint(logs_bp)
    
    # 初始化中间件的 gRPC 远程验证
    from .middleware import init_middleware_grpc
    try:
        grpc_client = get_grpc_client()
        init_middleware_grpc(grpc_client)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"gRPC 中间件初始化失败，将使用本地 API Key 验证: {e}"
        )
