"""
跟单机器人示例

演示如何使用 CopyTradingBot 跟单目标交易者
"""
import asyncio
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from engine.copy_trading import CopyTradingBot, CopyTradingConfig
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
        f"logs/copy_trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        rotation="1 day",
        level="DEBUG"
    )


def on_copy_callback(symbol: str, side: str, size: float):
    """复制交易回调"""
    logger.success(f"✅ 复制成功: {symbol} {side.upper()} {size}")


def on_close_callback(symbol: str, pnl: float):
    """平仓回调"""
    emoji = "🟢" if pnl >= 0 else "🔴"
    logger.info(f"{emoji} 平仓: {symbol} PnL: ${pnl:.2f}")


def on_error_callback(error: Exception):
    """错误回调"""
    logger.error(f"❌ 错误: {error}")


async def run_copy_trading_demo():
    """运行跟单机器人演示"""
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("Hyperliquid 跟单机器人 Demo")
    logger.info("=" * 60)
    
    # ==================== 配置 ====================
    
    # 目标交易者地址（需要替换为真实地址）
    # 可以在 Hyperliquid 官网找到知名交易者的地址
    TARGET_ADDRESS = os.getenv(
        "COPY_TARGET_ADDRESS",
        "0x..."  # 替换为目标交易者地址
    )
    
    # 跟单配置
    config = CopyTradingConfig(
        # 目标设置
        target_address=TARGET_ADDRESS,
        
        # 跟单比例和限制
        copy_ratio=0.1,  # 跟单 10% 的仓位
        max_position_size_usd=500.0,  # 单个仓位最大 $500
        min_position_size_usd=20.0,  # 忽略小于 $20 的仓位
        
        # 币种过滤（可选）
        symbols_whitelist=[],  # 空 = 不限制
        symbols_blacklist=["SHIB", "DOGE"],  # 不跟单这些币
        
        # 杠杆设置
        copy_leverage=True,  # 复制目标的杠杆
        max_leverage=5,  # 最大杠杆限制
        default_leverage=3,  # 默认杠杆
        
        # 频率控制
        check_interval=10.0,  # 每 10 秒检查一次
        order_delay=0.5,  # 下单延迟 0.5 秒
        
        # 风控
        max_total_positions=5,  # 最多 5 个仓位
        max_daily_trades=20,  # 每天最多 20 笔交易
        slippage=0.02,  # 2% 滑点容忍
        
        # 模式
        dry_run=True,  # 模拟模式（不实际下单）
    )
    
    # ==================== 初始化 ====================
    
    # 初始化客户端
    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key or None,
        testnet=settings.system.testnet_mode
    )
    
    # 如果没有私钥，只能模拟运行
    if not settings.hyperliquid.private_key:
        logger.warning("未配置私钥，将以只读模式运行")
        config.dry_run = True
    
    # 创建跟单机器人
    bot = CopyTradingBot(client, config)
    
    # 设置回调
    bot.set_on_copy(on_copy_callback)
    bot.set_on_close(on_close_callback)
    bot.set_on_error(on_error_callback)
    
    # ==================== 运行 ====================
    
    # 先显示目标交易者的当前持仓
    logger.info("\n📊 目标交易者当前持仓:")
    target_positions = bot._get_target_positions()
    
    if target_positions:
        for symbol, pos in target_positions.items():
            emoji = "🟢" if pos['side'] == 'long' else "🔴"
            logger.info(
                f"  {emoji} {symbol}: {pos['side'].upper()} "
                f"{abs(pos['size'])} @ {pos['entry_price']:.2f} "
                f"(x{pos['leverage']}) PnL: ${pos['unrealized_pnl']:.2f}"
            )
    else:
        logger.info("  无持仓")
    
    # 显示目标交易者的最近成交
    logger.info("\n📈 目标交易者最近成交:")
    recent_fills = bot.get_target_fills(5)
    
    for fill in recent_fills:
        emoji = "🟢" if fill['side'] == 'buy' else "🔴"
        logger.info(
            f"  {emoji} {fill['symbol']}: {fill['side'].upper()} "
            f"{fill['size']} @ {fill['price']:.2f} "
            f"({fill['time']})"
        )
    
    if not recent_fills:
        logger.info("  无最近成交")
    
    # 开始跟单
    logger.info("\n🚀 开始跟单...")
    logger.info("按 Ctrl+C 停止\n")
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("\n收到停止信号")
        bot.stop()
    
    # 显示统计
    status = bot.get_status()
    logger.info("\n📊 运行统计:")
    logger.info(f"  总复制次数: {status['stats']['total_copies_today']}")
    logger.info(f"  成功: {status['stats']['successful_copies']}")
    logger.info(f"  失败: {status['stats']['failed_copies']}")
    logger.info(f"  当日PnL: ${status['stats']['daily_pnl']:.2f}")


async def monitor_trader():
    """
    监控模式：只查看目标交易者的持仓和成交，不执行交易
    
    适合观察交易者的风格和表现
    """
    setup_logging()
    
    TARGET_ADDRESS = os.getenv(
        "COPY_TARGET_ADDRESS",
        "0x..."  # 替换为目标交易者地址
    )
    
    config = CopyTradingConfig(
        target_address=TARGET_ADDRESS,
        check_interval=30.0,  # 30 秒检查一次
        dry_run=True,
    )
    
    client = HyperliquidClient(testnet=settings.system.testnet_mode)
    bot = CopyTradingBot(client, config)
    
    logger.info(f"开始监控交易者: {TARGET_ADDRESS}")
    logger.info("按 Ctrl+C 停止\n")
    
    prev_positions = {}
    
    try:
        while True:
            positions = bot._get_target_positions()
            
            # 检测变化
            for symbol, pos in positions.items():
                if symbol not in prev_positions:
                    logger.info(f"🆕 新仓位: {symbol} {pos['side'].upper()} {abs(pos['size'])}")
                elif pos['side'] != prev_positions[symbol]['side']:
                    logger.info(f"🔄 方向变化: {symbol} -> {pos['side'].upper()}")
            
            for symbol in prev_positions:
                if symbol not in positions:
                    logger.info(f"❌ 平仓: {symbol}")
            
            prev_positions = positions
            
            # 显示当前状态
            if positions:
                total_pnl = sum(p['unrealized_pnl'] for p in positions.values())
                logger.info(
                    f"📊 持仓: {len(positions)} 个 | "
                    f"总未实现PnL: ${total_pnl:.2f}"
                )
            
            await asyncio.sleep(config.check_interval)
    
    except KeyboardInterrupt:
        logger.info("\n监控停止")


async def list_top_traders():
    """
    列出一些可以跟单的示例地址
    
    注意：这些地址仅作示例，实际跟单前请自行研究
    """
    logger.info("=" * 60)
    logger.info("Hyperliquid 热门交易者（示例）")
    logger.info("=" * 60)
    logger.info("")
    logger.info("💡 如何找到交易者地址：")
    logger.info("1. 访问 https://app.hyperliquid.xyz/leaderboard")
    logger.info("2. 点击感兴趣的交易者")
    logger.info("3. 复制其钱包地址")
    logger.info("")
    logger.info("⚠️ 风险提示：")
    logger.info("- 过去的表现不代表未来收益")
    logger.info("- 始终使用模拟模式测试")
    logger.info("- 设置合理的仓位限制")
    logger.info("- 不要投入超出承受能力的资金")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="跟单机器人示例")
    parser.add_argument(
        "--mode",
        choices=["copy", "monitor", "list"],
        default="copy",
        help="运行模式：copy=跟单，monitor=监控，list=列出示例"
    )
    
    args = parser.parse_args()
    
    if args.mode == "copy":
        asyncio.run(run_copy_trading_demo())
    elif args.mode == "monitor":
        asyncio.run(monitor_trader())
    elif args.mode == "list":
        asyncio.run(list_top_traders())

