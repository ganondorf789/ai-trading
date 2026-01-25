"""
交易者持仓和仓位历史相关路由
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db

logger = logging.getLogger(__name__)

traders_positions_bp = Blueprint('traders_positions', __name__)


# ==================== 交易者持仓 API ====================

@traders_positions_bp.route('/api/traders/<address>/positions', methods=['GET'])
def get_trader_positions(address: str):
    """获取交易者当前持仓
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 持仓列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            count:
              type: integer
      500:
        description: 服务器错误
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
    """刷新交易者持仓
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 刷新成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            count:
              type: integer
            message:
              type: string
      404:
        description: 无法获取用户状态
      500:
        description: 服务器错误
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
    """获取交易者仓位历史
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: coin
        in: query
        type: string
        description: 筛选特定币种
      - name: status
        in: query
        type: string
        enum: [open, closed]
        description: 筛选状态
      - name: direction
        in: query
        type: string
        enum: [long, short]
        description: 筛选方向
      - name: start_time
        in: query
        type: string
        format: date-time
        description: 开始时间ISO格式
      - name: end_time
        in: query
        type: string
        format: date-time
        description: 结束时间ISO格式
      - name: pnl_filter
        in: query
        type: string
        enum: [profit, loss]
        description: 盈亏筛选
      - name: sort_by
        in: query
        type: string
        default: open_time
        description: 排序字段
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
        default: desc
        description: 排序方向
      - name: page
        in: query
        type: integer
        default: 1
        description: 页码
      - name: limit
        in: query
        type: integer
        default: 50
        description: 每页数量
    responses:
      200:
        description: 仓位历史列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            pagination:
              type: object
      500:
        description: 服务器错误
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
    """重建交易者仓位历史
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 重建成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            count:
              type: integer
      500:
        description: 服务器错误
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
    """获取交易者仓位历史统计
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 统计信息
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      500:
        description: 服务器错误
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
    """获取按币种汇总的仓位历史
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 按币种汇总的仓位数据
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
      500:
        description: 服务器错误
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
    """获取所有交易员仓位历史
    ---
    tags:
      - Traders - Positions
    parameters:
      - name: coin
        in: query
        type: string
        description: 筛选特定币种
      - name: status
        in: query
        type: string
        enum: [open, closed]
        description: 筛选状态
      - name: direction
        in: query
        type: string
        enum: [long, short]
        description: 筛选方向
      - name: min_pnl
        in: query
        type: number
        description: 最小盈亏
      - name: max_pnl
        in: query
        type: number
        description: 最大盈亏
      - name: page
        in: query
        type: integer
        default: 1
        description: 页码
      - name: limit
        in: query
        type: integer
        default: 50
        description: 每页数量
    responses:
      200:
        description: 仓位历史列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            stats:
              type: object
            pagination:
              type: object
      500:
        description: 服务器错误
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
    """获取全局仓位历史统计
    ---
    tags:
      - Traders - Positions
    responses:
      200:
        description: 统计信息
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      500:
        description: 服务器错误
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
    """获取全局按币种汇总的仓位历史
    ---
    tags:
      - Traders - Positions
    responses:
      200:
        description: 按币种汇总的仓位数据
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
      500:
        description: 服务器错误
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


# ==================== 新仓位检测记录 API ====================

@traders_positions_bp.route('/api/new-positions', methods=['GET'])
def get_new_positions():
    """获取新仓位检测记录（游标分页）
    ---
    tags:
      - Traders - New Positions
    parameters:
      - name: before
        in: query
        type: integer
        description: 游标ID，获取此ID之前的记录。为空则从最新记录开始
      - name: limit
        in: query
        type: integer
        default: 50
        description: 返回数量限制（最大100）
      - name: trader_address
        in: query
        type: string
        description: 按交易员地址过滤
      - name: coin
        in: query
        type: string
        description: 按币种过滤
      - name: direction
        in: query
        type: string
        enum: [long, short]
        description: 按方向过滤
      - name: rating
        in: query
        type: string
        description: 按交易员评级过滤
      - name: min_position_value
        in: query
        type: number
        description: 最小仓位价值 (USD)
      - name: max_position_value
        in: query
        type: number
        description: 最大仓位价值 (USD)
      - name: min_leverage
        in: query
        type: integer
        description: 最小杠杆
      - name: max_leverage
        in: query
        type: integer
        description: 最大杠杆
    responses:
      200:
        description: 新仓位记录列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            has_more:
              type: boolean
              description: 是否还有更多数据
            next_before:
              type: integer
              description: 下一页的游标ID
      500:
        description: 服务器错误
    """
    try:
        # 解析参数
        before = request.args.get('before', type=int)
        limit = min(int(request.args.get('limit', 50)), 100)  # 最大100
        trader_address = request.args.get('trader_address')
        coin = request.args.get('coin')
        direction = request.args.get('direction')
        rating = request.args.get('rating')
        min_position_value = request.args.get('min_position_value', type=float)
        max_position_value = request.args.get('max_position_value', type=float)
        min_leverage = request.args.get('min_leverage', type=int)
        max_leverage = request.args.get('max_leverage', type=int)

        # 查询数据（多取一条用于判断是否有更多）
        positions = db.get_new_positions_cursor(
            limit=limit + 1,
            before=before,
            trader_address=trader_address,
            coin=coin,
            direction=direction,
            rating=rating,
            min_position_value=min_position_value,
            max_position_value=max_position_value,
            min_leverage=min_leverage,
            max_leverage=max_leverage
        )

        # 判断是否有更多数据
        has_more = len(positions) > limit
        if has_more:
            positions = positions[:limit]

        # 计算下一页游标
        next_before = positions[-1]['id'] if positions else None

        return jsonify({
            'success': True,
            'data': positions,
            'has_more': has_more,
            'next_before': next_before
        })

    except Exception as e:
        logger.error(f"获取新仓位记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


