"""
交易数据代理路由
通过 Hyperliquid API 获取指定地址的 Perp Positions、Open Orders、TWAP
"""
from flask import Blueprint, jsonify, request
import logging

from hyperliquid.info import Info
from hyperliquid.utils import constants

from .middleware import login_required

logger = logging.getLogger(__name__)

trading_bp = Blueprint('trading', __name__)

# 复用单例 Info 客户端
_info: Info = None


def _get_info() -> Info:
    global _info
    if _info is None:
        _info = Info(constants.MAINNET_API_URL, skip_ws=True)
    return _info


# ==================== Perp Positions ====================

@trading_bp.route('/api/trading/<address>/positions', methods=['GET'])
@login_required
def get_perp_positions(address: str):
    """获取指定地址的永续合约持仓
    ---
    tags:
      - Trading
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 钱包地址
    responses:
      200:
        description: 持仓数据
      500:
        description: 服务器错误
    """
    try:
        info = _get_info()
        user_state = info.user_state(address)

        if not user_state:
            return jsonify({'success': False, 'error': '无法获取用户状态'}), 404

        asset_positions = user_state.get('assetPositions', [])
        margin_summary = user_state.get('marginSummary', {})
        cross_margin_summary = user_state.get('crossMarginSummary', {})

        # 只保留有仓位的（szi != 0）
        active_positions = []
        for item in asset_positions:
            pos = item.get('position', {})
            szi = float(pos.get('szi', 0))
            if szi != 0:
                active_positions.append({
                    'coin': pos.get('coin'),
                    'size': szi,
                    'side': 'long' if szi > 0 else 'short',
                    'entryPx': pos.get('entryPx'),
                    'positionValue': pos.get('positionValue'),
                    'unrealizedPnl': pos.get('unrealizedPnl'),
                    'returnOnEquity': pos.get('returnOnEquity'),
                    'leverage': pos.get('leverage'),
                    'liquidationPx': pos.get('liquidationPx'),
                    'marginUsed': pos.get('marginUsed'),
                    'maxLeverage': pos.get('maxLeverage'),
                })

        return jsonify({
            'success': True,
            'data': {
                'positions': active_positions,
                'marginSummary': margin_summary,
                'crossMarginSummary': cross_margin_summary,
                'withdrawable': user_state.get('withdrawable'),
            },
            'count': len(active_positions)
        })

    except Exception as e:
        logger.error(f"获取持仓数据失败 [{address}]: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Open Orders ====================

@trading_bp.route('/api/trading/<address>/open-orders', methods=['GET'])
@login_required
def get_open_orders(address: str):
    """获取指定地址的挂单（含触发单详情）
    ---
    tags:
      - Trading
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 钱包地址
    responses:
      200:
        description: 挂单列表
      500:
        description: 服务器错误
    """
    try:
        info = _get_info()
        orders = info.frontend_open_orders(address)

        return jsonify({
            'success': True,
            'data': orders,
            'count': len(orders)
        })

    except Exception as e:
        logger.error(f"获取挂单数据失败 [{address}]: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== TWAP ====================

@trading_bp.route('/api/trading/<address>/twap', methods=['GET'])
@login_required
def get_twap_slice_fills(address: str):
    """获取指定地址的 TWAP 切片成交记录
    ---
    tags:
      - Trading
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 钱包地址
    responses:
      200:
        description: TWAP 切片成交记录（最多2000条）
      500:
        description: 服务器错误
    """
    try:
        info = _get_info()
        twap_fills = info.user_twap_slice_fills(address)

        return jsonify({
            'success': True,
            'data': twap_fills,
            'count': len(twap_fills) if twap_fills else 0
        })

    except Exception as e:
        logger.error(f"获取TWAP数据失败 [{address}]: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
