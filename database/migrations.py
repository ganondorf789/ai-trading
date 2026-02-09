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

                    -- 用户标记
                    is_starred BOOLEAN DEFAULT FALSE,

                    -- 交易者标签
                    tag_capital_scale TEXT,
                    tag_trading_direction TEXT,
                    tag_trading_cycle TEXT,
                    tag_frequency_style TEXT,
                    tag_return_risk TEXT,
                    tag_strategy_capability TEXT
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
                    id SERIAL PRIMARY KEY,
                    address TEXT NOT NULL UNIQUE,
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

                    -- 时间戳
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                    id SERIAL PRIMARY KEY,
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
                    target_is_starred BOOLEAN DEFAULT FALSE,  -- 目标交易员是否被标记
                    
                    -- 交易员评分信息
                    target_score REAL,                        -- 目标交易员评分
                    target_rating TEXT,                       -- 目标交易员评级
                    
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
                    used_by_user_id INTEGER,                     -- 使用此秘钥的用户ID
                    
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
                    id SERIAL PRIMARY KEY,
                    account TEXT NOT NULL UNIQUE,                -- 账号（唯一）
                    password_hash TEXT NOT NULL,                 -- 密码哈希
                    secret_key_id INTEGER,                       -- 关联的秘钥ID
                    
                    -- 用户身份: user(普通用户) / member(会员) / admin(超级管理员)
                    role TEXT DEFAULT 'user',
                    
                    -- Hyperliquid API 设置
                    api_wallet TEXT DEFAULT '',                  -- API 钱包地址
                    wallet_address TEXT DEFAULT '',              -- 钱包地址
                    
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

            # 创建用户收藏表（用户维度的交易者收藏）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_favorites (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,              -- 用户 ID
                    trader_address TEXT NOT NULL,          -- 交易者地址
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- 唯一约束：每个用户对每个交易者只能收藏一次
                    UNIQUE(user_id, trader_address),
                    
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

            # 创建跟单配置规则表（支持按杠杆区间分配不同配置）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_config_rules (
                    id SERIAL PRIMARY KEY,
                    
                    -- 规则类型和名称
                    config_type TEXT NOT NULL,          -- 'default' 或 'immediate'
                    name TEXT NOT NULL,                 -- 规则名称
                    description TEXT DEFAULT '',        -- 规则描述
                    
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

            # 运行增量迁移
            self._run_migrations(cursor)

            logger.info("PostgreSQL 数据库表结构初始化完成")

    def _run_migrations(self, cursor):
        """运行增量迁移"""
        # 删除分组功能相关的表和列
        self._migrate_remove_groups(cursor)
        
        # 添加 is_starred 字段到 trader_metrics 表
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'is_starred', 'BOOLEAN DEFAULT FALSE'
        )

        # 添加 open_time 字段到 asset_positions 表（用于记录仓位开仓时间）
        self._migrate_add_column_if_not_exists(
            cursor, 'asset_positions', 'open_time', 'TIMESTAMP'
        )

        # 添加自动补仓相关字段到 copy_trading_addresses 表
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_trading_addresses', 'auto_replenish', 'BOOLEAN DEFAULT FALSE'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_trading_addresses', 'replenish_ratio', 'REAL DEFAULT 0.5'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_trading_addresses', 'replenish_min_value_usd', 'REAL DEFAULT 10.0'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_trading_addresses', 'replenish_max_value_usd', 'REAL DEFAULT 100.0'
        )

        # 添加只跟一次字段到 copy_trading_addresses 表
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_trading_addresses', 'copy_once', 'BOOLEAN DEFAULT FALSE'
        )

        # 添加 target_is_starred 字段到 detected_new_positions 表
        self._migrate_add_column_if_not_exists(
            cursor, 'detected_new_positions', 'target_is_starred', 'BOOLEAN DEFAULT FALSE'
        )

        # 添加 target_is_starred 字段到 copy_position_tracking 表
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'target_is_starred', 'BOOLEAN DEFAULT FALSE'
        )

        # 添加 target_initial_leverage 字段到 copy_position_tracking 表
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'target_initial_leverage', 'REAL'
        )

        # 添加自动补仓相关字段到 copy_position_tracking 表
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'auto_replenish', 'BOOLEAN DEFAULT FALSE'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'replenish_ratio', 'REAL DEFAULT 0.5'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'replenish_min_value_usd', 'REAL DEFAULT 10.0'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'replenish_max_value_usd', 'REAL DEFAULT 100.0'
        )

        # 添加 symbol 字段到 copy_config_rules 表（立即跟单按币种配置）
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_config_rules', 'symbol', 'TEXT'
        )
        
        # 创建立即跟单配置规则的币种唯一索引（每个币种最多一个配置）
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_copy_config_rules_immediate_symbol
            ON copy_config_rules(config_type, symbol)
            WHERE config_type = 'immediate' AND symbol IS NOT NULL
        """)

        # 添加 role 字段到 users 表（用户身份）
        self._migrate_add_column_if_not_exists(
            cursor, 'users', 'role', "TEXT DEFAULT 'user'"
        )
        
        # 添加 secret_key_id 字段到 users 表（关联秘钥）
        self._migrate_add_column_if_not_exists(
            cursor, 'users', 'secret_key_id', 'INTEGER'
        )
        
        # 添加 is_used 字段到 secret_keys 表（是否已使用）
        self._migrate_add_column_if_not_exists(
            cursor, 'secret_keys', 'is_used', 'BOOLEAN DEFAULT FALSE'
        )
        
        # 添加 used_by_user_id 字段到 secret_keys 表（使用秘钥的用户ID）
        self._migrate_add_column_if_not_exists(
            cursor, 'secret_keys', 'used_by_user_id', 'INTEGER'
        )

        # 添加 user_id 字段到 copy_trading_addresses 表（每个用户独立的跟单地址配置）
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_trading_addresses', 'user_id', 'INTEGER'
        )
        # 创建用户+地址的唯一索引，并移除旧的地址唯一约束
        cursor.execute("""
            ALTER TABLE copy_trading_addresses 
            DROP CONSTRAINT IF EXISTS copy_trading_addresses_address_key
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_copy_trading_addresses_user_address
            ON copy_trading_addresses(user_id, address)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_copy_trading_addresses_user_id
            ON copy_trading_addresses(user_id)
        """)

        # 添加 user_id 字段到 copy_config_rules 表（每个用户独立的配置规则）
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_config_rules', 'user_id', 'INTEGER'
        )
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_copy_config_rules_user_id
            ON copy_config_rules(user_id)
        """)
        # 更新立即跟单配置规则的唯一索引，加入 user_id
        cursor.execute("""
            DROP INDEX IF EXISTS idx_copy_config_rules_immediate_symbol
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_copy_config_rules_immediate_symbol
            ON copy_config_rules(user_id, config_type, symbol)
            WHERE config_type = 'immediate' AND symbol IS NOT NULL
        """)

        # 添加交易者标签字段到 trader_metrics 表
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'tag_capital_scale', 'TEXT'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'tag_trading_direction', 'TEXT'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'tag_trading_cycle', 'TEXT'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'tag_frequency_style', 'TEXT'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'tag_return_risk', 'TEXT'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'tag_strategy_capability', 'TEXT'
        )

        # 添加 target_score 和 target_rating 字段到 copy_position_tracking 表
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'target_score', 'REAL'
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'copy_position_tracking', 'target_rating', 'TEXT'
        )

        # 添加 api_key 字段到 users 表（Trading 服务认证用）
        self._migrate_add_column_if_not_exists(
            cursor, 'users', 'api_key', 'TEXT'
        )
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_api_key
            ON users(api_key)
            WHERE api_key IS NOT NULL
        """)

        # 添加 allowed_ip 和 allowed_port 字段到 users 表
        self._migrate_add_column_if_not_exists(
            cursor, 'users', 'allowed_ip', "TEXT DEFAULT ''"
        )
        self._migrate_add_column_if_not_exists(
            cursor, 'users', 'allowed_port', "TEXT DEFAULT ''"
        )

        # 添加 user_id 字段到 notifications 表（通知与用户关联）
        self._migrate_add_column_if_not_exists(
            cursor, 'notifications', 'user_id', 'INTEGER'
        )
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_user_id
            ON notifications(user_id)
        """)

        # 添加 display_name 字段到 trader_metrics 表（排行榜显示名称）
        self._migrate_add_column_if_not_exists(
            cursor, 'trader_metrics', 'display_name', "TEXT DEFAULT ''"
        )

        # 创建通知已读标记表（基于水位线的每用户已读追踪）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_read_marks (
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,          -- 'all' | 'announcement' | 'market' | 'trading' | 'error'
                read_before_id INTEGER NOT NULL DEFAULT 0,  -- notification.id <= 此值视为已读
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, category)
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notification_read_marks_user
            ON notification_read_marks(user_id)
        """)

    def _migrate_remove_groups(self, cursor):
        """
        移除分组功能相关的表和列
        
        这是一个破坏性迁移，会删除：
        - copy_trading_groups 表
        - copy_trading_addresses.group_id 列
        - idx_copy_group 索引
        """
        # 检查 group_id 列是否存在
        if self._column_exists(cursor, 'copy_trading_addresses', 'group_id'):
            # 删除索引
            cursor.execute("DROP INDEX IF EXISTS idx_copy_group")
            logger.info("数据库迁移: 删除索引 idx_copy_group")
            
            # 删除外键约束（如果存在）
            cursor.execute("""
                ALTER TABLE copy_trading_addresses 
                DROP CONSTRAINT IF EXISTS copy_trading_addresses_group_id_fkey
            """)
            
            # 删除列
            cursor.execute("ALTER TABLE copy_trading_addresses DROP COLUMN group_id")
            logger.info("数据库迁移: 删除列 copy_trading_addresses.group_id")
        
        # 删除分组表
        cursor.execute("DROP TABLE IF EXISTS copy_trading_groups")
        logger.info("数据库迁移: 删除表 copy_trading_groups")
