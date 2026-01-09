"""
分组对比分析管理模块 (PostgreSQL)
"""
from typing import List, Dict, Any, Optional
import pendulum
import json
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ


class GroupComparisonOps:
    """分组对比分析相关操作"""

    def save_group_comparison_session(self, data: Dict[str, Any]) -> int:
        """
        保存分组对比会话

        Args:
            data: 会话数据

        Returns:
            会话ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO group_comparison_sessions (
                    rating, total_traders, group_size, top_per_group, final_size,
                    num_groups, total_rounds,
                    min_sharpe, min_sortino, max_drawdown, min_win_rate, max_win_rate,
                    finalists_count, final_ranking, ai_provider, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                data.get('rating', 'S'),
                data.get('total_traders', 0),
                data.get('group_size', 6),
                data.get('top_per_group', 2),
                data.get('final_size', 6),
                data.get('num_groups', 0),
                data.get('total_rounds', 0),
                data.get('min_sharpe'),
                data.get('min_sortino'),
                data.get('max_drawdown'),
                data.get('min_win_rate'),
                data.get('max_win_rate'),
                data.get('finalists_count', 0),
                json.dumps(data.get('final_ranking'), ensure_ascii=False) if data.get('final_ranking') else None,
                data.get('ai_provider', 'default'),
                data.get('status', 'completed'),
                pendulum.now(SHANGHAI_TZ).to_iso8601_string()
            ))

            session_id = cursor.fetchone()[0]
            logger.info(f"保存分组对比会话: session_id={session_id}")
            return session_id

    def save_group_comparison_group(
        self,
        session_id: int,
        round_num: int,
        group_num: int,
        total_in_group: int,
        analysis: str
    ) -> int:
        """
        保存分组对比分组

        Args:
            session_id: 会话ID
            round_num: 轮次
            group_num: 组号
            total_in_group: 组内人数
            analysis: AI分析结果

        Returns:
            分组ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO group_comparison_groups (
                    session_id, round_num, group_num, total_in_group, analysis
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (session_id, round_num, group_num, total_in_group, analysis))

            return cursor.fetchone()[0]

    def save_group_comparison_traders(
        self,
        session_id: int,
        traders: List[Dict],
        group_id: int = None,
        is_finalist: bool = False,
        eliminated_round: int = None
    ) -> int:
        """
        保存分组对比交易员

        Args:
            session_id: 会话ID
            traders: 交易员列表
            group_id: 分组ID
            is_finalist: 是否晋级
            eliminated_round: 被淘汰的轮次

        Returns:
            保存的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            count = 0

            for t in traders:
                cursor.execute("""
                    INSERT INTO group_comparison_traders (
                        session_id, group_id, address,
                        overall_score, win_rate, total_pnl, recent_7d_pnl,
                        max_drawdown, sharpe_ratio, sortino_ratio, profit_factor,
                        is_finalist, final_rank, eliminated_round, elimination_reason
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session_id,
                    group_id,
                    t.get('address'),
                    t.get('overall_score', 0),
                    t.get('win_rate', 0),
                    t.get('total_pnl', 0),
                    t.get('recent_7d_pnl', 0),
                    t.get('max_drawdown', 0),
                    t.get('sharpe_ratio', 0),
                    t.get('sortino_ratio', 0),
                    t.get('profit_factor', 0),
                    is_finalist,
                    t.get('final_rank'),
                    eliminated_round,
                    t.get('elimination_reason')
                ))
                count += 1

            return count

    def update_group_comparison_trader(
        self,
        session_id: int,
        address: str,
        updates: Dict
    ) -> bool:
        """
        更新分组对比交易员

        Args:
            session_id: 会话ID
            address: 交易员地址
            updates: 更新数据

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            set_clauses = []
            params = []

            for key, value in updates.items():
                if key in ('is_finalist', 'final_rank', 'elimination_reason', 'group_id'):
                    set_clauses.append(f"{key} = %s")
                    params.append(value)

            if not set_clauses:
                return False

            params.extend([session_id, address])
            cursor.execute(f"""
                UPDATE group_comparison_traders
                SET {', '.join(set_clauses)}
                WHERE session_id = %s AND address = %s
            """, params)

            return cursor.rowcount > 0

    def get_group_comparison_sessions(
        self,
        limit: int = 20,
        status: str = None
    ) -> List[Dict]:
        """
        获取分组对比会话列表

        Args:
            limit: 返回数量
            status: 状态筛选

        Returns:
            会话列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if status:
                cursor.execute("""
                    SELECT * FROM group_comparison_sessions
                    WHERE status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT * FROM group_comparison_sessions
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))

            results = []
            for row in cursor.fetchall():
                item = dict(row)
                if item.get('final_ranking'):
                    try:
                        item['final_ranking'] = json.loads(item['final_ranking'])
                    except:
                        pass
                results.append(item)

            return results

    def get_group_comparison_session(self, session_id: int) -> Optional[Dict]:
        """
        获取单个分组对比会话详情

        Args:
            session_id: 会话ID

        Returns:
            会话详情
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 获取会话基本信息
            cursor.execute("""
                SELECT * FROM group_comparison_sessions
                WHERE id = %s
            """, (session_id,))

            row = cursor.fetchone()
            if not row:
                return None

            session = dict(row)
            if session.get('final_ranking'):
                try:
                    session['final_ranking'] = json.loads(session['final_ranking'])
                except:
                    pass

            # 获取分组信息
            cursor.execute("""
                SELECT * FROM group_comparison_groups
                WHERE session_id = %s
                ORDER BY group_num
            """, (session_id,))
            session['groups'] = [dict(r) for r in cursor.fetchall()]

            # 获取交易员信息
            cursor.execute("""
                SELECT * FROM group_comparison_traders
                WHERE session_id = %s
                ORDER BY is_finalist DESC, final_rank ASC, overall_score DESC
            """, (session_id,))
            session['traders'] = [dict(r) for r in cursor.fetchall()]

            # 获取晋级者
            cursor.execute("""
                SELECT * FROM group_comparison_traders
                WHERE session_id = %s AND is_finalist = TRUE
                ORDER BY final_rank ASC, overall_score DESC
            """, (session_id,))
            session['finalists'] = [dict(r) for r in cursor.fetchall()]

            return session

    def update_group_comparison_session(
        self,
        session_id: int,
        updates: Dict
    ) -> bool:
        """
        更新分组对比会话

        Args:
            session_id: 会话ID
            updates: 更新数据

        Returns:
            是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            set_clauses = []
            params = []

            for key, value in updates.items():
                if key in ('status', 'finalists_count', 'final_ranking', 'ai_provider'):
                    if key == 'final_ranking' and isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    set_clauses.append(f"{key} = %s")
                    params.append(value)

            if not set_clauses:
                return False

            params.append(session_id)
            cursor.execute(f"""
                UPDATE group_comparison_sessions
                SET {', '.join(set_clauses)}
                WHERE id = %s
            """, params)

            return cursor.rowcount > 0

    def get_group_comparison_stats(self) -> Dict:
        """
        获取分组对比统计信息

        Returns:
            统计数据字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            # 总会话数
            cursor.execute("SELECT COUNT(*) as count FROM group_comparison_sessions")
            total_sessions = cursor.fetchone()['count']

            # 按状态统计
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM group_comparison_sessions
                GROUP BY status
            """)
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # 最近7天会话数
            cursor.execute("""
                SELECT COUNT(*) as count FROM group_comparison_sessions
                WHERE created_at >= NOW() - INTERVAL '7 days'
            """)
            recent_sessions = cursor.fetchone()['count']

            # 平均晋级人数
            cursor.execute("""
                SELECT AVG(finalists_count) as avg_finalists
                FROM group_comparison_sessions
                WHERE status = 'completed'
            """)
            avg_finalists = cursor.fetchone()['avg_finalists'] or 0

            return {
                'total_sessions': total_sessions,
                'by_status': by_status,
                'recent_sessions': recent_sessions,
                'avg_finalists': round(float(avg_finalists), 1)
            }
