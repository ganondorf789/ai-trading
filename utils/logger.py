"""
日志工具
"""
import sys
from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: str = "logs/trading.log",
    rotation: str = "1 day",
    retention: str = "30 days"
):
    """
    配置日志
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        rotation: 轮转周期
        retention: 保留时间
    """
    # 移除默认处理器
    logger.remove()
    
    # 控制台输出
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>"
    )
    
    # 文件输出
    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation=rotation,
        retention=retention,
        compression="gz"
    )
    
    return logger


def get_logger(name: str = None):
    """获取日志器"""
    if name:
        return logger.bind(name=name)
    return logger

