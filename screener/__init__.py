"""
Hyperliquid 交易者筛选模块

自动发现和筛选优质交易者地址

模块结构:
- models: 数据模型 (TraderMetrics, QualityRating, ...)
- config: 配置管理 (ScreenerConfig, FilterConfig, ...)
- cache: 缓存系统 (CacheManager, TTLCache)
- api_client: API 客户端 (SyncAPIClient, AsyncAPIClient)
- metrics_calculator: 指标计算 (MetricsCalculator)
- scorer: 评分系统 (TraderScorer)
- trader_screener: 主筛选器 (TraderScreener)
- utils: 工具函数
- exceptions: 异常类

使用示例:
    ```python
    from screener import TraderScreener, ScreenerConfig
    
    # 创建筛选器（使用默认配置，自动保存持仓到数据库）
    screener = TraderScreener()
    
    # 或使用自定义配置
    config = ScreenerConfig()
    config.filter.min_win_rate = 0.5
    config.filter.min_profit_factor = 1.5
    screener = TraderScreener(config)
    
    # 分析单个交易者（会自动保存当前持仓到asset_positions表）
    metrics = screener.analyze_trader("0x...")
    print(f"评分: {metrics.overall_score}, 评级: {metrics.rating.value}")
    print(f"持仓数: {len(metrics.asset_positions)}")
    
    # 批量筛选
    addresses = ["0x...", "0x...", ...]
    qualified = screener.screen_traders(addresses)
    
    # 打印结果
    screener.print_summary(qualified, detailed=True)
    
    # 保存结果
    screener.save_results(qualified, "qualified_traders.json")
    ```

异步使用示例:
    ```python
    import asyncio
    from screener import TraderScreener
    
    async def main():
        screener = TraderScreener()
        addresses = ["0x...", "0x...", ...]
        qualified = await screener.screen_traders_async(addresses)
        return qualified
    
    results = asyncio.run(main())
    ```

使用预设配置:
    ```python
    from screener import TraderScreener
    from screener.config import PresetConfigs
    
    # 保守配置
    screener = TraderScreener(PresetConfigs.conservative())
    
    # 高频交易者筛选
    screener = TraderScreener(PresetConfigs.high_frequency())
    
    # 大资金交易者筛选
    screener = TraderScreener(PresetConfigs.whale())
    ```
"""

# 主要类
from screener.trader_screener import (
    TraderScreener,
    discover_active_traders,
    quick_analyze,
    quick_screen,
)

# 数据模型
from screener.models import (
    TraderMetrics,
    QualityRating,
    PnLMetrics,
    RiskMetrics,
    TradeMetrics,
    ActivityMetrics,
    PositionMetrics,
    ROIMetrics,
    ScoreMetrics,
    FillData,
)

# 配置
from screener.config import (
    ScreenerConfig,
    FilterConfig,
    ScoringConfig,
    APIConfig,
    ConcurrencyConfig,
    CacheConfig,
    DataConfig,
    OutputConfig,
    PresetConfigs,
)

# 缓存
from screener.cache import (
    CacheManager,
    TTLCache,
    get_cache_manager,
    reset_cache_manager,
)

# API 客户端
from screener.api_client import (
    BaseAPIClient,
    SyncAPIClient,
    AsyncAPIClient,
    create_api_client,
)

# 指标计算
from screener.metrics_calculator import (
    MetricsCalculator,
    calculate_metrics,
)

# 增量获取
from screener.incremental_fetcher import (
    fetch_incremental_fills,
    fetch_all_history_fills,
    fetch_fills_for_period,
    fetch_fills_by_weeks,
    fetch_fills_by_days,
    fetch_fills_by_hours,
    fetch_fills_by_minutes,
    probe_trader_fills,
    find_first_fill_half_year,
)

# 评分系统
from screener.scorer import (
    TraderScorer,
    CustomScorer,
    calculate_scores,
    get_rating_description,
    get_score_breakdown,
)

# 异常
from screener.exceptions import (
    ScreenerError,
    APIError,
    APIRateLimitError,
    APITimeoutError,
    TraderDataError,
    InvalidAddressError,
    ConfigurationError,
    InsufficientDataError,
    CacheError,
)

# 工具函数
from screener.utils import (
    SHANGHAI_TZ,
    timestamp_to_pendulum,
    now_shanghai,
    validate_address,
    short_address,
    format_pnl,
    format_percentage,
    safe_divide,
    calculate_trade_type,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_var,
    calculate_expected_shortfall,
    calculate_consecutive_streaks,
    calculate_holding_time,
)

__version__ = "2.0.0"

__all__ = [
    # 版本
    "__version__",
    
    # 主要类
    "TraderScreener",
    "discover_active_traders",
    "quick_analyze",
    "quick_screen",
    
    # 数据模型
    "TraderMetrics",
    "QualityRating",
    "PnLMetrics",
    "RiskMetrics",
    "TradeMetrics",
    "ActivityMetrics",
    "PositionMetrics",
    "ROIMetrics",
    "ScoreMetrics",
    "FillData",
    
    # 配置
    "ScreenerConfig",
    "FilterConfig",
    "ScoringConfig",
    "APIConfig",
    "ConcurrencyConfig",
    "CacheConfig",
    "DataConfig",
    "OutputConfig",
    "PresetConfigs",
    
    # 缓存
    "CacheManager",
    "TTLCache",
    "get_cache_manager",
    "reset_cache_manager",
    
    # API 客户端
    "BaseAPIClient",
    "SyncAPIClient",
    "AsyncAPIClient",
    "create_api_client",
    
    # 指标计算
    "MetricsCalculator",
    "calculate_metrics",
    
    # 增量获取
    "fetch_incremental_fills",
    "fetch_all_history_fills",
    "fetch_fills_for_period",
    "fetch_fills_by_weeks",
    "fetch_fills_by_days",
    "fetch_fills_by_hours",
    "fetch_fills_by_minutes",
    "probe_trader_fills",
    "find_first_fill_half_year",
    
    # 评分系统
    "TraderScorer",
    "CustomScorer",
    "calculate_scores",
    "get_rating_description",
    "get_score_breakdown",
    
    # 异常
    "ScreenerError",
    "APIError",
    "APIRateLimitError",
    "APITimeoutError",
    "TraderDataError",
    "InvalidAddressError",
    "ConfigurationError",
    "InsufficientDataError",
    "CacheError",
    
    # 工具函数
    "SHANGHAI_TZ",
    "timestamp_to_pendulum",
    "now_shanghai",
    "validate_address",
    "short_address",
    "format_pnl",
    "format_percentage",
    "safe_divide",
    "calculate_trade_type",
    "calculate_max_drawdown",
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_calmar_ratio",
    "calculate_var",
    "calculate_expected_shortfall",
    "calculate_consecutive_streaks",
    "calculate_holding_time",
]
