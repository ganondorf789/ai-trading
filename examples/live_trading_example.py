"""
实盘交易示例
演示如何使用 Hyperliquid 进行实盘交易
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime
from loguru import logger

from config import settings
from clients import HyperliquidClient
from strategies import SMAStrategy, RSIStrategy
from strategies.base import StrategyConfig
from engine import LiveEngine, LiveEngineConfig
from risk import RiskManager, RiskConfig
from core.models import Signal, SignalType


async def simple_live_trading():
    """
    简单实盘交易示例
    
    使用模拟模式运行，不实际下单
    """
    logger.info("启动简单实盘交易示例（模拟模式）")
    
    # 创建客户端（不需要私钥，因为是模拟模式）
    client = HyperliquidClient()
    
    # 创建策略
    strategy_config = StrategyConfig(
        name="SMA_Demo",
        symbols=["ETH"],
        timeframe="1h",
        position_size_pct=0.1,
        stop_loss_pct=0.02,
        take_profit_pct=0.04
    )
    
    strategy = SMAStrategy(fast_period=10, slow_period=30, config=strategy_config)
    
    # 创建引擎配置
    engine_config = LiveEngineConfig(
        symbols=["ETH"],
        timeframe="1h",
        update_interval=60.0,  # 每60秒更新
        leverage=5,
        dry_run=True  # 模拟模式
    )
    
    # 创建引擎
    engine = LiveEngine(client, strategy, engine_config)
    
    # 设置信号回调
    def on_signal(signal: Signal):
        logger.info(f"[{datetime.now()}] 信号: {signal.signal_type.value}")
        logger.info(f"  价格: {signal.price}")
        if signal.stop_loss:
            logger.info(f"  止损: {signal.stop_loss}")
        if signal.take_profit:
            logger.info(f"  止盈: {signal.take_profit}")
        if signal.metadata:
            logger.info(f"  原因: {signal.metadata.get('reason', 'N/A')}")
    
    engine.set_on_signal(on_signal)
    
    # 运行引擎（运行5分钟后停止）
    async def run_with_timeout():
        task = asyncio.create_task(engine.run())
        await asyncio.sleep(300)  # 运行5分钟
        engine.stop()
        await task
    
    logger.info("开始运行（将在5分钟后自动停止）...")
    await run_with_timeout()


async def live_trading_with_risk_management():
    """
    带风险管理的实盘交易示例
    """
    logger.info("启动带风险管理的实盘交易示例")
    
    # 检查私钥配置
    private_key = os.getenv("HYPERLIQUID_PRIVATE_KEY")
    
    if not private_key:
        logger.warning("未设置私钥，将使用模拟模式")
        dry_run = True
        client = HyperliquidClient()
    else:
        dry_run = False
        # 使用测试网
        client = HyperliquidClient(
            private_key=private_key,
            testnet=True  # 使用测试网！
        )
    
    # 创建策略
    strategy = RSIStrategy(
        period=14,
        overbought=70,
        oversold=30
    )
    strategy.config.symbols = ["ETH"]
    strategy.config.position_size_pct = 0.1
    
    # 创建风险管理器
    risk_config = RiskConfig(
        max_drawdown_percent=0.1,  # 最大回撤10%
        max_daily_loss_percent=0.05,  # 每日最大亏损5%
        max_daily_loss_usd=500.0,  # 每日最大亏损$500
        max_position_size_usd=1000.0,  # 单仓最大$1000
        max_positions=2,  # 最多2个仓位
        max_consecutive_losses=3,  # 最多连续亏损3次
        max_trades_per_day=10  # 每日最多10笔交易
    )
    
    risk_manager = RiskManager(risk_config)
    
    # 初始化风险管理器
    if not dry_run:
        account = client.get_account_info()
        risk_manager.initialize(account.equity)
    else:
        risk_manager.initialize(10000.0)  # 模拟账户$10000
    
    # 创建引擎
    engine_config = LiveEngineConfig(
        symbols=["ETH"],
        timeframe="15m",  # 15分钟周期
        update_interval=60.0,
        leverage=5,
        dry_run=dry_run
    )
    
    engine = LiveEngine(client, strategy, engine_config)
    
    # 风险检查函数
    def risk_check(signal: Signal) -> bool:
        positions = client.get_positions() if not dry_run else []
        
        # 更新账户权益
        if not dry_run:
            account = client.get_account_info()
            risk_manager.update_equity(account.equity)
        
        # 检查信号
        passed = risk_manager.check_signal(signal, positions)
        
        if not passed:
            logger.warning(f"信号未通过风险检查: {risk_manager.state.warnings}")
        
        return passed
    
    engine.set_risk_check(risk_check)
    
    # 信号回调
    def on_signal(signal: Signal):
        status = risk_manager.get_status()
        logger.info(f"信号: {signal.signal_type.value} @ {signal.price}")
        logger.info(f"风险状态: {status['risk_level']}, 回撤: {status['current_drawdown']}")
    
    def on_error(error: Exception):
        logger.error(f"交易错误: {error}")
        # 可以在这里发送通知
    
    engine.set_on_signal(on_signal)
    engine.set_on_error(on_error)
    
    # 运行
    logger.info("开始运行...")
    logger.info(f"模式: {'模拟' if dry_run else '实盘（测试网）'}")
    
    try:
        await engine.run()
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        engine.stop()


async def monitor_and_alert():
    """
    市场监控和告警示例
    """
    logger.info("启动市场监控")
    
    client = HyperliquidClient()
    
    # 监控的交易对
    symbols = ["BTC", "ETH", "SOL"]
    
    # 价格缓存
    price_cache = {}
    
    def on_price_update(message):
        """价格更新回调"""
        if 'data' in message and 'mids' in message['data']:
            mids = message['data']['mids']
            
            for symbol in symbols:
                if symbol in mids:
                    new_price = float(mids[symbol])
                    
                    if symbol in price_cache:
                        old_price = price_cache[symbol]
                        change = (new_price - old_price) / old_price
                        
                        # 如果价格变化超过1%，发出告警
                        if abs(change) > 0.01:
                            direction = "上涨" if change > 0 else "下跌"
                            logger.warning(
                                f"⚠️ {symbol} 价格{direction} {abs(change)*100:.2f}%! "
                                f"当前价格: {new_price}"
                            )
                    
                    price_cache[symbol] = new_price
    
    # 订阅价格更新
    client.subscribe_all_mids(on_price_update)
    
    logger.info(f"开始监控: {symbols}")
    logger.info("按 Ctrl+C 停止")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("监控已停止")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="实盘交易示例")
    parser.add_argument(
        "--mode", 
        choices=["simple", "risk", "monitor"],
        default="simple",
        help="运行模式"
    )
    
    args = parser.parse_args()
    
    if args.mode == "simple":
        asyncio.run(simple_live_trading())
    elif args.mode == "risk":
        asyncio.run(live_trading_with_risk_management())
    elif args.mode == "monitor":
        asyncio.run(monitor_and_alert())


if __name__ == "__main__":
    main()

