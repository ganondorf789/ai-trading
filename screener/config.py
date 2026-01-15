"""
配置模块
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

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
    profitability_weight: float = 0.35  # 盈利能力权重
    risk_weight: float = 0.30  # 风险控制权重
    consistency_weight: float = 0.20  # 稳定性权重
    activity_weight: float = 0.15  # 活跃度权重
    
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
class ProxyConfig:
    """代理配置"""
    enabled: bool = True  # 是否启用代理
    host: str = "proxy.smartproxy.net"  # 代理主机
    port: int = 3120  # 代理端口
    username: str = "smart-cbbncrcrkj60_area-SG"  # 代理用户名
    password: str = "NYBYuI6rARSnQJwg"  # 代理密码
    
    @property
    def proxy_url(self) -> Optional[str]:
        """获取代理 URL"""
        if not self.enabled or not self.host:
            return None
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"


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
    api_call_delay: float = 1.0  # API 调用间隔（秒），使用代理时可设为 0
    
    # 代理配置
    proxy: ProxyConfig = field(default_factory=ProxyConfig)


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
    
    @property
    def proxy_url(self) -> Optional[str]:
        return self.api.proxy.proxy_url
    
    @property
    def proxy_enabled(self) -> bool:
        return self.api.proxy.enabled
    
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
            api_data = data['api'].copy()
            # 单独处理嵌套的 proxy 配置
            if 'proxy' in api_data:
                api_data['proxy'] = ProxyConfig(**api_data['proxy'])
            config.api = APIConfig(**api_data)
        if 'proxy' in data:
            # 支持顶层 proxy 配置
            config.api.proxy = ProxyConfig(**data['proxy'])
        if 'concurrency' in data:
            config.concurrency = ConcurrencyConfig(**data['concurrency'])
        if 'cache' in data:
            config.cache = CacheConfig(**data['cache'])
        if 'data' in data:
            config.data = DataConfig(**data['data'])
        if 'output' in data:
            config.output = OutputConfig(**data['output'])
        
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
