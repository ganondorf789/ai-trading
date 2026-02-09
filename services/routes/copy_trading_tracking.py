"""
仓位级别跟单相关路由（第二种跟单模式）
"""
import json
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required, get_current_user_id, get_current_user_ulid
from ..shared import get_redis_client

logger = logging.getLogger(__name__)

copy_trading_tracking_bp = Blueprint('copy_trading_tracking', __name__)


def _notify_open_position(tracking_id: int, user_ulid: str = '') -> bool:
    """
    发送开仓通知到 Redis，机器人收到后立即开仓
    
    消息格式（JSON）：{"tracking_id": "<ULID>", "user_ulid": "<ULID>"}
    机器人会校验 user_ulid 是否与自身 BOT_USER_ID 一致后才执行开仓
    
    Args:
        tracking_id: 跟单记录整数 ID
        user_ulid: 用户 ULID（从 JWT 中获取，无需查询数据库）
    """
    redis_client = get_redis_client()
    
    if redis_client is None:
        return False
    
    if not user_ulid:
        logger.warning(f"发送开仓通知失败: 未提供 user_ulid (tracking_id={tracking_id})")
        return False
    
    try:
        # 查询记录的 ULID
        tracking = db.get_position_tracking(tracking_id)
        if not tracking or not tracking.get('ulid'):
            logger.warning(f"发送开仓通知失败: 找不到 tracking_id={tracking_id} 的 ULID")
            return False
        
        tracking_ulid = tracking['ulid']
        
        # 发送 JSON 格式的开仓通知
        REDIS_OPEN_CHANNEL = "position_tracking_open"
        open_msg = json.dumps({
            'tracking_id': tracking_ulid,
            'user_ulid': user_ulid,
        })
        redis_client.publish(REDIS_OPEN_CHANNEL, open_msg)
        logger.info(f"已发送开仓通知: tracking_id={tracking_id}, ulid={tracking_ulid}, user={user_ulid[:8]}...")
        return True
    except Exception as e:
        logger.warning(f"发送开仓通知失败: {e}")
        return False


def _notify_config_changed() -> bool:
    """发送配置变更通知到 Redis，机器人收到后立即重载配置"""
    redis_client = get_redis_client()
    
    if redis_client is None:
        return False
    
    try:
        REDIS_CONFIG_RELOAD_CHANNEL = "copy_trading:config:reload"
        redis_client.publish(REDIS_CONFIG_RELOAD_CHANNEL, "reload")
        logger.info("已发送配置重载通知")
        return True
    except Exception as e:
        logger.warning(f"发送配置重载通知失败: {e}")
        return False


# ==================== 仓位级别跟单 API ====================

@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking', methods=['GET'])
@login_required
def get_position_trackings():
    """获取仓位跟单列表
    ---
    tags:
      - Copy Trading - Tracking
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
      - name: status
        in: query
        type: string
        enum: [pending, active, closed, stopped]
        description: 状态筛选
      - name: is_enabled
        in: query
        type: boolean
        description: 启用状态筛选
      - name: target_address
        in: query
        type: string
        description: 目标地址筛选
      - name: symbol
        in: query
        type: string
        description: 币种筛选
    responses:
      200:
        description: 跟单列表
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
        status = request.args.get('status')
        is_enabled = request.args.get('is_enabled')
        target_address = request.args.get('target_address')
        symbol = request.args.get('symbol')

        # 处理 is_enabled 参数
        if is_enabled is not None:
            is_enabled = is_enabled.lower() == 'true'

        offset = (page - 1) * limit
        trackings, total_count = db.get_position_trackings(
            status=status,
            is_enabled=is_enabled,
            target_address=target_address,
            symbol=symbol,
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
        logger.error(f"获取仓位跟单列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/stats', methods=['GET'])
@login_required
def get_position_tracking_stats():
    """获取仓位跟单统计
    ---
    tags:
      - Copy Trading - Tracking
    responses:
      200:
        description: 跟单统计
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
        stats = db.get_position_tracking_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取仓位跟单统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/<int:tracking_id>', methods=['GET'])
@login_required
def get_position_tracking(tracking_id: int):
    """获取仓位跟单详情
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟单记录ID
    responses:
      200:
        description: 跟单详情
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
        tracking = db.get_position_tracking(tracking_id)
        if not tracking:
            return jsonify({
                'success': False,
                'error': '跟单记录不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': tracking
        })
    except Exception as e:
        logger.error(f"获取仓位跟单详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking', methods=['POST'])
@login_required
def create_position_tracking():
    """创建仓位跟单
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - target_address
            - symbol
          properties:
            target_address:
              type: string
              description: 目标交易员地址
            symbol:
              type: string
              description: 币种
            target_name:
              type: string
              description: 交易员名称
            copy_ratio:
              type: number
              description: 跟单比例
            max_position_size_usd:
              type: number
              description: 最大仓位
    responses:
      200:
        description: 创建成功
      400:
        description: 参数错误
      409:
        description: 跟单已存在
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

        # 验证必需字段
        target_address = data.get('target_address', '').strip()
        symbol = data.get('symbol', '').strip()

        if not target_address:
            return jsonify({
                'success': False,
                'error': '目标地址不能为空'
            }), 400

        if not symbol:
            return jsonify({
                'success': False,
                'error': '币种不能为空'
            }), 400

        # 验证地址格式
        if not target_address.startswith('0x') or len(target_address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        # 检查是否已存在活跃的跟单
        if db.check_position_tracking_exists(target_address, symbol):
            return jsonify({
                'success': False,
                'error': f'已存在 {symbol} 的活跃跟单',
                'exists': True
            }), 409  # Conflict

        # 获取默认配置
        default_config = db.get_default_copy_config()

        # 构建跟单数据
        tracking_data = {
            'target_address': target_address,
            'target_name': data.get('target_name', ''),
            'symbol': symbol,
            'is_enabled': data.get('is_enabled', True),
            'copy_ratio': data.get('copy_ratio', default_config.get('copy_ratio', 0.1)),
            'max_position_size_usd': data.get('max_position_size_usd', default_config.get('max_position_size_usd', 500)),
            'min_position_size_usd': data.get('min_position_size_usd', default_config.get('min_position_size_usd', 20)),
            'copy_leverage': data.get('copy_leverage', default_config.get('copy_leverage', True)),
            'max_leverage': data.get('max_leverage', default_config.get('max_leverage', 10)),
            'default_leverage': data.get('default_leverage', default_config.get('default_leverage', 5)),
            'slippage': data.get('slippage', default_config.get('slippage', 0.01)),
            'auto_replenish': data.get('auto_replenish', False),
            'replenish_ratio': data.get('replenish_ratio', 0.5),
            'replenish_min_value_usd': data.get('replenish_min_value_usd', 10.0),
            'replenish_max_value_usd': data.get('replenish_max_value_usd', 100.0),
            'status': 'pending',
        }

        # 保存到数据库
        tracking_id = db.save_position_tracking(tracking_data)

        # 通知引擎重载配置
        _notify_config_changed()

        return jsonify({
            'success': True,
            'data': {'id': tracking_id},
            'message': f'仓位跟单创建成功: {symbol}'
        })
    except Exception as e:
        logger.error(f"创建仓位跟单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/<int:tracking_id>', methods=['PUT'])
@login_required
def update_position_tracking(tracking_id: int):
    """更新仓位跟单配置
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟单记录ID
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
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 检查记录是否存在
        existing = db.get_position_tracking(tracking_id)
        if not existing:
            return jsonify({
                'success': False,
                'error': '跟单记录不存在'
            }), 404

        # 只允许更新配置字段，不允许修改目标和币种
        update_data = {
            'id': tracking_id,
            'target_address': existing['target_address'],
            'symbol': existing['symbol'],
            'target_name': data.get('target_name', existing.get('target_name', '')),
            'is_enabled': data.get('is_enabled', existing.get('is_enabled', True)),
            'copy_ratio': data.get('copy_ratio', existing.get('copy_ratio', 0.1)),
            'max_position_size_usd': data.get('max_position_size_usd', existing.get('max_position_size_usd', 500)),
            'min_position_size_usd': data.get('min_position_size_usd', existing.get('min_position_size_usd', 20)),
            'copy_leverage': data.get('copy_leverage', existing.get('copy_leverage', True)),
            'max_leverage': data.get('max_leverage', existing.get('max_leverage', 10)),
            'default_leverage': data.get('default_leverage', existing.get('default_leverage', 5)),
            'slippage': data.get('slippage', existing.get('slippage', 0.01)),
            'auto_replenish': data.get('auto_replenish', existing.get('auto_replenish', False)),
            'replenish_ratio': data.get('replenish_ratio', existing.get('replenish_ratio', 0.5)),
            'replenish_min_value_usd': data.get('replenish_min_value_usd', existing.get('replenish_min_value_usd', 10.0)),
            'replenish_max_value_usd': data.get('replenish_max_value_usd', existing.get('replenish_max_value_usd', 100.0)),
            'status': existing.get('status', 'pending'),
            # 保留现有的仓位状态
            'target_initial_size': existing.get('target_initial_size'),
            'target_initial_side': existing.get('target_initial_side'),
            'target_initial_entry_price': existing.get('target_initial_entry_price'),
            'my_size': existing.get('my_size', 0),
            'my_side': existing.get('my_side'),
            'my_entry_price': existing.get('my_entry_price'),
            'closed_pnl': existing.get('closed_pnl'),
            'close_reason': existing.get('close_reason'),
            'started_at': existing.get('started_at'),
            'closed_at': existing.get('closed_at'),
        }

        db.save_position_tracking(update_data)

        # 通知引擎重载配置
        _notify_config_changed()

        return jsonify({
            'success': True,
            'message': '更新成功'
        })
    except Exception as e:
        logger.error(f"更新仓位跟单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/<int:tracking_id>', methods=['DELETE'])
@login_required
def delete_position_tracking(tracking_id: int):
    """删除仓位跟单记录
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟单记录ID
    responses:
      200:
        description: 删除成功
      400:
        description: 请先停止跟单
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        # 检查记录是否存在
        existing = db.get_position_tracking(tracking_id)
        if not existing:
            return jsonify({
                'success': False,
                'error': '跟单记录不存在'
            }), 404

        # 如果状态是 active，不允许直接删除（需要先停止）
        if existing.get('status') == 'active':
            return jsonify({
                'success': False,
                'error': '请先停止跟单再删除'
            }), 400

        success = db.delete_position_tracking(tracking_id)
        if success:
            # 通知引擎重载配置
            _notify_config_changed()

            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '删除失败'
            }), 500
    except Exception as e:
        logger.error(f"删除仓位跟单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/<int:tracking_id>/toggle', methods=['POST'])
@login_required
def toggle_position_tracking(tracking_id: int):
    """启用/禁用仓位跟单
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟单记录ID
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
        data = request.get_json()
        if data is None or 'is_enabled' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 is_enabled 参数'
            }), 400

        is_enabled = bool(data['is_enabled'])
        success = db.toggle_position_tracking(tracking_id, is_enabled)

        if success:
            # 通知引擎重载配置
            _notify_config_changed()

            return jsonify({
                'success': True,
                'message': '已启用' if is_enabled else '已禁用'
            })
        else:
            return jsonify({
                'success': False,
                'error': '跟单记录不存在'
            }), 404
    except Exception as e:
        logger.error(f"切换仓位跟单状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/<int:tracking_id>/stop', methods=['POST'])
@login_required
def stop_position_tracking(tracking_id: int):
    """停止仓位跟单
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟单记录ID
      - name: close_position
        in: query
        type: boolean
        default: false
        description: 是否同时平仓
    responses:
      200:
        description: 停止成功
      400:
        description: 状态不正确
      404:
        description: 记录不存在
      500:
        description: 服务器错误
    """
    try:
        # 检查记录是否存在
        existing = db.get_position_tracking(tracking_id)
        if not existing:
            return jsonify({
                'success': False,
                'error': '跟单记录不存在'
            }), 404

        if existing.get('status') not in ('pending', 'active'):
            return jsonify({
                'success': False,
                'error': f"状态为 {existing.get('status')}，无法停止"
            }), 400

        # 更新状态为 stopped
        success = db.update_tracking_status(tracking_id, 'stopped', '手动停止')

        if success:
            # 通知引擎重载配置
            _notify_config_changed()

            return jsonify({
                'success': True,
                'message': '已停止跟单'
            })
        else:
            return jsonify({
                'success': False,
                'error': '停止失败'
            }), 500
    except Exception as e:
        logger.error(f"停止仓位跟单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/quick-add', methods=['POST'])
@login_required
def quick_add_position_tracking():
    """快速添加仓位跟单
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - target_address
            - symbol
          properties:
            target_address:
              type: string
              description: 目标交易员地址
            symbol:
              type: string
              description: 币种
            target_name:
              type: string
              description: 交易员名称
    responses:
      200:
        description: 添加成功
      400:
        description: 参数错误
      409:
        description: 跟单已存在
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

        # 验证必需字段
        target_address = data.get('target_address', '').strip()
        symbol = data.get('symbol', '').strip()

        if not target_address:
            return jsonify({
                'success': False,
                'error': '目标地址不能为空'
            }), 400

        if not symbol:
            return jsonify({
                'success': False,
                'error': '币种不能为空'
            }), 400

        # 验证地址格式
        if not target_address.startswith('0x') or len(target_address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        # 检查是否已存在活跃的跟单
        if db.check_position_tracking_exists(target_address, symbol):
            return jsonify({
                'success': False,
                'error': f'已存在 {symbol} 的活跃跟单',
                'exists': True
            }), 409  # Conflict

        # 获取默认配置
        default_config = db.get_default_copy_config()

        # 构建跟单数据
        tracking_data = {
            'target_address': target_address,
            'target_name': data.get('target_name', ''),
            'symbol': symbol,
            'is_enabled': True,
            'copy_ratio': default_config.get('copy_ratio', 0.1),
            'max_position_size_usd': default_config.get('max_position_size_usd', 500),
            'min_position_size_usd': default_config.get('min_position_size_usd', 20),
            'copy_leverage': default_config.get('copy_leverage', True),
            'max_leverage': default_config.get('max_leverage', 10),
            'default_leverage': default_config.get('default_leverage', 5),
            'slippage': default_config.get('slippage', 0.01),
            'auto_replenish': False,
            'replenish_ratio': 0.5,
            'replenish_min_value_usd': 10.0,
            'replenish_max_value_usd': 100.0,
            'status': 'pending',
        }

        # 保存到数据库
        tracking_id = db.save_position_tracking(tracking_data)

        # 通知引擎重载配置
        _notify_config_changed()

        trader_display = data.get('target_name') or f"{target_address[:10]}..."

        return jsonify({
            'success': True,
            'data': {'id': tracking_id},
            'message': f'已添加 {trader_display} 的 {symbol} 仓位跟单'
        })
    except Exception as e:
        logger.error(f"快速添加仓位跟单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/quick-copy', methods=['POST'])
@login_required
def quick_copy_position():
    """快速跟单仓位（支持自定义跟单比例）
    
    用于 APP 新仓位列表的一键跟单功能，支持用户选择跟单比例。
    创建跟单后会自动发送 Redis 通知，触发跟单机器人立即开仓。
    根据传入的杠杆值匹配对应的配置规则。
    
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - target_address
            - symbol
          properties:
            target_address:
              type: string
              description: 目标交易员地址
            symbol:
              type: string
              description: 币种（如 BTC, ETH）
            target_name:
              type: string
              description: 交易员名称（可选）
            leverage:
              type: number
              description: 目标仓位杠杆倍数（用于匹配配置规则，不传则默认为1）
            ratio:
              type: number
              description: 跟单比例（百分比，如 10、20、30，不传则使用匹配规则的配置）
    responses:
      200:
        description: 跟单添加成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                id:
                  type: integer
                  description: 跟单记录ID
                copy_ratio:
                  type: number
                  description: 实际使用的跟单比例（小数）
                notified:
                  type: boolean
                  description: 是否成功发送了开仓通知
            message:
              type: string
      400:
        description: 参数错误
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
      409:
        description: 已存在该仓位的活跃跟单
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
            exists:
              type: boolean
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

        # 获取参数
        target_address = data.get('target_address', '').strip()
        symbol = data.get('symbol', '').strip()
        target_name = data.get('target_name', '').strip()
        leverage = data.get('leverage', 1)  # 目标仓位杠杆，用于匹配配置规则
        ratio = data.get('ratio')  # 百分比，如 10, 20, 30

        # 验证必需字段
        if not target_address:
            return jsonify({
                'success': False,
                'error': '目标地址不能为空'
            }), 400

        if not symbol:
            return jsonify({
                'success': False,
                'error': '币种不能为空'
            }), 400

        # 验证地址格式
        if not target_address.startswith('0x') or len(target_address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        # 转换杠杆值
        try:
            leverage = float(leverage or 1)
        except (ValueError, TypeError):
            leverage = 1.0

        logger.info(f"[快速跟单] 请求跟单:")
        logger.info(f"  - 交易员地址: {target_address}")
        logger.info(f"  - 币种: {symbol}")
        logger.info(f"  - 名称: {target_name}")
        logger.info(f"  - 杠杆: {leverage}x")
        if ratio is not None:
            logger.info(f"  - 跟单比例: {ratio}%")

        # 检查是否已存在活跃的跟单
        if db.check_position_tracking_exists(target_address, symbol):
            return jsonify({
                'success': False,
                'error': f'已存在 {symbol} 的活跃跟单',
                'exists': True
            }), 409  # Conflict

        # 根据杠杆匹配配置规则
        matched_config = db.get_copy_config_by_leverage('default', leverage)
        matched_rule_name = matched_config.get('_matched_rule_name')
        
        if matched_rule_name:
            logger.info(f"  - 匹配规则: {matched_rule_name}")
        else:
            logger.info(f"  - 使用默认配置（无匹配规则）")

        # 计算跟单比例：优先使用传入的 ratio，否则使用匹配规则的配置
        if ratio is not None:
            try:
                copy_ratio = float(ratio) / 100.0  # 传入的是百分比，转换为小数
                # 限制范围 0.01 ~ 10.0 (1% ~ 1000%)
                copy_ratio = max(0.01, min(10.0, copy_ratio))
            except (ValueError, TypeError):
                return jsonify({
                    'success': False,
                    'error': f'无效的跟单比例: {ratio}'
                }), 400
        else:
            copy_ratio = matched_config.get('copy_ratio', 0.1)

        # 构建跟单数据（使用匹配的配置）
        tracking_data = {
            'target_address': target_address,
            'target_name': target_name or "",
            'symbol': symbol,
            'is_enabled': True,
            'copy_ratio': copy_ratio,
            'max_position_size_usd': matched_config.get('max_position_size_usd', 500),
            'min_position_size_usd': matched_config.get('min_position_size_usd', 20),
            'copy_leverage': matched_config.get('copy_leverage', False),
            'max_leverage': matched_config.get('max_leverage', 10),
            'default_leverage': matched_config.get('default_leverage', 3),
            'slippage': matched_config.get('slippage', 0.001),
            'auto_replenish': False,
            'replenish_ratio': 0.5,
            'replenish_min_value_usd': 10.0,
            'replenish_max_value_usd': 100.0,
            'status': 'pending',
        }

        # 保存到数据库
        tracking_id = db.save_position_tracking(tracking_data)

        if not tracking_id:
            return jsonify({
                'success': False,
                'error': '保存跟单配置失败'
            }), 500

        trader_display = target_name if target_name else f"{target_address[:10]}..."
        logger.info(f"[快速跟单] 添加成功: #{tracking_id} {symbol} @ {trader_display} (比例: {copy_ratio * 100:.0f}%)")

        # 发送 Redis 开仓通知，让机器人立即开仓
        notified = _notify_open_position(tracking_id, user_ulid=get_current_user_ulid())

        return jsonify({
            'success': True,
            'data': {
                'id': tracking_id,
                'copy_ratio': copy_ratio,
                'notified': notified
            },
            'message': f'已添加 {symbol} 仓位跟单，跟单比例: {copy_ratio * 100:.0f}%' + ('，正在开仓...' if notified else '')
        })
    except Exception as e:
        logger.error(f"快速跟单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_tracking_bp.route('/api/copy-trading/position-tracking/<int:tracking_id>/notify-open', methods=['POST'])
@login_required
def notify_tracking_open(tracking_id: int):
    """手动触发开仓通知
    
    用于重新发送开仓通知到 Redis，让跟单机器人重新尝试开仓。
    适用于之前开仓失败或需要重试的情况。
    
    ---
    tags:
      - Copy Trading - Tracking
    parameters:
      - name: tracking_id
        in: path
        type: integer
        required: true
        description: 跟单记录ID
    responses:
      200:
        description: 通知发送成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      404:
        description: 跟单记录不存在
      400:
        description: 状态不允许发送通知
      500:
        description: 服务器错误
    """
    try:
        # 检查记录是否存在
        existing = db.get_position_tracking(tracking_id)
        if not existing:
            return jsonify({
                'success': False,
                'error': '跟单记录不存在'
            }), 404

        # 只有 pending 状态才允许发送开仓通知
        if existing.get('status') != 'pending':
            return jsonify({
                'success': False,
                'error': f"当前状态为 {existing.get('status')}，只有 pending 状态才能发送开仓通知"
            }), 400

        # 发送开仓通知
        notified = _notify_open_position(tracking_id, user_ulid=get_current_user_ulid())

        if notified:
            return jsonify({
                'success': True,
                'message': f'开仓通知已发送，等待机器人处理'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Redis 连接失败，无法发送通知'
            }), 500
    except Exception as e:
        logger.error(f"发送开仓通知失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
