"""
跟单机器人

通过轮询目标交易者的持仓变化进行跟单
从数据库加载跟单配置，支持同时跟单多个交易者
使用前请先在 Web 跟单管理页面添加并启用跟单地址
"""

VERSION = "1.1.0"
import asyncio
import os
import sys
import pendulum

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from engine.copy_trading import MultiTargetCopyTradingBot
from config.settings import settings


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    logger.add(
        f"logs/copy_trading_{pendulum.now().format('YYYYMMDD_HHmmss')}.log",
        rotation="1 day",
        level="DEBUG"
    )


def on_copy_callback(target: str, symbol: str, side: str, size: float):
    """复制交易回调"""
    logger.success(f"[{target[:8]}] 复制成功: {symbol} {side.upper()} {size}")


def on_close_callback(target: str, symbol: str, pnl: float):
    """平仓回调"""
    emoji = "+" if pnl >= 0 else ""
    logger.info(f"[{target[:8]}] 平仓: {symbol} PnL: ${emoji}{pnl:.2f}")


def on_error_callback(error: Exception):
    """错误回调"""
    logger.error(f"错误: {error}")


def on_adjust_callback(target: str, symbol: str, side: str, size: float, is_increase: bool):
    """调整仓位回调（加仓/减仓）"""
    action = "加仓" if is_increase else "减仓"
    logger.info(f"[{target[:8]}] {action}: {symbol} {side.upper()} {size}")


async def run():
    """运行多目标跟单机器人"""
    setup_logging()

    logger.info("=" * 60)
    logger.info(f"Hyperliquid 跟单机器人 v{VERSION}")
    logger.info("=" * 60)

    # 初始化客户端
    if not settings.hyperliquid.private_key:
        logger.error("需要配置 HYPERLIQUID_PRIVATE_KEY")
        return

    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key,
        wallet_address=settings.hyperliquid.wallet_address,
        testnet=settings.system.testnet_mode
    )

    # 创建多目标跟单机器人
    bot = MultiTargetCopyTradingBot(
        client=client,
        check_interval=10.0,  # 检查间隔（秒）
        reload_interval=60.0,  # 配置重载间隔（秒）
    )

    # 设置回调
    bot.set_on_copy(on_copy_callback)
    bot.set_on_close(on_close_callback)
    bot.set_on_adjust(on_adjust_callback)
    bot.set_on_error(on_error_callback)

    logger.info("启动跟单机器人...")
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
        logger.info(f"  跟单目标数: {status['target_count']}")
        if status.get('locked_target'):
            logger.info(f"  锁定交易员: {status['locked_target'][:10]}...")
        logger.info(f"  总复制次数: {status['total_stats']['total_copies_today']}")
        logger.info(f"  成功: {status['total_stats']['successful_copies']}")
        logger.info(f"  失败: {status['total_stats']['failed_copies']}")
        logger.info(f"  总PnL: ${status['total_stats']['daily_pnl']:.2f}")

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
    import signal
    import sys

    # Windows 上需要特殊处理
    if sys.platform == "win32":
        # 设置事件循环策略
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    finally:
        # 强制退出，避免后台线程阻塞
        import os
        os._exit(0)
