"""
回测示例
演示如何使用历史数据进行策略回测，包括新增的6个高级策略
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timedelta
from loguru import logger

from clients import BirdeyeClient, HyperliquidClient
from strategies import (
    # 原有基础策略
    SMAStrategy, RSIStrategy, MACDStrategy, BollingerBandsStrategy, CombinedStrategy,
    # 新增高级策略
    SuperTrendStrategy,
    VolumeBreakoutStrategy,
    MomentumTrendStrategy,
    MeanReversionATRStrategy,
    TripleScreenStrategy,
    SmartMoneyStrategy
)
from engine import BacktestEngine, BacktestConfig
from core.models import OHLCVDataFrame


def backtest_new_strategies():
    """
    回测6个新增高级策略
    
    使用 ETH 数据对比新策略与旧策略的表现
    """
    # 创建客户端
    client = HyperliquidClient()
    
    # 获取历史数据
    symbol = "ETH"
    
    logger.info(f"从 Hyperliquid 获取 {symbol} 历史数据...")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=90)  # 90天数据
    
    data = client.get_candles_dataframe(
        symbol=symbol,
        interval="1h",
        start_time=start_time,
        end_time=end_time
    )
    
    logger.info(f"获取到 {len(data)} 条数据")
    
    # ========== 新增的6个高级策略 ==========
    new_strategies = [
        # 1. SuperTrend策略 - 基于ATR的趋势跟踪
        SuperTrendStrategy(
            atr_period=10,
            atr_multiplier=3.0
        ),
        
        # 2. 成交量确认突破策略
        VolumeBreakoutStrategy(
            lookback_period=20,
            volume_multiplier=1.5,
            atr_period=14
        ),
        
        # 3. 动量趋势策略 - EMA + ADX + RSI
        MomentumTrendStrategy(
            ema_fast=8,
            ema_slow=21,
            ema_trend=50,
            adx_threshold=25
        ),
        
        # 4. 改进版均值回归策略
        MeanReversionATRStrategy(
            lookback=20,
            z_threshold=2.0,
            rsi_oversold=25,
            rsi_overbought=75
        ),
        
        # 5. 三重滤网策略
        TripleScreenStrategy(
            trend_ema=50,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            breakout_period=5
        ),
        
        # 6. 聪明资金策略
        SmartMoneyStrategy(
            structure_lookback=10,
            liquidity_threshold=0.005,
            atr_period=14
        ),
    ]
    
    # 创建回测引擎
    engine = BacktestEngine(BacktestConfig(
        initial_capital=10000.0,
        commission_rate=0.0006,  # 0.06% 手续费
        slippage=0.0001,         # 0.01% 滑点
        leverage=5,              # 5倍杠杆
        allow_short=True         # 允许做空
    ))
    
    # 运行回测
    results = engine.run_multiple(new_strategies, data, symbol)
    
    # 输出结果
    print("\n" + "=" * 70)
    print("🚀 新增高级策略回测结果")
    print("=" * 70)
    
    for result in results:
        print(result.summary())
    
    # 比较策略
    print("\n📊 策略对比表:")
    comparison = engine.compare_strategies(results)
    print(comparison.to_string())
    
    return results


def backtest_all_strategies():
    """
    回测所有策略（包括原有策略和新策略）进行全面对比
    """
    # 创建客户端
    client = HyperliquidClient()
    
    symbol = "ETH"
    
    logger.info(f"从 Hyperliquid 获取 {symbol} 历史数据...")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=90)
    
    data = client.get_candles_dataframe(
        symbol=symbol,
        interval="1h",
        start_time=start_time,
        end_time=end_time
    )
    
    logger.info(f"获取到 {len(data)} 条数据")
    
    # 所有策略
    all_strategies = [
        # 原有基础策略
        SMAStrategy(fast_period=10, slow_period=30),
        RSIStrategy(period=14, overbought=70, oversold=30),
        MACDStrategy(fast_period=12, slow_period=26, signal_period=9),
        BollingerBandsStrategy(period=20, std_dev=2.0),
        
        # 新增高级策略
        SuperTrendStrategy(atr_period=10, atr_multiplier=3.0),
        VolumeBreakoutStrategy(lookback_period=20, volume_multiplier=1.5),
        MomentumTrendStrategy(ema_fast=8, ema_slow=21, adx_threshold=25),
        MeanReversionATRStrategy(z_threshold=2.0),
        TripleScreenStrategy(trend_ema=50),
        SmartMoneyStrategy(structure_lookback=10),
    ]
    
    # 创建回测引擎
    engine = BacktestEngine(BacktestConfig(
        initial_capital=10000.0,
        commission_rate=0.0006,
        slippage=0.0001,
        leverage=5,
        allow_short=True
    ))
    
    # 运行回测
    results = engine.run_multiple(all_strategies, data, symbol)
    
    # 输出结果
    print("\n" + "=" * 70)
    print("📈 所有策略回测结果对比（原有 vs 新增）")
    print("=" * 70)
    
    # 按收益率排序
    sorted_results = sorted(results, key=lambda x: x.total_return, reverse=True)
    
    for i, result in enumerate(sorted_results, 1):
        strategy_type = "🆕 新策略" if result.strategy_name in [
            "SuperTrend", "VolumeBreakout", "MomentumTrend", 
            "MeanReversionATR", "TripleScreen", "SmartMoney"
        ] else "📌 原策略"
        
        print(f"\n{'='*50}")
        print(f"排名 #{i} - {strategy_type}")
        print(result.summary())
    
    # 比较策略
    print("\n" + "=" * 70)
    print("📊 策略对比表（按收益率排序）:")
    print("=" * 70)
    comparison = engine.compare_strategies(sorted_results)
    print(comparison.to_string())
    
    return results


def backtest_combined_new_strategies():
    """
    组合新策略回测
    
    结合多个新策略信号进行交易决策
    """
    # 创建客户端
    client = HyperliquidClient()
    
    symbol = "ETH"
    
    logger.info(f"获取 {symbol} 历史数据...")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=90)
    
    data = client.get_candles_dataframe(
        symbol=symbol,
        interval="4h",  # 4小时周期
        start_time=start_time,
        end_time=end_time
    )
    
    logger.info(f"获取到 {len(data)} 条数据")
    
    # 创建子策略（选择3个最佳的新策略组合）
    sub_strategies = [
        SuperTrendStrategy(atr_period=10, atr_multiplier=3.0),
        MomentumTrendStrategy(ema_fast=8, ema_slow=21, adx_threshold=25),
        TripleScreenStrategy(trend_ema=50),
    ]
    
    # 创建组合策略（至少2个策略同意才交易）
    combined = CombinedStrategy(
        strategies=sub_strategies,
        min_agreement=2
    )
    
    # 创建回测引擎
    engine = BacktestEngine(BacktestConfig(
        initial_capital=10000.0,
        commission_rate=0.0006,
        slippage=0.0001,
        leverage=5,
        allow_short=True
    ))
    
    # 运行回测
    result = engine.run(combined, data, symbol)
    
    print("\n" + "=" * 70)
    print("🔗 组合策略回测结果（SuperTrend + MomentumTrend + TripleScreen）")
    print("=" * 70)
    print(result.summary())
    
    return result


async def backtest_with_birdeye():
    """
    使用 Birdeye 数据进行回测
    
    适用于 Solana 链上代币
    """
    api_key = os.getenv("BIRDEYE_API_KEY", "your_api_key")
    
    if api_key == "your_api_key":
        logger.warning("请设置 BIRDEYE_API_KEY 环境变量")
        return
    
    client = BirdeyeClient(api_key)
    sol_address = "So11111111111111111111111111111111111111112"
    
    logger.info("从 Birdeye 获取 SOL 历史数据...")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=30)
    
    try:
        data = await client.get_ohlcv_dataframe(
            address=sol_address,
            interval="1h",
            start_time=start_time,
            end_time=end_time,
            chain="solana"
        )
        
        logger.info(f"获取到 {len(data)} 条数据")
        
        # 使用新策略
        strategies = [
            SuperTrendStrategy(atr_period=10, atr_multiplier=3.0),
            MomentumTrendStrategy(ema_fast=8, ema_slow=21, adx_threshold=25),
        ]
        
        engine = BacktestEngine(BacktestConfig(
            initial_capital=10000.0,
            commission_rate=0.0006,
            leverage=1
        ))
        
        results = engine.run_multiple(strategies, data, "SOL")
        
        for result in results:
            print(result.summary())
        
    finally:
        await client.close()


def main():
    """主函数"""
    print("=" * 70)
    print("📊 策略回测系统")
    print("=" * 70)
    
    print("\n" + "=" * 70)
    print("1️⃣  回测6个新增高级策略")
    print("=" * 70)
    backtest_new_strategies()
    
    print("\n" + "=" * 70)
    print("2️⃣  所有策略对比（原有 vs 新增）")
    print("=" * 70)
    backtest_all_strategies()
    
    print("\n" + "=" * 70)
    print("3️⃣  组合策略回测")
    print("=" * 70)
    backtest_combined_new_strategies()
    
    # 如果设置了 Birdeye API Key，也运行 Birdeye 回测
    if os.getenv("BIRDEYE_API_KEY"):
        print("\n" + "=" * 70)
        print("4️⃣  使用 Birdeye 数据回测 (SOL)")
        print("=" * 70)
        asyncio.run(backtest_with_birdeye())


if __name__ == "__main__":
    main()

