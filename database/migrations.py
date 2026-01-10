"""
数据库迁移和表结构初始化 (PostgreSQL)
"""
from loguru import logger


class DatabaseMigrations:
    """数据库迁移管理类"""

    def _init_database(self):
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 创建交易者指标表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_metrics (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 基础统计
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,

                    -- 盈亏指标
                    total_pnl REAL DEFAULT 0.0,
                    realized_pnl REAL DEFAULT 0.0,
                    unrealized_pnl REAL DEFAULT 0.0,
                    total_volume REAL DEFAULT 0.0,

                    -- 收益率指标
                    roi REAL DEFAULT 0.0,
                    avg_profit_per_trade REAL DEFAULT 0.0,

                    -- 风险指标
                    win_rate REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    max_drawdown_abs REAL DEFAULT 0.0,
                    sharpe_ratio REAL DEFAULT 0.0,
                    sortino_ratio REAL DEFAULT 0.0,
                    calmar_ratio REAL DEFAULT 0.0,
                    var_95 REAL DEFAULT 0.0,
                    var_99 REAL DEFAULT 0.0,
                    cvar_95 REAL DEFAULT 0.0,

                    -- 交易特征
                    avg_holding_time_hours REAL DEFAULT 0.0,
                    trade_frequency_per_day REAL DEFAULT 0.0,
                    avg_leverage REAL DEFAULT 1.0,
                    max_leverage REAL DEFAULT 1.0,

                    -- 活跃度
                    active_days INTEGER DEFAULT 0,
                    last_trade_time TIMESTAMP,
                    first_trade_time TIMESTAMP,

                    -- 持仓信息
                    current_positions INTEGER DEFAULT 0,
                    current_equity REAL DEFAULT 0.0,

                    -- 综合评分
                    overall_score REAL DEFAULT 0.0,
                    rating TEXT DEFAULT 'F',

                    -- 分项评分
                    profitability_score REAL DEFAULT 0.0,
                    risk_score REAL DEFAULT 0.0,
                    consistency_score REAL DEFAULT 0.0,
                    activity_score REAL DEFAULT 0.0,

                    -- 新增分析字段
                    avg_trade_price REAL DEFAULT 0.0,
                    avg_trade_size REAL DEFAULT 0.0,
                    max_single_win REAL DEFAULT 0.0,
                    max_single_loss REAL DEFAULT 0.0,
                    max_consecutive_wins INTEGER DEFAULT 0,
                    max_consecutive_losses INTEGER DEFAULT 0,
                    avg_win_amount REAL DEFAULT 0.0,
                    avg_loss_amount REAL DEFAULT 0.0,
                    unique_symbols INTEGER DEFAULT 0,
                    favorite_symbol TEXT DEFAULT '',
                    recent_7d_pnl REAL DEFAULT 0.0,
                    recent_7d_win_rate REAL DEFAULT 0.0,
                    long_short_ratio REAL DEFAULT 0.0,

                    -- 时间段统计
                    daily_pnl REAL DEFAULT 0.0,
                    weekly_pnl REAL DEFAULT 0.0,
                    monthly_pnl REAL DEFAULT 0.0,
                    daily_roi REAL DEFAULT 0.0,
                    weekly_roi REAL DEFAULT 0.0,
                    monthly_roi REAL DEFAULT 0.0,
                    daily_volume REAL DEFAULT 0.0,
                    weekly_volume REAL DEFAULT 0.0,
                    monthly_volume REAL DEFAULT 0.0,

                    -- 用户标记
                    is_starred BOOLEAN DEFAULT FALSE
                )
            """)

            # 创建唯一索引
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_trader_address_unique
                ON trader_metrics(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trader_rating
                ON trader_metrics(rating)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trader_score
                ON trader_metrics(overall_score DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyzed_at
                ON trader_metrics(analyzed_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trader_starred
                ON trader_metrics(is_starred)
            """)

            # 创建筛选会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screening_sessions (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 配置
                    lookback_days INTEGER,
                    min_total_trades INTEGER,
                    min_win_rate REAL,
                    min_profit_factor REAL,
                    min_total_pnl REAL,
                    max_drawdown REAL,

                    -- 统计
                    total_analyzed INTEGER DEFAULT 0,
                    qualified_count INTEGER DEFAULT 0
                )
            """)

            # 创建会话-交易者关联表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_traders (
                    session_id INTEGER,
                    trader_id INTEGER,
                    rank INTEGER,
                    PRIMARY KEY (session_id, trader_id),
                    FOREIGN KEY (session_id) REFERENCES screening_sessions(id),
                    FOREIGN KEY (trader_id) REFERENCES trader_metrics(id)
                )
            """)

            # 创建交易记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_fills (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,

                    -- 交易信息
                    coin TEXT,
                    side TEXT,
                    px REAL,
                    sz REAL,
                    time BIGINT,
                    trade_time TIMESTAMP,

                    -- 盈亏
                    closed_pnl REAL DEFAULT 0.0,

                    -- 其他信息
                    hash TEXT,
                    start_position REAL,
                    dir TEXT,
                    crossed BOOLEAN,
                    fee REAL DEFAULT 0.0,
                    oid BIGINT,
                    tid BIGINT,
                    trade_type TEXT,

                    -- 唯一约束：使用 tid 作为唯一标识（tid 是交易的真正唯一ID）
                    UNIQUE(address, tid)
                )
            """)

            # 创建交易记录索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_address
                ON trader_fills(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_time
                ON trader_fills(trade_time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_coin
                ON trader_fills(coin)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_trade_type
                ON trader_fills(trade_type)
            """)

            # 创建持仓表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asset_positions (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 持仓信息
                    coin TEXT NOT NULL,
                    szi REAL DEFAULT 0.0,
                    entry_px REAL DEFAULT 0.0,
                    position_value REAL DEFAULT 0.0,
                    unrealized_pnl REAL DEFAULT 0.0,
                    return_on_equity REAL DEFAULT 0.0,
                    liquidation_px REAL,
                    margin_used REAL DEFAULT 0.0,
                    max_leverage INTEGER DEFAULT 1,
                    leverage_type TEXT,
                    leverage_value INTEGER DEFAULT 1,

                    -- 唯一约束
                    UNIQUE(address, coin)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_address
                ON asset_positions(address)
            """)

            # 创建AI分析表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_ai_analysis (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 分析结果
                    rating TEXT,
                    overall_score REAL DEFAULT 0.0,
                    analysis_text TEXT,
                    summary TEXT,
                    strengths TEXT,
                    risks TEXT,
                    trading_style TEXT,
                    copy_trading_advice TEXT,
                    improvement_suggestions TEXT,

                    -- 元数据
                    ai_provider TEXT DEFAULT 'default',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建分组对比分析表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_comparison_sessions (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 配置
                    rating TEXT DEFAULT 'S',
                    total_traders INTEGER DEFAULT 0,
                    group_size INTEGER DEFAULT 6,
                    top_per_group INTEGER DEFAULT 2,
                    final_size INTEGER DEFAULT 6,
                    num_groups INTEGER DEFAULT 0,
                    total_rounds INTEGER DEFAULT 0,

                    -- 预筛选条件
                    min_sharpe REAL,
                    min_sortino REAL,
                    max_drawdown REAL,
                    min_win_rate REAL,
                    max_win_rate REAL,

                    -- 结果
                    finalists_count INTEGER DEFAULT 0,
                    final_ranking TEXT,
                    ai_provider TEXT DEFAULT 'default',
                    status TEXT DEFAULT 'pending'
                )
            """)

            # 创建分组对比详情表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_comparison_groups (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    round_num INTEGER DEFAULT 1,
                    group_num INTEGER NOT NULL,
                    total_in_group INTEGER DEFAULT 0,
                    analysis TEXT,

                    FOREIGN KEY (session_id) REFERENCES group_comparison_sessions(id)
                )
            """)

            # 创建分组对比交易员表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_comparison_traders (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    group_id INTEGER,
                    address TEXT NOT NULL,

                    -- 交易员指标快照
                    overall_score REAL DEFAULT 0.0,
                    win_rate REAL DEFAULT 0.0,
                    total_pnl REAL DEFAULT 0.0,
                    recent_7d_pnl REAL DEFAULT 0.0,
                    max_drawdown REAL DEFAULT 0.0,
                    sharpe_ratio REAL DEFAULT 0.0,
                    sortino_ratio REAL DEFAULT 0.0,
                    profit_factor REAL DEFAULT 0.0,

                    -- 分组对比结果
                    is_finalist BOOLEAN DEFAULT FALSE,
                    final_rank INTEGER,
                    eliminated_round INTEGER,
                    elimination_reason TEXT,

                    FOREIGN KEY (session_id) REFERENCES group_comparison_sessions(id),
                    FOREIGN KEY (group_id) REFERENCES group_comparison_groups(id)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_gc_session_traders
                ON group_comparison_traders(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_gc_finalists
                ON group_comparison_traders(session_id, is_finalist)
            """)

            # 创建跟单分组表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_trading_groups (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    color TEXT DEFAULT '#3B82F6',
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 插入默认分组
            cursor.execute("""
                INSERT INTO copy_trading_groups (id, name, description, color)
                VALUES (1, '默认分组', '未分组的跟单地址', '#6B7280')
                ON CONFLICT (id) DO NOTHING
            """)

            # 创建跟单地址表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_trading_addresses (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,
                    name TEXT DEFAULT '',
                    group_id INTEGER DEFAULT NULL,
                    is_enabled BOOLEAN DEFAULT TRUE,

                    -- 跟单配置
                    copy_ratio REAL DEFAULT 0.1,
                    max_position_size_usd REAL DEFAULT 500.0,
                    min_position_size_usd REAL DEFAULT 20.0,
                    copy_leverage BOOLEAN DEFAULT TRUE,
                    max_leverage INTEGER DEFAULT 10,
                    default_leverage INTEGER DEFAULT 5,
                    max_total_positions INTEGER DEFAULT 10,
                    max_daily_trades INTEGER DEFAULT 50,
                    slippage REAL DEFAULT 0.01,
                    symbols_whitelist TEXT DEFAULT '[]',
                    symbols_blacklist TEXT DEFAULT '[]',
                    check_interval REAL DEFAULT 10.0,
                    dry_run BOOLEAN DEFAULT TRUE,
                    sync_position BOOLEAN DEFAULT TRUE,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (group_id) REFERENCES copy_trading_groups(id) ON DELETE SET NULL
                )
            """)

            # 创建跟单地址索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_address
                ON copy_trading_addresses(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_enabled
                ON copy_trading_addresses(is_enabled)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_group
                ON copy_trading_addresses(group_id)
            """)

            # 创建 Hyperliquid 币种表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hyperliquid_coins (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    sz_decimals INTEGER DEFAULT 0,
                    max_leverage INTEGER DEFAULT 1,
                    only_isolated BOOLEAN DEFAULT FALSE,
                    is_active BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建跟单订单记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_trading_orders (
                    id SERIAL PRIMARY KEY,
                    target_address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    action TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL,
                    leverage INTEGER DEFAULT 1,
                    copy_ratio REAL,
                    target_size REAL,
                    target_entry_price REAL,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    pnl REAL DEFAULT 0.0,
                    is_dry_run BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    executed_at TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_target
                ON copy_trading_orders(target_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_symbol
                ON copy_trading_orders(symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_created
                ON copy_trading_orders(created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_status
                ON copy_trading_orders(status)
            """)

            # 创建跟单仓位状态表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_position_states (
                    id SERIAL PRIMARY KEY,
                    target_address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    size REAL NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL,
                    leverage INTEGER DEFAULT 1,
                    notional REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 唯一约束
                    UNIQUE(target_address, symbol)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_states_target
                ON copy_position_states(target_address)
            """)

            # 创建系统配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    id SERIAL PRIMARY KEY,
                    config_key TEXT NOT NULL UNIQUE,
                    config_value TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 创建仓位历史表（记录完整的开仓→平仓周期）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS position_history (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,
                    coin TEXT NOT NULL,

                    -- 仓位方向
                    direction TEXT NOT NULL,           -- 'long' 或 'short'

                    -- 时间信息
                    open_time TIMESTAMP NOT NULL,      -- 开仓时间
                    close_time TIMESTAMP,              -- 平仓时间（NULL表示未平仓）

                    -- 仓位信息
                    max_size REAL DEFAULT 0.0,         -- 最大仓位大小
                    avg_entry_price REAL DEFAULT 0.0,  -- 平均开仓价格
                    avg_close_price REAL,              -- 平均平仓价格
                    total_volume REAL DEFAULT 0.0,     -- 总交易量（开仓+平仓）

                    -- 盈亏信息
                    realized_pnl REAL DEFAULT 0.0,     -- 已实现盈亏
                    total_fee REAL DEFAULT 0.0,        -- 总手续费

                    -- 交易统计
                    open_trades INTEGER DEFAULT 1,     -- 开仓交易次数（包含加仓）
                    close_trades INTEGER DEFAULT 0,    -- 平仓交易次数

                    -- 持仓时长（小时）
                    holding_hours REAL,

                    -- 状态
                    status TEXT DEFAULT 'open',        -- 'open' 或 'closed'

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_address
                ON position_history(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_coin
                ON position_history(coin)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_status
                ON position_history(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_open_time
                ON position_history(open_time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_history_address_coin
                ON position_history(address, coin)
            """)

            # 运行增量迁移
            self._run_migrations(cursor)

            logger.info("PostgreSQL 数据库表结构初始化完成")

    def _run_migrations(self, cursor):
        """运行增量迁移"""
        # 添加 is_starred 字段到 trader_metrics 表
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'is_starred', 'BOOLEAN DEFAULT FALSE'
        )

        # 添加 open_time 字段到 asset_positions 表（用于记录仓位开仓时间）
        self._migrate_add_column_if_not_exists(
            cursor, 'asset_positions', 'open_time', 'TIMESTAMP'
        )
