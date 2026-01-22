"""
跟单订单和仓位状态管理相关路由
包括：订单管理、仓位状态管理
"""
from flask import Blueprint, jsonify, request
import logging

from database import TraderDatabase

logger = logging.getLogger(__name__)

copy_trading_orders_bp = Blueprint('copy_trading_orders', __name__)
db = TraderDatabase()


# ==================== 跟单订单管理 API ====================

@copy_trading_orders_bp.route('/api/copy-trading/orders', methods=['GET'])
def get_copy_trading_orders():
    """
    获取跟单订单列表
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - target_address: str, 筛选目标地址
        - symbol: str, 筛选交易对
        - status: str, 筛选状态 (pending/success/failed)
        - action: str, 筛选操作类型 (open/close)
        - is_dry_run: bool, 筛选模拟/实盘
        - days: int, 最近N天，默认7
        - sort_by: str, 排序字段，默认created_at
        - sort_order: str, 排序方向，默认desc
        - min_win_rate: float, 最小胜率
        - max_win_rate: float, 最大胜率
        - min_profit_factor: float, 最小盈亏比
        - max_profit_factor: float, 最大盈亏比
        - min_pnl: float, 最小总盈亏
        - max_pnl: float, 最大总盈亏
        - min_drawdown: float, 最小回撤
        - max_drawdown: float, 最大回撤
        - min_sharpe: float, 最小Sharpe
        - max_sharpe: float, 最大Sharpe
        - min_trades: int, 最小交易数
        - max_trades: int, 最大交易数
        - min_score: float, 最小综合评分
        - max_score: float, 最大综合评分
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
def get_copy_trading_order_stats():
    """
    获取跟单订单统计
    Query Parameters:
        - target_address: str, 筛选目标地址
        - days: int, 统计天数，默认7
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
def cleanup_copy_trading_orders():
    """
    清理旧订单记录
    Query Parameters:
        - days: int, 保留最近N天的记录，默认30
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
def get_copy_position_states():
    """
    获取所有跟单仓位状态（用于重启后恢复的持久化状态）
    Query Parameters:
        - target_address: str, 筛选目标地址
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
def get_copy_position_stats():
    """
    获取跟单仓位统计
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
def get_target_position_states(target_address: str):
    """
    获取特定目标的仓位状态
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
def delete_position_state(target_address: str, symbol: str):
    """
    删除单个仓位状态
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
def clear_target_position_states(target_address: str):
    """
    清空目标的所有仓位状态
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
def clear_all_position_states():
    """
    清空所有仓位状态（谨慎使用）
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
