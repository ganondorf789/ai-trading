"""
回测示例
演示如何使用 Birdeye 历史数据进行策略回测
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime, timedelta
from loguru import logger

from clients import BirdeyeClient, HyperliquidClient
from strategies import SMAStrategy, RSIStrategy, MACDStrategy, BollingerBandsStrategy, CombinedStrategy
from engine import BacktestEngine, BacktestConfig
from core.models import OHLCVDataFrame


async def backtest_with_birdeye():
    """
    使用 Birdeye 数据进行回测
    
    适用于 Solana 链上代币
    """
    # Birdeye API Key
    api_key = os.getenv("BIRDEYE_API_KEY", "your_api_key")
    
    if api_key == "your_api_key":
        logger.warning("请设置 BIRDEYE_API_KEY 环境变量")
        return
    
    # 创建客户端
    client = BirdeyeClient(api_key)
    
    # SOL 代币地址
    sol_address = "So11111111111111111111111111111111111111112"
    
    # 获取历史数据
    logger.info("从 Birdeye 获取历史数据...")
    
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
        
        # 创建策略
        strategy = SMAStrategy(fast_period=10, slow_period=30)
        
        # 创建回测引擎
        engine = BacktestEngine(BacktestConfig(
            initial_capital=10000.0,
            commission_rate=0.0006,
            leverage=1
        ))
        
        # 运行回测
        result = engine.run(strategy, data, "SOL")
        
        # 输出结果
        print(result.summary())
        
    finally:
        await client.close()


def backtest_with_hyperliquid():
    """
    使用 Hyperliquid 数据进行回测
    
    适用于 Hyperliquid 上的永续合约
    """
    # 创建客户端（不需要私钥，只获取数据）
    client = HyperliquidClient()
    
    # 获取历史数据
    symbol = "ETH"
    
    logger.info(f"从 Hyperliquid 获取 {symbol} 历史数据...")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=60)  # 60天数据
    
    data = client.get_candles_dataframe(
        symbol=symbol,
        interval="1h",
        start_time=start_time,
        end_time=end_time
    )
    
    logger.info(f"获取到 {len(data)} 条数据")
    
    # 创建多个策略进行对比
    strategies = [
        SMAStrategy(fast_period=10, slow_period=30),
        RSIStrategy(period=14, overbought=70, oversold=30),
        MACDStrategy(fast_period=12, slow_period=26, signal_period=9),
        BollingerBandsStrategy(period=20, std_dev=2.0)
    ]
    
    # 创建回测引擎
    engine = BacktestEngine(BacktestConfig(
        initial_capital=10000.0,
        commission_rate=0.0006,
        slippage=0.0001,
        leverage=5,  # 5倍杠杆
        allow_short=True
    ))
    
    # 运行回测
    results = engine.run_multiple(strategies, data, symbol)
    
    # 输出结果
    print("\n" + "=" * 60)
    print("各策略回测结果")
    print("=" * 60)
    
    for result in results:
        print(result.summary())
    
    # 比较策略
    print("\n策略对比表:")
    comparison = engine.compare_strategies(results)
    print(comparison.to_string())
    
    return results


def backtest_combined_strategy():
    """
    组合策略回测
    
    结合多个策略信号进行交易决策
    """
    # 创建客户端
    client = HyperliquidClient()
    
    # 获取数据
    symbol = "BTC"
    
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
    
    # 创建子策略
    sub_strategies = [
        SMAStrategy(fast_period=10, slow_period=30),
        RSIStrategy(period=14),
        MACDStrategy()
    ]
    
    # 创建组合策略（至少2个策略同意才交易）
    combined = CombinedStrategy(
        strategies=sub_strategies,
        min_agreement=2
    )
    
    # 创建回测引擎
    engine = BacktestEngine(BacktestConfig(
        initial_capital=10000.0,
        leverage=3
    ))
    
    # 运行回测
    result = engine.run(combined, data, symbol)
    
    print(result.summary())
    
    return result


def main():
    """主函数"""
    print("=" * 60)
    print("回测示例")
    print("=" * 60)
    
    print("\n1. 使用 Hyperliquid 数据回测")
    print("-" * 40)
    backtest_with_hyperliquid()
    
    print("\n2. 组合策略回测")
    print("-" * 40)
    backtest_combined_strategy()
    
    # 如果设置了 Birdeye API Key，也运行 Birdeye 回测
    if os.getenv("BIRDEYE_API_KEY"):
        print("\n3. 使用 Birdeye 数据回测")
        print("-" * 40)
        asyncio.run(backtest_with_birdeye())


if __name__ == "__main__":
    main()

