"""
SQLite 数据库模块
用于存储交易者分析结果
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from loguru import logger

from .trader_screener import TraderMetrics, QualityRating


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
                    long_short_ratio REAL DEFAULT 0.0
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
                    win_rate, profit_factor, max_drawdown, sharpe_ratio, sortino_ratio,
                    avg_holding_time_hours, trade_frequency_per_day, avg_leverage,
                    active_days, last_trade_time, first_trade_time,
                    current_positions, current_equity,
                    overall_score, rating,
                    profitability_score, risk_score, consistency_score, activity_score,
                    avg_trade_price, avg_trade_size, max_single_win, max_single_loss,
                    max_consecutive_wins, max_consecutive_losses,
                    avg_win_amount, avg_loss_amount,
                    unique_symbols, favorite_symbol,
                    recent_7d_pnl, recent_7d_win_rate, long_short_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    long_short_ratio = excluded.long_short_ratio
            """, (
                metrics.address,
                datetime.now().isoformat(),
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
                metrics.long_short_ratio
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
                    trade_time = datetime.fromtimestamp(time_ms / 1000).isoformat() if time_ms else None

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
        position_type: str = 'all'
    ) -> List[Dict]:
        """
        获取交易者的交易记录

        Args:
            address: 交易者地址
            limit: 返回数量
            coin: 筛选特定币种
            sort_by: 排序字段 (time, coin, side, px, sz, closed_pnl, fee)
            sort_order: 排序方向 (asc, desc)
            position_type: 持仓类型 (all/open/closed)
                - all: 所有记录
                - open: 当前持仓 (closed_pnl = 0)
                - closed: 已平仓 (closed_pnl != 0)

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

            # 根据 position_type 筛选
            if position_type == 'open':
                conditions.append("closed_pnl = 0")
            elif position_type == 'closed':
                conditions.append("closed_pnl != 0")

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

    def get_fills_summary(self, address: str) -> Dict[str, Any]:
        """
        获取交易者交易记录汇总

        Args:
            address: 交易者地址

        Returns:
            汇总信息字典
        """
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
            by_coin = [dict(row) for row in cursor.fetchall()]

            # 总盈亏
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
