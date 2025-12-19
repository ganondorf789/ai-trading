"""
数据模型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import pandas as pd


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"


class SignalType(Enum):
    """信号类型"""
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    HOLD = "hold"


@dataclass
class OHLCV:
    """K线数据"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OHLCV':
        """从字典创建"""
        return cls(
            timestamp=data.get('timestamp') or datetime.fromtimestamp(data.get('t', 0) / 1000),
            open=float(data.get('open') or data.get('o', 0)),
            high=float(data.get('high') or data.get('h', 0)),
            low=float(data.get('low') or data.get('l', 0)),
            close=float(data.get('close') or data.get('c', 0)),
            volume=float(data.get('volume') or data.get('v', 0))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }


@dataclass
class Ticker:
    """行情数据"""
    symbol: str
    bid: float
    ask: float
    last: float
    volume_24h: float
    timestamp: datetime
    
    @property
    def mid_price(self) -> float:
        """中间价"""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """价差"""
        return self.ask - self.bid
    
    @property
    def spread_percent(self) -> float:
        """价差百分比"""
        return self.spread / self.mid_price if self.mid_price > 0 else 0


@dataclass
class Order:
    """订单"""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    size: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_size: float = 0
    filled_price: float = 0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    client_order_id: Optional[str] = None
    
    @property
    def is_buy(self) -> bool:
        """是否为买入"""
        return self.side in [OrderSide.BUY, OrderSide.LONG]
    
    @property
    def remaining_size(self) -> float:
        """剩余数量"""
        return self.size - self.filled_size


@dataclass
class Position:
    """持仓"""
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float = 0
    leverage: int = 1
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    liquidation_price: Optional[float] = None
    margin_used: float = 0
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def notional_value(self) -> float:
        """名义价值"""
        return self.size * self.current_price
    
    @property
    def pnl_percent(self) -> float:
        """盈亏百分比"""
        if self.entry_price <= 0:
            return 0
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price
    
    def update_price(self, price: float):
        """更新当前价格"""
        self.current_price = price
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - price) * self.size


@dataclass
class Signal:
    """交易信号"""
    signal_type: SignalType
    symbol: str
    price: float
    timestamp: datetime
    strength: float = 1.0  # 信号强度 0-1
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_entry(self) -> bool:
        """是否为入场信号"""
        return self.signal_type in [SignalType.BUY, SignalType.SELL]
    
    @property
    def is_exit(self) -> bool:
        """是否为出场信号"""
        return self.signal_type == SignalType.CLOSE


@dataclass
class Trade:
    """成交记录"""
    id: str
    symbol: str
    side: OrderSide
    price: float
    size: float
    pnl: float = 0
    fee: float = 0
    timestamp: datetime = field(default_factory=datetime.now)
    order_id: Optional[str] = None
    
    @property
    def net_pnl(self) -> float:
        """净盈亏"""
        return self.pnl - self.fee


@dataclass
class AccountInfo:
    """账户信息"""
    balance: float
    equity: float
    available_margin: float
    used_margin: float
    unrealized_pnl: float
    realized_pnl: float
    positions: List[Position] = field(default_factory=list)
    
    @property
    def margin_ratio(self) -> float:
        """保证金使用率"""
        if self.equity <= 0:
            return 0
        return self.used_margin / self.equity
    
    @property
    def total_pnl(self) -> float:
        """总盈亏"""
        return self.unrealized_pnl + self.realized_pnl


class OHLCVDataFrame:
    """OHLCV 数据帧封装"""
    
    def __init__(self, data: List[OHLCV]):
        """
        初始化
        
        Args:
            data: OHLCV 数据列表
        """
        self._data = data
        self._df: Optional[pd.DataFrame] = None
    
    @property
    def df(self) -> pd.DataFrame:
        """获取 DataFrame"""
        if self._df is None:
            self._df = pd.DataFrame([d.to_dict() for d in self._data])
            if not self._df.empty:
                self._df.set_index('timestamp', inplace=True)
                self._df.sort_index(inplace=True)
        return self._df
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> 'OHLCVDataFrame':
        """从 DataFrame 创建"""
        data = []
        for idx, row in df.iterrows():
            data.append(OHLCV(
                timestamp=idx if isinstance(idx, datetime) else datetime.fromtimestamp(idx),
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row.get('volume', 0)
            ))
        instance = cls.__new__(cls)
        instance._data = data
        instance._df = df.copy()
        return instance
    
    def __len__(self) -> int:
        return len(self._data)
    
    def __getitem__(self, idx: int) -> OHLCV:
        return self._data[idx]
    
    @property
    def latest(self) -> Optional[OHLCV]:
        """获取最新数据"""
        return self._data[-1] if self._data else None
    
    @property
    def latest_close(self) -> float:
        """获取最新收盘价"""
        return self.latest.close if self.latest else 0

