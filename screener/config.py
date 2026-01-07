"""
配置模块
"""
from dataclasses import dataclass, field
from typing import Dict

from hyperliquid.utils import constants


@dataclass
class FilterConfig:
    """筛选条件配置"""
    min_total_trades: int = 10  # 最小交易次数
    min_win_rate: float = 0.45  # 最小胜率
    min_profit_factor: float = 1.0  # 最小盈亏比
    min_total_pnl: float = 0.0  # 最小总盈利
    max_drawdown: float = 0.5  # 最大回撤限制
    min_active_days: int = 5  # 最小活跃天数
    min_sharpe_ratio: float = 0.0  # 最小夏普比率


@dataclass
class ScoringConfig:
    """评分配置"""
    # 权重配置 (总和为 1.0)
    profitability_weight: float = 0.30  # 盈利能力权重
    risk_weight: float = 0.25  # 风险控制权重
    consistency_weight: float = 0.20  # 稳定性权重
    activity_weight: float = 0.15  # 活跃度权重
    timing_weight: float = 0.10  # 择时能力权重（技术面）
    
    # 评级阈值
    rating_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'S': 85.0,
        'A': 70.0,
        'B': 55.0,
        'C': 40.0,
        'D': 25.0,
    })
    
    # 盈利能力评分参数
    win_rate_max_score: float = 30.0  # 胜率最高得分
    win_rate_multiplier: float = 50.0  # 胜率乘数
    profit_factor_max_score: float = 30.0  # 盈亏比最高得分
    profit_factor_multiplier: float = 10.0  # 盈亏比乘数
    pnl_max_score: float = 40.0  # PnL 最高得分
    pnl_log_multiplier: float = 10.0  # PnL 对数乘数
    
    # 风险评分参数
    drawdown_penalty_multiplier: float = 100.0  # 回撤惩罚乘数
    drawdown_max_penalty: float = 50.0  # 回撤最大惩罚
    sharpe_bonus_multiplier: float = 10.0  # 夏普加分乘数
    sharpe_max_bonus: float = 30.0  # 夏普最大加分
    
    # 稳定性评分参数
    trades_bonus_divisor: float = 10.0  # 交易次数除数
    trades_max_bonus: float = 20.0  # 交易次数最高加分
    active_days_max_bonus: float = 20.0  # 活跃天数最高加分
    profit_factor_threshold: float = 1.5  # 盈亏比阈值（加分）
    profit_factor_bonus: float = 10.0  # 盈亏比超过阈值的加分
    
    # 活跃度评分参数
    frequency_multiplier: float = 20.0  # 频率乘数
    frequency_max_score: float = 40.0  # 频率最高得分
    recent_trade_1d_bonus: float = 30.0  # 1天内交易加分
    recent_trade_7d_bonus: float = 20.0  # 7天内交易加分
    recent_trade_30d_bonus: float = 10.0  # 30天内交易加分
    has_position_bonus: float = 30.0  # 有持仓加分


@dataclass
class APIConfig:
    """API 配置"""
    api_url: str = constants.MAINNET_API_URL
    testnet: bool = False
    
    # 重试配置
    max_retries: int = 3  # 最大重试次数
    retry_delay: float = 2.0  # 重试延迟（秒）
    
    # 超时配置
    connect_timeout: float = 10.0  # 连接超时
    read_timeout: float = 30.0  # 读取超时
    
    # 频率限制
    api_call_delay: float = 0.3  # API 调用间隔（秒）


@dataclass
class ConcurrencyConfig:
    """并发配置"""
    max_concurrent_requests: int = 3  # 最大并发请求数
    request_delay: float = 0.5  # 请求间隔（秒）


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True  # 是否启用缓存
    metrics_ttl: int = 300  # 指标缓存 TTL（秒）
    user_state_ttl: int = 60  # 用户状态缓存 TTL（秒）
    max_size: int = 1000  # 最大缓存条目数


@dataclass
class DataConfig:
    """数据获取配置"""
    max_fills_per_trader: int = 0  # 每个交易者最大获取成交数 (0=不限制)
    lookback_days: int = 0  # 回溯天数 (0=获取所有记录)


@dataclass
class OutputConfig:
    """输出配置"""
    top_n: int = 20  # 输出前 N 名
    output_file: str = "qualified_traders.json"


@dataclass
class TechnicalConfig:
    """技术面分析配置"""
    
    # 是否启用技术面分析
    enabled: bool = True
    
    # K线配置
    candle_interval: str = "1h"  # K线间隔 (1m, 5m, 15m, 1h, 4h, 1d)
    lookback_bars: int = 50  # 回溯K线数量
    min_candles_required: int = 20  # 最少需要的K线数量
    
    # 技术指标参数
    sma_period: int = 20  # 简单移动平均周期
    rsi_period: int = 14  # RSI 周期
    atr_period: int = 14  # ATR 周期
    atr_lookback_bars: int = 30  # ATR 计算回溯K线数
    
    # 评分权重
    trend_weight: float = 0.40  # 趋势一致性权重
    rsi_weight: float = 0.30  # RSI 入场质量权重
    ma_weight: float = 0.30  # 均线位置权重
    
    # 缓存配置
    max_cache_size: int = 500  # 最大K线缓存条目数
    
    # 评分系统配置
    timing_score_weight: float = 0.10  # 择时评分在总评分中的权重


@dataclass
class ScreenerConfig:
    """
    筛选器主配置
    
    整合所有子配置模块
    """
    # 子配置模块
    filter: FilterConfig = field(default_factory=FilterConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    api: APIConfig = field(default_factory=APIConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    data: DataConfig = field(default_factory=DataConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    technical: TechnicalConfig = field(default_factory=TechnicalConfig)  # 技术面分析配置
    
    # ===== 便捷属性（向后兼容）=====
    @property
    def api_url(self) -> str:
        return self.api.api_url
    
    @property
    def testnet(self) -> bool:
        return self.api.testnet
    
    @property
    def max_fills_per_trader(self) -> int:
        return self.data.max_fills_per_trader
    
    @property
    def lookback_days(self) -> int:
        return self.data.lookback_days
    
    @property
    def min_total_trades(self) -> int:
        return self.filter.min_total_trades
    
    @property
    def min_win_rate(self) -> float:
        return self.filter.min_win_rate
    
    @property
    def min_profit_factor(self) -> float:
        return self.filter.min_profit_factor
    
    @property
    def min_total_pnl(self) -> float:
        return self.filter.min_total_pnl
    
    @property
    def max_drawdown(self) -> float:
        return self.filter.max_drawdown
    
    @property
    def min_active_days(self) -> int:
        return self.filter.min_active_days
    
    @property
    def min_sharpe_ratio(self) -> float:
        return self.filter.min_sharpe_ratio
    
    @property
    def profitability_weight(self) -> float:
        return self.scoring.profitability_weight
    
    @property
    def risk_weight(self) -> float:
        return self.scoring.risk_weight
    
    @property
    def consistency_weight(self) -> float:
        return self.scoring.consistency_weight
    
    @property
    def activity_weight(self) -> float:
        return self.scoring.activity_weight
    
    @property
    def top_n(self) -> int:
        return self.output.top_n
    
    @property
    def output_file(self) -> str:
        return self.output.output_file
    
    @property
    def max_concurrent_requests(self) -> int:
        return self.concurrency.max_concurrent_requests
    
    @property
    def request_delay(self) -> float:
        return self.concurrency.request_delay
    
    @property
    def api_call_delay(self) -> float:
        return self.api.api_call_delay
    
    @property
    def max_retries(self) -> int:
        return self.api.max_retries
    
    @property
    def retry_delay(self) -> float:
        return self.api.retry_delay
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ScreenerConfig':
        """从字典创建配置"""
        config = cls()
        
        # 解析子配置
        if 'filter' in data:
            config.filter = FilterConfig(**data['filter'])
        if 'scoring' in data:
            config.scoring = ScoringConfig(**data['scoring'])
        if 'api' in data:
            config.api = APIConfig(**data['api'])
        if 'concurrency' in data:
            config.concurrency = ConcurrencyConfig(**data['concurrency'])
        if 'cache' in data:
            config.cache = CacheConfig(**data['cache'])
        if 'data' in data:
            config.data = DataConfig(**data['data'])
        if 'output' in data:
            config.output = OutputConfig(**data['output'])
        if 'technical' in data:
            config.technical = TechnicalConfig(**data['technical'])
        
        # 支持旧版扁平配置格式
        flat_mappings = {
            'min_total_trades': ('filter', 'min_total_trades'),
            'min_win_rate': ('filter', 'min_win_rate'),
            'min_profit_factor': ('filter', 'min_profit_factor'),
            'min_total_pnl': ('filter', 'min_total_pnl'),
            'max_drawdown': ('filter', 'max_drawdown'),
            'min_active_days': ('filter', 'min_active_days'),
            'min_sharpe_ratio': ('filter', 'min_sharpe_ratio'),
            'profitability_weight': ('scoring', 'profitability_weight'),
            'risk_weight': ('scoring', 'risk_weight'),
            'consistency_weight': ('scoring', 'consistency_weight'),
            'activity_weight': ('scoring', 'activity_weight'),
            'api_url': ('api', 'api_url'),
            'testnet': ('api', 'testnet'),
            'max_retries': ('api', 'max_retries'),
            'retry_delay': ('api', 'retry_delay'),
            'api_call_delay': ('api', 'api_call_delay'),
            'max_concurrent_requests': ('concurrency', 'max_concurrent_requests'),
            'request_delay': ('concurrency', 'request_delay'),
            'max_fills_per_trader': ('data', 'max_fills_per_trader'),
            'lookback_days': ('data', 'lookback_days'),
            'top_n': ('output', 'top_n'),
            'output_file': ('output', 'output_file'),
            'technical_enabled': ('technical', 'enabled'),
            'candle_interval': ('technical', 'candle_interval'),
            'timing_weight': ('scoring', 'timing_weight'),
        }
        
        for key, (sub_config, attr) in flat_mappings.items():
            if key in data:
                sub = getattr(config, sub_config)
                setattr(sub, attr, data[key])
        
        return config


# 预设配置
class PresetConfigs:
    """预设配置集合"""
    
    @staticmethod
    def conservative() -> ScreenerConfig:
        """保守配置：更高的筛选门槛"""
        return ScreenerConfig(
            filter=FilterConfig(
                min_total_trades=50,
                min_win_rate=0.55,
                min_profit_factor=1.5,
                min_total_pnl=1000.0,
                max_drawdown=0.3,
                min_active_days=14,
                min_sharpe_ratio=0.5,
            )
        )
    
    @staticmethod
    def aggressive() -> ScreenerConfig:
        """激进配置：更低的筛选门槛"""
        return ScreenerConfig(
            filter=FilterConfig(
                min_total_trades=5,
                min_win_rate=0.35,
                min_profit_factor=0.8,
                min_total_pnl=-1000.0,
                max_drawdown=0.7,
                min_active_days=3,
                min_sharpe_ratio=-1.0,
            )
        )
    
    @staticmethod
    def high_frequency() -> ScreenerConfig:
        """高频交易者筛选配置"""
        return ScreenerConfig(
            filter=FilterConfig(
                min_total_trades=100,
                min_win_rate=0.50,
                min_profit_factor=1.2,
                min_active_days=7,
            ),
            scoring=ScoringConfig(
                profitability_weight=0.25,
                risk_weight=0.25,
                consistency_weight=0.25,
                activity_weight=0.25,
            )
        )
    
    @staticmethod
    def whale() -> ScreenerConfig:
        """大资金交易者筛选配置"""
        return ScreenerConfig(
            filter=FilterConfig(
                min_total_trades=20,
                min_win_rate=0.45,
                min_profit_factor=1.3,
                min_total_pnl=10000.0,
                max_drawdown=0.4,
            )
        )
