"""
跟单交易员持仓和配置管理相关路由
包括：交易员持仓、风控配置、默认配置、立即跟单配置、AI分析
"""
from flask import Blueprint, jsonify, request
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


# ==================== 风控配置 API ====================

@copy_trading_positions_bp.route('/api/copy-trading/risk-control', methods=['GET'])
@login_required
def get_risk_control_config():
    """获取风控配置
    ---
    tags:
      - Copy Trading - Config
    responses:
      200:
        description: 风控配置
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


@copy_trading_positions_bp.route('/api/copy-trading/risk-control', methods=['PUT'])
@login_required
def update_risk_control_config():
    """更新风控配置
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
        if 'sync_position_symbols' in data:
            config['sync_position_symbols'] = data['sync_position_symbols'] if isinstance(data['sync_position_symbols'], list) else []

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
        config = db.get_immediate_copy_config()
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

        success = db.save_immediate_copy_config(config)
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
            'sync_position': (bool, None, None),
            'dry_run': (bool, None, None),
            # 自动补仓配置
            'auto_replenish': (bool, None, None),
            'replenish_ratio': (float, 0.01, 10.0),
            'replenish_min_value_usd': (float, 1, 100000),
            'replenish_max_value_usd': (float, 1, 1000000),
        }
        
        validated_config = _validate_config_fields(config_data, valid_fields)
        
        # 处理数组字段
        if 'symbols_whitelist' in config_data:
            validated_config['symbols_whitelist'] = config_data['symbols_whitelist'] if isinstance(config_data['symbols_whitelist'], list) else []
        if 'symbols_blacklist' in config_data:
            validated_config['symbols_blacklist'] = config_data['symbols_blacklist'] if isinstance(config_data['symbols_blacklist'], list) else []
        if 'sync_position_symbols' in config_data:
            validated_config['sync_position_symbols'] = config_data['sync_position_symbols'] if isinstance(config_data['sync_position_symbols'], list) else []
        
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
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        rules = db.get_copy_config_rules('default', enabled_only=enabled_only)
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
        
        rule_id = db.save_copy_config_rule(validated_data)
        if rule_id:
            rule = db.get_copy_config_rule_by_id(rule_id)
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
        rule = db.get_copy_config_rule_by_id(rule_id)
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
        # 检查规则是否存在
        existing = db.get_copy_config_rule_by_id(rule_id)
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
        
        result_id = db.save_copy_config_rule(validated_data)
        if result_id:
            rule = db.get_copy_config_rule_by_id(result_id)
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
        existing = db.get_copy_config_rule_by_id(rule_id)
        if not existing or existing.get('config_type') != 'default':
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
        
        success = db.delete_copy_config_rule(rule_id)
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
        enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
        rules = db.get_copy_config_rules('immediate', enabled_only=enabled_only)
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
            existing = db.get_immediate_config_rule_by_symbol(symbol)
            if existing:
                return jsonify({
                    'success': False,
                    'error': f'币种 {symbol} 已存在配置规则'
                }), 400
        
        rule_id = db.save_copy_config_rule(validated_data)
        if rule_id:
            rule = db.get_copy_config_rule_by_id(rule_id)
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
        rule = db.get_copy_config_rule_by_id(rule_id)
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
        # 检查规则是否存在
        existing = db.get_copy_config_rule_by_id(rule_id)
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
            existing_by_symbol = db.get_immediate_config_rule_by_symbol(new_symbol)
            if existing_by_symbol:
                return jsonify({
                    'success': False,
                    'error': f'币种 {new_symbol} 已存在配置规则'
                }), 400
        
        result_id = db.save_copy_config_rule(validated_data)
        if result_id:
            rule = db.get_copy_config_rule_by_id(result_id)
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
        existing = db.get_copy_config_rule_by_id(rule_id)
        if not existing or existing.get('config_type') != 'immediate':
            return jsonify({
                'success': False,
                'error': '配置规则不存在'
            }), 404
        
        success = db.delete_copy_config_rule(rule_id)
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
        config_type = request.args.get('config_type', 'immediate')
        leverage = float(request.args.get('leverage', 1))
        
        if config_type not in ('default', 'immediate'):
            return jsonify({
                'success': False,
                'error': 'config_type 必须是 default 或 immediate'
            }), 400
        
        rule = db.match_copy_config_rule(config_type, leverage)
        config = db.get_copy_config_by_leverage(config_type, leverage)
        
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


# ==================== 持仓 AI 分析 API ====================

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


@copy_trading_positions_bp.route('/api/copy-trading/trader-positions/ai-analysis', methods=['POST'])
@login_required
def ai_analyze_all_positions():
    """AI分析所有持仓
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            positions:
              type: array
              description: 持仓数据列表
            provider:
              type: string
              enum: [zhipu, qwen, deepseek, openrouter]
            force_refresh:
              type: boolean
              default: false
    responses:
      200:
        description: AI分析结果
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            cached:
              type: boolean
      400:
        description: 没有找到持仓数据
      500:
        description: 服务器错误
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


@copy_trading_positions_bp.route('/api/copy-trading/trader-positions/ai-analysis/coin', methods=['POST'])
@login_required
def ai_analyze_coin_positions():
    """AI分析单个币种持仓
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - coin
          properties:
            coin:
              type: string
              description: 币种名称
            provider:
              type: string
              enum: [zhipu, qwen, deepseek, openrouter]
            force_refresh:
              type: boolean
              default: false
    responses:
      200:
        description: AI分析结果
      400:
        description: 参数错误
      500:
        description: 服务器错误
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


@copy_trading_positions_bp.route('/api/copy-trading/trader-positions/ai-analysis/single', methods=['POST'])
@login_required
def ai_analyze_single_position():
    """AI分析单个仓位
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - position
          properties:
            position:
              type: object
              description: 仓位数据
            provider:
              type: string
              enum: [zhipu, qwen, deepseek, openrouter]
            force_refresh:
              type: boolean
              default: false
    responses:
      200:
        description: AI分析结果
      400:
        description: 参数错误
      500:
        description: 服务器错误
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


@copy_trading_positions_bp.route('/api/copy-trading/trader-positions/ai-analysis/check', methods=['POST'])
@login_required
def check_positions_ai_analysis():
    """检查是否已有持仓AI分析结果
    ---
    tags:
      - Copy Trading - Positions
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - positions
          properties:
            analysis_type:
              type: string
              enum: [overall, coin, single]
              default: overall
            positions:
              type: array
              items:
                type: object
            coin:
              type: string
            address:
              type: string
    responses:
      200:
        description: 检查结果
        schema:
          type: object
          properties:
            success:
              type: boolean
            exists:
              type: boolean
            data:
              type: object
      400:
        description: 参数错误
      500:
        description: 服务器错误
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
