"""
自定义异常类
"""


class ScreenerError(Exception):
    """筛选器基础异常"""
    pass


class APIError(ScreenerError):
    """API 调用异常"""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(message)


class APIRateLimitError(APIError):
    """API 频率限制异常"""
    def __init__(self, retry_after: float = 0):
        self.retry_after = retry_after
        super().__init__(f"API 频率限制，{retry_after}秒后重试", status_code=429)


class APITimeoutError(APIError):
    """API 超时异常"""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"API 请求超时 ({timeout}秒)", status_code=408)


class TraderDataError(ScreenerError):
    """交易者数据异常"""
    def __init__(self, address: str, reason: str):
        self.address = address
        self.reason = reason
        super().__init__(f"交易者 {address[:10]}... 数据异常: {reason}")


class InvalidAddressError(ScreenerError):
    """无效地址异常"""
    def __init__(self, address: str):
        self.address = address
        super().__init__(f"无效的交易者地址: {address}")


class ConfigurationError(ScreenerError):
    """配置错误异常"""
    def __init__(self, param: str, reason: str):
        self.param = param
        super().__init__(f"配置参数 '{param}' 错误: {reason}")


class InsufficientDataError(ScreenerError):
    """数据不足异常"""
    def __init__(self, address: str, required: int, actual: int):
        self.address = address
        self.required = required
        self.actual = actual
        super().__init__(
            f"交易者 {address[:10]}... 数据不足: 需要 {required} 条，实际 {actual} 条"
        )


class CacheError(ScreenerError):
    """缓存异常"""
    pass
