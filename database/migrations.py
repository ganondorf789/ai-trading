"""
数据库迁移和表结构初始化
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    monthly_volume REAL DEFAULT 0.0
                )
            """)

            # 创建唯一索引（address 作为主键）
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

            # 创建筛选会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS screening_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,

                    -- 交易信息
                    coin TEXT,
                    side TEXT,
                    px REAL,
                    sz REAL,
                    time INTEGER,
                    trade_time TIMESTAMP,

                    -- 盈亏
                    closed_pnl REAL DEFAULT 0.0,

                    -- 其他信息
                    hash TEXT,
                    start_position REAL,
                    dir TEXT,
                    crossed BOOLEAN,
                    fee REAL DEFAULT 0.0,
                    oid INTEGER,
                    tid INTEGER,
                    trade_type TEXT,  -- 交易类型: open_long/add_long/close_long/open_short/add_short/close_short

                    -- 唯一约束：同一地址同一时间同一交易
                    UNIQUE(address, time, oid)
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

            # 迁移：为现有表添加新列（如果不存在）
            self._migrate_add_new_columns(cursor)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_coin
                ON trader_fills(coin)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_trade_type
                ON trader_fills(trade_type)
            """)

            # 为 trader_fills 表添加 trade_type 列（如果不存在）
            self._migrate_fills_add_trade_type(cursor)

            # 创建持仓表（存储 assetPositions）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asset_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

                    -- 唯一约束：同一地址同一币种只保留一条记录
                    UNIQUE(address, coin)
                )
            """)

            # 创建AI分析表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trader_ai_analysis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    final_ranking TEXT,  -- JSON: 最终排名分析
                    ai_provider TEXT DEFAULT 'default',
                    status TEXT DEFAULT 'pending'  -- pending/running/completed/failed
                )
            """)

            # 创建分组对比详情表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_comparison_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    round_num INTEGER DEFAULT 1,
                    group_num INTEGER NOT NULL,
                    total_in_group INTEGER DEFAULT 0,
                    analysis TEXT,  -- AI 分析结果

                    FOREIGN KEY (session_id) REFERENCES group_comparison_sessions(id)
                )
            """)

            # 创建分组对比交易员表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS group_comparison_traders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    final_rank INTEGER,  -- 最终排名
                    eliminated_round INTEGER,  -- 在第几轮被淘汰（NULL表示未被淘汰）
                    elimination_reason TEXT,  -- 淘汰原因

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

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_address
                ON asset_positions(address)
            """)

            # 数据库迁移：为已存在的表添加缺失的列
            migrations = [
                # group_comparison_sessions 表
                ('group_comparison_sessions', 'rating', 'TEXT DEFAULT "S"'),
                ('group_comparison_sessions', 'total_traders', 'INTEGER DEFAULT 0'),
                ('group_comparison_sessions', 'group_size', 'INTEGER DEFAULT 6'),
                ('group_comparison_sessions', 'top_per_group', 'INTEGER DEFAULT 2'),
                ('group_comparison_sessions', 'final_size', 'INTEGER DEFAULT 6'),
                ('group_comparison_sessions', 'num_groups', 'INTEGER DEFAULT 0'),
                ('group_comparison_sessions', 'total_rounds', 'INTEGER DEFAULT 0'),
                ('group_comparison_sessions', 'min_sharpe', 'REAL'),
                ('group_comparison_sessions', 'min_sortino', 'REAL'),
                ('group_comparison_sessions', 'max_drawdown', 'REAL'),
                ('group_comparison_sessions', 'min_win_rate', 'REAL'),
                ('group_comparison_sessions', 'max_win_rate', 'REAL'),
                ('group_comparison_sessions', 'finalists_count', 'INTEGER DEFAULT 0'),
                ('group_comparison_sessions', 'final_ranking', 'TEXT'),
                ('group_comparison_sessions', 'ai_provider', 'TEXT DEFAULT "default"'),
                ('group_comparison_sessions', 'status', 'TEXT DEFAULT "pending"'),
                # group_comparison_traders 表
                ('group_comparison_traders', 'session_id', 'INTEGER'),
                ('group_comparison_traders', 'group_id', 'INTEGER'),
                ('group_comparison_traders', 'address', 'TEXT'),
                ('group_comparison_traders', 'overall_score', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'win_rate', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'total_pnl', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'recent_7d_pnl', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'max_drawdown', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'sharpe_ratio', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'sortino_ratio', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'profit_factor', 'REAL DEFAULT 0.0'),
                ('group_comparison_traders', 'is_finalist', 'BOOLEAN DEFAULT FALSE'),
                ('group_comparison_traders', 'final_rank', 'INTEGER'),
                ('group_comparison_traders', 'eliminated_round', 'INTEGER'),
                ('group_comparison_traders', 'elimination_reason', 'TEXT'),
                # group_comparison_groups 表
                ('group_comparison_groups', 'session_id', 'INTEGER'),
                ('group_comparison_groups', 'round_num', 'INTEGER DEFAULT 1'),
                ('group_comparison_groups', 'group_num', 'INTEGER'),
                ('group_comparison_groups', 'total_in_group', 'INTEGER DEFAULT 0'),
                ('group_comparison_groups', 'analysis', 'TEXT'),
            ]
            for table, column, column_def in migrations:
                self._migrate_add_column_if_not_exists(cursor, table, column, column_def)

            # 创建跟单分组表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_trading_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    color TEXT DEFAULT '#3B82F6',
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 插入默认分组
            cursor.execute("""
                INSERT OR IGNORE INTO copy_trading_groups (id, name, description, color)
                VALUES (1, '默认分组', '未分组的跟单地址', '#6B7280')
            """)

            # 创建跟单地址表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_trading_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

            # 迁移：为 copy_trading_addresses 添加新列
            self._migrate_copy_trading_addresses(cursor)

            # 创建 Hyperliquid 币种表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hyperliquid_coins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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

            # 创建跟单仓位状态表（用于重启后恢复状态）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS copy_position_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_address TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    size REAL NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL,
                    leverage INTEGER DEFAULT 1,
                    notional REAL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- 唯一约束：每个目标每个币种只保留一条
                    UNIQUE(target_address, symbol)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_position_states_target
                ON copy_position_states(target_address)
            """)

    def _migrate_add_new_columns(self, cursor):
        """为现有表添加新列（数据库迁移）"""
        # 获取现有列
        cursor.execute("PRAGMA table_info(trader_metrics)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # 需要添加的新列及其默认值
        new_columns = [
            ("avg_trade_price", "REAL DEFAULT 0.0"),
            ("avg_trade_size", "REAL DEFAULT 0.0"),
            ("max_single_win", "REAL DEFAULT 0.0"),
            ("max_single_loss", "REAL DEFAULT 0.0"),
            ("max_consecutive_wins", "INTEGER DEFAULT 0"),
            ("max_consecutive_losses", "INTEGER DEFAULT 0"),
            ("avg_win_amount", "REAL DEFAULT 0.0"),
            ("avg_loss_amount", "REAL DEFAULT 0.0"),
            ("unique_symbols", "INTEGER DEFAULT 0"),
            ("favorite_symbol", "TEXT DEFAULT ''"),
            ("recent_7d_pnl", "REAL DEFAULT 0.0"),
            ("recent_7d_win_rate", "REAL DEFAULT 0.0"),
            ("long_short_ratio", "REAL DEFAULT 0.0"),
            ("calmar_ratio", "REAL DEFAULT 0.0"),
            ("daily_pnl", "REAL DEFAULT 0.0"),
            ("weekly_pnl", "REAL DEFAULT 0.0"),
            ("monthly_pnl", "REAL DEFAULT 0.0"),
            ("daily_roi", "REAL DEFAULT 0.0"),
            ("weekly_roi", "REAL DEFAULT 0.0"),
            ("monthly_roi", "REAL DEFAULT 0.0"),
            ("daily_volume", "REAL DEFAULT 0.0"),
            ("weekly_volume", "REAL DEFAULT 0.0"),
            ("monthly_volume", "REAL DEFAULT 0.0"),
            # 新增风险指标 (v2.0)
            ("max_drawdown_abs", "REAL DEFAULT 0.0"),
            ("var_95", "REAL DEFAULT 0.0"),
            ("var_99", "REAL DEFAULT 0.0"),
            ("cvar_95", "REAL DEFAULT 0.0"),
            ("max_leverage", "REAL DEFAULT 1.0"),
        ]

        # 添加缺失的列
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(
                        f"ALTER TABLE trader_metrics ADD COLUMN {col_name} {col_type}"
                    )
                    logger.debug(f"已添加新列: {col_name}")
                except Exception as e:
                    logger.debug(f"添加列 {col_name} 失败（可能已存在）: {e}")

    def _migrate_fills_add_trade_type(self, cursor):
        """为 trader_fills 表添加 trade_type 列（数据库迁移）"""
        cursor.execute("PRAGMA table_info(trader_fills)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if "trade_type" not in existing_columns:
            try:
                cursor.execute(
                    "ALTER TABLE trader_fills ADD COLUMN trade_type TEXT"
                )
                logger.debug("已为 trader_fills 添加 trade_type 列")
            except Exception as e:
                logger.debug(f"添加 trade_type 列失败（可能已存在）: {e}")

    def _migrate_copy_trading_addresses(self, cursor):
        """为 copy_trading_addresses 表添加新列（数据库迁移）"""
        cursor.execute("PRAGMA table_info(copy_trading_addresses)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        new_columns = [
            ("sync_position", "BOOLEAN DEFAULT TRUE"),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(
                        f"ALTER TABLE copy_trading_addresses ADD COLUMN {col_name} {col_type}"
                    )
                    logger.debug(f"已为 copy_trading_addresses 添加 {col_name} 列")
                except Exception as e:
                    logger.debug(f"添加 {col_name} 列失败（可能已存在）: {e}")
