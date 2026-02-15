"""
跟单交易员持仓和配置管理相关路由
包括：交易员持仓、风控配置、默认配置、立即跟单配置、AI分析
"""
from flask import Blueprint, jsonify, request, g
import logging

from .db import db
from .middleware import login_required
from database.cache import cache

logger = logging.getLogger(__name__)

# 持仓数据缓存 TTL（秒）
POSITIONS_CACHE_TTL = 60  # 1分钟

copy_trading_positions_bp = Blueprint('copy_trading_positions', __name__)


# ==================== 跟单交易员实时持仓 API ====================

@copy_trading_positions_bp.route('/api/copy-trading/trader-positions', methods=['GET'])
@login_required
def get_all_trader_positions():
    """获取最近N分钟内更新的所有跟单交易员当前持仓（纯前端筛选，后端仅返回数据）
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: minutes
        in: query
        type: integer
        default: 10
        description: 获取最近N分钟内更新的数据
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
      500:
        description: 服务器错误
    """
    try:
        minutes = request.args.get('minutes', 10, type=int)
        # 限制 minutes 范围：1-60
        minutes = max(1, min(60, minutes))
        
        # 构建缓存键
        cache_key = f"trader_positions:minutes_{minutes}"
        
        # 尝试从缓存获取
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"从缓存获取持仓数据: {cache_key}")
            return jsonify({
                'success': True,
                'data': cached_data,
                'cached': True
            })
        
        # 缓存未命中，从数据库获取
        positions = db.get_trader_positions_recent(minutes=minutes)
        
        # 写入缓存（1分钟过期）
        cache.set(cache_key, positions, ttl=POSITIONS_CACHE_TTL)
        logger.debug(f"持仓数据已缓存: {cache_key}, 共 {len(positions)} 条")

        return jsonify({
            'success': True,
            'data': positions,
            'cached': False
        })
    except Exception as e:
        logger.error(f"获取跟单交易员持仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/trader-positions/refresh', methods=['POST'])
@login_required
def refresh_all_trader_positions():
    """刷新所有跟单交易员持仓
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: enabled_only
        in: query
        type: boolean
        default: true
        description: 是否只刷新已启用的跟单地址
    responses:
      200:
        description: 刷新成功
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
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        import time

        user_id = g.current_user['user_id']
        enabled_only = request.args.get('enabled_only', 'true').lower() == 'true'

        addresses = db.get_copy_trading_addresses_list(user_id, enabled_only)

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


# ==================== 默认跟单配置 API ====================

@copy_trading_positions_bp.route('/api/copy-trading/default-config', methods=['GET'])
@login_required
def get_default_copy_config():
    """获取默认跟单配置
    ---
    tags:
      - Copy Trading - Config
    responses:
      200:
        description: 默认跟单配置
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
        config = db.get_default_copy_config(user_id)
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


@copy_trading_positions_bp.route('/api/copy-trading/default-config', methods=['PUT'])
@login_required
def update_default_copy_config():
    """更新默认跟单配置
    ---
    tags:
      - Copy Trading - Config
    parameters:
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
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
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
            'dry_run': (bool, None, None),
            # 自动补仓配置
            'auto_replenish': (bool, None, None),
            'replenish_ratio': (float, 0.01, 10.0),
            'replenish_min_value_usd': (float, 1, 100000),
            'replenish_max_value_usd': (float, 1, 100000),
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

        success = db.save_default_copy_config(user_id, config)
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


# ==================== 立即跟单配置 API ====================

@copy_trading_positions_bp.route('/api/copy-trading/immediate-config', methods=['GET'])
@login_required
def get_immediate_copy_config():
    """获取立即跟单配置
    ---
    tags:
      - Copy Trading - Config
    responses:
      200:
        description: 立即跟单配置
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
        config = db.get_immediate_copy_config(user_id)
        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logger.error(f"获取立即跟单配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/immediate-config', methods=['PUT'])
@login_required
def update_immediate_copy_config():
    """更新立即跟单配置
    ---
    tags:
      - Copy Trading - Config
    parameters:
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
      500:
        description: 服务器错误
    """
    try:
        user_id = g.current_user['user_id']
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 验证配置字段
        valid_fields = {
            # 跟单参数
            'copy_ratio': (float, 0.01, 10.0),
            'max_position_size_usd': (float, 1, 1000000),
            'min_position_size_usd': (float, 1, 100000),
            'max_leverage': (int, 1, 100),
            'default_leverage': (int, 1, 100),
            'slippage': (float, 0.0001, 0.1),
            'copy_leverage': (bool, None, None),
            # 跟单条件
            'min_trader_overall_score': (float, 0, 100),  # 最低评分 0-100，0表示不限制
            'min_trader_leverage': (float, 0, 100),  # 目标交易员最小杠杆，>=此值才跟单，0表示不限制
            'min_position_value_usd': (float, 0, 10000000),
            'max_position_value_usd': (float, 0, 10000000),
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

        success = db.save_immediate_copy_config(user_id, config)
        if success:
            return jsonify({
                'success': True,
                'data': config,
                'message': '立即跟单配置更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '保存配置失败'
            }), 500
    except Exception as e:
        logger.error(f"更新立即跟单配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 跟单配置规则 API（多配置支持） ====================

def _validate_config_rule_data(data: dict, config_type: str) -> tuple[dict, str]:
    """
    验证并处理配置规则数据
    
    Args:
        data: 请求数据
        config_type: 配置类型 ('default' 或 'immediate')
        
    Returns:
        (处理后的数据, 错误信息) - 错误信息为空表示验证通过
    """
    if not data.get('name'):
        return None, '规则名称不能为空'
    
    # 验证 config_data
    config_data = data.get('config_data', {})
    if not isinstance(config_data, dict):
        return None, 'config_data 必须是对象'
    
    # 根据配置类型验证
    if config_type == 'default':
        # 默认跟单配置：使用杠杆区间匹配
        leverage_min = float(data.get('leverage_min', 0))
        leverage_max = float(data.get('leverage_max', 100))
        
        if leverage_min < 0:
            leverage_min = 0
        if leverage_max < leverage_min:
            return None, '杠杆上限不能小于下限'
        
        valid_fields = {
            'copy_ratio': (float, 0.01, 10.0),
            'max_position_size_usd': (float, 1, 1000000),
            'min_position_size_usd': (float, 1, 100000),
            'max_leverage': (int, 1, 100),
            'default_leverage': (int, 1, 100),
            'slippage': (float, 0.0001, 0.1),
            'copy_leverage': (bool, None, None),
            'dry_run': (bool, None, None),
            # 自动补仓配置
            'auto_replenish': (bool, None, None),
            'replenish_ratio': (float, 0.01, 10.0),
            'replenish_min_value_usd': (float, 1, 100000),
            'replenish_max_value_usd': (float, 1, 1000000),
            # 止盈止损配置
            'take_profit_enabled': (bool, None, None),
            'take_profit_percent': (float, 1, 1000),
            'stop_loss_enabled': (bool, None, None),
            'stop_loss_percent': (float, 1, 1000),
        }

        validated_config = _validate_config_fields(config_data, valid_fields)

        # 处理数组字段
        if 'symbols_whitelist' in config_data:
            validated_config['symbols_whitelist'] = config_data['symbols_whitelist'] if isinstance(config_data['symbols_whitelist'], list) else []
        if 'symbols_blacklist' in config_data:
            validated_config['symbols_blacklist'] = config_data['symbols_blacklist'] if isinstance(config_data['symbols_blacklist'], list) else []
        
        result = {
            'name': data.get('name', '').strip(),
            'description': data.get('description', '').strip(),
            'leverage_min': leverage_min,
            'leverage_max': leverage_max,
            'config_data': validated_config,
            'priority': int(data.get('priority', 0)),
            'is_enabled': bool(data.get('is_enabled', True)),
            'is_default': bool(data.get('is_default', False)),
            'config_type': config_type,
        }
    else:
        # 立即跟单配置：按币种配置，每个币种最多一个配置
        symbol = data.get('symbol', '').strip().upper()
        if not symbol:
            return None, '币种不能为空'
        
        valid_fields = {
            'copy_ratio': (float, 0.01, 10.0),
            'max_position_size_usd': (float, 1, 1000000),
            'min_position_size_usd': (float, 1, 100000),
            'max_leverage': (int, 1, 100),
            'default_leverage': (int, 1, 100),
            'slippage': (float, 0.0001, 0.1),
            'copy_leverage': (bool, None, None),
            'copy_only_once': (bool, None, None),  # 只跟一次
            # 跟单条件
            'min_trader_overall_score': (float, 0, 100),
            'min_trader_leverage': (float, 0, 100),
            'max_trader_leverage': (float, 0, 100),  # 新增：目标最大杠杆
            'min_position_value_usd': (float, 0, 10000000),
            'max_position_value_usd': (float, 0, 10000000),
            'min_coin_price': (float, 0, 10000000),  # 新增：币种最低价格
            'max_coin_price': (float, 0, 10000000),  # 新增：币种最高价格
            # 自动补仓配置
            'auto_replenish': (bool, None, None),
            'replenish_ratio': (float, 0.01, 10.0),
            'replenish_min_value_usd': (float, 1, 100000),
            'replenish_max_value_usd': (float, 1, 1000000),
            # 止盈止损配置
            'take_profit_enabled': (bool, None, None),
            'take_profit_percent': (float, 1, 1000),
            'stop_loss_enabled': (bool, None, None),
            'stop_loss_percent': (float, 1, 1000),
        }

        validated_config = _validate_config_fields(config_data, valid_fields)

        result = {
            'name': data.get('name', '').strip(),
            'description': data.get('description', '').strip(),
            'symbol': symbol,
            'config_data': validated_config,
            'is_enabled': bool(data.get('is_enabled', True)),
            'config_type': config_type,
            # 立即跟单不再使用以下字段，但数据库需要
            'leverage_min': 0,
            'leverage_max': 100,
            'priority': 0,
            'is_default': False,
        }
    
    if data.get('id'):
        result['id'] = int(data['id'])
    
    return result, ''


def _validate_config_fields(config_data: dict, valid_fields: dict) -> dict:
    """验证并转换配置字段"""
    validated_config = {}
    for field, (field_type, min_val, max_val) in valid_fields.items():
        if field in config_data:
            value = config_data[field]
            try:
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
                validated_config[field] = value
            except (ValueError, TypeError):
                pass  # 跳过无效值
    return validated_config


@copy_trading_positions_bp.route('/api/copy-trading/default-config-rules', methods=['GET'])
@login_required
def get_default_config_rules():
    """获取所有默认跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: enabled_only
        in: query
        type: boolean
        default: false
        description: 是否只返回启用的规则
    responses:
      200:
        description: 配置规则列表
    """
    try:
        user_id = g.current_user['user_id']
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        rules = db.get_copy_config_rules(user_id, 'default', enabled_only=enabled_only)
        return jsonify({
            'success': True,
            'data': rules
        })
    except Exception as e:
        logger.error(f"获取默认配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/default-config-rules', methods=['POST'])
@login_required
def create_default_config_rule():
    """创建默认跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: 规则名称
            description:
              type: string
              description: 规则描述
            leverage_min:
              type: number
              description: 杠杆下限（不包含）
            leverage_max:
              type: number
              description: 杠杆上限（包含）
            config_data:
              type: object
              description: 配置数据
            priority:
              type: integer
              description: 优先级
            is_enabled:
              type: boolean
            is_default:
              type: boolean
    responses:
      200:
        description: 创建成功
      400:
        description: 请求参数错误
    """
    try:
        user_id = g.current_user['user_id']
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        validated_data, error = _validate_config_rule_data(data, 'default')
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        rule_id = db.save_copy_config_rule(user_id, validated_data)
        if rule_id:
            rule = db.get_copy_config_rule_by_id(user_id, rule_id)
            return jsonify({
                'success': True,
                'data': rule,
                'message': '配置规则创建成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '创建配置规则失败'
            }), 500
    except Exception as e:
        logger.error(f"创建默认配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/default-config-rules/<int:rule_id>', methods=['GET'])
@login_required
def get_default_config_rule(rule_id: int):
    """获取单个默认跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: rule_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 配置规则详情
      404:
        description: 规则不存在
    """
    try:
        user_id = g.current_user['user_id']
        rule = db.get_copy_config_rule_by_id(user_id, rule_id)
        if rule and rule.get('config_type') == 'default':
            return jsonify({
                'success': True,
                'data': rule
            })
        else:
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
    except Exception as e:
        logger.error(f"获取默认配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/default-config-rules/<int:rule_id>', methods=['PUT'])
@login_required
def update_default_config_rule(rule_id: int):
    """更新默认跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: rule_id
        in: path
        type: integer
        required: true
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
        description: 规则不存在
    """
    try:
        user_id = g.current_user['user_id']
        # 检查规则是否存在
        existing = db.get_copy_config_rule_by_id(user_id, rule_id)
        if not existing or existing.get('config_type') != 'default':
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        data['id'] = rule_id
        validated_data, error = _validate_config_rule_data(data, 'default')
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        result_id = db.save_copy_config_rule(user_id, validated_data)
        if result_id:
            rule = db.get_copy_config_rule_by_id(user_id, result_id)
            return jsonify({
                'success': True,
                'data': rule,
                'message': '配置规则更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '更新配置规则失败'
            }), 500
    except Exception as e:
        logger.error(f"更新默认配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/default-config-rules/<int:rule_id>', methods=['DELETE'])
@login_required
def delete_default_config_rule(rule_id: int):
    """删除默认跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: rule_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 删除成功
      404:
        description: 规则不存在
    """
    try:
        user_id = g.current_user['user_id']
        existing = db.get_copy_config_rule_by_id(user_id, rule_id)
        if not existing or existing.get('config_type') != 'default':
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
        
        success = db.delete_copy_config_rule(user_id, rule_id)
        if success:
            return jsonify({
                'success': True,
                'message': '配置规则删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '删除配置规则失败'
            }), 500
    except Exception as e:
        logger.error(f"删除默认配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 立即跟单配置规则 API ====================

@copy_trading_positions_bp.route('/api/copy-trading/immediate-config-rules', methods=['GET'])
@login_required
def get_immediate_config_rules():
    """获取所有立即跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: enabled_only
        in: query
        type: boolean
        default: false
        description: 是否只返回启用的规则
    responses:
      200:
        description: 配置规则列表
    """
    try:
        user_id = g.current_user['user_id']
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        rules = db.get_copy_config_rules(user_id, 'immediate', enabled_only=enabled_only)
        return jsonify({
            'success': True,
            'data': rules
        })
    except Exception as e:
        logger.error(f"获取立即跟单配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/immediate-config-rules', methods=['POST'])
@login_required
def create_immediate_config_rule():
    """创建立即跟单配置规则（按币种配置，每个币种最多一个配置）
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: 规则名称
            description:
              type: string
              description: 规则描述
            symbol:
              type: string
              description: 币种（每个币种最多一个配置）
            config_data:
              type: object
              description: 配置数据
            is_enabled:
              type: boolean
    responses:
      200:
        description: 创建成功
      400:
        description: 请求参数错误
    """
    try:
        user_id = g.current_user['user_id']
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        validated_data, error = _validate_config_rule_data(data, 'immediate')
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        # 检查币种唯一性
        symbol = validated_data.get('symbol')
        if symbol:
            existing = db.get_immediate_config_rule_by_symbol(user_id, symbol)
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'币种 {symbol} 已存在配置规则'
                }), 400
        
        rule_id = db.save_copy_config_rule(user_id, validated_data)
        if rule_id:
            rule = db.get_copy_config_rule_by_id(user_id, rule_id)
            return jsonify({
                'success': True,
                'data': rule,
                'message': '配置规则创建成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '创建配置规则失败'
            }), 500
    except Exception as e:
        logger.error(f"创建立即跟单配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/immediate-config-rules/<int:rule_id>', methods=['GET'])
@login_required
def get_immediate_config_rule(rule_id: int):
    """获取单个立即跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: rule_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 配置规则详情
      404:
        description: 规则不存在
    """
    try:
        user_id = g.current_user['user_id']
        rule = db.get_copy_config_rule_by_id(user_id, rule_id)
        if rule and rule.get('config_type') == 'immediate':
            return jsonify({
                'success': True,
                'data': rule
            })
        else:
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
    except Exception as e:
        logger.error(f"获取立即跟单配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/immediate-config-rules/<int:rule_id>', methods=['PUT'])
@login_required
def update_immediate_config_rule(rule_id: int):
    """更新立即跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: rule_id
        in: path
        type: integer
        required: true
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
        description: 规则不存在
    """
    try:
        user_id = g.current_user['user_id']
        # 检查规则是否存在
        existing = db.get_copy_config_rule_by_id(user_id, rule_id)
        if not existing or existing.get('config_type') != 'immediate':
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        data['id'] = rule_id
        validated_data, error = _validate_config_rule_data(data, 'immediate')
        if error:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        # 检查币种唯一性（如果币种变更了）
        new_symbol = validated_data.get('symbol')
        old_symbol = existing.get('symbol')
        if new_symbol and new_symbol != old_symbol:
            existing_by_symbol = db.get_immediate_config_rule_by_symbol(user_id, new_symbol)
            if existing_by_symbol:
                return jsonify({
                    'success': False,
                    'error': f'币种 {new_symbol} 已存在配置规则'
                }), 400
        
        result_id = db.save_copy_config_rule(user_id, validated_data)
        if result_id:
            rule = db.get_copy_config_rule_by_id(user_id, result_id)
            return jsonify({
                'success': True,
                'data': rule,
                'message': '配置规则更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '更新配置规则失败'
            }), 500
    except Exception as e:
        logger.error(f"更新立即跟单配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/immediate-config-rules/<int:rule_id>', methods=['DELETE'])
@login_required
def delete_immediate_config_rule(rule_id: int):
    """删除立即跟单配置规则
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: rule_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: 删除成功
      404:
        description: 规则不存在
    """
    try:
        user_id = g.current_user['user_id']
        existing = db.get_copy_config_rule_by_id(user_id, rule_id)
        if not existing or existing.get('config_type') != 'immediate':
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
        
        success = db.delete_copy_config_rule(user_id, rule_id)
        if success:
            return jsonify({
                'success': True,
                'message': '配置规则删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '删除配置规则失败'
            }), 500
    except Exception as e:
        logger.error(f"删除立即跟单配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@copy_trading_positions_bp.route('/api/copy-trading/config-rules/match', methods=['GET'])
@login_required
def match_config_rule():
    """根据杠杆匹配配置规则（用于测试/预览）
    ---
    tags:
      - Copy Trading - Config Rules
    parameters:
      - name: config_type
        in: query
        type: string
        required: true
        description: 配置类型 ('default' 或 'immediate')
      - name: leverage
        in: query
        type: number
        required: true
        description: 杠杆倍数
    responses:
      200:
        description: 匹配结果
    """
    try:
        user_id = g.current_user['user_id']
        config_type = request.args.get('config_type', 'immediate')
        leverage = float(request.args.get('leverage', 1))
        
        if config_type not in ('default', 'immediate'):
            return jsonify({
                'success': False,
                'error': 'config_type 必须是 default 或 immediate'
            }), 400
        
        rule = db.match_copy_config_rule(user_id, config_type, leverage)
        config = db.get_copy_config_by_leverage(user_id, config_type, leverage)
        
        return jsonify({
            'success': True,
            'data': {
                'matched_rule': rule,
                'effective_config': config
            }
        })
    except Exception as e:
        logger.error(f"匹配配置规则失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
