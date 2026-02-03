"""
跟单订单和仓位状态管理相关路由
包括：订单管理、仓位状态管理
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required

logger = logging.getLogger(__name__)

copy_trading_orders_bp = Blueprint('copy_trading_orders', __name__)


# ==================== 跟单订单管理 API ====================

@copy_trading_orders_bp.route('/api/copy-trading/orders', methods=['GET'])
@login_required
def get_copy_trading_orders():
    """获取跟单订单列表
    ---
    tags:
      - Copy Trading - Orders
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: 页码
      - name: limit
        in: query
        type: integer
        default: 20
        description: 每页数量
      - name: target_address
        in: query
        type: string
        description: 筛选目标地址
      - name: symbol
        in: query
        type: string
        description: 筛选交易对
      - name: status
        in: query
        type: string
        enum: [pending, success, failed]
        description: 筛选状态
      - name: action
        in: query
        type: string
        enum: [open, close]
        description: 筛选操作类型
      - name: is_dry_run
        in: query
        type: boolean
        description: 筛选模拟/实盘
      - name: days
        in: query
        type: integer
        default: 7
        description: 最近N天
      - name: sort_by
        in: query
        type: string
        default: created_at
        description: 排序字段
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
        default: desc
        description: 排序方向
    responses:
      200:
        description: 订单列表
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
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        target_address = request.args.get('target_address')
        symbol = request.args.get('symbol')
        status = request.args.get('status')
        action = request.args.get('action')
        is_dry_run = request.args.get('is_dry_run')
        days = int(request.args.get('days', 7))
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')

        # 指标筛选参数
        min_win_rate = request.args.get('min_win_rate', type=float)
        max_win_rate = request.args.get('max_win_rate', type=float)
        min_profit_factor = request.args.get('min_profit_factor', type=float)
        max_profit_factor = request.args.get('max_profit_factor', type=float)
        min_pnl = request.args.get('min_pnl', type=float)
        max_pnl = request.args.get('max_pnl', type=float)
        min_drawdown = request.args.get('min_drawdown', type=float)
        max_drawdown = request.args.get('max_drawdown', type=float)
        min_sharpe = request.args.get('min_sharpe', type=float)
        max_sharpe = request.args.get('max_sharpe', type=float)
        min_trades = request.args.get('min_trades', type=int)
        max_trades = request.args.get('max_trades', type=int)
        min_score = request.args.get('min_score', type=float)
        max_score = request.args.get('max_score', type=float)

        # 处理 is_dry_run 参数
        if is_dry_run is not None:
            is_dry_run = is_dry_run.lower() == 'true'

        offset = (page - 1) * limit

        # 构建指标筛选条件
        metric_filters = {
            'min_win_rate': min_win_rate,
            'max_win_rate': max_win_rate,
            'min_profit_factor': min_profit_factor,
            'max_profit_factor': max_profit_factor,
            'min_pnl': min_pnl,
            'max_pnl': max_pnl,
            'min_drawdown': min_drawdown,
            'max_drawdown': max_drawdown,
            'min_sharpe': min_sharpe,
            'max_sharpe': max_sharpe,
            'min_trades': min_trades,
            'max_trades': max_trades,
            'min_score': min_score,
            'max_score': max_score,
        }

        orders, total_count = db.get_copy_orders(
            target_address=target_address,
            symbol=symbol,
            status=status,
            action=action,
            is_dry_run=is_dry_run,
            days=days,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            metric_filters=metric_filters
        )

        total_pages = (total_count + limit - 1) // limit

        return jsonify({
            'success': True,
            'data': orders,
            'pagination': {
                'page': page,
                'limit': limit,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
    except Exception as e:
        logger.error(f"获取跟单订单列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/orders/stats', methods=['GET'])
@login_required
def get_copy_trading_order_stats():
    """获取跟单订单统计
    ---
    tags:
      - Copy Trading - Orders
    parameters:
      - name: target_address
        in: query
        type: string
        description: 筛选目标地址
      - name: days
        in: query
        type: integer
        default: 7
        description: 统计天数
    responses:
      200:
        description: 订单统计
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
        target_address = request.args.get('target_address')
        days = int(request.args.get('days', 7))

        stats = db.get_copy_order_stats(
            target_address=target_address,
            days=days
        )

        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取跟单订单统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/orders/cleanup', methods=['POST'])
@login_required
def cleanup_copy_trading_orders():
    """清理旧订单记录
    ---
    tags:
      - Copy Trading - Orders
    parameters:
      - name: days
        in: query
        type: integer
        default: 30
        description: 保留最近N天的记录
    responses:
      200:
        description: 清理成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      500:
        description: 服务器错误
    """
    try:
        days = int(request.args.get('days', 30))
        deleted_count = db.delete_old_copy_orders(days)

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'已清理 {deleted_count} 条旧订单记录'
        })
    except Exception as e:
        logger.error(f"清理旧订单记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 跟单仓位状态管理 API ====================

@copy_trading_orders_bp.route('/api/copy-trading/positions', methods=['GET'])
@login_required
def get_copy_position_states():
    """获取所有跟单仓位状态
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: target_address
        in: query
        type: string
        description: 筛选目标地址
    responses:
      200:
        description: 仓位状态列表
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
        target_address = request.args.get('target_address')
        positions = db.get_copy_position_states(target_address)

        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions)
        })
    except Exception as e:
        logger.error(f"获取跟单仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/positions/stats', methods=['GET'])
@login_required
def get_copy_position_stats():
    """获取跟单仓位统计
    ---
    tags:
      - Copy Trading - Positions
    responses:
      200:
        description: 仓位统计
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
        stats = db.get_copy_position_stats()

        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取跟单仓位统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/positions/<target_address>', methods=['GET'])
@login_required
def get_target_position_states(target_address: str):
    """获取特定目标的仓位状态
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: target_address
        in: path
        type: string
        required: true
        description: 目标地址
    responses:
      200:
        description: 仓位状态列表
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
        positions = db.get_copied_positions(target_address)

        return jsonify({
            'success': True,
            'data': list(positions.values()),
            'count': len(positions)
        })
    except Exception as e:
        logger.error(f"获取目标仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/positions/<target_address>/<symbol>', methods=['DELETE'])
@login_required
def delete_position_state(target_address: str, symbol: str):
    """删除单个仓位状态
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: target_address
        in: path
        type: string
        required: true
        description: 目标地址
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对
    responses:
      200:
        description: 删除成功
      404:
        description: 仓位状态不存在
      500:
        description: 服务器错误
    """
    try:
        success = db.delete_copied_position(target_address, symbol)

        if success:
            return jsonify({
                'success': True,
                'message': f'已删除 {target_address[:10]}... 的 {symbol} 仓位状态'
            })
        else:
            return jsonify({
                'success': False,
                'error': '仓位状态不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/positions/<target_address>', methods=['DELETE'])
@login_required
def clear_target_position_states(target_address: str):
    """清空目标的所有仓位状态
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: target_address
        in: path
        type: string
        required: true
        description: 目标地址
    responses:
      200:
        description: 清空成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      500:
        description: 服务器错误
    """
    try:
        deleted_count = db.clear_copied_positions(target_address)

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'已清空 {target_address[:10]}... 的 {deleted_count} 个仓位状态'
        })
    except Exception as e:
        logger.error(f"清空仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_orders_bp.route('/api/copy-trading/positions/clear-all', methods=['POST'])
@login_required
def clear_all_position_states():
    """清空所有仓位状态
    ---
    tags:
      - Copy Trading - Positions
    responses:
      200:
        description: 清空成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      500:
        description: 服务器错误
    """
    try:
        deleted_count = db.clear_all_copy_position_states()

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'已清空所有 {deleted_count} 个仓位状态'
        })
    except Exception as e:
        logger.error(f"清空所有仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
