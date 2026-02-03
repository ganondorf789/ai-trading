"""
数据库管理模块
整合所有数据库操作功能 (PostgreSQL + Redis)
"""
from loguru import logger

from .base import DatabaseBase
from .cache import RedisCache, cache
from .migrations import DatabaseMigrations
from .trader_metrics import TraderMetricsOps
from .trader_fills import TraderFillsOps
from .positions import PositionsOps
from .copy_trading import CopyTradingOps
from .copy_orders import CopyOrdersOps
from .coins import CoinsOps
from .ai_analysis import AIAnalysisOps
from .position_history import PositionHistoryOps
from .position_tracking import PositionTrackingOps
from .new_positions import NewPositionsOps
from .notifications import NotificationsOps
from .users import UsersOps
from .secret_keys import SecretKeysOps
from .app_versions import AppVersionsOps
from .address_tracking import AddressTrackingOps


class TraderDatabase(
    DatabaseBase,
    DatabaseMigrations,
    TraderMetricsOps,
    TraderFillsOps,
    PositionsOps,
    CopyTradingOps,
    CopyOrdersOps,
    CoinsOps,
    AIAnalysisOps,
    PositionHistoryOps,
    PositionTrackingOps,
    NewPositionsOps,
    NotificationsOps,
    UsersOps,
    SecretKeysOps,
    AppVersionsOps,
    AddressTrackingOps
):
    """
    交易者数据库管理器 (PostgreSQL + Redis)

    整合了所有数据库操作功能，包括：
    - 交易者指标管理
    - 交易记录管理
    - 持仓管理
    - 跟单地址和分组管理
    - Hyperliquid 币种管理
    - AI 分析管理
    - 仓位级别跟单管理
    - 新仓位检测记录
    - 通知管理
    """

    def __init__(self):
        """初始化数据库"""
        super().__init__()
        self._init_database()
        logger.info("PostgreSQL 数据库初始化完成")

    def close(self):
        """关闭数据库和缓存连接"""
        DatabaseBase.close_pool()
        RedisCache.close()


# 导出主要类
__all__ = ['TraderDatabase', 'RedisCache', 'cache']
