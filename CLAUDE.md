# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A cryptocurrency futures auto-trading system using Hyperliquid for live trading and Birdeye for historical data. The system supports multiple technical analysis strategies, backtesting, and live trading with comprehensive risk management.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run backtest (all strategies)
python main.py backtest --symbol ETH --days 30

# Run backtest (single strategy)
python main.py backtest --strategy sma --symbol BTC --days 60 --leverage 5

# Live trading (dry run / simulation)
python main.py live --symbol ETH --strategy sma --dry-run

# Live trading (real)
python main.py live --symbol ETH --strategy rsi --leverage 5

# Monitor market
python main.py monitor --symbol ETH

# View account info
python main.py account

# Run tests
pytest
pytest tests/test_specific.py -v

# Screen quality traders
python screen_traders.py -a 0x1234...           # Analyze single trader
python screen_traders.py -f addresses.txt       # Batch screen from file
python screen_traders.py -f addresses.json --min-win-rate 0.55 --min-pnl 1000
```

## Architecture

### Core Flow
1. **Data Source**: `HyperliquidClient` fetches real-time OHLCV data; `BirdeyeClient` provides historical Solana token data
2. **Strategy**: Extends `BaseStrategy`, implements `calculate_indicators()` and `generate_signal()` methods
3. **Engine**: `BacktestEngine` simulates trades on historical data; `LiveEngine` executes real trades via Hyperliquid
4. **Risk Management**: `RiskManager` validates signals against risk rules before execution

### Key Abstractions

**Signal Flow**: `OHLCVDataFrame` → `Strategy.update()` → `Signal` → `RiskManager.check_signal()` → `Engine.execute()`

**Strategy Interface** (`strategies/base.py`):
- `calculate_indicators(data: OHLCVDataFrame) -> Dict[str, pd.Series]`
- `generate_signal(data, indicators, current_position) -> Signal`
- Built-in helpers: `calculate_stop_loss()`, `calculate_take_profit()`, `calculate_position_size()`

**Data Models** (`core/models.py`):
- `OHLCV`, `OHLCVDataFrame`: Candlestick data with pandas integration
- `Signal`: Trading signals with `SignalType` (BUY/SELL/CLOSE/HOLD)
- `Position`, `Order`, `Trade`: Trade execution models
- `AccountInfo`: Account state including margin and positions

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `config/settings.py` | Pydantic-based settings loaded from `.env` |
| `clients/hyperliquid_client.py` | Trading API: orders, positions, WebSocket subscriptions |
| `clients/birdeye_client.py` | Historical price data for Solana tokens |
| `strategies/examples.py` | SMA, RSI, MACD, Bollinger Bands, Combined strategies |
| `engine/backtest.py` | Historical simulation with metrics (Sharpe, Sortino, drawdown) |
| `engine/live.py` | Live trading loop with `LiveEngineWithWebSocket` variant |
| `risk/manager.py` | Risk checks, position sizing (fixed %, Kelly criterion) |
| `screener/trader_screener.py` | Trader screening with multi-dimensional scoring |
| `screener/address_sources.py` | Trader address discovery and management |

## Configuration

### Database Setup

The project uses PostgreSQL for data storage and Redis for caching. Start the services using Docker:

```bash
# Start PostgreSQL and Redis
docker-compose up -d

# Check service status
docker-compose ps
```

### Environment Variables (`.env`):

```
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=trading
POSTGRES_PASSWORD=trading123
POSTGRES_DATABASE=auto_trading

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Trading APIs
HYPERLIQUID_PRIVATE_KEY=...    # Required for live trading
BIRDEYE_API_KEY=...            # Required for Solana historical data
TESTNET_MODE=True              # Use testnet by default

# AI Models (optional)
AI_MODEL_DEFAULT_PROVIDER=zhipu
AI_MODEL_ZHIPU_API_KEY=...
```

Settings classes use `pydantic-settings` with environment variable prefixes (`POSTGRES_`, `REDIS_`, `HYPERLIQUID_`, `BIRDEYE_`).

## Creating Custom Strategies

```python
from strategies.base import BaseStrategy, StrategyConfig
from core.models import Signal, SignalType, OHLCVDataFrame

class MyStrategy(BaseStrategy):
    def __init__(self, my_param: int = 20):
        config = StrategyConfig(name="MyStrategy")
        config.params["my_param"] = my_param
        super().__init__(config)
        self.my_param = my_param

    def calculate_indicators(self, data: OHLCVDataFrame) -> Dict[str, pd.Series]:
        df = data.df
        return {"indicator": df['close'].rolling(self.my_param).mean()}

    def generate_signal(self, data, indicators, current_position) -> Signal:
        # Return Signal with signal_type, symbol, price, timestamp
        # Optionally include stop_loss, take_profit, strength, metadata
        ...
```

## Risk Management Rules

`RiskManager` enforces:
- Max drawdown (default 10%)
- Daily loss limits (% and USD)
- Max consecutive losses before position reduction
- Trade frequency limits (min interval, max per hour/day)
- Position count limits

Risk level escalation: LOW → MEDIUM → HIGH → CRITICAL (trading paused)

## Hyperliquid Client Key Methods

- `get_candles_dataframe(symbol, interval, start, end)` - Fetch OHLCV data
- `market_order(symbol, is_buy, size)` - Execute market order
- `limit_order(symbol, is_buy, size, price)` - Place limit order
- `stop_order(symbol, is_buy, size, trigger_price)` - Stop loss/take profit
- `set_leverage(symbol, leverage)` - Configure leverage
- `subscribe_trades/orderbook/candles()` - WebSocket subscriptions

## Trader Screening

`TraderScreener` analyzes and scores Hyperliquid traders:

**Metrics Calculated:**
- Win rate, profit factor, total PnL
- Sharpe ratio, Sortino ratio, max drawdown
- Trade frequency, active days, average leverage

**Scoring System (0-100):**
- Profitability (35%): Win rate, profit factor, total profits
- Risk Control (30%): Max drawdown, Sharpe ratio
- Consistency (20%): Trade count, active days
- Activity (15%): Recent trades, current positions

**Quality Ratings:** S (≥85) → A (≥70) → B (≥55) → C (≥40) → D (≥25) → F

```python
from screener.trader_screener import TraderScreener, ScreenerConfig

config = ScreenerConfig(
    min_win_rate=0.55,
    min_profit_factor=1.5,
    min_total_pnl=1000.0,
    max_drawdown=0.3,
    lookback_days=60
)
screener = TraderScreener(config)
qualified = screener.screen_traders(addresses)
```