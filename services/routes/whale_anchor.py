"""
巨鲸锚点路由
通过 Hyperliquid API 获取市场数据，计算每个币种的巨鲸仓位阈值

巨鲸仓位 ≈ max(
  0.4% × 24h Volume,
  1% × OI,
  30% × 1%盘口深度
)

所有用户可查看（从数据库读取），仅管理员可刷新（从 API 拉取并写入数据库）。
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, jsonify
import logging

from .db import db
from .middleware import login_required, admin_required
from hyperliquid.info import Info
from hyperliquid.utils import constants

logger = logging.getLogger(__name__)

whale_anchor_bp = Blueprint('whale_anchor', __name__)


def _get_info_client() -> Info:
    """获取 Hyperliquid Info 客户端"""
    return Info(constants.MAINNET_API_URL, skip_ws=True)


def _calculate_orderbook_depth_1pct(info: Info, coin: str, mid_price: float) -> float:
    """
    计算 1% 盘口深度（双边总和，USD 计价）

    遍历 L2 订单簿，累加中间价上下 1% 范围内的挂单量

    Args:
        info: Hyperliquid Info 客户端
        coin: 币种名称
        mid_price: 中间价

    Returns:
        1% 盘口深度的 USD 价值
    """
    try:
        orderbook = info.l2_snapshot(coin)
        levels = orderbook.get('levels', [[], []])
        bids = levels[0] if len(levels) > 0 else []
        asks = levels[1] if len(levels) > 1 else []

        lower_bound = mid_price * 0.99  # 1% below
        upper_bound = mid_price * 1.01  # 1% above

        depth_usd = 0.0

        # 买盘深度（mid 以下 1% 以内）
        for level in bids:
            px = float(level['px'])
            sz = float(level['sz'])
            if px >= lower_bound:
                depth_usd += px * sz
            else:
                break  # 价格递减排列，后续都更低

        # 卖盘深度（mid 以上 1% 以内）
        for level in asks:
            px = float(level['px'])
            sz = float(level['sz'])
            if px <= upper_bound:
                depth_usd += px * sz
            else:
                break  # 价格递增排列，后续都更高

        return depth_usd
    except Exception as e:
        logger.warning(f"获取 {coin} 盘口深度失败: {e}")
        return 0.0


def _fetch_whale_anchor_data() -> list:
    """
    从 Hyperliquid API 获取所有币种的巨鲸锚点数据

    Returns:
        巨鲸锚点数据列表
    """
    info = _get_info_client()

    # 1. 获取 meta 和资产上下文
    meta_and_ctxs = info.meta_and_asset_ctxs()
    meta, contexts = meta_and_ctxs
    universe = meta.get('universe', [])

    # 构建基础数据（排除已下架的）
    coins_data = []
    for idx, asset in enumerate(universe):
        if idx >= len(contexts):
            break
        if asset.get('isDelisted'):
            continue

        coin_name = asset['name']
        ctx = contexts[idx]

        mark_price = float(ctx.get('markPx', 0) or 0)
        if mark_price <= 0:
            continue

        day_ntl_vlm = float(ctx.get('dayNtlVlm', 0) or 0)
        open_interest_base = float(ctx.get('openInterest', 0) or 0)
        open_interest_usd = open_interest_base * mark_price

        coins_data.append({
            'coin': coin_name,
            'mark_price': mark_price,
            'day_ntl_vlm': day_ntl_vlm,
            'open_interest_usd': open_interest_usd,
            'open_interest_base': open_interest_base,
            'max_leverage': asset.get('maxLeverage', 0),
            'prev_day_px': float(ctx.get('prevDayPx', 0) or 0),
        })

    # 2. 并行获取 L2 盘口深度
    def fetch_depth(coin_info):
        coin = coin_info['coin']
        mid = coin_info['mark_price']
        depth = _calculate_orderbook_depth_1pct(info, coin, mid)
        coin_info['depth_1pct'] = depth
        return coin_info

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_depth, c): c for c in coins_data}
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                coin = futures[future]
                logger.warning(f"获取 {coin.get('coin', '?')} 数据失败: {e}")
                coin['depth_1pct'] = 0.0
                results.append(coin)

    # 3. 计算巨鲸锚点
    whale_data = []
    for item in results:
        volume_component = 0.004 * item['day_ntl_vlm']          # 0.4% × 24h Volume
        oi_component = 0.01 * item['open_interest_usd']          # 1% × OI
        depth_component = 0.30 * item['depth_1pct']              # 30% × 1% 盘口深度

        whale_threshold = max(volume_component, oi_component, depth_component)

        # 判断主导因子
        if whale_threshold > 0:
            if whale_threshold == volume_component:
                dominant_factor = 'volume'
            elif whale_threshold == oi_component:
                dominant_factor = 'oi'
            else:
                dominant_factor = 'depth'
        else:
            dominant_factor = 'none'

        # 价格24h变化
        prev_price = item['prev_day_px']
        mark_price = item['mark_price']
        price_change_pct = ((mark_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

        whale_data.append({
            'coin': item['coin'],
            'mark_price': round(mark_price, 6),
            'price_change_24h_pct': round(price_change_pct, 2),
            'day_volume_usd': round(item['day_ntl_vlm'], 2),
            'open_interest_usd': round(item['open_interest_usd'], 2),
            'depth_1pct_usd': round(item['depth_1pct'], 2),
            'volume_component': round(volume_component, 2),
            'oi_component': round(oi_component, 2),
            'depth_component': round(depth_component, 2),
            'whale_threshold': round(whale_threshold, 2),
            'dominant_factor': dominant_factor,
            'max_leverage': item['max_leverage'],
        })

    # 按巨鲸阈值降序排列
    whale_data.sort(key=lambda x: x['whale_threshold'], reverse=True)

    return whale_data


# ==================== API Routes ====================


@whale_anchor_bp.route('/api/whale-anchor', methods=['GET'])
@login_required
def get_whale_anchors():
    """获取所有币种的巨鲸锚点数据（从数据库读取）
    ---
    tags:
      - Whale Anchor
    responses:
      200:
        description: 成功获取巨鲸锚点数据
    """
    try:
        data = db.get_whale_anchors()

        # 将 updated_at 转为字符串
        updated_at = None
        for item in data:
            if item.get('updated_at'):
                updated_at = item['updated_at'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(item['updated_at'], 'strftime') else str(item['updated_at'])
                item['updated_at'] = updated_at

        return jsonify({
            'success': True,
            'data': data,
            'total': len(data),
            'updated_at': updated_at,
        })

    except Exception as e:
        logger.error(f"获取巨鲸锚点数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@whale_anchor_bp.route('/api/whale-anchor/refresh', methods=['POST'])
@login_required
@admin_required
def refresh_whale_anchors():
    """刷新巨鲸锚点数据（仅管理员）
    从 Hyperliquid API 获取最新数据并保存到数据库。
    ---
    tags:
      - Whale Anchor
    responses:
      200:
        description: 刷新成功
      403:
        description: 需要管理员权限
    """
    try:
        data = _fetch_whale_anchor_data()

        # 保存到数据库
        saved = db.save_whale_anchors(data)

        return jsonify({
            'success': True,
            'message': f'已刷新 {saved} 个币种的巨鲸锚点数据',
            'total': saved,
        })

    except Exception as e:
        logger.error(f"刷新巨鲸锚点数据失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
