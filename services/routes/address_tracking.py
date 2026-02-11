"""
地址跟踪相关路由
用于监控特定地址的交易活动并发送通知
"""
from flask import Blueprint, jsonify, request, g
import logging

from .db import db
from .middleware import login_required

logger = logging.getLogger(__name__)

address_tracking_bp = Blueprint('address_tracking', __name__)


# ==================== 地址跟踪 API ====================

@address_tracking_bp.route('/api/address-tracking', methods=['GET'])
@login_required
def get_address_trackings():
    """获取地址跟踪列表
    ---
    tags:
      - Address Tracking
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
      - name: is_enabled
        in: query
        type: boolean
        description: 启用状态筛选
      - name: search
        in: query
        type: string
        description: 搜索地址或备注
    responses:
      200:
        description: 跟踪列表
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
        user_id = g.current_user['user_id']
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        is_enabled = request.args.get('is_enabled')
        search = request.args.get('search')

        # 处理 is_enabled 参数
        if is_enabled is not None:
            is_enabled = is_enabled.lower() == 'true'

        offset = (page - 1) * limit
        trackings, total_count = db.get_address_trackings(
            user_id=user_id,
            is_enabled=is_enabled,
            search=search,
            limit=limit,
            offset=offset
        )

        total_pages = (total_count + limit - 1) // limit

        return jsonify({
            'success': True,
            'data': trackings,
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
        logger.error(f"获取地址跟踪列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/stats', methods=['GET'])
@login_required
def get_address_tracking_stats():
    """获取地址跟踪统计
    ---
    tags:
      - Address Tracking
    responses:
      200:
        description: 跟踪统计
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
        user_id = g.current_user['user_id']
        stats = db.get_address_tracking_stats(user_id)
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取地址跟踪统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/<int:tracking_id>', methods=['GET'])
@login_required
def get_address_tracking(tracking_id: int):
    """获取地址跟踪详情
    ---
    tags:
      - Address Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟踪记录ID
    responses:
      200:
        description: 跟踪详情
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        tracking = db.get_address_tracking(user_id, tracking_id)
        if not tracking:
            return jsonify({
                'success': False,
                'error': '跟踪记录不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': tracking
        })
    except Exception as e:
        logger.error(f"获取地址跟踪详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking', methods=['POST'])
@login_required
def create_address_tracking():
    """创建地址跟踪
    ---
    tags:
      - Address Tracking
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - tracking_address
          properties:
            tracking_address:
              type: string
              description: 跟踪地址
            address_remark:
              type: string
              description: 地址备注
            is_enabled:
              type: boolean
              description: 是否启用
            enable_notification:
              type: boolean
              description: 是否开启通知
            monitor_events:
              type: array
              items:
                type: string
              description: 监控事件列表 (open/close/add/reduce)
    responses:
      200:
        description: 创建成功
      400:
        description: 参数错误
      409:
        description: 跟踪已存在
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        user_ulid = g.current_user.get('user_ulid', '')
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 验证必需字段
        tracking_address = data.get('tracking_address', '').strip()

        if not tracking_address:
            return jsonify({
                'success': False,
                'error': '跟踪地址不能为空'
            }), 400

        # 验证地址格式
        if not tracking_address.startswith('0x') or len(tracking_address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        # 检查是否已存在
        if db.check_address_tracking_exists(user_id, tracking_address):
            return jsonify({
                'success': False,
                'error': f'已存在该地址的跟踪记录',
                'exists': True
            }), 409  # Conflict

        # 验证监控事件
        valid_events = {'open', 'close', 'add', 'reduce'}
        monitor_events = data.get('monitor_events', ['open', 'close', 'add', 'reduce'])
        if isinstance(monitor_events, list):
            monitor_events = [e for e in monitor_events if e in valid_events]
        else:
            monitor_events = list(valid_events)

        # 构建跟踪数据
        tracking_data = {
            'tracking_address': tracking_address,
            'address_remark': data.get('address_remark', ''),
            'is_enabled': data.get('is_enabled', True),
            'enable_notification': data.get('enable_notification', True),
            'monitor_events': monitor_events,
        }

        # 保存到数据库
        tracking_id = db.save_address_tracking(user_id, tracking_data, user_ulid=user_ulid)

        return jsonify({
            'success': True,
            'data': {'id': tracking_id},
            'message': f'地址跟踪创建成功'
        })
    except Exception as e:
        logger.error(f"创建地址跟踪失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/<int:tracking_id>', methods=['PUT'])
@login_required
def update_address_tracking(tracking_id: int):
    """更新地址跟踪配置
    ---
    tags:
      - Address Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟踪记录ID
      - name: body
        in: body
        required: true
        schema:
          type: object
    responses:
      200:
        description: 更新成功
      400:
        description: 参数错误
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        user_ulid = g.current_user.get('user_ulid', '')
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 检查记录是否存在
        existing = db.get_address_tracking(user_id, tracking_id)
        if not existing:
            return jsonify({
                'success': False,
                'error': '跟踪记录不存在'
            }), 404

        # 验证监控事件
        valid_events = {'open', 'close', 'add', 'reduce'}
        monitor_events = data.get('monitor_events', existing.get('monitor_events', []))
        if isinstance(monitor_events, list):
            monitor_events = [e for e in monitor_events if e in valid_events]

        # 构建更新数据
        update_data = {
            'id': tracking_id,
            'tracking_address': existing['tracking_address'],  # 不允许修改跟踪地址
            'address_remark': data.get('address_remark', existing.get('address_remark', '')),
            'is_enabled': data.get('is_enabled', existing.get('is_enabled', True)),
            'enable_notification': data.get('enable_notification', existing.get('enable_notification', True)),
            'monitor_events': monitor_events,
        }

        db.save_address_tracking(user_id, update_data, user_ulid=user_ulid)

        return jsonify({
            'success': True,
            'message': '更新成功'
        })
    except Exception as e:
        logger.error(f"更新地址跟踪失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/<int:tracking_id>', methods=['DELETE'])
@login_required
def delete_address_tracking(tracking_id: int):
    """删除地址跟踪记录
    ---
    tags:
      - Address Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟踪记录ID
    responses:
      200:
        description: 删除成功
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        success = db.delete_address_tracking(user_id, tracking_id)
        if success:
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '跟踪记录不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除地址跟踪失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/<int:tracking_id>/toggle', methods=['POST'])
@login_required
def toggle_address_tracking(tracking_id: int):
    """启用/禁用地址跟踪
    ---
    tags:
      - Address Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟踪记录ID
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
    responses:
      200:
        description: 操作成功
      400:
        description: 缺少参数
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        data = request.get_json()
        if data is None or 'is_enabled' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 is_enabled 参数'
            }), 400

        is_enabled = bool(data['is_enabled'])
        success = db.toggle_address_tracking(user_id, tracking_id, is_enabled)

        if success:
            return jsonify({
                'success': True,
                'message': '已启用' if is_enabled else '已禁用'
            })
        else:
            return jsonify({
                'success': False,
                'error': '跟踪记录不存在'
            }), 404
    except Exception as e:
        logger.error(f"切换地址跟踪状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/<int:tracking_id>/toggle-notification', methods=['POST'])
@login_required
def toggle_address_tracking_notification(tracking_id: int):
    """启用/禁用地址跟踪通知
    ---
    tags:
      - Address Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟踪记录ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - enable_notification
          properties:
            enable_notification:
              type: boolean
    responses:
      200:
        description: 操作成功
      400:
        description: 缺少参数
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        data = request.get_json()
        if data is None or 'enable_notification' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 enable_notification 参数'
            }), 400

        enable_notification = bool(data['enable_notification'])
        success = db.toggle_address_tracking_notification(user_id, tracking_id, enable_notification)

        if success:
            return jsonify({
                'success': True,
                'message': '通知已启用' if enable_notification else '通知已禁用'
            })
        else:
            return jsonify({
                'success': False,
                'error': '跟踪记录不存在'
            }), 404
    except Exception as e:
        logger.error(f"切换地址跟踪通知状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@address_tracking_bp.route('/api/address-tracking/batch-delete', methods=['POST'])
@login_required
def batch_delete_address_trackings():
    """批量删除地址跟踪记录
    ---
    tags:
      - Address Tracking
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - tracking_ids
          properties:
            tracking_ids:
              type: array
              items:
                type: integer
              description: 跟踪记录ID列表
    responses:
      200:
        description: 删除成功
      400:
        description: 参数错误
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        data = request.get_json()
        if not data or 'tracking_ids' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 tracking_ids 参数'
            }), 400

        tracking_ids = data['tracking_ids']
        if not isinstance(tracking_ids, list):
            return jsonify({
                'success': False,
                'error': 'tracking_ids 必须是数组'
            }), 400

        deleted_count = db.batch_delete_address_trackings(user_id, tracking_ids)

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'成功删除 {deleted_count} 条记录'
        })
    except Exception as e:
        logger.error(f"批量删除地址跟踪失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
