"""
跟单机器人

从数据库加载跟单配置，支持同时跟单多个交易者
使用前请先在 Web 跟单管理页面添加并启用跟单地址
"""
import asyncio
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from clients.feishu_client import FeishuClient, CopyTradingNotifier
from engine.copy_trading import MultiTargetCopyTradingBot
from config.settings import settings


# 全局通知器
notifier: CopyTradingNotifier = None


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    logger.add(
        f"logs/copy_trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        rotation="1 day",
        level="DEBUG"
    )


def setup_feishu_notifier() -> CopyTradingNotifier:
    """初始化飞书通知器"""
    feishu_client = FeishuClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        webhook_url=settings.feishu.webhook_url,
        default_user_id=settings.feishu.default_user_id
    )

    # 检查是否配置了飞书
    if settings.feishu.webhook_url:
        logger.info("飞书 Webhook 已配置")
    elif settings.feishu.app_id and settings.feishu.app_secret:
        logger.info("飞书应用已配置")
    else:
        logger.warning("飞书未配置，将不会发送通知")

    return CopyTradingNotifier(feishu_client)


def on_copy_callback(target: str, symbol: str, side: str, size: float):
    """复制交易回调"""
    logger.success(f"[{target[:8]}] 复制成功: {symbol} {side.upper()} {size}")

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


def on_close_callback(target: str, symbol: str, pnl: float):
    """平仓回调"""
    emoji = "+" if pnl >= 0 else ""
    logger.info(f"[{target[:8]}] 平仓: {symbol} PnL: ${emoji}{pnl:.2f}")

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


async def run():
    """运行多目标跟单机器人"""
    global notifier

    setup_logging()

    # 是否启用模拟模式（无需私钥）
    DRY_RUN_MODE = True

    logger.info("=" * 60)
    logger.info("Hyperliquid 跟单机器人")
    logger.info("=" * 60)
    logger.info("")
    logger.info("使用说明:")
    logger.info("  1. 启动 Web 服务: python api_server.py")
    logger.info("  2. 访问跟单管理页面添加目标地址")
    logger.info("  3. 配置跟单参数并启用")
    logger.info("  4. 运行此脚本开始跟单")
    logger.info("")

    # 初始化飞书通知器
    notifier = setup_feishu_notifier()

    # 初始化客户端（模拟模式下可以不需要私钥）
    client = None
    if not DRY_RUN_MODE:
        # 实盘模式需要私钥
        if not settings.hyperliquid.private_key:
            logger.error("实盘模式需要配置 HYPERLIQUID_PRIVATE_KEY")
            return
        client = HyperliquidClient(
            private_key=settings.hyperliquid.private_key,
            testnet=settings.system.testnet_mode
        )
    else:
        logger.info("[模拟模式] 无需配置私钥")

    # 创建多目标跟单机器人
    bot = MultiTargetCopyTradingBot(
        client=client,
        db_path="data/traders.db",
        global_dry_run=DRY_RUN_MODE,  # 全局模拟模式，设为 False 进行实盘
        check_interval=10.0,  # 检查间隔（秒）
        reload_interval=60.0  # 配置重载间隔（秒）
    )

    # 设置回调
    bot.set_on_copy(on_copy_callback)
    bot.set_on_close(on_close_callback)
    bot.set_on_error(on_error_callback)

    logger.info("启动跟单机器人...")
    logger.info("按 Ctrl+C 停止\n")

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("\n收到停止信号")
        bot.stop()

    # 显示统计
    status = bot.get_status()
    logger.info("\n运行统计:")
    logger.info(f"  跟单目标数: {status['target_count']}")
    logger.info(f"  总复制次数: {status['total_stats']['total_copies_today']}")
    logger.info(f"  成功: {status['total_stats']['successful_copies']}")
    logger.info(f"  失败: {status['total_stats']['failed_copies']}")
    logger.info(f"  总PnL: ${status['total_stats']['daily_pnl']:.2f}")

    # 发送状态摘要到飞书
    if notifier:
        try:
            notifier.notify_status(
                target_count=status['target_count'],
                total_copies=status['total_stats']['total_copies_today'],
                successful=status['total_stats']['successful_copies'],
                failed=status['total_stats']['failed_copies'],
                daily_pnl=status['total_stats']['daily_pnl']
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")

    if status['targets']:
        logger.info("\n各目标统计:")
        for target in status['targets']:
            logger.info(
                f"  {target['address'][:10]}... | "
                f"复制: {target['copies_today']} | "
                f"成功: {target['successful']} | "
                f"PnL: ${target['daily_pnl']:.2f}"
            )


if __name__ == "__main__":
    asyncio.run(run())
