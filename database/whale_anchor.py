"""
巨鲸锚点数据库操作
"""
from typing import List, Dict, Optional
from loguru import logger


class WhaleAnchorOps:
    """巨鲸锚点数据库操作 Mixin"""

    def save_whale_anchors(self, items: List[Dict]) -> int:
        """
        批量保存巨鲸锚点数据（先清空再插入）

        Args:
            items: 巨鲸锚点数据列表

        Returns:
            保存的记录数
        """
        if not items:
            return 0

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # 清空旧数据
                cursor.execute("DELETE FROM whale_anchor")

                # 批量插入
                for item in items:
                    cursor.execute("""
                        INSERT INTO whale_anchor (
                            coin, mark_price, price_change_24h_pct,
                            day_volume_usd, open_interest_usd, depth_1pct_usd,
                            volume_component, oi_component, depth_component,
                            whale_threshold, dominant_factor, max_leverage
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s
                        )
                    """, (
                        item['coin'],
                        item['mark_price'],
                        item['price_change_24h_pct'],
                        item['day_volume_usd'],
                        item['open_interest_usd'],
                        item['depth_1pct_usd'],
                        item['volume_component'],
                        item['oi_component'],
                        item['depth_component'],
                        item['whale_threshold'],
                        item['dominant_factor'],
                        item['max_leverage'],
                    ))

                logger.info(f"巨鲸锚点数据已保存: {len(items)} 条")
                return len(items)

        except Exception as e:
            logger.error(f"保存巨鲸锚点数据失败: {e}")
            return 0

    def get_whale_anchors(self) -> List[Dict]:
        """
        获取所有巨鲸锚点数据（按 whale_threshold 降序）

        Returns:
            巨鲸锚点数据列表
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT coin, mark_price, price_change_24h_pct,
                           day_volume_usd, open_interest_usd, depth_1pct_usd,
                           volume_component, oi_component, depth_component,
                           whale_threshold, dominant_factor, max_leverage,
                           updated_at
                    FROM whale_anchor
                    ORDER BY whale_threshold DESC
                """)

                rows = cursor.fetchall()
                columns = [
                    'coin', 'mark_price', 'price_change_24h_pct',
                    'day_volume_usd', 'open_interest_usd', 'depth_1pct_usd',
                    'volume_component', 'oi_component', 'depth_component',
                    'whale_threshold', 'dominant_factor', 'max_leverage',
                    'updated_at'
                ]

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"获取巨鲸锚点数据失败: {e}")
            return []

    def get_whale_threshold_for_coin(self, coin: str) -> Optional[float]:
        """
        获取指定币种的巨鲸仓位阈值

        Args:
            coin: 币种名称

        Returns:
            巨鲸仓位阈值（USD），未找到返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT whale_threshold FROM whale_anchor WHERE coin = %s",
                    (coin,)
                )
                row = cursor.fetchone()
                return float(row[0]) if row else None

        except Exception as e:
            logger.error(f"获取 {coin} 巨鲸阈值失败: {e}")
            return None

    def get_whale_thresholds_map(self) -> Dict[str, float]:
        """
        获取所有币种的巨鲸仓位阈值映射

        Returns:
            {coin: threshold} 字典
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT coin, whale_threshold FROM whale_anchor")
                rows = cursor.fetchall()
                return {row[0]: float(row[1]) for row in rows}

        except Exception as e:
            logger.error(f"获取巨鲸阈值映射失败: {e}")
            return {}
