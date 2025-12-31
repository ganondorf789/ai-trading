"""
交易测试脚本
测试下单、加仓、平仓功能
"""
import asyncio
import os
import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from config.settings import settings


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )


def run_test():
    """运行交易测试"""
    setup_logging()

    logger.info("=" * 60)
    logger.info("Hyperliquid 交易测试")
    logger.info("=" * 60)

    # 检查配置
    if not settings.hyperliquid.private_key:
        logger.error("请在 .env 中配置 HYPERLIQUID_PRIVATE_KEY")
        return

    # 初始化客户端
    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key,
        wallet_address=settings.hyperliquid.wallet_address,
        testnet=settings.system.testnet_mode
    )

    logger.info(f"钱包地址: {client.wallet_address}")
    logger.info(f"网络: {'测试网' if settings.system.testnet_mode else '主网'}")

    # 测试参数
    symbol = "AAVE"
    wait_seconds = 5  # 等待 30 秒后平仓

    try:
        # 1. 获取当前价格
        logger.info(f"\n[1] 获取 {symbol} 当前价格...")
        price = client.get_mid_price(symbol)
        if price <= 0:
            logger.error(f"无法获取 {symbol} 价格")
            return
        logger.info(f"{symbol} 当前价格: ${price:.2f}")

        # 2. 查看账户信息
        logger.info("\n[2] 查看账户信息...")
        account = client.get_account_info()
        logger.info(f"账户余额: ${account.balance:.2f}")
        logger.info(f"可用保证金: ${account.available_margin:.2f}")

        # 3. 查看当前持仓
        logger.info("\n[3] 查看当前持仓...")
        positions = client.get_positions()
        logger.info(f"总共 {len(positions)} 个持仓")

        aave_position = None
        for pos in positions:
            logger.info(f"  {pos.symbol}: {pos.size} @ ${pos.entry_price:.2f} | "
                       f"{pos.side.value} | {pos.leverage}x | PnL: ${pos.unrealized_pnl:.2f}")
            if pos.symbol == symbol:
                aave_position = pos

        if not aave_position:
            logger.warning(f"未找到 {symbol} 持仓")
        else:
            logger.info(f"\n{symbol} 持仓详情:")
            logger.info(f"  方向: {aave_position.side.value}")
            logger.info(f"  数量: {aave_position.size}")
            logger.info(f"  开仓价: ${aave_position.entry_price:.2f}")
            logger.info(f"  当前价: ${aave_position.current_price:.2f}")
            logger.info(f"  杠杆: {aave_position.leverage}x")
            logger.info(f"  未实现盈亏: ${aave_position.unrealized_pnl:.2f}")

        # 4. 等待 30 秒
        logger.info(f"\n[4] 等待 {wait_seconds} 秒后平仓...")
        for i in range(wait_seconds, 0, -5):
            logger.info(f"  剩余 {i} 秒...")
            time.sleep(5)

        # 5. 平仓
        logger.info(f"\n[5] 平仓 {symbol}...")
        result = client.close_position(symbol, slippage=0.01)
        if result and result.get('status') == 'ok':
            logger.success(f"平仓成功!")
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            if statuses:
                fill = statuses[0].get('filled', {})
                logger.info(f"  平仓价: ${float(fill.get('avgPx', 0)):.2f}")
                logger.info(f"  平仓量: {fill.get('totalSz', 0)} {symbol}")
                closed_pnl = float(fill.get('closedPnl', 0))
                if closed_pnl >= 0:
                    logger.success(f"  实现盈亏: +${closed_pnl:.2f}")
                else:
                    logger.warning(f"  实现盈亏: ${closed_pnl:.2f}")
        elif result is None:
            logger.warning("平仓返回空结果，可能没有持仓或已平仓")
        else:
            logger.error(f"平仓失败: {result}")

        # 6. 最终账户状态
        logger.info("\n[6] 最终账户状态...")
        account = client.get_account_info()
        logger.info(f"账户余额: ${account.balance:.2f}")
        logger.info(f"可用保证金: ${account.available_margin:.2f}")

        # 确认没有持仓
        positions = client.get_positions()
        aave_pos = [p for p in positions if p.symbol == symbol]
        if not aave_pos:
            logger.success(f"{symbol} 仓位已全部平掉")
        else:
            logger.warning(f"仍有 {symbol} 持仓: {aave_pos[0].size}")

        logger.info("\n" + "=" * 60)
        logger.info("测试完成!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

        # 尝试平仓
        logger.warning("尝试平仓以清理...")
        try:
            client.close_position(symbol)
            logger.info("紧急平仓完成")
        except:
            pass


if __name__ == "__main__":
    # 安全提示
    network = "测试网" if settings.system.testnet_mode else "主网"
    print("\n" + "=" * 60)
    print("警告: 此脚本将平仓现有 AAVE 仓位!")
    print("请确认以下信息:")
    print(f"  - 网络模式: {network}")
    print(f"  - 交易对: AAVE")
    print(f"  - 操作: 等待 30 秒后平仓")
    print("=" * 60)

    confirm = input("\n确认执行? (yes/no): ")
    if confirm.lower() == 'yes':
        run_test()
    else:
        print("已取消")
