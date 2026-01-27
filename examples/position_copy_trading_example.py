"""
仓位级别跟单机器人

第二种跟单模式：跟单特定交易员的特定仓位
通过轮询目标交易者的特定仓位变化进行跟单
从数据库加载仓位跟单配置，支持同时跟单多个仓位
使用前请先在 Web 持仓页面点击"跟单此仓位"按钮添加跟单

启动方式：
python examples/position_copy_trading_example.py
"""

VERSION = "1.0.0"
import asyncio
import os
import sys
import threading
import pendulum

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from clients.feishu_client import (
    FeishuClient, CopyTradingNotifier, FeishuCallbackClient, CardActionEvent
)
from engine.position_copy_trading import PositionCopyTradingBot
from config.settings import settings
from database import TraderDatabase

# Redis 支持（可选）
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# 全局通知器
notifier: CopyTradingNotifier = None
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


def setup_feishu_notifier() -> CopyTradingNotifier:
    """初始化飞书通知器"""
    feishu_client = FeishuClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        default_user_id=settings.feishu.default_user_id
    )

    # 检查是否配置了飞书
    if settings.feishu.app_id and settings.feishu.app_secret:
        logger.info("飞书应用已配置")
    else:
        logger.warning("飞书未配置，将不会发送通知")

    return CopyTradingNotifier(feishu_client)


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


def on_copy_callback(tracking_id: int, target: str, symbol: str, side: str, size: float):
    """复制交易回调"""
    logger.success(f"[#{tracking_id}] 开仓成功: {symbol} {side.upper()} {size} (目标: {target[:8]}...)")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_copy_open(
                target_address=target,
                symbol=symbol,
                side=side,
                size=size
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def on_close_callback(tracking_id: int, target: str, symbol: str, pnl: float):
    """平仓回调"""
    emoji = "+" if pnl >= 0 else ""
    logger.info(f"[#{tracking_id}] 平仓: {symbol} PnL: ${emoji}{pnl:.2f} (目标: {target[:8]}...)")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_copy_close(
                target_address=target,
                symbol=symbol,
                pnl=pnl
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def on_error_callback(error: Exception):
    """错误回调"""
    logger.error(f"错误: {error}")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_error(str(error))
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def on_adjust_callback(tracking_id: int, target: str, symbol: str, side: str, size: float, is_increase: bool):
    """调整仓位回调（加仓/减仓）"""
    action = "加仓" if is_increase else "减仓"
    logger.info(f"[#{tracking_id}] {action}: {symbol} {side.upper()} {size} (目标: {target[:8]}...)")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_copy_adjust(
                target_address=target,
                symbol=symbol,
                side=side,
                size=size,
                is_increase=is_increase
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def start_callback_server():
    """启动飞书长连接回调服务（使用新仓位推送专用配置）"""
    # 检查配置（使用 feishu_position 配置）
    if not settings.feishu_position.app_id or not settings.feishu_position.app_secret:
        logger.error("错误: 请配置飞书新仓位推送 FEISHU_POSITION_APP_ID 和 FEISHU_POSITION_APP_SECRET")
        return
    
    # 创建回调客户端（使用 feishu_position 配置）
    callback_client = FeishuCallbackClient(
        app_id=settings.feishu_position.app_id,
        app_secret=settings.feishu_position.app_secret,
        push_url=settings.feishu_position.callback_push_url,
        log_level=settings.feishu_position.callback_log_level
    )
    
    # 注册全局日志处理器
    def log_all_events(event: CardActionEvent):
        logger.debug(f"[事件日志] action={event.action_tag}, user={event.user_id}, value={event.action_value}")
        return None
    
    callback_client.register_global_handler(log_all_events)
    
    # 启动长连接（阻塞模式）
    logger.info("=" * 50)
    logger.info("飞书长连接回调服务（新仓位推送）")
    logger.info("=" * 50)
    logger.info(f"APP_ID: {settings.feishu_position.app_id[:8]}...")
    logger.info("-" * 50)
    logger.info("正在启动长连接...")
    
    callback_client.start()


async def run():
    """运行仓位跟单机器人"""
    global notifier, db

    setup_logging()

    logger.info("=" * 60)
    logger.info(f"仓位级别跟单机器人 v{VERSION}")
    logger.info("第二种跟单模式：跟单特定仓位")
    logger.info("=" * 60)

    # 初始化数据库
    db = TraderDatabase()

    # 初始化飞书通知器
    notifier = setup_feishu_notifier()
    
    # 初始化 Redis（用于发送/接收开仓通知）
    setup_redis_client()

    # 在后台线程启动飞书回调服务（使用 feishu_position 配置）
    if settings.feishu_position.app_id and settings.feishu_position.app_secret:
        logger.info("启动飞书回调服务...")
        callback_thread = threading.Thread(target=start_callback_server, daemon=True)
        callback_thread.start()
    else:
        logger.warning("飞书新仓位推送未配置，跳过回调服务")

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

    # 设置回调
    bot.set_on_copy(on_copy_callback)
    bot.set_on_close(on_close_callback)
    bot.set_on_adjust(on_adjust_callback)
    bot.set_on_error(on_error_callback)

    logger.info("启动仓位跟单机器人...")
    logger.info("在 Web 持仓页面点击'跟单此仓位'按钮添加跟单")
    logger.info("或通过飞书消息卡片点击'跟单此仓位'按钮")
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
