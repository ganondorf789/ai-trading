"""
跟单仓位状态管理相关路由
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required

logger = logging.getLogger(__name__)

copy_trading_orders_bp = Blueprint('copy_trading_orders', __name__)


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
