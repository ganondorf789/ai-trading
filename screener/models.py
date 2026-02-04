"""
数据模型模块
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from enum import Enum
import pendulum

from .utils import SHANGHAI_TZ


class QualityRating(Enum):
    """交易者质量评级"""
    S_TIER = "S"  # 顶级交易者
    A_TIER = "A"  # 优秀交易者
    B_TIER = "B"  # 良好交易者
    C_TIER = "C"  # 一般交易者
    D_TIER = "D"  # 较差交易者
    F_TIER = "F"  # 不推荐


class TradeType:
    """
    交易类型常量（使用整数节省空间）
    
    开仓类型 (1-2): 做多方向
    平仓类型 (3): 平多
    开仓类型 (4-5): 做空方向
    平仓类型 (6): 平空
    """
    OPEN_LONG = 1    # 开多（新开仓）
    ADD_LONG = 2     # 加多（加仓）
    CLOSE_LONG = 3   # 平多
    OPEN_SHORT = 4   # 开空（新开仓）
    ADD_SHORT = 5    # 加空（加仓）
    CLOSE_SHORT = 6  # 平空
    
    # 类型分组（用于快速判断）
    OPEN_TYPES = {1, 2, 4, 5}   # 所有开仓类型
    CLOSE_TYPES = {3, 6}        # 所有平仓类型
    LONG_TYPES = {1, 2, 3}      # 多头相关类型
    SHORT_TYPES = {4, 5, 6}     # 空头相关类型
    
    @classmethod
    def is_open(cls, trade_type: Optional[int]) -> bool:
        """判断是否为开仓类型"""
        return trade_type in cls.OPEN_TYPES if trade_type else False
    
    @classmethod
    def is_close(cls, trade_type: Optional[int]) -> bool:
        """判断是否为平仓类型"""
        return trade_type in cls.CLOSE_TYPES if trade_type else False
    
    @classmethod
    def is_long(cls, trade_type: Optional[int]) -> bool:
        """判断是否为多头相关"""
        return trade_type in cls.LONG_TYPES if trade_type else False
    
    @classmethod
    def is_short(cls, trade_type: Optional[int]) -> bool:
        """判断是否为空头相关"""
        return trade_type in cls.SHORT_TYPES if trade_type else False
    
    @classmethod
    def to_name(cls, trade_type: Optional[int]) -> Optional[str]:
        """将整数类型转换为名称字符串"""
        return cls.NAMES.get(trade_type) if trade_type else None


@dataclass
class PnLMetrics:
    """
    盈亏相关指标
    
    注意：total_pnl、realized_pnl、recent_7d_pnl、max_single_win、max_single_loss、
    avg_win_amount、avg_loss_amount 这些指标是基于完整的仓位历史计算的。
    """
    total_pnl: float = 0.0  # 总盈亏（所有仓位的已实现盈亏之和）
    realized_pnl: float = 0.0  # 已实现盈亏
    unrealized_pnl: float = 0.0  # 未实现盈亏
    
    # 时间段统计
    daily_pnl: float = 0.0  # 日均 PnL
    weekly_pnl: float = 0.0  # 周均 PnL
    monthly_pnl: float = 0.0  # 月均 PnL
    recent_7d_pnl: float = 0.0  # 最近 7 天 PnL（基于7天内平仓的仓位）
    
    # 单仓统计（基于完整仓位）
    max_single_win: float = 0.0  # 最大单仓盈利
    max_single_loss: float = 0.0  # 最大单仓亏损
    avg_win_amount: float = 0.0  # 盈利仓位平均收益
    avg_loss_amount: float = 0.0  # 亏损仓位平均损失
    avg_profit_per_trade: float = 0.0  # 平均每仓收益（基于已平仓位数）
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskMetrics:
    """
    风险指标
    
    注意：max_drawdown、sharpe_ratio、sortino_ratio、var_*、cvar_*、
    max_consecutive_wins、max_consecutive_losses 这些指标是基于仓位盈亏序列计算的，
    而不是单笔成交记录。这样更能准确反映真实的风险特征。
    """
    max_drawdown: float = 0.0  # 最大回撤（比例，基于仓位累计盈亏）
    max_drawdown_abs: float = 0.0  # 最大回撤（绝对值）
    sharpe_ratio: float = 0.0  # 夏普比率（基于仓位盈亏序列）
    sortino_ratio: float = 0.0  # 索提诺比率
    calmar_ratio: float = 0.0  # 卡玛比率
    
    # VaR 指标（基于仓位盈亏）
    var_95: float = 0.0  # 95% VaR
    var_99: float = 0.0  # 99% VaR
    cvar_95: float = 0.0  # 95% CVaR (Expected Shortfall)
    
    # 连续统计（基于仓位盈亏序列）
    max_consecutive_wins: int = 0  # 最大连续盈利仓位数
    max_consecutive_losses: int = 0  # 最大连续亏损仓位数
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TradeMetrics:
    """
    交易统计指标
    
    注意：winning_trades、losing_trades、win_rate、profit_factor、recent_7d_win_rate
    这些指标是基于完整的仓位历史（开仓→平仓周期）计算的，而不是单笔成交记录。
    这样更能准确反映交易者的真实表现。
    """
    total_trades: int = 0  # 总仓位数（已平仓 + 未平仓）
    winning_trades: int = 0  # 盈利仓位数（已平仓且盈利）
    losing_trades: int = 0  # 亏损仓位数（已平仓且亏损）
    
    # 胜率和盈亏比（基于已平仓位计算）
    win_rate: float = 0.0  # 胜率 = 盈利仓位数 / 已平仓位数
    profit_factor: float = 0.0  # 盈亏比 = 总盈利 / 总亏损
    recent_7d_win_rate: float = 0.0  # 最近 7 天胜率（基于7天内平仓的仓位）
    
    # 交易规模（基于成交记录）
    total_volume: float = 0.0  # 总交易量
    avg_trade_price: float = 0.0  # 平均交易价格
    avg_trade_size: float = 0.0  # 平均交易规模（USD）
    
    # 交易量时间段统计
    daily_volume: float = 0.0  # 日均交易量
    weekly_volume: float = 0.0  # 周均交易量
    monthly_volume: float = 0.0  # 月均交易量
    
    # 交易偏好
    unique_symbols: int = 0  # 交易品种数量
    favorite_symbol: str = ""  # 最常交易的品种
    long_short_ratio: float = 0.0  # 多空比例（多单占比）
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActivityMetrics:
    """活跃度指标"""
    active_days: int = 0  # 活跃天数
    trade_frequency_per_day: float = 0.0  # 日均交易频率
    avg_holding_time_hours: float = 0.0  # 平均持仓时间（小时）
    
    # 时间范围
    first_trade_time: Optional[pendulum.DateTime] = None  # 首次交易时间
    last_trade_time: Optional[pendulum.DateTime] = None  # 最后交易时间
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.first_trade_time:
            result['first_trade_time'] = self.first_trade_time.to_iso8601_string()
        if self.last_trade_time:
            result['last_trade_time'] = self.last_trade_time.to_iso8601_string()
        return result


@dataclass
class PositionMetrics:
    """持仓指标"""
    current_positions: int = 0  # 当前持仓数
    current_equity: float = 0.0  # 当前权益
    avg_leverage: float = 1.0  # 平均杠杆
    max_leverage: float = 1.0  # 最大杠杆
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ROIMetrics:
    """收益率指标"""
    roi: float = 0.0  # 总投资回报率
    daily_roi: float = 0.0  # 日均 ROI
    weekly_roi: float = 0.0  # 周均 ROI
    monthly_roi: float = 0.0  # 月均 ROI
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreMetrics:
    """评分指标"""
    overall_score: float = 0.0  # 综合评分
    profitability_score: float = 0.0  # 盈利能力评分
    risk_score: float = 0.0  # 风险控制评分
    consistency_score: float = 0.0  # 稳定性评分
    activity_score: float = 0.0  # 活跃度评分
    rating: QualityRating = QualityRating.F_TIER  # 质量等级
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['rating'] = self.rating.value
        return result


@dataclass
class TagMetrics:
    """
    交易者标签指标
    
    基于交易数据自动分类的标签系统
    """
    # 资金规模: 小资金 / 中等资金 / 大资金
    capital_scale: Optional[str] = None
    
    # 交易方向: 偏空头 / 中性 / 偏多头
    trading_direction: Optional[str] = None
    
    # 交易周期: 长线 / 波段 / 短线 / 超短线
    trading_cycle: Optional[str] = None
    
    # 频率与风格: 高频激进 / 低频稳健 / 低频激进
    frequency_style: Optional[str] = None
    
    # 收益与风险: 稳定盈利 / 持续盈利 / 波动盈利 / 盈亏平衡 / 高风险高回报 / 低回撤
    return_risk: Optional[str] = None
    
    # 策略能力: 波动策略 / 非对称高手
    strategy_capability: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_list(self) -> List[str]:
        """返回所有非空标签的列表"""
        tags = []
        if self.capital_scale:
            tags.append(self.capital_scale)
        if self.trading_direction:
            tags.append(self.trading_direction)
        if self.trading_cycle:
            tags.append(self.trading_cycle)
        if self.frequency_style:
            tags.append(self.frequency_style)
        if self.return_risk:
            tags.append(self.return_risk)
        if self.strategy_capability:
            tags.append(self.strategy_capability)
        return tags


@dataclass
class TraderMetrics:
    """
    交易者综合指标
    
    整合所有子指标模块
    """
    address: str
    
    # 子指标模块
    pnl: PnLMetrics = field(default_factory=PnLMetrics)
    risk: RiskMetrics = field(default_factory=RiskMetrics)
    trade: TradeMetrics = field(default_factory=TradeMetrics)
    activity: ActivityMetrics = field(default_factory=ActivityMetrics)
    position: PositionMetrics = field(default_factory=PositionMetrics)
    roi: ROIMetrics = field(default_factory=ROIMetrics)
    score: ScoreMetrics = field(default_factory=ScoreMetrics)
    tags: TagMetrics = field(default_factory=TagMetrics)
    
    # 原始数据（可选）
    fills: List[Dict] = field(default_factory=list)
    asset_positions: List[Dict] = field(default_factory=list)
    
    # ===== 便捷属性（向后兼容）=====
    @property
    def total_trades(self) -> int:
        return self.trade.total_trades
    
    @property
    def winning_trades(self) -> int:
        return self.trade.winning_trades
    
    @property
    def losing_trades(self) -> int:
        return self.trade.losing_trades
    
    @property
    def total_pnl(self) -> float:
        return self.pnl.total_pnl
    
    @property
    def realized_pnl(self) -> float:
        return self.pnl.realized_pnl
    
    @property
    def unrealized_pnl(self) -> float:
        return self.pnl.unrealized_pnl
    
    @property
    def total_volume(self) -> float:
        return self.trade.total_volume
    
    @property
    def win_rate(self) -> float:
        return self.trade.win_rate
    
    @property
    def profit_factor(self) -> float:
        return self.trade.profit_factor
    
    @property
    def max_drawdown(self) -> float:
        return self.risk.max_drawdown
    
    @property
    def sharpe_ratio(self) -> float:
        return self.risk.sharpe_ratio
    
    @property
    def sortino_ratio(self) -> float:
        return self.risk.sortino_ratio
    
    @property
    def calmar_ratio(self) -> float:
        return self.risk.calmar_ratio
    
    @property
    def active_days(self) -> int:
        return self.activity.active_days
    
    @property
    def last_trade_time(self) -> Optional[pendulum.DateTime]:
        return self.activity.last_trade_time
    
    @property
    def first_trade_time(self) -> Optional[pendulum.DateTime]:
        return self.activity.first_trade_time
    
    @property
    def current_positions(self) -> int:
        return self.position.current_positions
    
    @property
    def current_equity(self) -> float:
        return self.position.current_equity
    
    @property
    def avg_leverage(self) -> float:
        return self.position.avg_leverage
    
    @property
    def overall_score(self) -> float:
        return self.score.overall_score
    
    @property
    def rating(self) -> QualityRating:
        return self.score.rating
    
    @property
    def profitability_score(self) -> float:
        return self.score.profitability_score
    
    @property
    def risk_score(self) -> float:
        return self.score.risk_score
    
    @property
    def consistency_score(self) -> float:
        return self.score.consistency_score
    
    @property
    def activity_score(self) -> float:
        return self.score.activity_score
    
    @property
    def trade_frequency_per_day(self) -> float:
        return self.activity.trade_frequency_per_day
    
    @property
    def avg_holding_time_hours(self) -> float:
        return self.activity.avg_holding_time_hours
    
    @property
    def avg_profit_per_trade(self) -> float:
        return self.pnl.avg_profit_per_trade
    
    @property
    def daily_pnl(self) -> float:
        return self.pnl.daily_pnl
    
    @property
    def weekly_pnl(self) -> float:
        return self.pnl.weekly_pnl
    
    @property
    def monthly_pnl(self) -> float:
        return self.pnl.monthly_pnl
    
    @property
    def recent_7d_pnl(self) -> float:
        return self.pnl.recent_7d_pnl
    
    @property
    def recent_7d_win_rate(self) -> float:
        return self.trade.recent_7d_win_rate
    
    @property
    def max_single_win(self) -> float:
        return self.pnl.max_single_win
    
    @property
    def max_single_loss(self) -> float:
        return self.pnl.max_single_loss
    
    @property
    def avg_win_amount(self) -> float:
        return self.pnl.avg_win_amount
    
    @property
    def avg_loss_amount(self) -> float:
        return self.pnl.avg_loss_amount
    
    @property
    def max_consecutive_wins(self) -> int:
        return self.risk.max_consecutive_wins
    
    @property
    def max_consecutive_losses(self) -> int:
        return self.risk.max_consecutive_losses
    
    @property
    def unique_symbols(self) -> int:
        return self.trade.unique_symbols
    
    @property
    def favorite_symbol(self) -> str:
        return self.trade.favorite_symbol
    
    @property
    def long_short_ratio(self) -> float:
        return self.trade.long_short_ratio
    
    @property
    def avg_trade_price(self) -> float:
        return self.trade.avg_trade_price
    
    @property
    def avg_trade_size(self) -> float:
        return self.trade.avg_trade_size
    
    @property
    def daily_volume(self) -> float:
        return self.trade.daily_volume
    
    @property
    def weekly_volume(self) -> float:
        return self.trade.weekly_volume
    
    @property
    def monthly_volume(self) -> float:
        return self.trade.monthly_volume
    
    @property
    def daily_roi(self) -> float:
        return self.roi.daily_roi
    
    @property
    def weekly_roi(self) -> float:
        return self.roi.weekly_roi
    
    @property
    def monthly_roi(self) -> float:
        return self.roi.monthly_roi
    
    # ===== 标签便捷属性 =====
    @property
    def tag_capital_scale(self) -> Optional[str]:
        return self.tags.capital_scale
    
    @property
    def tag_trading_direction(self) -> Optional[str]:
        return self.tags.trading_direction
    
    @property
    def tag_trading_cycle(self) -> Optional[str]:
        return self.tags.trading_cycle
    
    @property
    def tag_frequency_style(self) -> Optional[str]:
        return self.tags.frequency_style
    
    @property
    def tag_return_risk(self) -> Optional[str]:
        return self.tags.return_risk
    
    @property
    def tag_strategy_capability(self) -> Optional[str]:
        return self.tags.strategy_capability
    
    @property
    def tag_list(self) -> List[str]:
        """获取所有标签列表"""
        return self.tags.to_list()
    
    def to_dict(
        self,
        include_fills: bool = False,
        include_positions: bool = False
    ) -> Dict[str, Any]:
        """
        转换为字典
        
        Args:
            include_fills: 是否包含原始交易记录
            include_positions: 是否包含当前持仓
        
        Returns:
            字典形式的指标数据
        """
        result = {
            'address': self.address,
            'pnl': self.pnl.to_dict(),
            'risk': self.risk.to_dict(),
            'trade': self.trade.to_dict(),
            'activity': self.activity.to_dict(),
            'position': self.position.to_dict(),
            'roi': self.roi.to_dict(),
            'score': self.score.to_dict(),
            'tags': self.tags.to_dict(),
        }
        
        if include_fills:
            result['fills'] = self.fills
        
        if include_positions:
            result['asset_positions'] = self.asset_positions
        
        return result
    
    def to_flat_dict(
        self,
        include_fills: bool = False,
        include_positions: bool = False
    ) -> Dict[str, Any]:
        """
        转换为扁平字典（向后兼容）
        
        Args:
            include_fills: 是否包含原始交易记录
            include_positions: 是否包含当前持仓
        
        Returns:
            扁平化的字典
        """
        result = {
            'address': self.address,
            
            # PnL
            'total_pnl': self.pnl.total_pnl,
            'realized_pnl': self.pnl.realized_pnl,
            'unrealized_pnl': self.pnl.unrealized_pnl,
            'daily_pnl': self.pnl.daily_pnl,
            'weekly_pnl': self.pnl.weekly_pnl,
            'monthly_pnl': self.pnl.monthly_pnl,
            'recent_7d_pnl': self.pnl.recent_7d_pnl,
            'max_single_win': self.pnl.max_single_win,
            'max_single_loss': self.pnl.max_single_loss,
            'avg_win_amount': self.pnl.avg_win_amount,
            'avg_loss_amount': self.pnl.avg_loss_amount,
            'avg_profit_per_trade': self.pnl.avg_profit_per_trade,
            
            # Risk
            'max_drawdown': self.risk.max_drawdown,
            'sharpe_ratio': self.risk.sharpe_ratio,
            'sortino_ratio': self.risk.sortino_ratio,
            'calmar_ratio': self.risk.calmar_ratio,
            'var_95': self.risk.var_95,
            'var_99': self.risk.var_99,
            'cvar_95': self.risk.cvar_95,
            'max_consecutive_wins': self.risk.max_consecutive_wins,
            'max_consecutive_losses': self.risk.max_consecutive_losses,
            
            # Trade
            'total_trades': self.trade.total_trades,
            'winning_trades': self.trade.winning_trades,
            'losing_trades': self.trade.losing_trades,
            'win_rate': self.trade.win_rate,
            'profit_factor': self.trade.profit_factor,
            'recent_7d_win_rate': self.trade.recent_7d_win_rate,
            'total_volume': self.trade.total_volume,
            'avg_trade_price': self.trade.avg_trade_price,
            'avg_trade_size': self.trade.avg_trade_size,
            'daily_volume': self.trade.daily_volume,
            'weekly_volume': self.trade.weekly_volume,
            'monthly_volume': self.trade.monthly_volume,
            'unique_symbols': self.trade.unique_symbols,
            'favorite_symbol': self.trade.favorite_symbol,
            'long_short_ratio': self.trade.long_short_ratio,
            
            # Activity
            'active_days': self.activity.active_days,
            'trade_frequency_per_day': self.activity.trade_frequency_per_day,
            'avg_holding_time_hours': self.activity.avg_holding_time_hours,
            'first_trade_time': (
                self.activity.first_trade_time.to_iso8601_string()
                if self.activity.first_trade_time else None
            ),
            'last_trade_time': (
                self.activity.last_trade_time.to_iso8601_string()
                if self.activity.last_trade_time else None
            ),
            
            # Position
            'current_positions': self.position.current_positions,
            'current_equity': self.position.current_equity,
            'avg_leverage': self.position.avg_leverage,
            
            # ROI
            'roi': self.roi.roi,
            'daily_roi': self.roi.daily_roi,
            'weekly_roi': self.roi.weekly_roi,
            'monthly_roi': self.roi.monthly_roi,
            
            # Score
            'overall_score': self.score.overall_score,
            'profitability_score': self.score.profitability_score,
            'risk_score': self.score.risk_score,
            'consistency_score': self.score.consistency_score,
            'activity_score': self.score.activity_score,
            'rating': self.score.rating.value,
            
            # Tags
            'tag_capital_scale': self.tags.capital_scale,
            'tag_trading_direction': self.tags.trading_direction,
            'tag_trading_cycle': self.tags.trading_cycle,
            'tag_frequency_style': self.tags.frequency_style,
            'tag_return_risk': self.tags.return_risk,
            'tag_strategy_capability': self.tags.strategy_capability,
        }
        
        if include_fills:
            result['fills'] = self.fills
        
        if include_positions:
            result['asset_positions'] = self.asset_positions
        
        return result


@dataclass
class FillData:
    """
    成交记录数据
    
    用于数据验证和标准化
    """
    time: int  # 时间戳（毫秒）
    coin: str  # 交易对
    px: float  # 价格
    sz: float  # 数量
    side: str  # 方向 (B/A 或 BUY/SELL)
    closed_pnl: float = 0.0  # 已平仓盈亏
    dir: Optional[str] = None  # 方向描述
    start_position: Optional[float] = None  # 开始仓位
    trade_type: Optional[int] = None  # 交易类型（整数，参见 TradeType）
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FillData':
        """从字典创建"""
        # 处理 trade_type，支持整数或字符串
        trade_type_raw = data.get('trade_type')
        if isinstance(trade_type_raw, int):
            trade_type = trade_type_raw
        elif isinstance(trade_type_raw, str):
            # 兼容旧的字符串格式
            trade_type = {
                'open_long': TradeType.OPEN_LONG,
                'add_long': TradeType.ADD_LONG,
                'close_long': TradeType.CLOSE_LONG,
                'open_short': TradeType.OPEN_SHORT,
                'add_short': TradeType.ADD_SHORT,
                'close_short': TradeType.CLOSE_SHORT,
            }.get(trade_type_raw)
        else:
            trade_type = None
        
        return cls(
            time=int(data.get('time', 0)),
            coin=str(data.get('coin', '')),
            px=float(data.get('px', 0)),
            sz=float(data.get('sz', 0)),
            side=str(data.get('side', '')),
            closed_pnl=float(data.get('closedPnl', 0)),
            dir=data.get('dir'),
            start_position=float(data['startPosition']) if data.get('startPosition') else None,
            trade_type=trade_type,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'time': self.time,
            'coin': self.coin,
            'px': self.px,
            'sz': self.sz,
            'side': self.side,
            'closedPnl': self.closed_pnl,
            'dir': self.dir,
            'startPosition': self.start_position,
            'trade_type': self.trade_type,
        }
    
    @property
    def volume(self) -> float:
        """交易量（USD）"""
        return self.px * self.sz
    
    @property
    def is_buy(self) -> bool:
        """是否为买入"""
        return self.side.upper() in ('B', 'BUY')
    
    @property
    def is_sell(self) -> bool:
        """是否为卖出"""
        return self.side.upper() in ('A', 'SELL')
    
    def validate(self) -> bool:
        """验证数据有效性"""
        if self.time <= 0:
            return False
        if not self.coin:
            return False
        if self.px < 0 or self.sz < 0:
            return False
        return True
