"""
仓位级别跟单机器人

第二种跟单模式：跟单特定交易员的特定仓位
通过轮询目标交易者的特定仓位变化进行跟单
从数据库加载仓位跟单配置，支持同时跟单多个仓位
使用前请先在 Web 持仓页面点击"跟单此仓位"按钮添加跟单

启动方式：
python examples/position_copy_trading_example.py
"""

VERSION = "1.0.1"
import asyncio
import os
import sys
import pendulum

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from engine.position_copy_trading import PositionCopyTradingBot
from config.settings import settings
from database import TraderDatabase

# Redis 支持（可选）
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# 全局数据库
db: TraderDatabase = None
# 全局 Redis 客户端（用于发送开仓通知）
redis_client = None
# 全局 Hyperliquid 客户端（复用实例，避免重复创建）
hl_client: HyperliquidClient = None


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    logger.add(
        f"logs/position_copy_{pendulum.now().format('YYYYMMDD_HHmmss')}.log",
        rotation="1 day",
        level="DEBUG"
    )


def setup_redis_client():
    """初始化 Redis 客户端（用于发送配置重载通知）"""
    global redis_client
    
    if not REDIS_AVAILABLE:
        logger.warning("Redis 库未安装，配置重载通知将不可用")
        return None
    
    try:
        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=True
        )
        redis_client.ping()
        logger.info(f"Redis 已连接，开仓通知已启用")
        return redis_client
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}")
        redis_client = None
        return None


async def run():
    """运行仓位跟单机器人"""
    global db

    setup_logging()

    logger.info("=" * 60)
    logger.info(f"仓位级别跟单机器人 v{VERSION}")
    logger.info("第二种跟单模式：跟单特定仓位")
    logger.info("=" * 60)

    # 初始化数据库
    db = TraderDatabase()
    
    # 初始化 Redis（用于发送/接收开仓通知）
    setup_redis_client()

    # 初始化客户端
    if not settings.hyperliquid.private_key:
        logger.error("需要配置 HYPERLIQUID_PRIVATE_KEY")
        return

    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key,
        wallet_address=settings.hyperliquid.wallet_address,
        testnet=settings.system.testnet_mode
    )

    # 创建仓位跟单机器人（传入 redis_client 接收开仓通知）
    bot = PositionCopyTradingBot(
        client=client,
        check_interval=0.1,  # 检查间隔（秒）
        reload_interval=60.0,  # 配置重载间隔（秒）
        redis_client=redis_client,  # 接收开仓通知
    )

    logger.info("启动仓位跟单机器人...")
    logger.info("在 Web 持仓页面点击'跟单此仓位'按钮添加跟单")
    logger.info("按 Ctrl+C 停止\n")

    try:
        await bot.run()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("\n正在停止...")
        bot.stop()

        # 显示统计
        status = bot.get_status()
        logger.info("\n运行统计:")
        logger.info(f"  跟单数量: {status['tracking_count']}")
        logger.info(f"  活跃: {status['active_count']}")
        logger.info(f"  等待: {status['pending_count']}")

        if status['trackings']:
            logger.info("\n各仓位跟单状态:")
            for t in status['trackings']:
                logger.info(
                    f"  #{t['tracking_id']} | {t['symbol']} | "
                    f"状态: {t['status']} | "
                    f"我方: {t['my_size']:.4f} {t['my_side'] or '-'}"
                )


if __name__ == "__main__":
    # Windows 上需要特殊处理
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    
    # 强制退出，避免后台线程阻塞
    os._exit(0)
