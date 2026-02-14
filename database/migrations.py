"""
数据库迁移和表结构初始化 (PostgreSQL)
"""
from ulid import ULID
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
                    display_name TEXT DEFAULT '',
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

                    -- 账户和保证金
                    account_value REAL DEFAULT 0.0,
                    used_margin REAL DEFAULT 0.0,
                    perp_total_value REAL DEFAULT 0.0,
                    position_value REAL DEFAULT 0.0,
                    long_position_value REAL DEFAULT 0.0,
                    short_position_value REAL DEFAULT 0.0,
                    margin_usage_rate REAL DEFAULT 0.0,

                    -- 多空分项
                    long_trades INTEGER DEFAULT 0,
                    long_realized_pnl REAL DEFAULT 0.0,
                    long_win_rate REAL DEFAULT 0.0,
                    short_trades INTEGER DEFAULT 0,
                    short_realized_pnl REAL DEFAULT 0.0,
                    short_win_rate REAL DEFAULT 0.0,
                    long_position_ratio REAL DEFAULT 0.0,

                    -- 用户标记
                    is_starred BOOLEAN DEFAULT FALSE,

                    -- 交易者标签（旧6列）
                    tag_capital_scale TEXT,
                    tag_trading_direction TEXT,
                    tag_trading_cycle TEXT,
                    tag_frequency_style TEXT,
                    tag_return_risk TEXT,
                    tag_strategy_capability TEXT,

                    -- 交易者标签（新5列，英文值存储）
                    tag_account_value TEXT,
                    tag_trading_rhythm TEXT,
                    tag_profit_status TEXT,
                    tag_direction_preference TEXT,
                    tag_trading_style TEXT
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

            # 迁移：为已有数据库添加新列
            new_columns = [
                ("account_value", "REAL DEFAULT 0.0"),
                ("used_margin", "REAL DEFAULT 0.0"),
                ("perp_total_value", "REAL DEFAULT 0.0"),
                ("position_value", "REAL DEFAULT 0.0"),
                ("long_position_value", "REAL DEFAULT 0.0"),
                ("short_position_value", "REAL DEFAULT 0.0"),
                ("margin_usage_rate", "REAL DEFAULT 0.0"),
                ("long_trades", "INTEGER DEFAULT 0"),
                ("long_realized_pnl", "REAL DEFAULT 0.0"),
                ("long_win_rate", "REAL DEFAULT 0.0"),
                ("short_trades", "INTEGER DEFAULT 0"),
                ("short_realized_pnl", "REAL DEFAULT 0.0"),
                ("short_win_rate", "REAL DEFAULT 0.0"),
                ("long_position_ratio", "REAL DEFAULT 0.0"),
            ]
            for col_name, col_def in new_columns:
                cursor.execute(f"""
                    ALTER TABLE trader_metrics
                    ADD COLUMN IF NOT EXISTS {col_name} {col_def}
                """)

            # 创建交易记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_fills (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,

                    -- 交易信息
                    coin TEXT,
                    side CHAR(1),                   -- 'A' 或 'B'（1字节）
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
                    trade_type SMALLINT,            -- 1-6（2字节）

                    -- 唯一约束：使用 tid 作为唯一标识（tid 是交易的真正唯一ID）
                    UNIQUE(address, tid)
                )
            """)

            # trader_fills 索引已通过 scripts/add_fills_index.py 单独创建
            # 避免在初始化时创建大表索引导致超时

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
                    open_time TIMESTAMP,

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

            # 创建跟单地址表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_trading_addresses (
                    id TEXT PRIMARY KEY,                  -- ULID
                    user_id TEXT,                         -- 用户ID (ULID)
                    address TEXT NOT NULL,
                    name TEXT DEFAULT '',
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

                    -- 自动补仓
                    auto_replenish BOOLEAN DEFAULT FALSE,
                    replenish_ratio REAL DEFAULT 0.5,
                    replenish_min_value_usd REAL DEFAULT 10.0,
                    replenish_max_value_usd REAL DEFAULT 100.0,

                    -- 只跟一次
                    copy_once BOOLEAN DEFAULT FALSE,

                    -- 保证金模式: cross(全仓) / isolated(逐仓)
                    margin_mode TEXT DEFAULT 'cross',

                    -- 止盈止损
                    take_profit_enabled BOOLEAN DEFAULT FALSE,
                    take_profit_percent FLOAT DEFAULT 50,
                    stop_loss_enabled BOOLEAN DEFAULT FALSE,
                    stop_loss_percent FLOAT DEFAULT 20,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 唯一约束：每个用户对同一地址只能有一条记录
                    UNIQUE(user_id, address)
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
                CREATE INDEX IF NOT EXISTS idx_copy_trading_addresses_user_id
                ON copy_trading_addresses(user_id)
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

            # 注意: copy_trading_orders 表已弃用，不再创建
            # 如需删除此表，请手动执行: DROP TABLE IF EXISTS copy_trading_orders;

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

            # 创建仓位级别跟单表（第二种跟单模式：跟单特定仓位）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_position_tracking (
                    id TEXT PRIMARY KEY,                  -- ULID
                    target_address TEXT NOT NULL,         -- 目标交易员地址
                    target_name TEXT DEFAULT '',          -- 交易员名称
                    symbol TEXT NOT NULL,                 -- 跟单币种

                    -- 跟单配置
                    is_enabled BOOLEAN DEFAULT TRUE,
                    copy_ratio REAL DEFAULT 0.1,
                    max_position_size_usd REAL DEFAULT 500.0,
                    min_position_size_usd REAL DEFAULT 20.0,
                    copy_leverage BOOLEAN DEFAULT TRUE,
                    max_leverage INTEGER DEFAULT 10,
                    default_leverage INTEGER DEFAULT 5,
                    slippage REAL DEFAULT 0.01,

                    -- 自动补仓
                    auto_replenish BOOLEAN DEFAULT FALSE,
                    replenish_ratio REAL DEFAULT 0.5,
                    replenish_min_value_usd REAL DEFAULT 10.0,
                    replenish_max_value_usd REAL DEFAULT 100.0,

                    -- 目标仓位快照（开始跟单时的状态）
                    target_initial_size REAL,
                    target_initial_side TEXT,
                    target_initial_entry_price REAL,
                    target_initial_leverage REAL,

                    -- 我方跟单状态
                    my_size REAL DEFAULT 0.0,
                    my_side TEXT,
                    my_entry_price REAL,

                    -- 状态: pending/active/closed/stopped
                    status TEXT DEFAULT 'pending',
                    closed_pnl REAL,
                    close_reason TEXT,

                    -- 交易员标记
                    target_is_starred BOOLEAN DEFAULT FALSE,

                    -- 交易员评分信息
                    target_score REAL,
                    target_rating TEXT,

                    -- 保证金模式: cross(全仓) / isolated(逐仓)
                    position_mode TEXT DEFAULT 'cross',

                    -- 止盈止损
                    take_profit_enabled BOOLEAN DEFAULT FALSE,
                    take_profit_percent FLOAT DEFAULT 50,
                    stop_loss_enabled BOOLEAN DEFAULT FALSE,
                    stop_loss_percent FLOAT DEFAULT 20,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    closed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_tracking_target
                ON copy_position_tracking(target_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_tracking_symbol
                ON copy_position_tracking(symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_tracking_status
                ON copy_position_tracking(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_tracking_enabled
                ON copy_position_tracking(is_enabled)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_position_tracking_active_unique
                ON copy_position_tracking(target_address, symbol)
                WHERE status IN ('pending', 'active')
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

            # 创建仓位计算状态表（用于增量计算）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS position_calc_state (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,

                    -- 最后处理的 fill 时间戳
                    last_processed_fill_time BIGINT DEFAULT 0,

                    -- 当前未平仓仓位的 JSON 快照
                    open_positions_snapshot JSONB DEFAULT '{}',

                    -- 计算统计
                    total_fills_processed INTEGER DEFAULT 0,
                    total_positions_generated INTEGER DEFAULT 0,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_calc_state_address
                ON position_calc_state(address)
            """)

            # 创建持仓AI分析结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions_ai_analysis (
                    id SERIAL PRIMARY KEY,

                    -- 分析类型和标识
                    analysis_type TEXT NOT NULL,        -- 'overall' | 'coin' | 'single'
                    analysis_key TEXT NOT NULL UNIQUE,  -- 唯一标识符：overall_hash / coin_{coin}_hash / single_{address}_{coin}_hash

                    -- 分析目标信息
                    coin TEXT,                          -- 币种（coin/single类型时有值）
                    address TEXT,                       -- 地址（single类型时有值）
                    position_count INTEGER DEFAULT 0,   -- 分析的持仓数量

                    -- 分析结果
                    analysis_text TEXT,                 -- 完整分析文本
                    sections JSONB,                     -- 分段解析后的JSON

                    -- 分析时的统计数据快照
                    stats_snapshot JSONB,               -- 统计数据快照

                    -- 元数据
                    ai_provider TEXT DEFAULT 'default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_ai_analysis_type
                ON positions_ai_analysis(analysis_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_ai_analysis_key
                ON positions_ai_analysis(analysis_key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_ai_analysis_coin
                ON positions_ai_analysis(coin)
            """)

            # 创建新仓位检测记录表（监控脚本检测到的新仓位）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detected_new_positions (
                    id SERIAL PRIMARY KEY,

                    -- 交易员信息
                    trader_address TEXT NOT NULL,
                    trader_name TEXT DEFAULT '',
                    trader_rating TEXT,
                    trader_score REAL,

                    -- 仓位信息
                    coin TEXT NOT NULL,
                    direction TEXT NOT NULL,          -- 'long' 或 'short'
                    szi REAL DEFAULT 0.0,             -- 仓位大小（绝对值）
                    entry_px REAL DEFAULT 0.0,        -- 开仓价格
                    position_value REAL DEFAULT 0.0,  -- 仓位价值（USD）
                    leverage INTEGER DEFAULT 1,       -- 杠杆倍数

                    -- 检测信息
                    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified BOOLEAN DEFAULT FALSE,   -- 是否已发送通知

                    -- 可选：跟单相关
                    copy_tracking_id INTEGER,         -- 关联的跟单记录ID

                    -- 交易员标记
                    target_is_starred BOOLEAN DEFAULT FALSE,  -- 目标交易员是否被标记
                    is_whale BOOLEAN DEFAULT FALSE,

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detected_new_positions_trader
                ON detected_new_positions(trader_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detected_new_positions_coin
                ON detected_new_positions(coin)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detected_new_positions_detected_at
                ON detected_new_positions(detected_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detected_new_positions_rating
                ON detected_new_positions(trader_rating)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_detected_new_positions_direction
                ON detected_new_positions(direction)
            """)

            # 创建通知表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,

                    -- 通知类型和内容
                    type TEXT NOT NULL,                    -- 'open' | 'close' | 'adjust' | 'error'
                    title TEXT NOT NULL,                   -- 通知标题
                    content TEXT NOT NULL,                 -- Markdown 格式内容

                    -- 关联信息
                    target_address TEXT,                   -- 目标交易员地址
                    symbol TEXT,                           -- 交易对
                    side TEXT,                             -- 'long' | 'short'
                    size REAL,                             -- 仓位大小
                    pnl REAL,                              -- 盈亏（平仓时）

                    -- 用户关联
                    user_id TEXT,                              -- 用户ID (ULID)

                    -- 状态
                    is_read BOOLEAN DEFAULT FALSE,         -- 是否已读

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_type
                ON notifications(type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_is_read
                ON notifications(is_read)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_created_at
                ON notifications(created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_target_address
                ON notifications(target_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notifications_user_id
                ON notifications(user_id)
            """)

            # 创建通知已读标记表（基于水位线的每用户已读追踪）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notification_read_marks (
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    read_before_id INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, category)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notification_read_marks_user
                ON notification_read_marks(user_id)
            """)

            # 创建秘钥表（用于注册验证）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS secret_keys (
                    id SERIAL PRIMARY KEY,
                    key_value TEXT NOT NULL UNIQUE,              -- 秘钥值（唯一）
                    key_name TEXT DEFAULT '',                    -- 秘钥名称/备注

                    -- 秘钥配置
                    user_role TEXT DEFAULT 'user',               -- 使用此秘钥注册的用户身份: user/member/admin
                    expires_days INTEGER DEFAULT 30,             -- 注册用户的有效天数（0表示永不过期）
                    is_used BOOLEAN DEFAULT FALSE,               -- 是否已使用
                    used_by_user_id TEXT,                        -- 使用此秘钥的用户ID (ULID)

                    -- 状态
                    is_active BOOLEAN DEFAULT TRUE,              -- 是否启用

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,                        -- 秘钥过期时间（NULL表示永不过期）
                    created_by INTEGER                           -- 创建者用户ID
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_secret_keys_value
                ON secret_keys(key_value)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_secret_keys_is_active
                ON secret_keys(is_active)
            """)

            # 创建用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,                         -- ULID
                    account TEXT NOT NULL UNIQUE,                -- 账号（唯一）
                    password_hash TEXT NOT NULL,                 -- 密码哈希
                    secret_key_id INTEGER,                       -- 关联的秘钥ID

                    -- 用户身份: user(普通用户) / member(会员) / admin(超级管理员)
                    role TEXT DEFAULT 'user',

                    -- Hyperliquid API 设置
                    api_wallet TEXT DEFAULT '',                  -- API 钱包地址
                    wallet_address TEXT DEFAULT '',              -- 钱包地址
                    api_key TEXT,                                -- Trading 服务认证用

                    -- 访问控制
                    allowed_ip TEXT DEFAULT '',                  -- 允许的IP
                    allowed_port TEXT DEFAULT '',                -- 允许的端口

                    -- 账户状态
                    expires_at TIMESTAMP,                        -- 过期时间（NULL表示永不过期）
                    is_active BOOLEAN DEFAULT TRUE,              -- 账户是否激活

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TIMESTAMP,                     -- 最后登录时间

                    FOREIGN KEY (secret_key_id) REFERENCES secret_keys(id) ON DELETE SET NULL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_account
                ON users(account)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_is_active
                ON users(is_active)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_expires_at
                ON users(expires_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_role
                ON users(role)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_api_key
                ON users(api_key)
                WHERE api_key IS NOT NULL
            """)

            # 创建用户收藏表（用户维度的交易者收藏）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_favorites (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,                 -- 用户 ID (ULID)
                    trader_address TEXT NOT NULL,          -- 交易者地址
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 唯一约束：每个用户对每个交易者只能收藏一次
                    UNIQUE(user_id, trader_address)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_favorites_user_id
                ON user_favorites(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_favorites_trader_address
                ON user_favorites(trader_address)
            """)

            # 创建应用版本管理表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_versions (
                    id SERIAL PRIMARY KEY,
                    version TEXT NOT NULL,                       -- 版本号（如 1.0.0）
                    version_name TEXT DEFAULT '',                -- 版本名称/别名
                    description TEXT DEFAULT '',                 -- 版本描述
                    release_notes TEXT DEFAULT '',               -- 更新日志
                    download_url TEXT DEFAULT '',                -- 下载链接

                    -- 更新配置
                    is_force_update BOOLEAN DEFAULT FALSE,       -- 是否强制更新
                    is_visible BOOLEAN DEFAULT TRUE,             -- 是否对用户可见（管理员可控制）
                    min_supported_version TEXT DEFAULT '',       -- 最低支持版本

                    -- 平台
                    platform TEXT DEFAULT 'all',                 -- 平台: all/android/ios/web

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER                           -- 创建者用户ID
                )
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_app_versions_version_platform
                ON app_versions(version, platform)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_app_versions_is_visible
                ON app_versions(is_visible)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_app_versions_platform
                ON app_versions(platform)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_app_versions_created_at
                ON app_versions(created_at DESC)
            """)

            # 创建地址跟踪表（用于监控特定地址的交易活动）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS address_tracking (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,                       -- 用户ID (ULID)
                    tracking_address TEXT NOT NULL,              -- 跟踪地址
                    address_remark TEXT DEFAULT '',              -- 地址备注

                    -- 跟踪配置
                    is_enabled BOOLEAN DEFAULT TRUE,             -- 是否启用跟踪
                    enable_notification BOOLEAN DEFAULT TRUE,    -- 是否开启通知
                    monitor_events TEXT DEFAULT '["open","close","add","reduce"]',  -- 监控事件（JSON数组）

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 唯一约束：每个用户对同一地址只能有一个跟踪记录
                    UNIQUE(user_id, tracking_address)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_address_tracking_user_id
                ON address_tracking(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_address_tracking_address
                ON address_tracking(tracking_address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_address_tracking_enabled
                ON address_tracking(is_enabled)
            """)

            # 创建跟单配置规则表（支持按杠杆区间分配不同配置）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_config_rules (
                    id TEXT PRIMARY KEY,                -- ULID
                    user_id TEXT,                       -- 用户ID (ULID)

                    -- 规则类型和名称
                    config_type TEXT NOT NULL,          -- 'default' 或 'immediate'
                    name TEXT NOT NULL,                 -- 规则名称
                    description TEXT DEFAULT '',        -- 规则描述
                    symbol TEXT,                        -- 币种（立即跟单时指定）

                    -- 杠杆区间（左开右闭: leverage_min < leverage <= leverage_max）
                    leverage_min REAL DEFAULT 0,        -- 杠杆下限（不包含），0表示从最小开始
                    leverage_max REAL DEFAULT 100,      -- 杠杆上限（包含），100表示无上限

                    -- 配置数据（JSON格式）
                    config_data JSONB NOT NULL,

                    -- 优先级和状态
                    priority INTEGER DEFAULT 0,         -- 优先级，数字越小优先级越高
                    is_enabled BOOLEAN DEFAULT TRUE,    -- 是否启用
                    is_default BOOLEAN DEFAULT FALSE,   -- 是否为默认配置（兜底规则）

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_config_rules_type
                ON copy_config_rules(config_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_config_rules_enabled
                ON copy_config_rules(is_enabled)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_config_rules_priority
                ON copy_config_rules(config_type, priority)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_copy_config_rules_user_id
                ON copy_config_rules(user_id)
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_copy_config_rules_user_immediate_symbol
                ON copy_config_rules(user_id, config_type, symbol)
                WHERE config_type = 'immediate' AND symbol IS NOT NULL AND user_id IS NOT NULL
            """)

            # 创建资金费历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_funding_history (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,

                    -- 资金费信息
                    coin TEXT NOT NULL,
                    funding_rate TEXT,             -- 资金费率（保留字符串精度）
                    szi REAL DEFAULT 0.0,          -- 持仓数量
                    usdc REAL DEFAULT 0.0,         -- 资金费金额（USDC）
                    n_samples INTEGER,             -- 采样数
                    hash TEXT,                     -- 交易哈希
                    time BIGINT NOT NULL,          -- 毫秒时间戳

                    -- 唯一约束：同一地址、时间、币种只会有一条资金费记录
                    UNIQUE(address, time, coin)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_funding_history_address
                ON trader_funding_history(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_funding_history_time
                ON trader_funding_history(time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_funding_history_address_time
                ON trader_funding_history(address, time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_funding_history_coin
                ON trader_funding_history(coin)
            """)

            # 创建历史委托表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_historical_orders (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,

                    -- 委托信息
                    coin TEXT,
                    side CHAR(1),                   -- 'A' 或 'B'
                    limit_px TEXT,                   -- 限价（保留字符串精度）
                    sz TEXT,                         -- 当前数量
                    orig_sz TEXT,                    -- 原始数量
                    oid BIGINT NOT NULL,             -- 委托 ID
                    order_type TEXT DEFAULT 'Limit', -- 委托类型
                    is_trigger BOOLEAN DEFAULT FALSE,
                    trigger_condition TEXT DEFAULT '',
                    trigger_px TEXT DEFAULT '',
                    is_position_tpsl BOOLEAN DEFAULT FALSE,
                    reduce_only BOOLEAN DEFAULT FALSE,
                    order_timestamp BIGINT DEFAULT 0, -- 下单时间（毫秒）
                    cloid TEXT DEFAULT '',            -- 客户端委托 ID

                    -- 状态
                    status TEXT DEFAULT '',           -- filled/canceled/rejected/triggered/open/marginCanceled
                    status_timestamp BIGINT DEFAULT 0, -- 状态更新时间（毫秒）

                    -- 唯一约束：同一地址的同一委托 ID 唯一
                    UNIQUE(address, oid)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_historical_orders_address
                ON trader_historical_orders(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_historical_orders_status
                ON trader_historical_orders(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_historical_orders_address_status_ts
                ON trader_historical_orders(address, status_timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_historical_orders_coin
                ON trader_historical_orders(coin)
            """)

            # 创建出入金（非资金费账本更新）表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_ledger_updates (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,

                    -- 账本信息
                    delta_type TEXT NOT NULL,         -- 类型: deposit, withdraw, internalTransfer,
                                                     -- spotTransfer, accountClassTransfer, liquidation 等
                    usdc REAL DEFAULT 0.0,            -- 金额（USDC）
                    fee REAL DEFAULT 0.0,             -- 手续费
                    nonce BIGINT,                     -- 交易 nonce（部分类型有）
                    destination TEXT DEFAULT '',      -- 目标地址（转账时有）
                    user_field TEXT DEFAULT '',       -- 用户字段（部分类型有）
                    hash TEXT,                        -- 交易哈希
                    time BIGINT NOT NULL,             -- 毫秒时间戳
                    delta_json JSONB,                 -- 完整 delta 数据（灵活存储）

                    -- 唯一约束
                    UNIQUE(address, hash, time)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_updates_address
                ON trader_ledger_updates(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_updates_time
                ON trader_ledger_updates(time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_updates_address_time
                ON trader_ledger_updates(address, time DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_updates_delta_type
                ON trader_ledger_updates(delta_type)
            """)

            # 创建巨鲸锚点表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whale_anchor (
                    id SERIAL PRIMARY KEY,
                    coin TEXT NOT NULL UNIQUE,
                    mark_price REAL NOT NULL DEFAULT 0,
                    price_change_24h_pct REAL NOT NULL DEFAULT 0,
                    day_volume_usd REAL NOT NULL DEFAULT 0,
                    open_interest_usd REAL NOT NULL DEFAULT 0,
                    depth_1pct_usd REAL NOT NULL DEFAULT 0,
                    volume_component REAL NOT NULL DEFAULT 0,
                    oi_component REAL NOT NULL DEFAULT 0,
                    depth_component REAL NOT NULL DEFAULT 0,
                    whale_threshold REAL NOT NULL DEFAULT 0,
                    dominant_factor TEXT NOT NULL DEFAULT 'none',
                    max_leverage INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whale_anchor_coin
                ON whale_anchor(coin)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_whale_anchor_threshold
                ON whale_anchor(whale_threshold DESC)
            """)

            # 创建交易者 PnL 历史表（portfolio perp 数据）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_pnl_history (
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL,
                    period TEXT NOT NULL,
                    time BIGINT NOT NULL,
                    pnl DOUBLE PRECISION DEFAULT 0.0,
                    account_value DOUBLE PRECISION DEFAULT 0.0,
                    vlm DOUBLE PRECISION DEFAULT 0.0,

                    UNIQUE(address, period, time)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pnl_history_address
                ON trader_pnl_history(address)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_pnl_history_address_period
                ON trader_pnl_history(address, period)
            """)

            # 创建持仓多空比快照表（用于 Short Ratio 曲线图）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS position_ratio_snapshots (
                    id SERIAL PRIMARY KEY,
                    coin TEXT NOT NULL,
                    snapshot_time TIMESTAMP NOT NULL,
                    long_count INTEGER NOT NULL DEFAULT 0,
                    short_count INTEGER NOT NULL DEFAULT 0,
                    long_value DOUBLE PRECISION NOT NULL DEFAULT 0,
                    short_value DOUBLE PRECISION NOT NULL DEFAULT 0,

                    UNIQUE(coin, snapshot_time)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ratio_snapshots_coin_time
                ON position_ratio_snapshots(coin, snapshot_time DESC)
            """)

            logger.info("PostgreSQL 数据库表结构初始化完成")
