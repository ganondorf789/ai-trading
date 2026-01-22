"""
交易者持仓和仓位历史相关路由
"""
from flask import Blueprint, jsonify, request
import logging

from database import TraderDatabase

logger = logging.getLogger(__name__)

traders_positions_bp = Blueprint('traders_positions', __name__)
db = TraderDatabase()


# ==================== 交易者持仓 API ====================

@traders_positions_bp.route('/api/traders/<address>/positions', methods=['GET'])
def get_trader_positions(address: str):
    """
    获取交易者的当前持仓（来自 assetPositions）
    """
    try:
        positions = db.get_positions(address)

        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions)
        })

    except Exception as e:
        logger.error(f"获取持仓数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_positions_bp.route('/api/traders/<address>/positions/refresh', methods=['POST'])
def refresh_trader_positions(address: str):
    """
    刷新交易者的当前持仓（从 Hyperliquid API 获取最新数据）
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants

        logger.info(f"刷新持仓数据: {address}")

        # 获取最新持仓
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        user_state = info.user_state(address)

        if not user_state:
            return jsonify({
                'success': False,
                'error': '无法获取用户状态'
            }), 404

        # 保存持仓数据
        asset_positions = user_state.get('assetPositions', [])
        positions_saved = db.save_positions(address, asset_positions)

        # 返回更新后的数据
        positions = db.get_positions(address)

        logger.info(f"持仓数据刷新完成: {address}, 持仓数: {positions_saved}")

        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions),
            'message': f'已更新 {positions_saved} 个持仓'
        })

    except Exception as e:
        logger.error(f"刷新持仓数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 交易者仓位历史 API ====================

@traders_positions_bp.route('/api/traders/<address>/position-history', methods=['GET'])
def get_trader_position_history(address: str):
    """
    获取交易者的仓位历史记录
    Query Parameters:
        - coin: str, 筛选特定币种（可选）
        - status: str, 筛选状态 'open'/'closed'（可选）
        - direction: str, 筛选方向 'long'/'short'（可选）
        - start_time: str, 开始时间ISO格式（可选）
        - end_time: str, 结束时间ISO格式（可选）
        - pnl_filter: str, 盈亏筛选 'profit'/'loss'（可选）
        - sort_by: str, 排序字段（可选，默认open_time）
        - sort_order: str, 排序方向 'asc'/'desc'（可选，默认desc）
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认50
    """
    try:
        coin = request.args.get('coin')
        status = request.args.get('status')
        direction = request.args.get('direction')
        start_time = request.args.get('start_time')
        end_time = request.args.get('end_time')
        pnl_filter = request.args.get('pnl_filter')
        sort_by = request.args.get('sort_by', 'open_time')
        sort_order = request.args.get('sort_order', 'desc')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit

        # 获取仓位历史
        positions = db.get_position_history(
            address,
            coin=coin,
            status=status,
            direction=direction,
            start_time=start_time,
            end_time=end_time,
            pnl_filter=pnl_filter,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )

        # 获取总数
        total_count = db.get_position_history_count(
            address,
            coin=coin,
            status=status,
            direction=direction,
            start_time=start_time,
            end_time=end_time,
            pnl_filter=pnl_filter
        )

        return jsonify({
            'success': True,
            'data': positions,
            'pagination': {
                'page': page,
                'limit': limit,
                'total_count': total_count,
                'total_pages': (total_count + limit - 1) // limit
            }
        })

    except Exception as e:
        logger.error(f"获取仓位历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_positions_bp.route('/api/traders/<address>/position-history/rebuild', methods=['POST'])
def rebuild_trader_position_history(address: str):
    """
    重建交易者的仓位历史（从 fills 重新计算）
    """
    try:
        logger.info(f"重建仓位历史: {address}")

        saved_count = db.rebuild_position_history(address)

        return jsonify({
            'success': True,
            'message': f'已重建 {saved_count} 条仓位历史记录',
            'count': saved_count
        })

    except Exception as e:
        logger.error(f"重建仓位历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_positions_bp.route('/api/traders/<address>/position-history/stats', methods=['GET'])
def get_trader_position_history_stats(address: str):
    """
    获取交易者的仓位历史统计信息
    """
    try:
        stats = db.get_position_history_stats(address)

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"获取仓位历史统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_positions_bp.route('/api/traders/<address>/position-history/by-coin', methods=['GET'])
def get_trader_position_history_by_coin(address: str):
    """
    获取按币种汇总的仓位历史
    """
    try:
        by_coin = db.get_position_history_by_coin(address)

        return jsonify({
            'success': True,
            'data': by_coin
        })

    except Exception as e:
        logger.error(f"获取币种仓位统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 全局仓位历史 API ====================

@traders_positions_bp.route('/api/position-history', methods=['GET'])
def get_all_position_history():
    """
    获取所有交易员的仓位历史
    Query Parameters:
        - coin: str, 筛选特定币种（可选）
        - status: str, 筛选状态 'open'/'closed'（可选）
        - direction: str, 筛选方向 'long'/'short'（可选）
        - min_pnl: float, 最小盈亏（可选）
        - max_pnl: float, 最大盈亏（可选）
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认50
    """
    try:
        coin = request.args.get('coin')
        status = request.args.get('status')
        direction = request.args.get('direction')
        min_pnl = request.args.get('min_pnl', type=float)
        max_pnl = request.args.get('max_pnl', type=float)
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit

        # 获取仓位历史
        positions = db.get_all_position_history(
            coin=coin,
            status=status,
            direction=direction,
            min_pnl=min_pnl,
            max_pnl=max_pnl,
            limit=limit,
            offset=offset
        )

        # 获取总数
        total_count = db.get_all_position_history_count(
            coin=coin,
            status=status,
            direction=direction,
            min_pnl=min_pnl,
            max_pnl=max_pnl
        )

        # 获取统计信息
        stats = db.get_all_position_history_stats()

        return jsonify({
            'success': True,
            'data': positions,
            'stats': stats,
            'pagination': {
                'page': page,
                'limit': limit,
                'total_count': total_count,
                'total_pages': (total_count + limit - 1) // limit
            }
        })

    except Exception as e:
        logger.error(f"获取全局仓位历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_positions_bp.route('/api/position-history/stats', methods=['GET'])
def get_all_position_history_stats():
    """
    获取所有交易员的仓位历史统计
    """
    try:
        stats = db.get_all_position_history_stats()

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"获取全局仓位历史统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_positions_bp.route('/api/position-history/by-coin', methods=['GET'])
def get_all_position_history_by_coin():
    """
    获取所有交易员按币种汇总的仓位历史
    """
    try:
        by_coin = db.get_all_position_history_by_coin()

        return jsonify({
            'success': True,
            'data': by_coin
        })

    except Exception as e:
        logger.error(f"获取币种仓位统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
