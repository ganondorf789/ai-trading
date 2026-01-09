"""
Hyperliquid 币种管理模块 (PostgreSQL)
"""
from typing import List, Dict
import pendulum
from psycopg2 import extras
from loguru import logger

from screener.trader_screener import SHANGHAI_TZ
from .cache import cache


class CoinsOps:
    """Hyperliquid 币种管理相关操作"""

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
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT(name) DO UPDATE SET
                            sz_decimals = EXCLUDED.sz_decimals,
                            max_leverage = EXCLUDED.max_leverage,
                            only_isolated = EXCLUDED.only_isolated,
                            is_active = EXCLUDED.is_active,
                            updated_at = EXCLUDED.updated_at
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

            # 使缓存失效
            cache.delete("coins:all")

            return saved_count

    def get_hyperliquid_coins(self, active_only: bool = True) -> List[Dict]:
        """
        获取 Hyperliquid 币种列表

        Args:
            active_only: 是否只返回活跃币种

        Returns:
            币种列表
        """
        # 尝试从缓存获取
        if active_only:
            cached = cache.get_coins()
            if cached:
                return cached

        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

            if active_only:
                cursor.execute("""
                    SELECT * FROM hyperliquid_coins
                    WHERE is_active = TRUE
                    ORDER BY name
                """)
            else:
                cursor.execute("""
                    SELECT * FROM hyperliquid_coins
                    ORDER BY name
                """)

            result = [dict(row) for row in cursor.fetchall()]

            # 缓存结果
            if active_only and result:
                cache.cache_coins(result)

            return result

    def get_hyperliquid_coin_names(self) -> List[str]:
        """
        获取 Hyperliquid 币种名称列表（仅活跃币种）

        Returns:
            币种名称列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute("""
                SELECT name FROM hyperliquid_coins
                WHERE is_active = TRUE
                ORDER BY name
            """)
            return [row['name'] for row in cursor.fetchall()]
