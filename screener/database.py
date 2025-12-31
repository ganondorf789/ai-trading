"""
SQLite 数据库模块
用于存储交易者分析结果
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import pendulum

from loguru import logger

from .trader_screener import TraderMetrics, QualityRating, SHANGHAI_TZ


class TraderDatabase:
    """交易者数据库管理器"""

    DEFAULT_DB_PATH = "data/traders.db"

    def __init__(self, db_path: str = None):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
        logger.info(f"数据库初始化完成: {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

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
                    sharpe_ratio REAL DEFAULT 0.0,
                    sortino_ratio REAL DEFAULT 0.0,
                    calmar_ratio REAL DEFAULT 0.0,

                    -- 交易特征
                    avg_holding_time_hours REAL DEFAULT 0.0,
                    trade_frequency_per_day REAL DEFAULT 0.0,
                    avg_leverage REAL DEFAULT 1.0,

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

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_address
                ON asset_positions(address)
            """)

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

    def save_trader(self, metrics: TraderMetrics) -> int:
        """
        保存或更新交易者指标（使用 address 作为唯一键）

        Args:
            metrics: 交易者指标对象

        Returns:
            记录ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO trader_metrics (
                    address, analyzed_at,
                    total_trades, winning_trades, losing_trades,
                    total_pnl, realized_pnl, unrealized_pnl, total_volume,
                    roi, avg_profit_per_trade,
                    win_rate, profit_factor, max_drawdown, sharpe_ratio, sortino_ratio, calmar_ratio,
                    avg_holding_time_hours, trade_frequency_per_day, avg_leverage,
                    active_days, last_trade_time, first_trade_time,
                    current_positions, current_equity,
                    overall_score, rating,
                    profitability_score, risk_score, consistency_score, activity_score,
                    avg_trade_price, avg_trade_size, max_single_win, max_single_loss,
                    max_consecutive_wins, max_consecutive_losses,
                    avg_win_amount, avg_loss_amount,
                    unique_symbols, favorite_symbol,
                    recent_7d_pnl, recent_7d_win_rate, long_short_ratio,
                    daily_pnl, weekly_pnl, monthly_pnl,
                    daily_roi, weekly_roi, monthly_roi,
                    daily_volume, weekly_volume, monthly_volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    analyzed_at = excluded.analyzed_at,
                    total_trades = excluded.total_trades,
                    winning_trades = excluded.winning_trades,
                    losing_trades = excluded.losing_trades,
                    total_pnl = excluded.total_pnl,
                    realized_pnl = excluded.realized_pnl,
                    unrealized_pnl = excluded.unrealized_pnl,
                    total_volume = excluded.total_volume,
                    roi = excluded.roi,
                    avg_profit_per_trade = excluded.avg_profit_per_trade,
                    win_rate = excluded.win_rate,
                    profit_factor = excluded.profit_factor,
                    max_drawdown = excluded.max_drawdown,
                    sharpe_ratio = excluded.sharpe_ratio,
                    sortino_ratio = excluded.sortino_ratio,
                    calmar_ratio = excluded.calmar_ratio,
                    avg_holding_time_hours = excluded.avg_holding_time_hours,
                    trade_frequency_per_day = excluded.trade_frequency_per_day,
                    avg_leverage = excluded.avg_leverage,
                    active_days = excluded.active_days,
                    last_trade_time = excluded.last_trade_time,
                    first_trade_time = excluded.first_trade_time,
                    current_positions = excluded.current_positions,
                    current_equity = excluded.current_equity,
                    overall_score = excluded.overall_score,
                    rating = excluded.rating,
                    profitability_score = excluded.profitability_score,
                    risk_score = excluded.risk_score,
                    consistency_score = excluded.consistency_score,
                    activity_score = excluded.activity_score,
                    avg_trade_price = excluded.avg_trade_price,
                    avg_trade_size = excluded.avg_trade_size,
                    max_single_win = excluded.max_single_win,
                    max_single_loss = excluded.max_single_loss,
                    max_consecutive_wins = excluded.max_consecutive_wins,
                    max_consecutive_losses = excluded.max_consecutive_losses,
                    avg_win_amount = excluded.avg_win_amount,
                    avg_loss_amount = excluded.avg_loss_amount,
                    unique_symbols = excluded.unique_symbols,
                    favorite_symbol = excluded.favorite_symbol,
                    recent_7d_pnl = excluded.recent_7d_pnl,
                    recent_7d_win_rate = excluded.recent_7d_win_rate,
                    long_short_ratio = excluded.long_short_ratio,
                    daily_pnl = excluded.daily_pnl,
                    weekly_pnl = excluded.weekly_pnl,
                    monthly_pnl = excluded.monthly_pnl,
                    daily_roi = excluded.daily_roi,
                    weekly_roi = excluded.weekly_roi,
                    monthly_roi = excluded.monthly_roi,
                    daily_volume = excluded.daily_volume,
                    weekly_volume = excluded.weekly_volume,
                    monthly_volume = excluded.monthly_volume
            """, (
                metrics.address,
                pendulum.now(SHANGHAI_TZ).to_iso8601_string(),
                metrics.total_trades,
                metrics.winning_trades,
                metrics.losing_trades,
                metrics.total_pnl,
                metrics.realized_pnl,
                metrics.unrealized_pnl,
                metrics.total_volume,
                metrics.roi,
                metrics.avg_profit_per_trade,
                metrics.win_rate,
                metrics.profit_factor if metrics.profit_factor != float('inf') else 999999.0,
                metrics.max_drawdown,
                metrics.sharpe_ratio,
                metrics.sortino_ratio,
                metrics.calmar_ratio,
                metrics.avg_holding_time_hours,
                metrics.trade_frequency_per_day,
                metrics.avg_leverage,
                metrics.active_days,
                metrics.last_trade_time.isoformat() if metrics.last_trade_time else None,
                metrics.first_trade_time.isoformat() if metrics.first_trade_time else None,
                metrics.current_positions,
                metrics.current_equity,
                metrics.overall_score,
                metrics.rating.value,
                metrics.profitability_score,
                metrics.risk_score,
                metrics.consistency_score,
                metrics.activity_score,
                metrics.avg_trade_price,
                metrics.avg_trade_size,
                metrics.max_single_win,
                metrics.max_single_loss,
                metrics.max_consecutive_wins,
                metrics.max_consecutive_losses,
                metrics.avg_win_amount,
                metrics.avg_loss_amount,
                metrics.unique_symbols,
                metrics.favorite_symbol,
                metrics.recent_7d_pnl,
                metrics.recent_7d_win_rate,
                metrics.long_short_ratio,
                metrics.daily_pnl,
                metrics.weekly_pnl,
                metrics.monthly_pnl,
                metrics.daily_roi,
                metrics.weekly_roi,
                metrics.monthly_roi,
                metrics.daily_volume,
                metrics.weekly_volume,
                metrics.monthly_volume
            ))

            return cursor.lastrowid

    def save_traders(self, traders: List[TraderMetrics]) -> List[int]:
        """
        批量保存交易者指标

        Args:
            traders: 交易者指标列表

        Returns:
            插入的记录ID列表
        """
        ids = []
        for trader in traders:
            trader_id = self.save_trader(trader)
            ids.append(trader_id)
        logger.info(f"已保存 {len(ids)} 个交易者到数据库")
        return ids

    def save_fills(self, address: str, fills: List[Dict]) -> int:
        """
        保存交易者的交易记录

        Args:
            address: 交易者地址
            fills: 交易记录列表

        Returns:
            保存的记录数
        """
        if not fills:
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for fill in fills:
                try:
                    time_ms = fill.get('time', 0)
                    trade_time = pendulum.from_timestamp(time_ms / 1000, tz=SHANGHAI_TZ).to_iso8601_string() if time_ms else None

                    cursor.execute("""
                        INSERT INTO trader_fills (
                            address, coin, side, px, sz, time, trade_time,
                            closed_pnl, hash, start_position, dir, crossed, fee, oid, tid
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(address, time, oid) DO UPDATE SET
                            closed_pnl = excluded.closed_pnl,
                            px = excluded.px,
                            sz = excluded.sz
                    """, (
                        address,
                        fill.get('coin'),
                        fill.get('side'),
                        float(fill.get('px', 0)),
                        float(fill.get('sz', 0)),
                        time_ms,
                        trade_time,
                        float(fill.get('closedPnl', 0)),
                        fill.get('hash'),
                        float(fill.get('startPosition', 0)) if fill.get('startPosition') else None,
                        fill.get('dir'),
                        fill.get('crossed'),
                        float(fill.get('fee', 0)),
                        fill.get('oid'),
                        fill.get('tid')
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存交易记录失败: {e}")

        return saved_count

    def save_trader_with_fills(
        self,
        metrics: TraderMetrics,
        fills: List[Dict]
    ) -> tuple[int, int]:
        """
        保存交易者指标和交易记录

        Args:
            metrics: 交易者指标
            fills: 交易记录列表

        Returns:
            (trader_id, fills_count) 元组
        """
        trader_id = self.save_trader(metrics)
        fills_count = self.save_fills(metrics.address, fills)
        return trader_id, fills_count

    def get_trader_fills(
        self,
        address: str,
        limit: int = 100,
        coin: str = None,
        sort_by: str = 'time',
        sort_order: str = 'desc',
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict]:
        """
        获取交易者的交易记录

        Args:
            address: 交易者地址
            limit: 返回数量
            coin: 筛选特定币种
            sort_by: 排序字段 (time, coin, side, px, sz, closed_pnl, fee)
            sort_order: 排序方向 (asc, desc)
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            交易记录列表
        """
        # 验证排序字段（防止 SQL 注入）
        valid_sort_columns = {
            'time': 'time',
            'trade_time': 'time',
            'coin': 'coin',
            'side': 'side',
            'px': 'px',
            'sz': 'sz',
            'closed_pnl': 'closed_pnl',
            'fee': 'fee',
            'value': 'px * sz',
            'roi': 'CASE WHEN px * sz > 0 THEN closed_pnl / (px * sz) ELSE 0 END'
        }
        sort_column = valid_sort_columns.get(sort_by, 'time')
        order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = ["address = ?"]
            params = [address]

            if coin:
                conditions.append("coin = ?")
                params.append(coin)

            # 日期范围筛选（将 YYYY-MM-DD 转换为时间戳毫秒）
            if start_date:
                # 将开始日期转换为当天 00:00:00 的时间戳（毫秒）
                start_dt = pendulum.parse(start_date, tz=SHANGHAI_TZ).start_of('day')
                start_timestamp_ms = int(start_dt.timestamp() * 1000)
                conditions.append("time >= ?")
                params.append(start_timestamp_ms)

            if end_date:
                # 将结束日期转换为当天 23:59:59.999 的时间戳（毫秒）
                end_dt = pendulum.parse(end_date, tz=SHANGHAI_TZ).end_of('day')
                end_timestamp_ms = int(end_dt.timestamp() * 1000)
                conditions.append("time <= ?")
                params.append(end_timestamp_ms)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM trader_fills
                WHERE {where_clause}
                ORDER BY {sort_column} {order_direction}
                LIMIT ?
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_trader_coins(self, address: str) -> List[str]:
        """
        获取交易者交易过的所有币种

        Args:
            address: 交易者地址

        Returns:
            币种列表（按交易次数降序排列）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT coin, COUNT(*) as count
                FROM trader_fills
                WHERE address = ?
                GROUP BY coin
                ORDER BY count DESC
            """, (address,))
            return [row['coin'] for row in cursor.fetchall()]

    def get_fills_summary(
        self,
        address: str,
        exclude_user_perps: bool = True
    ) -> Dict[str, Any]:
        """
        获取交易者交易记录汇总

        Args:
            address: 交易者地址
            exclude_user_perps: 是否排除用户创建的永续合约（@数字格式）

        Returns:
            汇总信息字典
        """
        import re

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 总交易数
            cursor.execute(
                "SELECT COUNT(*) FROM trader_fills WHERE address = ?",
                (address,)
            )
            total_fills = cursor.fetchone()[0]

            # 按币种统计
            cursor.execute("""
                SELECT coin, COUNT(*) as count, SUM(closed_pnl) as total_pnl
                FROM trader_fills
                WHERE address = ?
                GROUP BY coin
                ORDER BY count DESC
            """, (address,))

            # 过滤 @数字 格式的用户永续合约
            user_perp_pattern = re.compile(r'^@\d+$')
            by_coin = []
            for row in cursor.fetchall():
                coin = row['coin']
                if exclude_user_perps and coin and user_perp_pattern.match(coin):
                    continue
                by_coin.append(dict(row))

            # 总盈亏（基于过滤后的币种）
            if exclude_user_perps:
                total_pnl = sum(c['total_pnl'] or 0 for c in by_coin)
            else:
                cursor.execute(
                    "SELECT SUM(closed_pnl) FROM trader_fills WHERE address = ?",
                    (address,)
                )
                total_pnl = cursor.fetchone()[0] or 0

            return {
                'total_fills': total_fills,
                'total_pnl': total_pnl,
                'by_coin': by_coin
            }

    def delete_trader_fills(self, address: str) -> int:
        """
        删除交易者的所有交易记录

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM trader_fills WHERE address = ?",
                (address,)
            )
            return cursor.rowcount

    def save_screening_session(
        self,
        traders: List[TraderMetrics],
        config: Dict[str, Any],
        total_analyzed: int
    ) -> int:
        """
        保存筛选会话

        Args:
            traders: 符合条件的交易者列表
            config: 筛选配置
            total_analyzed: 总分析数量

        Returns:
            会话ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 插入会话记录
            cursor.execute("""
                INSERT INTO screening_sessions (
                    lookback_days, min_total_trades, min_win_rate,
                    min_profit_factor, min_total_pnl, max_drawdown,
                    total_analyzed, qualified_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config.get('lookback_days', 30),
                config.get('min_total_trades', 10),
                config.get('min_win_rate', 0.45),
                config.get('min_profit_factor', 1.0),
                config.get('min_total_pnl', 0.0),
                config.get('max_drawdown', 0.5),
                total_analyzed,
                len(traders)
            ))

            session_id = cursor.lastrowid

            # 保存交易者并关联到会话
            for rank, trader in enumerate(traders, 1):
                # 保存交易者（复用 save_trader 的逻辑）
                trader_id = self.save_trader(trader)

                # 关联到会话
                cursor.execute("""
                    INSERT INTO session_traders (session_id, trader_id, rank)
                    VALUES (?, ?, ?)
                """, (session_id, trader_id, rank))

            logger.info(f"筛选会话已保存: session_id={session_id}, traders={len(traders)}")
            return session_id

    def get_trader_by_address(self, address: str) -> Optional[Dict]:
        """
        根据地址获取最新的交易者记录

        Args:
            address: 交易者地址

        Returns:
            交易者记录字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE address = ?
                ORDER BY analyzed_at DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_top_traders(
        self,
        limit: int = 20,
        min_rating: str = None
    ) -> List[Dict]:
        """
        获取评分最高的交易者

        Args:
            limit: 返回数量
            min_rating: 最低评级

        Returns:
            交易者记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM trader_metrics WHERE 1=1"

            if min_rating:
                rating_order = {'S': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'F': 6}
                min_order = rating_order.get(min_rating, 6)
                valid_ratings = [r for r, o in rating_order.items() if o <= min_order]
                placeholders = ','.join(['?' for _ in valid_ratings])
                query += f" AND rating IN ({placeholders})"
                cursor.execute(
                    query + " ORDER BY overall_score DESC LIMIT ?",
                    valid_ratings + [limit]
                )
            else:
                cursor.execute(query + " ORDER BY overall_score DESC LIMIT ?", (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_traders_by_rating(self, rating: str) -> List[Dict]:
        """
        根据评级获取交易者

        Args:
            rating: 评级 (S/A/B/C/D/F)

        Returns:
            交易者记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE rating = ?
                ORDER BY overall_score DESC
            """, (rating,))
            return [dict(row) for row in cursor.fetchall()]

    def get_session_traders(self, session_id: int) -> List[Dict]:
        """
        获取指定会话的交易者

        Args:
            session_id: 会话ID

        Returns:
            交易者记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tm.*, st.rank
                FROM trader_metrics tm
                JOIN session_traders st ON tm.id = st.trader_id
                WHERE st.session_id = ?
                ORDER BY st.rank
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的筛选会话

        Args:
            limit: 返回数量

        Returns:
            会话记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM screening_sessions
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_trader_history(self, address: str, limit: int = 10) -> List[Dict]:
        """
        获取交易者的分析记录

        注意：由于使用 address 作为唯一键，每个地址只保留最新一条记录

        Args:
            address: 交易者地址
            limit: 返回数量（当前每个地址只有一条记录）

        Returns:
            记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM trader_metrics
                WHERE address = ?
                ORDER BY analyzed_at DESC
                LIMIT ?
            """, (address, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        Returns:
            统计信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM trader_metrics")
            total_records = cursor.fetchone()[0]

            # 唯一地址数
            cursor.execute("SELECT COUNT(DISTINCT address) FROM trader_metrics")
            unique_addresses = cursor.fetchone()[0]

            # 各评级分布
            cursor.execute("""
                SELECT rating, COUNT(*) as count
                FROM trader_metrics
                GROUP BY rating
            """)
            rating_distribution = {row['rating']: row['count'] for row in cursor.fetchall()}

            # 会话数
            cursor.execute("SELECT COUNT(*) FROM screening_sessions")
            total_sessions = cursor.fetchone()[0]

            return {
                'total_records': total_records,
                'unique_addresses': unique_addresses,
                'rating_distribution': rating_distribution,
                'total_sessions': total_sessions
            }

    def delete_old_records(self, days: int = 90):
        """
        删除旧记录

        Args:
            days: 保留最近多少天的记录
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM trader_metrics
                WHERE analyzed_at < datetime('now', ?)
            """, (f'-{days} days',))
            deleted = cursor.rowcount
            logger.info(f"已删除 {deleted} 条旧记录")

    def get_all_coins(
        self,
        exclude_user_perps: bool = True,
        address: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有币种及其统计信息

        Args:
            exclude_user_perps: 是否排除用户创建的永续合约（@数字格式）
            address: 可选，筛选特定交易者的币种

        Returns:
            币种列表，包含交易次数和总盈亏
        """
        import re

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if address:
                cursor.execute("""
                    SELECT coin, COUNT(*) as count, SUM(closed_pnl) as total_pnl
                    FROM trader_fills
                    WHERE address = ?
                    GROUP BY coin
                    ORDER BY count DESC
                """, (address,))
            else:
                cursor.execute("""
                    SELECT coin, COUNT(*) as count, SUM(closed_pnl) as total_pnl
                    FROM trader_fills
                    GROUP BY coin
                    ORDER BY count DESC
                """)

            results = []
            # 匹配 @数字 格式的用户创建永续合约
            user_perp_pattern = re.compile(r'^@\d+$')

            for row in cursor.fetchall():
                coin = row['coin']
                is_user_perp = bool(user_perp_pattern.match(coin)) if coin else False

                # 如果需要排除用户永续合约且当前是用户永续合约，则跳过
                if exclude_user_perps and is_user_perp:
                    continue

                results.append({
                    'coin': coin,
                    'count': row['count'],
                    'total_pnl': row['total_pnl'] or 0,
                    'is_user_perp': is_user_perp
                })

            return results

    def save_positions(self, address: str, positions: List[Dict]) -> int:
        """
        保存交易者的当前持仓（来自 assetPositions）

        Args:
            address: 交易者地址
            positions: 持仓列表（从 user_state['assetPositions'] 获取）

        Returns:
            保存的记录数
        """
        if not positions:
            # 清空该地址的所有持仓
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM asset_positions WHERE address = ?",
                    (address,)
                )
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 先删除旧持仓
            cursor.execute(
                "DELETE FROM asset_positions WHERE address = ?",
                (address,)
            )

            for pos_data in positions:
                try:
                    pos = pos_data.get('position', {})
                    leverage = pos.get('leverage', {})

                    # 跳过空仓位
                    szi = float(pos.get('szi', 0))
                    if szi == 0:
                        continue

                    cursor.execute("""
                        INSERT INTO asset_positions (
                            address, coin, szi, entry_px, position_value,
                            unrealized_pnl, return_on_equity, liquidation_px,
                            margin_used, max_leverage, leverage_type, leverage_value,
                            updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        address,
                        pos.get('coin'),
                        szi,
                        float(pos.get('entryPx', 0)),
                        float(pos.get('positionValue', 0)),
                        float(pos.get('unrealizedPnl', 0)),
                        float(pos.get('returnOnEquity', 0)),
                        float(pos.get('liquidationPx')) if pos.get('liquidationPx') else None,
                        float(pos.get('marginUsed', 0)),
                        int(pos.get('maxLeverage', 1)),
                        leverage.get('type'),
                        int(leverage.get('value', 1)),
                        pendulum.now(SHANGHAI_TZ).to_iso8601_string()
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存持仓记录失败: {e}")

        return saved_count

    def get_positions(self, address: str) -> List[Dict]:
        """
        获取交易者的当前持仓

        Args:
            address: 交易者地址

        Returns:
            持仓列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM asset_positions
                WHERE address = ?
                ORDER BY ABS(position_value) DESC
            """, (address,))
            return [dict(row) for row in cursor.fetchall()]

    # ==================== 跟单地址管理 ====================

    def get_copy_trading_groups(self) -> List[Dict]:
        """
        获取所有跟单分组

        Returns:
            分组列表，包含每个分组的地址数量
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT g.*, COUNT(a.id) as address_count
                FROM copy_trading_groups g
                LEFT JOIN copy_trading_addresses a ON g.id = a.group_id
                GROUP BY g.id
                ORDER BY g.sort_order, g.id
            """)
            return [dict(row) for row in cursor.fetchall()]

    def save_copy_trading_group(self, data: Dict) -> int:
        """
        保存或更新跟单分组

        Args:
            data: 分组数据 {name, description, color, sort_order}

        Returns:
            分组ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if data.get('id'):
                # 更新
                cursor.execute("""
                    UPDATE copy_trading_groups
                    SET name = ?, description = ?, color = ?, sort_order = ?
                    WHERE id = ?
                """, (
                    data.get('name'),
                    data.get('description', ''),
                    data.get('color', '#3B82F6'),
                    data.get('sort_order', 0),
                    data['id']
                ))
                return data['id']
            else:
                # 插入
                cursor.execute("""
                    INSERT INTO copy_trading_groups (name, description, color, sort_order)
                    VALUES (?, ?, ?, ?)
                """, (
                    data.get('name'),
                    data.get('description', ''),
                    data.get('color', '#3B82F6'),
                    data.get('sort_order', 0)
                ))
                return cursor.lastrowid

    def delete_copy_trading_group(self, group_id: int) -> bool:
        """
        删除跟单分组（不能删除默认分组）

        Args:
            group_id: 分组ID

        Returns:
            是否删除成功
        """
        if group_id == 1:
            return False  # 默认分组不能删除

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 将该分组下的地址移到默认分组
            cursor.execute("""
                UPDATE copy_trading_addresses
                SET group_id = 1
                WHERE group_id = ?
            """, (group_id,))
            # 删除分组
            cursor.execute("DELETE FROM copy_trading_groups WHERE id = ?", (group_id,))
            return cursor.rowcount > 0

    def get_copy_trading_addresses(
        self,
        group_id: int = None,
        is_enabled: bool = None,
        search: str = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = 'updated_at',
        sort_order: str = 'desc'
    ) -> tuple[List[Dict], int]:
        """
        获取跟单地址列表（带关联的交易者指标）

        Args:
            group_id: 分组ID筛选
            is_enabled: 启用状态筛选
            search: 搜索地址或名称
            limit: 每页数量
            offset: 偏移量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            (地址列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 构建查询条件
            conditions = []
            params = []

            if group_id is not None:
                conditions.append("cta.group_id = ?")
                params.append(group_id)

            if is_enabled is not None:
                conditions.append("cta.is_enabled = ?")
                params.append(is_enabled)

            if search:
                conditions.append("(cta.address LIKE ? OR cta.name LIKE ?)")
                params.extend([f'%{search}%', f'%{search}%'])

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 验证排序字段
            valid_sort_fields = {
                'updated_at', 'created_at', 'name', 'address',
                'copy_ratio', 'is_enabled', 'win_rate', 'total_pnl', 'rating'
            }
            if sort_by not in valid_sort_fields:
                sort_by = 'updated_at'
            order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

            # 处理关联字段排序
            if sort_by in ('win_rate', 'total_pnl', 'rating'):
                sort_column = f'tm.{sort_by}'
            else:
                sort_column = f'cta.{sort_by}'

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) FROM copy_trading_addresses cta
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()[0]

            # 查询数据（关联 trader_metrics 和 groups）
            cursor.execute(f"""
                SELECT
                    cta.*,
                    g.name as group_name,
                    g.color as group_color,
                    tm.win_rate,
                    tm.total_pnl as trader_pnl,
                    tm.rating,
                    tm.overall_score,
                    tm.total_trades,
                    tm.profit_factor,
                    tm.max_drawdown,
                    tm.sharpe_ratio,
                    tm.analyzed_at
                FROM copy_trading_addresses cta
                LEFT JOIN copy_trading_groups g ON cta.group_id = g.id
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE {where_clause}
                ORDER BY {sort_column} {order_direction}
                LIMIT ? OFFSET ?
            """, params + [limit, offset])

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # 解析 JSON 字段
                import json
                try:
                    item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
                except:
                    item['symbols_whitelist'] = []
                try:
                    item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
                except:
                    item['symbols_blacklist'] = []
                results.append(item)

            return results, total_count

    def get_copy_trading_address(self, address: str) -> Optional[Dict]:
        """
        获取单个跟单地址详情

        Args:
            address: 交易者地址

        Returns:
            地址详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    cta.*,
                    g.name as group_name,
                    g.color as group_color,
                    tm.win_rate,
                    tm.total_pnl as trader_pnl,
                    tm.rating,
                    tm.overall_score,
                    tm.total_trades,
                    tm.profit_factor,
                    tm.max_drawdown,
                    tm.sharpe_ratio,
                    tm.analyzed_at
                FROM copy_trading_addresses cta
                LEFT JOIN copy_trading_groups g ON cta.group_id = g.id
                LEFT JOIN trader_metrics tm ON cta.address = tm.address
                WHERE cta.address = ?
            """, (address,))
            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            import json
            try:
                item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
            except:
                item['symbols_whitelist'] = []
            try:
                item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
            except:
                item['symbols_blacklist'] = []
            return item

    def save_copy_trading_address(self, data: Dict) -> int:
        """
        保存或更新跟单地址

        Args:
            data: 地址数据

        Returns:
            记录ID
        """
        import json

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 处理 JSON 字段
            whitelist = data.get('symbols_whitelist', [])
            blacklist = data.get('symbols_blacklist', [])
            if isinstance(whitelist, list):
                whitelist = json.dumps(whitelist)
            if isinstance(blacklist, list):
                blacklist = json.dumps(blacklist)

            cursor.execute("""
                INSERT INTO copy_trading_addresses (
                    address, name, group_id, is_enabled,
                    copy_ratio, max_position_size_usd, min_position_size_usd,
                    copy_leverage, max_leverage, default_leverage,
                    max_total_positions, max_daily_trades, slippage,
                    symbols_whitelist, symbols_blacklist,
                    check_interval, dry_run, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    name = excluded.name,
                    group_id = excluded.group_id,
                    is_enabled = excluded.is_enabled,
                    copy_ratio = excluded.copy_ratio,
                    max_position_size_usd = excluded.max_position_size_usd,
                    min_position_size_usd = excluded.min_position_size_usd,
                    copy_leverage = excluded.copy_leverage,
                    max_leverage = excluded.max_leverage,
                    default_leverage = excluded.default_leverage,
                    max_total_positions = excluded.max_total_positions,
                    max_daily_trades = excluded.max_daily_trades,
                    slippage = excluded.slippage,
                    symbols_whitelist = excluded.symbols_whitelist,
                    symbols_blacklist = excluded.symbols_blacklist,
                    check_interval = excluded.check_interval,
                    dry_run = excluded.dry_run,
                    updated_at = excluded.updated_at
            """, (
                data.get('address'),
                data.get('name', ''),
                data.get('group_id'),
                data.get('is_enabled', True),
                data.get('copy_ratio', 0.1),
                data.get('max_position_size_usd', 500.0),
                data.get('min_position_size_usd', 20.0),
                data.get('copy_leverage', True),
                data.get('max_leverage', 10),
                data.get('default_leverage', 5),
                data.get('max_total_positions', 10),
                data.get('max_daily_trades', 50),
                data.get('slippage', 0.01),
                whitelist,
                blacklist,
                data.get('check_interval', 10.0),
                data.get('dry_run', True),
                pendulum.now(SHANGHAI_TZ).to_iso8601_string()
            ))

            return cursor.lastrowid

    def delete_copy_trading_address(self, address: str) -> bool:
        """
        删除跟单地址

        Args:
            address: 交易者地址

        Returns:
            是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM copy_trading_addresses WHERE address = ?",
                (address,)
            )
            return cursor.rowcount > 0

    def toggle_copy_trading_address(self, address: str, is_enabled: bool) -> bool:
        """
        启用/禁用跟单地址

        Args:
            address: 交易者地址
            is_enabled: 是否启用

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE copy_trading_addresses
                SET is_enabled = ?, updated_at = ?
                WHERE address = ?
            """, (is_enabled, pendulum.now(SHANGHAI_TZ).to_iso8601_string(), address))
            return cursor.rowcount > 0

    def batch_update_copy_trading_addresses(
        self,
        addresses: List[str],
        action: str,
        group_id: int = None
    ) -> int:
        """
        批量操作跟单地址

        Args:
            addresses: 地址列表
            action: 操作类型 (enable/disable/delete/move_group)
            group_id: 目标分组ID（仅 move_group 时需要）

        Returns:
            影响的记录数
        """
        if not addresses:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in addresses])

            if action == 'enable':
                cursor.execute(f"""
                    UPDATE copy_trading_addresses
                    SET is_enabled = 1, updated_at = ?
                    WHERE address IN ({placeholders})
                """, [pendulum.now(SHANGHAI_TZ).to_iso8601_string()] + addresses)
            elif action == 'disable':
                cursor.execute(f"""
                    UPDATE copy_trading_addresses
                    SET is_enabled = 0, updated_at = ?
                    WHERE address IN ({placeholders})
                """, [pendulum.now(SHANGHAI_TZ).to_iso8601_string()] + addresses)
            elif action == 'delete':
                cursor.execute(f"""
                    DELETE FROM copy_trading_addresses
                    WHERE address IN ({placeholders})
                """, addresses)
            elif action == 'move_group' and group_id is not None:
                cursor.execute(f"""
                    UPDATE copy_trading_addresses
                    SET group_id = ?, updated_at = ?
                    WHERE address IN ({placeholders})
                """, [group_id, pendulum.now(SHANGHAI_TZ).to_iso8601_string()] + addresses)
            else:
                return 0

            return cursor.rowcount

    # ==================== Hyperliquid 币种管理 ====================

    def save_hyperliquid_coins(self, coins: List[Dict]) -> int:
        """
        保存 Hyperliquid 币种列表

        Args:
            coins: 币种数据列表 [{name, szDecimals, maxLeverage, onlyIsolated}]

        Returns:
            保存的记录数
        """
        if not coins:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            saved_count = 0

            for coin in coins:
                try:
                    cursor.execute("""
                        INSERT INTO hyperliquid_coins (
                            name, sz_decimals, max_leverage, only_isolated, is_active, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            sz_decimals = excluded.sz_decimals,
                            max_leverage = excluded.max_leverage,
                            only_isolated = excluded.only_isolated,
                            is_active = excluded.is_active,
                            updated_at = excluded.updated_at
                    """, (
                        coin.get('name'),
                        coin.get('szDecimals', 0),
                        coin.get('maxLeverage', 1),
                        coin.get('onlyIsolated', False),
                        True,
                        pendulum.now(SHANGHAI_TZ).to_iso8601_string()
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存币种记录失败: {e}")

            return saved_count

    def get_hyperliquid_coins(self, active_only: bool = True) -> List[Dict]:
        """
        获取 Hyperliquid 币种列表

        Args:
            active_only: 是否只返回活跃币种

        Returns:
            币种列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if active_only:
                cursor.execute("""
                    SELECT * FROM hyperliquid_coins
                    WHERE is_active = 1
                    ORDER BY name
                """)
            else:
                cursor.execute("""
                    SELECT * FROM hyperliquid_coins
                    ORDER BY name
                """)

            return [dict(row) for row in cursor.fetchall()]

    def get_hyperliquid_coin_names(self) -> List[str]:
        """
        获取 Hyperliquid 币种名称列表（仅活跃币种）

        Returns:
            币种名称列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM hyperliquid_coins
                WHERE is_active = 1
                ORDER BY name
            """)
            return [row['name'] for row in cursor.fetchall()]

    def get_enabled_copy_addresses(self) -> List[Dict]:
        """
        获取所有启用的跟单地址及其完整配置（供跟单引擎使用）

        Returns:
            启用的跟单地址配置列表
        """
        import json

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE is_enabled = 1
                ORDER BY updated_at DESC
            """)

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                # 解析 JSON 字段
                try:
                    item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
                except:
                    item['symbols_whitelist'] = []
                try:
                    item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
                except:
                    item['symbols_blacklist'] = []
                results.append(item)

            return results

    def get_copy_address_config(self, address: str) -> Optional[Dict]:
        """
        获取单个跟单地址的完整配置

        Args:
            address: 交易者地址

        Returns:
            配置字典，如果不存在则返回 None
        """
        import json

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM copy_trading_addresses
                WHERE address = ?
            """, (address,))

            row = cursor.fetchone()
            if not row:
                return None

            item = dict(row)
            # 解析 JSON 字段
            try:
                item['symbols_whitelist'] = json.loads(item.get('symbols_whitelist') or '[]')
            except:
                item['symbols_whitelist'] = []
            try:
                item['symbols_blacklist'] = json.loads(item.get('symbols_blacklist') or '[]')
            except:
                item['symbols_blacklist'] = []

            return item

    # ==================== 跟单订单记录 ====================

    def save_copy_order(self, order: Dict) -> int:
        """
        保存跟单订单记录

        Args:
            order: 订单数据

        Returns:
            订单ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO copy_trading_orders (
                    target_address, symbol, side, action, size, price,
                    leverage, copy_ratio, target_size, target_entry_price,
                    status, error_message, pnl, is_dry_run, created_at, executed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.get('target_address'),
                order.get('symbol'),
                order.get('side'),
                order.get('action'),
                order.get('size', 0),
                order.get('price'),
                order.get('leverage', 1),
                order.get('copy_ratio'),
                order.get('target_size'),
                order.get('target_entry_price'),
                order.get('status', 'pending'),
                order.get('error_message'),
                order.get('pnl', 0),
                order.get('is_dry_run', True),
                order.get('created_at', pendulum.now(SHANGHAI_TZ).to_iso8601_string()),
                order.get('executed_at')
            ))
            return cursor.lastrowid

    def update_copy_order(self, order_id: int, updates: Dict) -> bool:
        """
        更新跟单订单状态

        Args:
            order_id: 订单ID
            updates: 更新数据

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            set_clauses = []
            params = []

            for key, value in updates.items():
                if key in ('status', 'error_message', 'pnl', 'executed_at', 'price'):
                    set_clauses.append(f"{key} = ?")
                    params.append(value)

            if not set_clauses:
                return False

            params.append(order_id)
            cursor.execute(f"""
                UPDATE copy_trading_orders
                SET {', '.join(set_clauses)}
                WHERE id = ?
            """, params)

            return cursor.rowcount > 0

    def get_copy_orders(
        self,
        target_address: str = None,
        symbol: str = None,
        status: str = None,
        action: str = None,
        is_dry_run: bool = None,
        days: int = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[Dict], int]:
        """
        获取跟单订单列表

        Args:
            target_address: 目标地址筛选
            symbol: 币种筛选
            status: 状态筛选
            action: 操作类型筛选
            is_dry_run: 是否模拟模式筛选
            days: 最近N天
            start_date: 开始日期
            end_date: 结束日期
            limit: 每页数量
            offset: 偏移量
            sort_by: 排序字段
            sort_order: 排序方向

        Returns:
            (订单列表, 总数量)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = []
            params = []

            if target_address:
                conditions.append("o.target_address = ?")
                params.append(target_address)

            if symbol:
                conditions.append("o.symbol = ?")
                params.append(symbol)

            if status:
                conditions.append("o.status = ?")
                params.append(status)

            if action:
                conditions.append("o.action = ?")
                params.append(action)

            if is_dry_run is not None:
                conditions.append("o.is_dry_run = ?")
                params.append(1 if is_dry_run else 0)

            if days is not None and days > 0:
                conditions.append("o.created_at >= datetime('now', ?)")
                params.append(f"-{days} days")

            if start_date:
                conditions.append("o.created_at >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("o.created_at <= ?")
                params.append(end_date)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            # 验证排序字段
            valid_sort_fields = {'created_at', 'executed_at', 'symbol', 'side', 'action', 'size', 'price', 'pnl', 'status'}
            if sort_by not in valid_sort_fields:
                sort_by = 'created_at'
            order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

            # 查询总数
            cursor.execute(f"""
                SELECT COUNT(*) FROM copy_trading_orders o
                WHERE {where_clause}
            """, params)
            total_count = cursor.fetchone()[0]

            # 查询数据（关联地址名称）
            cursor.execute(f"""
                SELECT
                    o.*,
                    cta.name as target_name
                FROM copy_trading_orders o
                LEFT JOIN copy_trading_addresses cta ON o.target_address = cta.address
                WHERE {where_clause}
                ORDER BY o.{sort_by} {order_direction}
                LIMIT ? OFFSET ?
            """, params + [limit, offset])

            return [dict(row) for row in cursor.fetchall()], total_count

    def get_copy_order_stats(
        self,
        target_address: str = None,
        days: int = 7
    ) -> Dict:
        """
        获取跟单订单统计

        Args:
            target_address: 目标地址筛选
            days: 统计天数

        Returns:
            统计数据
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            conditions = [f"created_at >= datetime('now', '-{days} days')"]
            params = []

            if target_address:
                conditions.append("target_address = ?")
                params.append(target_address)

            where_clause = " AND ".join(conditions)

            # 总体统计
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN action = 'open' THEN 1 ELSE 0 END) as opens,
                    SUM(CASE WHEN action = 'close' THEN 1 ELSE 0 END) as closes,
                    SUM(pnl) as total_pnl,
                    SUM(CASE WHEN is_dry_run = 0 THEN 1 ELSE 0 END) as real_orders
                FROM copy_trading_orders
                WHERE {where_clause}
            """, params)

            row = cursor.fetchone()
            stats = dict(row) if row else {}

            # 按币种统计
            cursor.execute(f"""
                SELECT
                    symbol,
                    COUNT(*) as count,
                    SUM(pnl) as pnl
                FROM copy_trading_orders
                WHERE {where_clause}
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT 10
            """, params)

            stats['by_symbol'] = [dict(r) for r in cursor.fetchall()]

            # 按目标地址统计
            cursor.execute(f"""
                SELECT
                    o.target_address,
                    cta.name as target_name,
                    COUNT(*) as count,
                    SUM(o.pnl) as pnl
                FROM copy_trading_orders o
                LEFT JOIN copy_trading_addresses cta ON o.target_address = cta.address
                WHERE {where_clause.replace('target_address', 'o.target_address').replace('created_at', 'o.created_at')}
                GROUP BY o.target_address
                ORDER BY count DESC
            """, params)

            stats['by_target'] = [dict(r) for r in cursor.fetchall()]

            return stats

    def delete_old_copy_orders(self, days: int = 30) -> int:
        """
        删除旧的跟单订单记录

        Args:
            days: 保留天数

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM copy_trading_orders
                WHERE created_at < datetime('now', ?)
            """, (f'-{days} days',))
            return cursor.rowcount

    def save_trader_ai_analysis(self, address: str, analysis: Dict[str, Any]) -> None:
        """
        保存交易员AI分析结果

        Args:
            address: 交易员地址
            analysis: AI分析结果字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO trader_ai_analysis (
                    address,
                    rating,
                    overall_score,
                    analysis_text,
                    summary,
                    strengths,
                    risks,
                    trading_style,
                    copy_trading_advice,
                    improvement_suggestions,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                address,
                analysis.get('rating'),
                analysis.get('overall_score'),
                analysis.get('analysis_text'),
                analysis.get('summary'),
                analysis.get('strengths'),
                analysis.get('risks'),
                analysis.get('trading_style'),
                analysis.get('copy_trading_advice'),
                analysis.get('improvement_suggestions')
            ))

            logger.info(f"保存AI分析结果: {address}")

    def get_trader_ai_analysis(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取交易员AI分析结果

        Args:
            address: 交易员地址

        Returns:
            AI分析结果字典，如果不存在返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT *
                FROM trader_ai_analysis
                WHERE address = ?
            """, (address,))

            row = cursor.fetchone()
            if not row:
                return None

            return dict(row)
