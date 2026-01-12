"""
跟单交易相关路由
包括：地址管理、订单管理、仓位管理
"""
from flask import Blueprint, jsonify, request
import logging

from database import TraderDatabase

logger = logging.getLogger(__name__)

copy_trading_bp = Blueprint('copy_trading', __name__)
db = TraderDatabase()


# ==================== 跟单地址管理 API ====================

@copy_trading_bp.route('/api/copy-trading/groups', methods=['GET'])
def get_copy_trading_groups():
    """获取跟单分组列表"""
    try:
        groups = db.get_copy_trading_groups()
        return jsonify({
            'success': True,
            'data': groups
        })
    except Exception as e:
        logger.error(f"获取跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/groups', methods=['POST'])
def create_copy_trading_group():
    """创建跟单分组"""
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({
                'success': False,
                'error': '分组名称不能为空'
            }), 400

        group_id = db.save_copy_trading_group(data)
        return jsonify({
            'success': True,
            'data': {'id': group_id},
            'message': '分组创建成功'
        })
    except Exception as e:
        logger.error(f"创建跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/groups/<int:group_id>', methods=['PUT'])
def update_copy_trading_group(group_id: int):
    """更新跟单分组"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        data['id'] = group_id
        db.save_copy_trading_group(data)
        return jsonify({
            'success': True,
            'message': '分组更新成功'
        })
    except Exception as e:
        logger.error(f"更新跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/groups/<int:group_id>', methods=['DELETE'])
def delete_copy_trading_group(group_id: int):
    """删除跟单分组"""
    try:
        if group_id == 1:
            return jsonify({
                'success': False,
                'error': '默认分组不能删除'
            }), 400

        success = db.delete_copy_trading_group(group_id)
        if success:
            return jsonify({
                'success': True,
                'message': '分组删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '分组不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses', methods=['GET'])
def get_copy_trading_addresses():
    """
    获取跟单地址列表
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - group_id: int, 分组ID筛选
        - is_enabled: bool, 状态筛选
        - search: str, 搜索地址或名称
        - sort_by: str, 排序字段
        - sort_order: str, 排序方向
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        group_id = request.args.get('group_id', type=int)
        is_enabled = request.args.get('is_enabled')
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')

        # 处理 is_enabled 参数
        if is_enabled is not None:
            is_enabled = is_enabled.lower() == 'true'

        offset = (page - 1) * limit
        addresses, total_count = db.get_copy_trading_addresses(
            group_id=group_id,
            is_enabled=is_enabled,
            search=search,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )

        total_pages = (total_count + limit - 1) // limit

        return jsonify({
            'success': True,
            'data': addresses,
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
        logger.error(f"获取跟单地址列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses/<address>', methods=['GET'])
def get_copy_trading_address(address: str):
    """获取单个跟单地址详情"""
    try:
        data = db.get_copy_trading_address(address)
        if not data:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        logger.error(f"获取跟单地址详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses', methods=['POST'])
def create_copy_trading_address():
    """添加跟单地址"""
    try:
        data = request.get_json()
        if not data or not data.get('address'):
            return jsonify({
                'success': False,
                'error': '地址不能为空'
            }), 400

        # 验证地址格式
        address = data['address'].strip()
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        data['address'] = address
        record_id = db.save_copy_trading_address(data)

        return jsonify({
            'success': True,
            'data': {'id': record_id},
            'message': '跟单地址添加成功'
        })
    except Exception as e:
        logger.error(f"添加跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses/<address>', methods=['PUT'])
def update_copy_trading_address(address: str):
    """更新跟单地址配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 检查地址是否存在
        existing = db.get_copy_trading_address(address)
        if not existing:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404

        data['address'] = address
        db.save_copy_trading_address(data)

        return jsonify({
            'success': True,
            'message': '更新成功'
        })
    except Exception as e:
        logger.error(f"更新跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses/<address>', methods=['DELETE'])
def delete_copy_trading_address(address: str):
    """删除跟单地址"""
    try:
        success = db.delete_copy_trading_address(address)
        if success:
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses/<address>/toggle', methods=['POST'])
def toggle_copy_trading_address(address: str):
    """启用/禁用跟单地址"""
    try:
        data = request.get_json()
        if data is None or 'is_enabled' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 is_enabled 参数'
            }), 400

        is_enabled = bool(data['is_enabled'])
        success = db.toggle_copy_trading_address(address, is_enabled)

        if success:
            return jsonify({
                'success': True,
                'message': '已启用' if is_enabled else '已禁用'
            })
        else:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404
    except Exception as e:
        logger.error(f"切换跟单地址状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses/<address>/sync-position', methods=['POST'])
def toggle_copy_trading_sync_position(address: str):
    """切换同步仓位状态"""
    try:
        data = request.get_json()
        if data is None or 'sync_position' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 sync_position 参数'
            }), 400

        sync_position = bool(data['sync_position'])
        success = db.toggle_copy_trading_sync_position(address, sync_position)

        if success:
            return jsonify({
                'success': True,
                'message': '已启用同步仓位' if sync_position else '已禁用同步仓位'
            })
        else:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404
    except Exception as e:
        logger.error(f"切换同步仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/addresses/batch', methods=['POST'])
def batch_update_copy_trading_addresses():
    """
    批量操作跟单地址
    Body:
        - action: str, 操作类型 (enable/disable/delete/move_group)
        - addresses: List[str], 地址列表
        - group_id: int, 目标分组ID（仅 move_group 时需要）
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        action = data.get('action')
        addresses = data.get('addresses', [])
        group_id = data.get('group_id')

        if action not in ('enable', 'disable', 'delete', 'move_group'):
            return jsonify({
                'success': False,
                'error': '无效的操作类型'
            }), 400

        if not addresses:
            return jsonify({
                'success': False,
                'error': '地址列表不能为空'
            }), 400

        if action == 'move_group' and group_id is None:
            return jsonify({
                'success': False,
                'error': '移动分组需要指定目标分组ID'
            }), 400

        affected_count = db.batch_update_copy_trading_addresses(
            addresses=addresses,
            action=action,
            group_id=group_id
        )

        return jsonify({
            'success': True,
            'affected_count': affected_count,
            'message': f'批量操作完成，影响 {affected_count} 条记录'
        })
    except Exception as e:
        logger.error(f"批量操作跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 跟单订单管理 API ====================

@copy_trading_bp.route('/api/copy-trading/orders', methods=['GET'])
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


@copy_trading_bp.route('/api/copy-trading/orders/stats', methods=['GET'])
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


@copy_trading_bp.route('/api/copy-trading/orders/cleanup', methods=['POST'])
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

@copy_trading_bp.route('/api/copy-trading/positions', methods=['GET'])
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


@copy_trading_bp.route('/api/copy-trading/positions/stats', methods=['GET'])
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


@copy_trading_bp.route('/api/copy-trading/positions/<target_address>', methods=['GET'])
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


@copy_trading_bp.route('/api/copy-trading/positions/<target_address>/<symbol>', methods=['DELETE'])
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


@copy_trading_bp.route('/api/copy-trading/positions/<target_address>', methods=['DELETE'])
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


@copy_trading_bp.route('/api/copy-trading/positions/clear-all', methods=['POST'])
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


# ==================== 跟单交易员实时持仓 API ====================

@copy_trading_bp.route('/api/copy-trading/trader-positions', methods=['GET'])
def get_all_trader_positions():
    """
    获取所有跟单交易员的当前持仓（从数据库 asset_positions 表）
    Query Parameters:
        - enabled_only: bool, 是否只显示已启用的跟单地址，默认 true
        - group_id: int, 按分组筛选
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
        - min_sortino: float, 最小Sortino
        - max_sortino: float, 最大Sortino
        - min_trades: int, 最小交易数
        - max_trades: int, 最大交易数
        - min_score: float, 最小综合评分
        - max_score: float, 最大综合评分
    """
    try:
        enabled_only = request.args.get('enabled_only', 'true').lower() == 'true'
        group_id = request.args.get('group_id', type=int)

        # 构建指标筛选条件
        metric_filters = {
            'min_win_rate': request.args.get('min_win_rate', type=float),
            'max_win_rate': request.args.get('max_win_rate', type=float),
            'min_profit_factor': request.args.get('min_profit_factor', type=float),
            'max_profit_factor': request.args.get('max_profit_factor', type=float),
            'min_pnl': request.args.get('min_pnl', type=float),
            'max_pnl': request.args.get('max_pnl', type=float),
            'min_drawdown': request.args.get('min_drawdown', type=float),
            'max_drawdown': request.args.get('max_drawdown', type=float),
            'min_sharpe': request.args.get('min_sharpe', type=float),
            'max_sharpe': request.args.get('max_sharpe', type=float),
            'min_sortino': request.args.get('min_sortino', type=float),
            'max_sortino': request.args.get('max_sortino', type=float),
            'min_trades': request.args.get('min_trades', type=int),
            'max_trades': request.args.get('max_trades', type=int),
            'min_score': request.args.get('min_score', type=float),
            'max_score': request.args.get('max_score', type=float),
        }

        positions, stats = db.get_trader_positions_with_filters(
            enabled_only=enabled_only,
            group_id=group_id,
            metric_filters=metric_filters
        )

        return jsonify({
            'success': True,
            'data': positions,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"获取跟单交易员持仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/risk-control', methods=['GET'])
def get_risk_control_config():
    """
    获取风控配置
    """
    try:
        config = db.get_risk_control_config()
        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logger.error(f"获取风控配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/risk-control', methods=['PUT'])
def update_risk_control_config():
    """
    更新风控配置
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 验证配置字段
        valid_fields = {
            'max_total_positions': (int, 1, 100),
            'max_daily_trades': (int, 1, 1000),
            'max_single_loss_usd': (float, 0, 100000),
            'max_daily_loss_usd': (float, 0, 1000000),
            'max_drawdown_pct': (float, 0, 100),
            'max_margin_usage_pct': (float, 0, 100),
            'pause_on_consecutive_losses': (int, 1, 100),
            'max_order_retries': (int, 0, 10),
            'retry_base_delay': (float, 0.1, 60),
        }

        config = {}
        for field, (field_type, min_val, max_val) in valid_fields.items():
            if field in data:
                value = data[field]
                if field_type == int:
                    value = int(value)
                else:
                    value = float(value)
                # 范围验证
                value = max(min_val, min(max_val, value))
                config[field] = value

        success = db.save_risk_control_config(config)
        if success:
            return jsonify({
                'success': True,
                'data': config,
                'message': '风控配置更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '保存配置失败'
            }), 500
    except Exception as e:
        logger.error(f"更新风控配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/default-config', methods=['GET'])
def get_default_copy_config():
    """
    获取默认跟单配置
    """
    try:
        config = db.get_default_copy_config()
        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logger.error(f"获取默认跟单配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/default-config', methods=['PUT'])
def update_default_copy_config():
    """
    更新默认跟单配置
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 验证配置字段
        valid_fields = {
            'copy_ratio': (float, 0.01, 10.0),
            'max_position_size_usd': (float, 1, 1000000),
            'min_position_size_usd': (float, 1, 100000),
            'max_leverage': (int, 1, 100),
            'default_leverage': (int, 1, 100),
            'slippage': (float, 0.0001, 0.1),
            'copy_leverage': (bool, None, None),
            'sync_position': (bool, None, None),
            'dry_run': (bool, None, None),
        }

        config = {}
        for field, (field_type, min_val, max_val) in valid_fields.items():
            if field in data:
                value = data[field]
                if field_type == int:
                    value = int(value)
                    if min_val is not None and max_val is not None:
                        value = max(min_val, min(max_val, value))
                elif field_type == float:
                    value = float(value)
                    if min_val is not None and max_val is not None:
                        value = max(min_val, min(max_val, value))
                elif field_type == bool:
                    value = bool(value)
                config[field] = value

        # 处理数组字段
        if 'symbols_whitelist' in data:
            config['symbols_whitelist'] = data['symbols_whitelist'] if isinstance(data['symbols_whitelist'], list) else []
        if 'symbols_blacklist' in data:
            config['symbols_blacklist'] = data['symbols_blacklist'] if isinstance(data['symbols_blacklist'], list) else []

        success = db.save_default_copy_config(config)
        if success:
            return jsonify({
                'success': True,
                'data': config,
                'message': '默认跟单配置更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '保存配置失败'
            }), 500
    except Exception as e:
        logger.error(f"更新默认跟单配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/trader-positions/refresh', methods=['POST'])
def refresh_all_trader_positions():
    """
    刷新所有跟单交易员的当前持仓（从 Hyperliquid API 获取最新数据）
    Query Parameters:
        - enabled_only: bool, 是否只刷新已启用的跟单地址，默认 true
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        import time

        enabled_only = request.args.get('enabled_only', 'true').lower() == 'true'

        addresses = db.get_copy_trading_addresses_list(enabled_only)

        if not addresses:
            return jsonify({
                'success': True,
                'data': {'refreshed_count': 0, 'total_positions': 0},
                'message': '没有需要刷新的跟单地址'
            })

        logger.info(f"开始刷新 {len(addresses)} 个跟单交易员的持仓数据...")

        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        refreshed_count = 0
        total_positions = 0
        errors = []

        for addr_info in addresses:
            address = addr_info['address']
            try:
                # 获取最新持仓
                user_state = info.user_state(address)

                if user_state:
                    asset_positions = user_state.get('assetPositions', [])
                    positions_saved = db.save_positions(address, asset_positions)
                    total_positions += positions_saved
                    refreshed_count += 1
                    logger.debug(f"刷新 {address[:10]}... 持仓: {positions_saved} 个")

                # 添加小延迟避免 API 限流
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"刷新 {address[:10]}... 持仓失败: {e}")
                errors.append({'address': address, 'error': str(e)})

        logger.info(f"持仓刷新完成: {refreshed_count}/{len(addresses)} 个地址，共 {total_positions} 个持仓")

        return jsonify({
            'success': True,
            'data': {
                'refreshed_count': refreshed_count,
                'total_positions': total_positions,
                'errors': errors if errors else None
            },
            'message': f'已刷新 {refreshed_count} 个交易员的持仓数据，共 {total_positions} 个持仓'
        })
    except Exception as e:
        logger.error(f"刷新跟单交易员持仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 持仓 AI 分析 API ====================

@copy_trading_bp.route('/api/copy-trading/trader-positions/ai-analysis', methods=['POST'])
def ai_analyze_all_positions():
    """
    AI分析所有持仓（整体分析）
    Body (JSON):
        - positions: List[Dict], 持仓数据列表（可选，不传则从数据库获取）
        - stats: Dict, 持仓统计数据（可选）
        - provider: str, AI提供商 (zhipu/qwen/deepseek/openrouter)
        - filters: Dict, 筛选条件（可选）
        - force_refresh: bool, 是否强制重新分析（忽略缓存）
    """
    try:
        from services.positions_analysis import analyze_all_positions
        
        data = request.get_json() or {}
        provider = data.get('provider') or request.args.get('provider')
        filters = data.get('filters', {})
        force_refresh = data.get('force_refresh', False)
        
        # 如果没有传入持仓数据，从数据库获取
        positions = data.get('positions')
        stats = data.get('stats')
        
        if not positions:
            # 构建指标筛选条件
            metric_filters = {
                'min_win_rate': filters.get('min_win_rate'),
                'max_win_rate': filters.get('max_win_rate'),
                'min_profit_factor': filters.get('min_profit_factor'),
                'max_profit_factor': filters.get('max_profit_factor'),
                'min_pnl': filters.get('min_pnl'),
                'max_pnl': filters.get('max_pnl'),
                'min_drawdown': filters.get('min_drawdown'),
                'max_drawdown': filters.get('max_drawdown'),
                'min_sharpe': filters.get('min_sharpe'),
                'max_sharpe': filters.get('max_sharpe'),
                'min_sortino': filters.get('min_sortino'),
                'max_sortino': filters.get('max_sortino'),
                'min_trades': filters.get('min_trades'),
                'max_trades': filters.get('max_trades'),
                'min_score': filters.get('min_score'),
                'max_score': filters.get('max_score'),
            }
            
            positions, stats = db.get_trader_positions_with_filters(
                enabled_only=filters.get('enabled_only', False),
                group_id=filters.get('group_id'),
                metric_filters=metric_filters
            )
        
        if not positions:
            return jsonify({
                'success': False,
                'error': '没有找到持仓数据'
            }), 400
        
        if not stats:
            # 构建基础统计
            stats = _build_positions_stats(positions)
        
        # 检查是否已有分析结果（除非强制刷新）
        if not force_refresh:
            existing = db.get_positions_ai_analysis('overall', positions)
            if existing:
                logger.info(f"返回已存在的整体持仓AI分析结果")
                return jsonify({
                    'success': True,
                    'data': {
                        'analysis_type': existing.get('analysis_type'),
                        'position_count': existing.get('position_count'),
                        'analysis_text': existing.get('analysis_text'),
                        'sections': existing.get('sections', {}),
                    },
                    'cached': True,
                    'analyzed_at': existing.get('updated_at').isoformat() if existing.get('updated_at') else None,
                    'message': '返回已存在的分析结果'
                })
        
        logger.info(f"开始整体持仓AI分析，共 {len(positions)} 个持仓，提供商: {provider or '默认'}")
        
        analysis = analyze_all_positions(positions, stats, provider=provider)
        
        # 保存分析结果到数据库
        db.save_positions_ai_analysis(
            analysis_type='overall',
            analysis=analysis,
            positions=positions,
            stats=stats,
            provider=provider
        )
        
        return jsonify({
            'success': True,
            'data': analysis,
            'cached': False,
            'message': 'AI分析完成'
        })
    except Exception as e:
        logger.error(f"整体持仓AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/trader-positions/ai-analysis/coin', methods=['POST'])
def ai_analyze_coin_positions():
    """
    AI分析单个币种的所有持仓
    Body (JSON):
        - coin: str, 币种名称（必填）
        - positions: List[Dict], 该币种的持仓数据列表（可选）
        - provider: str, AI提供商
        - force_refresh: bool, 是否强制重新分析
    """
    try:
        from services.positions_analysis import analyze_coin_positions
        
        data = request.get_json() or {}
        coin = data.get('coin')
        provider = data.get('provider') or request.args.get('provider')
        force_refresh = data.get('force_refresh', False)
        
        if not coin:
            return jsonify({
                'success': False,
                'error': '缺少 coin 参数'
            }), 400
        
        # 如果没有传入持仓数据，从数据库获取
        positions = data.get('positions')
        if not positions:
            all_positions, _ = db.get_trader_positions_with_filters(enabled_only=False)
            positions = [p for p in all_positions if p.get('coin') == coin]
        
        if not positions:
            return jsonify({
                'success': False,
                'error': f'没有找到 {coin} 的持仓数据'
            }), 400
        
        # 检查是否已有分析结果
        if not force_refresh:
            existing = db.get_positions_ai_analysis('coin', positions, coin=coin)
            if existing:
                logger.info(f"返回已存在的 {coin} 币种AI分析结果")
                return jsonify({
                    'success': True,
                    'data': {
                        'analysis_type': existing.get('analysis_type'),
                        'coin': existing.get('coin'),
                        'position_count': existing.get('position_count'),
                        'analysis_text': existing.get('analysis_text'),
                        'sections': existing.get('sections', {}),
                    },
                    'cached': True,
                    'analyzed_at': existing.get('updated_at').isoformat() if existing.get('updated_at') else None,
                    'message': f'返回已存在的 {coin} 分析结果'
                })
        
        # 构建币种统计
        coin_stats = _build_coin_stats(positions)
        
        logger.info(f"开始 {coin} 币种持仓AI分析，共 {len(positions)} 个持仓，提供商: {provider or '默认'}")
        
        analysis = analyze_coin_positions(coin, positions, coin_stats, provider=provider)
        
        # 保存分析结果
        db.save_positions_ai_analysis(
            analysis_type='coin',
            analysis=analysis,
            positions=positions,
            stats=coin_stats,
            coin=coin,
            provider=provider
        )
        
        return jsonify({
            'success': True,
            'data': analysis,
            'cached': False,
            'message': f'{coin} AI分析完成'
        })
    except Exception as e:
        logger.error(f"币种持仓AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/trader-positions/ai-analysis/single', methods=['POST'])
def ai_analyze_single_position():
    """
    AI分析单个仓位
    Body (JSON):
        - position: Dict, 仓位数据（必填）
        - provider: str, AI提供商
        - force_refresh: bool, 是否强制重新分析
    """
    try:
        from services.positions_analysis import analyze_single_position
        
        data = request.get_json() or {}
        position = data.get('position')
        provider = data.get('provider') or request.args.get('provider')
        force_refresh = data.get('force_refresh', False)
        
        if not position:
            return jsonify({
                'success': False,
                'error': '缺少 position 参数'
            }), 400
        
        address = position.get('address')
        coin = position.get('coin', 'Unknown')
        
        # 检查是否已有分析结果
        if not force_refresh:
            existing = db.get_positions_ai_analysis('single', [position], coin=coin, address=address)
            if existing:
                logger.info(f"返回已存在的单仓位 {coin} AI分析结果")
                return jsonify({
                    'success': True,
                    'data': {
                        'analysis_type': existing.get('analysis_type'),
                        'coin': existing.get('coin'),
                        'address': existing.get('address'),
                        'analysis_text': existing.get('analysis_text'),
                        'sections': existing.get('sections', {}),
                    },
                    'cached': True,
                    'analyzed_at': existing.get('updated_at').isoformat() if existing.get('updated_at') else None,
                    'message': f'返回已存在的 {coin} 仓位分析结果'
                })
        
        # 尝试获取交易员详细信息
        trader_info = None
        if address:
            trader_info = db.get_trader_by_address(address)
        
        logger.info(f"开始单仓位 {coin} AI分析，提供商: {provider or '默认'}")
        
        analysis = analyze_single_position(position, trader_info, provider=provider)
        
        # 保存分析结果
        db.save_positions_ai_analysis(
            analysis_type='single',
            analysis=analysis,
            positions=[position],
            coin=coin,
            address=address,
            provider=provider
        )
        
        return jsonify({
            'success': True,
            'data': analysis,
            'cached': False,
            'message': f'{coin} 仓位AI分析完成'
        })
    except Exception as e:
        logger.error(f"单仓位AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_bp.route('/api/copy-trading/trader-positions/ai-analysis/check', methods=['POST'])
def check_positions_ai_analysis():
    """
    检查是否已有持仓 AI 分析结果（不执行分析）
    Body (JSON):
        - analysis_type: str, 分析类型 (overall/coin/single)
        - positions: List[Dict], 持仓数据列表
        - coin: str, 币种（coin/single类型时需要）
        - address: str, 地址（single类型时需要）
    """
    try:
        data = request.get_json() or {}
        analysis_type = data.get('analysis_type', 'overall')
        positions = data.get('positions', [])
        coin = data.get('coin')
        address = data.get('address')
        
        if not positions:
            return jsonify({
                'success': False,
                'error': '缺少 positions 参数'
            }), 400
        
        existing = db.get_positions_ai_analysis(analysis_type, positions, coin=coin, address=address)
        
        if existing:
            return jsonify({
                'success': True,
                'exists': True,
                'data': {
                    'analysis_type': existing.get('analysis_type'),
                    'coin': existing.get('coin'),
                    'address': existing.get('address'),
                    'position_count': existing.get('position_count'),
                    'analysis_text': existing.get('analysis_text'),
                    'sections': existing.get('sections', {}),
                },
                'analyzed_at': existing.get('updated_at').isoformat() if existing.get('updated_at') else None
            })
        else:
            return jsonify({
                'success': True,
                'exists': False,
                'data': None
            })
    except Exception as e:
        logger.error(f"检查持仓AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _build_positions_stats(positions: list) -> dict:
    """构建持仓统计数据"""
    if not positions:
        return {
            'total_positions': 0,
            'total_traders': 0,
            'total_notional': 0,
            'long_count': 0,
            'short_count': 0,
            'long_notional': 0,
            'short_notional': 0,
            'total_unrealized_pnl': 0,
            'profit_count': 0,
            'loss_count': 0,
            'profit_pnl': 0,
            'loss_pnl': 0,
            'by_coin': [],
            'by_trader': [],
        }
    
    # 基础统计
    unique_traders = set(p.get('address') for p in positions)
    long_positions = [p for p in positions if p.get('szi', 0) > 0]
    short_positions = [p for p in positions if p.get('szi', 0) < 0]
    
    # 盈亏统计
    profit_positions = [p for p in positions if (p.get('unrealized_pnl') or 0) > 0]
    loss_positions = [p for p in positions if (p.get('unrealized_pnl') or 0) < 0]
    
    total_unrealized_pnl = sum(p.get('unrealized_pnl', 0) or 0 for p in positions)
    profit_pnl = sum(p.get('unrealized_pnl', 0) or 0 for p in profit_positions)
    loss_pnl = sum(p.get('unrealized_pnl', 0) or 0 for p in loss_positions)
    
    # 按币种分组统计
    coin_map = {}
    for p in positions:
        coin = p.get('coin', '-')
        if coin not in coin_map:
            coin_map[coin] = {'count': 0, 'notional': 0, 'long': 0, 'short': 0}
        coin_map[coin]['count'] += 1
        coin_map[coin]['notional'] += abs(p.get('position_value', 0) or 0)
        if p.get('szi', 0) > 0:
            coin_map[coin]['long'] += 1
        else:
            coin_map[coin]['short'] += 1
    
    by_coin = sorted(
        [{'coin': k, **v} for k, v in coin_map.items()],
        key=lambda x: x['notional'],
        reverse=True
    )
    
    # 按交易员分组统计
    trader_map = {}
    for p in positions:
        addr = p.get('address', '-')
        if addr not in trader_map:
            trader_map[addr] = {'name': p.get('trader_name'), 'count': 0, 'notional': 0}
        trader_map[addr]['count'] += 1
        trader_map[addr]['notional'] += abs(p.get('position_value', 0) or 0)
    
    by_trader = sorted(
        [{'address': k, **v} for k, v in trader_map.items()],
        key=lambda x: x['notional'],
        reverse=True
    )
    
    return {
        'total_positions': len(positions),
        'total_traders': len(unique_traders),
        'total_notional': sum(abs(p.get('position_value', 0) or 0) for p in positions),
        'long_count': len(long_positions),
        'short_count': len(short_positions),
        'long_notional': sum(abs(p.get('position_value', 0) or 0) for p in long_positions),
        'short_notional': sum(abs(p.get('position_value', 0) or 0) for p in short_positions),
        'total_unrealized_pnl': total_unrealized_pnl,
        'profit_count': len(profit_positions),
        'loss_count': len(loss_positions),
        'profit_pnl': profit_pnl,
        'loss_pnl': loss_pnl,
        'by_coin': by_coin,
        'by_trader': by_trader,
    }


def _build_coin_stats(positions: list) -> dict:
    """构建币种统计数据"""
    if not positions:
        return {'notional': 0, 'count': 0, 'long': 0, 'short': 0}
    
    long_positions = [p for p in positions if p.get('szi', 0) > 0]
    short_positions = [p for p in positions if p.get('szi', 0) < 0]
    
    return {
        'notional': sum(abs(p.get('position_value', 0) or 0) for p in positions),
        'count': len(positions),
        'long': len(long_positions),
        'short': len(short_positions),
    }