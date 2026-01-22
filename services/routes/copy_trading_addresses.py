"""
跟单地址管理相关路由
包括：分组管理、地址管理
"""
from flask import Blueprint, jsonify, request
import logging

from database import TraderDatabase

logger = logging.getLogger(__name__)

copy_trading_addresses_bp = Blueprint('copy_trading_addresses', __name__)
db = TraderDatabase()


# ==================== 跟单分组管理 API ====================

@copy_trading_addresses_bp.route('/api/copy-trading/groups', methods=['GET'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/groups', methods=['POST'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/groups/<int:group_id>', methods=['PUT'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/groups/<int:group_id>', methods=['DELETE'])
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


# ==================== 跟单地址管理 API ====================

@copy_trading_addresses_bp.route('/api/copy-trading/addresses', methods=['GET'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/<address>', methods=['GET'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses', methods=['POST'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/quick-add', methods=['POST'])
def quick_add_copy_trading_address():
    """
    快速添加跟单地址（使用默认配置）
    用于从持仓页面一键添加跟单
    
    Request Body:
        - address: 交易员地址（必需）
        - name: 名称（可选）
        - sync_position_symbols: 同步仓位的币种列表（可选，默认空列表表示同步所有）
    """
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

        # 检查地址是否已存在
        existing = db.get_copy_trading_address(address)
        if existing:
            # 如果已存在但是禁用状态，则重新启用
            if not existing.get('is_enabled', True):
                existing['is_enabled'] = True
                # 更新同步仓位币种（如果提供了）
                if data.get('sync_position_symbols'):
                    existing['sync_position_symbols'] = data.get('sync_position_symbols')
                existing['sync_position'] = True
                record_id = db.save_copy_trading_address(existing)
                
                sync_symbols = existing.get('sync_position_symbols', [])
                sync_msg = f"，同步币种: {', '.join(sync_symbols)}" if sync_symbols else "（同步所有币种）"
                
                return jsonify({
                    'success': True,
                    'data': {'id': record_id},
                    'message': f'交易员已重新启用{sync_msg}'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': '该交易员已在跟单列表中',
                    'exists': True
                }), 409  # Conflict

        # 获取默认配置
        default_config = db.get_default_copy_config()
        
        # 构建新地址配置
        new_address_data = {
            'address': address,
            'name': data.get('name', ''),
            'is_enabled': True,
            'copy_ratio': default_config.get('copy_ratio', 0.1),
            'max_position_size_usd': default_config.get('max_position_size_usd', 500),
            'min_position_size_usd': default_config.get('min_position_size_usd', 20),
            'copy_leverage': default_config.get('copy_leverage', False),
            'max_leverage': default_config.get('max_leverage', 10),
            'default_leverage': default_config.get('default_leverage', 3),
            'slippage': default_config.get('slippage', 0.001),
            'symbols_whitelist': default_config.get('symbols_whitelist', []),
            'symbols_blacklist': default_config.get('symbols_blacklist', []),
            'sync_position': True,  # 启用同步仓位
            'sync_position_symbols': data.get('sync_position_symbols', []),  # 同步指定币种
            'dry_run': default_config.get('dry_run', False),
        }
        
        record_id = db.save_copy_trading_address(new_address_data)
        
        sync_symbols = data.get('sync_position_symbols', [])
        sync_msg = f"，同步币种: {', '.join(sync_symbols)}" if sync_symbols else "（同步所有币种）"

        return jsonify({
            'success': True,
            'data': {'id': record_id},
            'message': f'跟单地址添加成功{sync_msg}'
        })
    except Exception as e:
        logger.error(f"快速添加跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/<address>', methods=['PUT'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/<address>', methods=['DELETE'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/<address>/toggle', methods=['POST'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/<address>/sync-position', methods=['POST'])
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


@copy_trading_addresses_bp.route('/api/copy-trading/addresses/batch', methods=['POST'])
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
