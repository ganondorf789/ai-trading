"""
出入金（非资金费）账本更新管理模块 (PostgreSQL)

存储和查询用户的存款、提款、转账、清算等非资金费账本记录
"""
import json
from typing import List, Dict, Any, Optional
from psycopg2 import extras
from loguru import logger

from utils import sanitize_float


class TraderLedgerOps:
    """出入金（非资金费账本更新）相关操作"""

    def save_ledger_records(self, address: str, records: List[Dict]) -> int:
        """
        保存用户的非资金费账本更新记录

        Args:
            address: 交易者地址
            records: 账本记录列表（API 原始格式）

        Returns:
            保存的记录数
        """
        if not records:
            return 0

        saved_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            for record in records:
                try:
                    delta = record.get('delta', {})
                    time_ms = record.get('time', 0)
                    hash_val = record.get('hash', '')
                    delta_type = delta.get('type', '')

                    # 提取通用 usdc 金额
                    usdc = sanitize_float(delta.get('usdc', 0))

                    # 提取额外字段
                    fee = sanitize_float(delta.get('fee', 0))
                    nonce = delta.get('nonce')
                    # 对于 internalTransfer / spotTransfer 等
                    destination = delta.get('destination', '')
                    user_field = delta.get('user', '')

                    cursor.execute("""
                        INSERT INTO trader_ledger_updates (
                            address, delta_type, usdc, fee, nonce,
                            destination, user_field, hash, time, delta_json
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(address, hash, time) DO UPDATE SET
                            delta_type = EXCLUDED.delta_type,
                            usdc = EXCLUDED.usdc,
                            fee = EXCLUDED.fee,
                            delta_json = EXCLUDED.delta_json
                    """, (
                        address,
                        delta_type,
                        usdc,
                        fee,
                        nonce,
                        destination,
                        user_field,
                        hash_val,
                        time_ms,
                        json.dumps(delta, ensure_ascii=False),
                    ))
                    saved_count += 1
                except Exception as e:
                    logger.debug(f"保存账本记录失败: {e}")

        return saved_count

    def get_ledger_records(
        self,
        address: str,
        limit: int = 100,
        delta_type: str = None,
        start_time: int = None,
        end_time: int = None,
        sort_order: str = 'desc'
    ) -> List[Dict]:
        """
        获取用户的非资金费账本更新记录

        Args:
            address: 交易者地址
            limit: 返回数量
            delta_type: 筛选类型 (deposit, withdraw, internalTransfer, 
                        spotTransfer, accountClassTransfer, liquidation, 等)
            start_time: 开始时间（毫秒时间戳）
            end_time: 结束时间（毫秒时间戳）
            sort_order: 排序方向 (asc, desc)

        Returns:
            账本记录列表
        """
        order_direction = 'ASC' if sort_order.lower() == 'asc' else 'DESC'

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            conditions = ["address = %s"]
            params = [address]

            if delta_type:
                conditions.append("delta_type = %s")
                params.append(delta_type)

            if start_time:
                conditions.append("time >= %s")
                params.append(start_time)

            if end_time:
                conditions.append("time <= %s")
                params.append(end_time)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(f"""
                SELECT * FROM trader_ledger_updates
                WHERE {where_clause}
                ORDER BY time {order_direction}
                LIMIT %s
            """, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_latest_ledger_record(self, address: str) -> Optional[Dict]:
        """
        获取用户最新的一条账本记录

        Args:
            address: 交易者地址

        Returns:
            最新的账本记录字典，如果没有记录则返回 None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_ledger_updates
                WHERE address = %s
                ORDER BY time DESC
                LIMIT 1
            """, (address,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_ledger_stats(self, address: str) -> Optional[Dict[str, Any]]:
        """
        获取用户账本更新的聚合统计

        Args:
            address: 交易者地址

        Returns:
            聚合统计字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COALESCE(SUM(usdc), 0) as net_usdc,
                    COALESCE(SUM(CASE WHEN usdc > 0 THEN usdc ELSE 0 END), 0) as total_inflow,
                    COALESCE(SUM(CASE WHEN usdc < 0 THEN usdc ELSE 0 END), 0) as total_outflow,
                    COALESCE(SUM(fee), 0) as total_fees,
                    MIN(time) as first_record_time,
                    MAX(time) as last_record_time
                FROM trader_ledger_updates
                WHERE address = %s
            """, (address,))

            row = cursor.fetchone()
            if not row or row['total_records'] == 0:
                return None

            return {
                'total_records': row['total_records'],
                'net_usdc': float(row['net_usdc']),
                'total_inflow': float(row['total_inflow']),
                'total_outflow': float(row['total_outflow']),
                'total_fees': float(row['total_fees']),
                'first_record_time': row['first_record_time'],
                'last_record_time': row['last_record_time'],
            }

    def get_ledger_by_type(self, address: str) -> Dict[str, Dict[str, Any]]:
        """
        按类型统计账本记录

        Args:
            address: 交易者地址

        Returns:
            {类型: {count, total_usdc}} 字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            cursor.execute("""
                SELECT 
                    delta_type,
                    COUNT(*) as count,
                    COALESCE(SUM(usdc), 0) as total_usdc,
                    COALESCE(SUM(fee), 0) as total_fee
                FROM trader_ledger_updates
                WHERE address = %s
                GROUP BY delta_type
                ORDER BY count DESC
            """, (address,))

            result = {}
            for row in cursor.fetchall():
                if row['delta_type']:
                    result[row['delta_type']] = {
                        'count': row['count'],
                        'total_usdc': float(row['total_usdc']),
                        'total_fee': float(row['total_fee']),
                    }

            return result

    def get_deposits_and_withdrawals(self, address: str, limit: int = 100) -> List[Dict]:
        """
        获取用户的存款和提款记录

        Args:
            address: 交易者地址
            limit: 返回数量

        Returns:
            存款/提款记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT * FROM trader_ledger_updates
                WHERE address = %s 
                AND delta_type IN ('deposit', 'withdraw')
                ORDER BY time DESC
                LIMIT %s
            """, (address, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_ledger_count(self, address: str) -> int:
        """获取用户账本记录总数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM trader_ledger_updates WHERE address = %s",
                (address,)
            )
            return cursor.fetchone()[0]

    def delete_ledger_records(self, address: str) -> int:
        """
        删除用户的所有账本记录

        Args:
            address: 交易者地址

        Returns:
            删除的记录数
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM trader_ledger_updates WHERE address = %s",
                (address,)
            )
            return cursor.rowcount
