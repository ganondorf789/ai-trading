# 自动交易系统

基于 Hyperliquid + Birdeye API 的合约自动交易系统。

## 功能特点

- 🚀 **实时交易**: 使用 Hyperliquid API 获取实时行情并执行交易
- 📊 **历史回测**: 使用 Birdeye API 获取历史数据进行策略回测
- 🎯 **多种策略**: 内置 SMA、RSI、MACD、布林带等多种交易策略
- ⚠️ **风险管理**: 完善的风险控制，包括止损止盈、最大回撤、每日亏损限制等
- 📈 **组合策略**: 支持多策略组合，信号投票决策

## 项目结构

```
auto-trading/
├── config/             # 配置管理
│   ├── __init__.py
│   └── settings.py     # 配置类
├── core/               # 核心模型
│   ├── __init__.py
│   └── models.py       # 数据模型
├── clients/            # API 客户端
│   ├── __init__.py
│   ├── birdeye_client.py    # Birdeye API
│   └── hyperliquid_client.py # Hyperliquid API
├── strategies/         # 交易策略
│   ├── __init__.py
│   ├── base.py         # 策略基类
│   └── examples.py     # 示例策略
├── engine/             # 交易引擎
│   ├── __init__.py
│   ├── backtest.py     # 回测引擎
│   └── live.py         # 实盘引擎
├── risk/               # 风险管理
│   ├── __init__.py
│   └── manager.py      # 风险管理器
├── utils/              # 工具函数
│   ├── __init__.py
│   ├── logger.py       # 日志工具
│   └── helpers.py      # 辅助函数
├── examples/           # 示例代码
│   ├── backtest_example.py
│   └── live_trading_example.py
├── main.py             # 主入口
├── requirements.txt    # 依赖
└── README.md
```

## 安装

1. 克隆项目:
```bash
git clone https://github.com/your-repo/auto-trading.git
cd auto-trading
```

2. 创建虚拟环境:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. 安装依赖:
```bash
pip install -r requirements.txt
```

4. 配置环境变量:
```bash
# 复制示例配置
cp .env.example .env
# 编辑 .env 文件，填入你的 API Key
```

## 配置

创建 `.env` 文件并配置以下内容:

```env
# Hyperliquid 配置
HYPERLIQUID_PRIVATE_KEY=your_private_key
HYPERLIQUID_API_URL=https://api.hyperliquid.xyz

# Birdeye 配置
BIRDEYE_API_KEY=your_birdeye_api_key

# 交易配置
DEFAULT_SYMBOL=ETH
DEFAULT_LEVERAGE=5
MAX_POSITION_SIZE_USD=1000

# 风险管理
MAX_DRAWDOWN_PERCENT=0.1
DEFAULT_STOP_LOSS_PERCENT=0.02
DEFAULT_TAKE_PROFIT_PERCENT=0.04

# 系统配置
LOG_LEVEL=INFO
TESTNET_MODE=True
```

## 使用方法

### 1. 运行回测

```bash
# 回测所有策略
python main.py backtest --symbol ETH --days 30

# 回测单个策略
python main.py backtest --strategy sma --symbol BTC --days 60 --leverage 5

# 可用策略: sma, rsi, macd, bb, all
```

### 2. 运行实盘交易

```bash
# 模拟运行（不实际下单）
python main.py live --symbol ETH --strategy sma --dry-run

# 实盘运行（需要配置私钥）
python main.py live --symbol ETH --strategy rsi --leverage 5
```

### 3. 监控市场

```bash
python main.py monitor --symbol ETH
```

### 4. 查看账户

```bash
python main.py account
```

## 策略说明

### SMA 策略 (简单移动平均线交叉)
- 快线上穿慢线时做多
- 快线下穿慢线时做空
- 参数: fast_period=10, slow_period=30

### RSI 策略 (相对强弱指标)
- RSI < 30 时做多（超卖）
- RSI > 70 时做空（超买）
- 参数: period=14, overbought=70, oversold=30

### MACD 策略
- MACD 线上穿信号线时做多
- MACD 线下穿信号线时做空
- 参数: fast=12, slow=26, signal=9

### 布林带策略
- 价格触及下轨时做多
- 价格触及上轨时做空
- 参数: period=20, std_dev=2.0

### 组合策略
- 结合多个策略信号
- 多数策略同意时才执行交易

## 自定义策略

继承 `BaseStrategy` 类创建自己的策略:

```python
from strategies.base import BaseStrategy, StrategyConfig
from core.models import Signal, SignalType

class MyStrategy(BaseStrategy):
    def __init__(self, config=None):
        config = config or StrategyConfig(name="MyStrategy")
        super().__init__(config)
    
    def calculate_indicators(self, data):
        # 计算指标
        df = data.df
        return {
            "my_indicator": df['close'].rolling(20).mean()
        }
    
    def generate_signal(self, data, indicators, current_position):
        # 生成信号
        indicator = indicators["my_indicator"]
        price = data.latest_close
        
        if price > indicator.iloc[-1]:
            return Signal(
                signal_type=SignalType.BUY,
                symbol=self.config.symbols[0],
                price=price,
                timestamp=data.latest.timestamp
            )
        
        return Signal(
            signal_type=SignalType.HOLD,
            symbol=self.config.symbols[0],
            price=price,
            timestamp=data.latest.timestamp
        )
```

## 风险管理

系统内置完善的风险管理:

- **最大回撤限制**: 账户回撤超过阈值时暂停交易
- **每日亏损限制**: 每日亏损超过阈值时暂停交易
- **连续亏损限制**: 连续亏损次数过多时降低仓位
- **交易频率限制**: 防止过度交易
- **仓位大小控制**: 基于风险计算仓位

## API 说明

### Hyperliquid API
- 获取实时行情和订单簿
- 执行市价/限价订单
- 管理仓位和止损止盈
- WebSocket 实时数据订阅

### Birdeye API
- 获取 Solana 链代币历史价格
- OHLCV 数据用于回测
- 支持多种时间周期

## 注意事项

⚠️ **重要提醒**:

1. **测试网优先**: 首次使用请先在测试网 (`TESTNET_MODE=True`) 验证
2. **小额测试**: 实盘交易前请用小额资金测试
3. **风险控制**: 设置合理的止损和最大仓位
4. **私钥安全**: 不要泄露你的私钥
5. **持续监控**: 定期检查系统运行状态

## License

MIT License

