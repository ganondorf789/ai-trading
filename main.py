"""
自动交易系统主入口
"""
import os
import sys
import asyncio
import argparse
from datetime import datetime, timedelta
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/trading_{time}.log", rotation="1 day", retention="30 days")


def setup_environment():
    """设置环境"""
    # 创建必要目录
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    
    # 加载环境变量
    from dotenv import load_dotenv
    load_dotenv()


def run_backtest(args):
    """运行回测"""
    from config import settings
    from clients import BirdeyeSyncClient, HyperliquidClient
    from strategies import (
        SMAStrategy, RSIStrategy, MACDStrategy, BollingerBandsStrategy,
        SuperTrendStrategy, MomentumBreakoutStrategy, TrendFollowingEMAStrategy,
        ScalpingStrategy, VWAPMomentumStrategy, AdaptiveTrendStrategy
    )
    from engine import BacktestEngine, BacktestConfig

    logger.info("=" * 50)
    logger.info("开始回测")
    logger.info("=" * 50)

    # 配置
    symbol = args.symbol or "ETH"
    days = args.days or 30
    initial_capital = args.capital or 10000.0

    # 获取历史数据
    # 优先使用 Hyperliquid 获取数据（如果可用）
    logger.info(f"获取 {symbol} {days} 天历史数据...")

    client = HyperliquidClient()
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    data = client.get_candles_dataframe(
        symbol,
        args.timeframe or "1h",
        start_time,
        end_time
    )

    logger.info(f"获取到 {len(data)} 条数据")

    # 创建策略
    strategies = []

    if args.strategy == "all" or args.strategy == "sma":
        strategies.append(SMAStrategy(fast_period=10, slow_period=30))

    if args.strategy == "all" or args.strategy == "rsi":
        strategies.append(RSIStrategy(period=14, overbought=70, oversold=30))

    if args.strategy == "all" or args.strategy == "macd":
        strategies.append(MACDStrategy())

    if args.strategy == "all" or args.strategy == "bb":
        strategies.append(BollingerBandsStrategy(period=20, std_dev=2.0))

    # ETH 合约交易优化策略
    if args.strategy == "supertrend":
        strategies.append(SuperTrendStrategy(atr_period=10, multiplier=3.0))

    if args.strategy == "momentum":
        strategies.append(MomentumBreakoutStrategy(breakout_period=20, volume_multiplier=2.0))

    if args.strategy == "ema":
        strategies.append(TrendFollowingEMAStrategy(fast_ema=8, medium_ema=21, slow_ema=55))

    if args.strategy == "scalping":
        strategies.append(ScalpingStrategy(ema_period=9, rsi_period=7))

    if args.strategy == "vwap":
        strategies.append(VWAPMomentumStrategy(vwap_period=20, momentum_period=10))

    if args.strategy == "adaptive":
        strategies.append(AdaptiveTrendStrategy(base_period=20, atr_period=14))

    if not strategies:
        strategies.append(SMAStrategy())
    
    # 创建回测引擎
    backtest_config = BacktestConfig(
        initial_capital=initial_capital,
        commission_rate=0.0006,
        slippage=0.0001,
        leverage=args.leverage or 1,
        allow_short=True
    )
    
    engine = BacktestEngine(backtest_config)
    
    # 运行回测
    results = engine.run_multiple(strategies, data, symbol)
    
    # 输出结果
    for result in results:
        print(result.summary())
    
    # 比较结果
    if len(results) > 1:
        print("\n策略比较:")
        comparison = engine.compare_strategies(results)
        print(comparison.to_string())
    
    return results


async def run_live(args):
    """运行实盘交易"""
    from config import settings
    from clients import HyperliquidClient
    from strategies import (
        SMAStrategy, RSIStrategy, MACDStrategy, BollingerBandsStrategy,
        SuperTrendStrategy, MomentumBreakoutStrategy, TrendFollowingEMAStrategy,
        ScalpingStrategy, VWAPMomentumStrategy, AdaptiveTrendStrategy
    )
    from engine import LiveEngine, LiveEngineConfig
    from risk import RiskManager, RiskConfig

    logger.info("=" * 50)
    logger.info("启动实盘交易")
    logger.info("=" * 50)

    # 验证配置
    if not settings.hyperliquid.private_key and not args.dry_run:
        logger.error("未配置私钥，请设置 HYPERLIQUID_PRIVATE_KEY 环境变量")
        return

    # 创建客户端
    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key if not args.dry_run else None,
        testnet=settings.system.testnet_mode
    )

    # 创建策略
    strategy_map = {
        "sma": lambda: SMAStrategy(fast_period=10, slow_period=30),
        "rsi": lambda: RSIStrategy(),
        "macd": lambda: MACDStrategy(),
        "bb": lambda: BollingerBandsStrategy(period=20, std_dev=2.0),
        "supertrend": lambda: SuperTrendStrategy(atr_period=10, multiplier=3.0),
        "momentum": lambda: MomentumBreakoutStrategy(breakout_period=20, volume_multiplier=2.0),
        "ema": lambda: TrendFollowingEMAStrategy(fast_ema=8, medium_ema=21, slow_ema=55),
        "scalping": lambda: ScalpingStrategy(ema_period=9, rsi_period=7),
        "vwap": lambda: VWAPMomentumStrategy(vwap_period=20, momentum_period=10),
        "adaptive": lambda: AdaptiveTrendStrategy(base_period=20, atr_period=14),
    }

    strategy = strategy_map.get(args.strategy, strategy_map["sma"])()
    
    # 更新策略配置
    strategy.config.symbols = [args.symbol or "ETH"]
    
    # 创建风险管理器
    risk_config = RiskConfig(
        max_drawdown_percent=0.1,
        max_daily_loss_percent=0.05,
        max_position_size_usd=args.max_position or 1000.0,
        max_leverage=args.leverage or 5
    )
    risk_manager = RiskManager(risk_config)
    
    # 创建引擎
    engine_config = LiveEngineConfig(
        symbols=[args.symbol or "ETH"],
        timeframe=args.timeframe or "1h",
        update_interval=args.interval or 60.0,
        leverage=args.leverage or 5,
        dry_run=args.dry_run
    )
    
    engine = LiveEngine(client, strategy, engine_config)
    
    # 设置风险检查
    def risk_check(signal):
        positions = client.get_positions() if not args.dry_run else []
        return risk_manager.check_signal(signal, positions)
    
    engine.set_risk_check(risk_check)
    
    # 设置回调
    def on_signal(signal):
        logger.info(f"信号: {signal.signal_type.value} @ {signal.price}")
    
    def on_error(error):
        logger.error(f"错误: {error}")
    
    engine.set_on_signal(on_signal)
    engine.set_on_error(on_error)
    
    # 运行
    try:
        await engine.run()
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        engine.stop()


def run_monitor(args):
    """运行监控"""
    from clients import HyperliquidClient
    
    logger.info("=" * 50)
    logger.info("启动监控模式")
    logger.info("=" * 50)
    
    client = HyperliquidClient()
    
    symbol = args.symbol or "ETH"
    
    def on_trade(message):
        if 'data' in message:
            for trade in message['data']:
                side = "买入" if trade.get('side') == 'B' else "卖出"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"{symbol} {side} {trade.get('sz')} @ {trade.get('px')}")
    
    def on_orderbook(message):
        if 'data' in message and 'levels' in message['data']:
            bids, asks = message['data']['levels']
            if bids and asks:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"{symbol} 买一: {bids[0]['px']} ({bids[0]['sz']}) | "
                      f"卖一: {asks[0]['px']} ({asks[0]['sz']})")
    
    print(f"开始监控 {symbol}...")
    print("按 Ctrl+C 停止\n")
    
    try:
        client.subscribe_trades(symbol, on_trade)
        
        # 保持运行
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n监控已停止")


def show_account(args):
    """显示账户信息"""
    from config import settings
    from clients import HyperliquidClient
    
    if not settings.hyperliquid.private_key:
        logger.error("未配置私钥")
        return
    
    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key,
        testnet=settings.system.testnet_mode
    )
    
    account = client.get_account_info()
    positions = client.get_positions()
    orders = client.get_open_orders()
    
    print("\n" + "=" * 50)
    print("账户信息")
    print("=" * 50)
    print(f"账户权益: ${account.equity:,.2f}")
    print(f"可用保证金: ${account.available_margin:,.2f}")
    print(f"已用保证金: ${account.used_margin:,.2f}")
    print(f"未实现盈亏: ${account.unrealized_pnl:,.2f}")
    
    if positions:
        print("\n持仓:")
        for pos in positions:
            print(f"  {pos.symbol}: {pos.side.value} {pos.size} @ {pos.entry_price} "
                  f"(PnL: ${pos.unrealized_pnl:,.2f})")
    else:
        print("\n无持仓")
    
    if orders:
        print("\n挂单:")
        for order in orders:
            print(f"  {order.symbol}: {order.side.value} {order.size} @ {order.price}")
    else:
        print("\n无挂单")


async def run_copy_trading(args):
    """运行跟单交易"""
    from config import settings
    from clients import HyperliquidClient
    from engine.copy_trading import CopyTradingBot, CopyTradingConfig
    
    logger.info("=" * 50)
    logger.info("启动跟单机器人")
    logger.info("=" * 50)
    
    if not args.target:
        logger.error("请使用 --target 指定目标交易者地址")
        return
    
    # 验证配置
    if not settings.hyperliquid.private_key and not args.dry_run:
        logger.error("未配置私钥，请设置 HYPERLIQUID_PRIVATE_KEY 环境变量")
        logger.info("可以添加 --dry-run 参数进行模拟运行")
        return
    
    # 创建客户端
    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key if not args.dry_run else None,
        testnet=settings.system.testnet_mode
    )
    
    # 解析白名单和黑名单
    whitelist = args.whitelist.split(",") if args.whitelist else []
    blacklist = args.blacklist.split(",") if args.blacklist else []
    
    # 创建跟单配置
    config = CopyTradingConfig(
        target_address=args.target,
        copy_ratio=args.ratio,
        max_position_size_usd=args.max_position,
        min_position_size_usd=args.min_position,
        symbols_whitelist=whitelist,
        symbols_blacklist=blacklist,
        copy_leverage=args.copy_leverage,
        max_leverage=args.max_leverage,
        default_leverage=args.leverage,
        check_interval=args.interval,
        max_total_positions=args.max_positions,
        max_daily_trades=args.max_trades,
        slippage=args.slippage,
        dry_run=args.dry_run,
    )
    
    # 创建跟单机器人
    bot = CopyTradingBot(client, config)
    
    # 设置回调
    def on_copy(symbol, side, size):
        logger.success(f"✅ 复制成功: {symbol} {side.upper()} {size}")
    
    def on_close(symbol, pnl):
        emoji = "🟢" if pnl >= 0 else "🔴"
        logger.info(f"{emoji} 平仓: {symbol} PnL: ${pnl:.2f}")
    
    def on_error(error):
        logger.error(f"❌ 错误: {error}")
    
    bot.set_on_copy(on_copy)
    bot.set_on_close(on_close)
    bot.set_on_error(on_error)
    
    # 先显示目标交易者信息
    print("\n📊 目标交易者当前持仓:")
    target_positions = bot._get_target_positions()
    
    if target_positions:
        for symbol, pos in target_positions.items():
            emoji = "🟢" if pos['side'] == 'long' else "🔴"
            print(
                f"  {emoji} {symbol}: {pos['side'].upper()} "
                f"{abs(pos['size'])} @ {pos['entry_price']:.2f} "
                f"(x{pos['leverage']}) PnL: ${pos['unrealized_pnl']:.2f}"
            )
    else:
        print("  无持仓")
    
    print("\n🚀 开始跟单...")
    print("按 Ctrl+C 停止\n")
    
    # 运行
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("收到停止信号")
        bot.stop()
    
    # 显示统计
    status = bot.get_status()
    print("\n📊 运行统计:")
    print(f"  总复制次数: {status['stats']['total_copies_today']}")
    print(f"  成功: {status['stats']['successful_copies']}")
    print(f"  失败: {status['stats']['failed_copies']}")
    print(f"  当日PnL: ${status['stats']['daily_pnl']:.2f}")


def main():
    """主函数"""
    setup_environment()
    
    parser = argparse.ArgumentParser(description="自动交易系统")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 策略选项
    backtest_strategies = ["all", "sma", "rsi", "macd", "bb",
                           "supertrend", "momentum", "ema", "scalping", "vwap", "adaptive"]
    live_strategies = ["sma", "rsi", "macd", "bb",
                       "supertrend", "momentum", "ema", "scalping", "vwap", "adaptive"]

    # 回测命令
    backtest_parser = subparsers.add_parser("backtest", help="运行回测")
    backtest_parser.add_argument("--symbol", "-s", default="ETH", help="交易对")
    backtest_parser.add_argument("--strategy", default="all",
                                 choices=backtest_strategies,
                                 help="策略 (supertrend/momentum/ema/scalping/vwap/adaptive 为 ETH 优化策略)")
    backtest_parser.add_argument("--days", "-d", type=int, default=30, help="回测天数")
    backtest_parser.add_argument("--timeframe", "-t", default="1h", help="时间周期")
    backtest_parser.add_argument("--capital", "-c", type=float, default=10000.0,
                                 help="初始资金")
    backtest_parser.add_argument("--leverage", "-l", type=int, default=1, help="杠杆")

    # 实盘命令
    live_parser = subparsers.add_parser("live", help="运行实盘交易")
    live_parser.add_argument("--symbol", "-s", default="ETH", help="交易对")
    live_parser.add_argument("--strategy", default="sma",
                             choices=live_strategies,
                             help="策略 (supertrend/momentum/ema/scalping/vwap/adaptive 为 ETH 优化策略)")
    live_parser.add_argument("--timeframe", "-t", default="1h", help="时间周期")
    live_parser.add_argument("--leverage", "-l", type=int, default=5, help="杠杆")
    live_parser.add_argument("--max-position", type=float, default=1000.0,
                             help="最大仓位价值(USD)")
    live_parser.add_argument("--interval", type=float, default=60.0,
                             help="更新间隔(秒)")
    live_parser.add_argument("--dry-run", action="store_true", help="模拟运行")
    
    # 监控命令
    monitor_parser = subparsers.add_parser("monitor", help="监控市场")
    monitor_parser.add_argument("--symbol", "-s", default="ETH", help="交易对")
    
    # 账户命令
    account_parser = subparsers.add_parser("account", help="显示账户信息")
    
    # 跟单命令
    copy_parser = subparsers.add_parser("copy", help="运行跟单交易")
    copy_parser.add_argument("--target", "-t", required=True,
                             help="目标交易者钱包地址")
    copy_parser.add_argument("--ratio", "-r", type=float, default=0.1,
                             help="跟单比例 (0.1 = 10%%)")
    copy_parser.add_argument("--max-position", type=float, default=500.0,
                             help="单仓位最大价值(USD)")
    copy_parser.add_argument("--min-position", type=float, default=20.0,
                             help="忽略小于此价值的仓位(USD)")
    copy_parser.add_argument("--whitelist", type=str, default="",
                             help="只跟单这些币种(逗号分隔，如 BTC,ETH)")
    copy_parser.add_argument("--blacklist", type=str, default="",
                             help="不跟单这些币种(逗号分隔)")
    copy_parser.add_argument("--copy-leverage", action="store_true", default=True,
                             help="复制目标杠杆")
    copy_parser.add_argument("--no-copy-leverage", dest="copy_leverage", 
                             action="store_false",
                             help="不复制目标杠杆")
    copy_parser.add_argument("--max-leverage", type=int, default=10,
                             help="最大杠杆限制")
    copy_parser.add_argument("--leverage", "-l", type=int, default=5,
                             help="默认杠杆")
    copy_parser.add_argument("--interval", type=float, default=10.0,
                             help="检查间隔(秒)")
    copy_parser.add_argument("--max-positions", type=int, default=10,
                             help="最大持仓数")
    copy_parser.add_argument("--max-trades", type=int, default=50,
                             help="每日最大交易次数")
    copy_parser.add_argument("--slippage", type=float, default=0.01,
                             help="滑点容忍度")
    copy_parser.add_argument("--dry-run", action="store_true",
                             help="模拟运行(不实际下单)")
    
    args = parser.parse_args()
    
    if args.command == "backtest":
        run_backtest(args)
    elif args.command == "live":
        asyncio.run(run_live(args))
    elif args.command == "monitor":
        run_monitor(args)
    elif args.command == "account":
        show_account(args)
    elif args.command == "copy":
        asyncio.run(run_copy_trading(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

