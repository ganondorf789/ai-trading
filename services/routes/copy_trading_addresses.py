"""
跟单地址管理相关路由
包括：分组管理、地址管理
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required

logger = logging.getLogger(__name__)

copy_trading_addresses_bp = Blueprint('copy_trading_addresses', __name__)


# ==================== 跟单分组管理 API ====================

@copy_trading_addresses_bp.route('/api/copy-trading/groups', methods=['GET'])
@login_required
def get_copy_trading_groups():
    """获取跟单分组列表
    ---
    tags:
      - Copy Trading - Groups
    responses:
      200:
        description: 分组列表
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
@login_required
def create_copy_trading_group():
    """创建跟单分组
    ---
    tags:
      - Copy Trading - Groups
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              description: 分组名称
    responses:
      200:
        description: 创建成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      400:
        description: 请求参数错误
      500:
        description: 服务器错误
    """
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
@login_required
def update_copy_trading_group(group_id: int):
    """更新跟单分组
    ---
    tags:
      - Copy Trading - Groups
    parameters:
      - name: group_id
        in: path
        type: integer
        required: true
        description: 分组ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: 分组名称
    responses:
      200:
        description: 更新成功
      400:
        description: 请求参数错误
      500:
        description: 服务器错误
    """
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
@login_required
def delete_copy_trading_group(group_id: int):
    """删除跟单分组
    ---
    tags:
      - Copy Trading - Groups
    parameters:
      - name: group_id
        in: path
        type: integer
        required: true
        description: 分组ID
    responses:
      200:
        description: 删除成功
      400:
        description: 默认分组不能删除
      404:
        description: 分组不存在
      500:
        description: 服务器错误
    """
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
@login_required
def get_copy_trading_addresses():
    """获取跟单地址列表
    ---
    tags:
      - Copy Trading - Addresses
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
      - name: group_id
        in: query
        type: integer
        description: 分组ID筛选
      - name: is_enabled
        in: query
        type: boolean
        description: 状态筛选
      - name: search
        in: query
        type: string
        description: 搜索地址或名称
      - name: sort_by
        in: query
        type: string
        default: updated_at
        description: 排序字段
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
        default: desc
        description: 排序方向
    responses:
      200:
        description: 地址列表
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
@login_required
def get_copy_trading_address(address: str):
    """获取单个跟单地址详情
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 跟单地址
    responses:
      200:
        description: 地址详情
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      404:
        description: 地址不存在
      500:
        description: 服务器错误
    """
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
@login_required
def create_copy_trading_address():
    """添加跟单地址
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - address
          properties:
            address:
              type: string
              description: 以太坊地址
    responses:
      200:
        description: 添加成功
      400:
        description: 请求参数错误
      500:
        description: 服务器错误
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
@login_required
def quick_add_copy_trading_address():
    """快速添加跟单地址
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - address
          properties:
            address:
              type: string
              description: 交易员地址
            name:
              type: string
              description: 名称
            sync_position_symbols:
              type: array
              items:
                type: string
              description: 同步仓位的币种列表
    responses:
      200:
        description: 添加成功
      400:
        description: 请求参数错误
      409:
        description: 地址已存在
      500:
        description: 服务器错误
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
@login_required
def update_copy_trading_address(address: str):
    """更新跟单地址配置
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 跟单地址
      - name: body
        in: body
        required: true
        schema:
          type: object
    responses:
      200:
        description: 更新成功
      400:
        description: 请求参数错误
      404:
        description: 地址不存在
      500:
        description: 服务器错误
    """
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
@login_required
def delete_copy_trading_address(address: str):
    """删除跟单地址
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 跟单地址
    responses:
      200:
        description: 删除成功
      404:
        description: 地址不存在
      500:
        description: 服务器错误
    """
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
@login_required
def toggle_copy_trading_address(address: str):
    """启用/禁用跟单地址
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 跟单地址
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - is_enabled
          properties:
            is_enabled:
              type: boolean
              description: 是否启用
    responses:
      200:
        description: 操作成功
      400:
        description: 缺少参数
      404:
        description: 地址不存在
      500:
        description: 服务器错误
    """
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
@login_required
def toggle_copy_trading_sync_position(address: str):
    """切换同步仓位状态
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 跟单地址
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - sync_position
          properties:
            sync_position:
              type: boolean
              description: 是否同步仓位
    responses:
      200:
        description: 操作成功
      400:
        description: 缺少参数
      404:
        description: 地址不存在
      500:
        description: 服务器错误
    """
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
@login_required
def batch_update_copy_trading_addresses():
    """批量操作跟单地址
    ---
    tags:
      - Copy Trading - Addresses
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - action
            - addresses
          properties:
            action:
              type: string
              enum: [enable, disable, delete, move_group]
              description: 操作类型
            addresses:
              type: array
              items:
                type: string
              description: 地址列表
            group_id:
              type: integer
              description: 目标分组ID（仅move_group时需要）
    responses:
      200:
        description: 操作成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            affected_count:
              type: integer
            message:
              type: string
      400:
        description: 请求参数错误
      500:
        description: 服务器错误
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
