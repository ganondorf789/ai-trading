"""
交易者统计和币种相关路由
包括：统计信息、币种列表、S级优选筛选
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db

logger = logging.getLogger(__name__)

traders_stats_bp = Blueprint('traders_stats', __name__)


# ==================== 统计信息 ====================

@traders_stats_bp.route('/api/stats', methods=['GET'])
def get_statistics():
    """获取数据库统计信息
    ---
    tags:
      - Traders - Stats
    responses:
      200:
        description: 统计信息
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
        stats = db.get_statistics()

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 币种列表 ====================

@traders_stats_bp.route('/api/coins', methods=['GET'])
def get_coins():
    """获取所有币种列表
    ---
    tags:
      - Traders - Stats
    parameters:
      - name: address
        in: query
        type: string
        description: 筛选特定交易者的币种
      - name: exclude_user_perps
        in: query
        type: boolean
        default: true
        description: 是否排除用户创建的永续合约
      - name: include_stats
        in: query
        type: boolean
        default: false
        description: 是否包含统计信息
    responses:
      200:
        description: 币种列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: string
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        address = request.args.get('address')
        exclude_user_perps = request.args.get('exclude_user_perps', 'true').lower() == 'true'
        include_stats = request.args.get('include_stats', 'false').lower() == 'true'

        coins_data = db.get_all_coins(
            exclude_user_perps=exclude_user_perps,
            address=address
        )

        if include_stats:
            # 返回完整的统计信息
            return jsonify({
                'success': True,
                'data': coins_data,
                'count': len(coins_data)
            })
        else:
            # 只返回币种名称列表
            coins = [c['coin'] for c in coins_data]
            return jsonify({
                'success': True,
                'data': coins,
                'count': len(coins)
            })

    except Exception as e:
        logger.error(f"获取币种列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_stats_bp.route('/api/hyperliquid/coins', methods=['GET'])
def get_hyperliquid_coins():
    """获取Hyperliquid可交易币种列表
    ---
    tags:
      - Traders - Stats
    parameters:
      - name: active_only
        in: query
        type: boolean
        default: true
        description: 是否只返回活跃币种
    responses:
      200:
        description: 币种列表
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
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        coins = db.get_hyperliquid_coins(active_only=active_only)

        return jsonify({
            'success': True,
            'data': coins,
            'count': len(coins)
        })

    except Exception as e:
        logger.error(f"获取 Hyperliquid 币种列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_stats_bp.route('/api/hyperliquid/coins/sync', methods=['POST'])
def sync_hyperliquid_coins():
    """同步Hyperliquid币种列表
    ---
    tags:
      - Traders - Stats
    responses:
      200:
        description: 同步成功
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
            message:
              type: string
      500:
        description: 服务器错误
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants

        logger.info("开始同步 Hyperliquid 币种列表...")

        # 获取市场元数据
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        meta = info.meta()

        if not meta or 'universe' not in meta:
            return jsonify({
                'success': False,
                'error': '无法获取 Hyperliquid 市场数据'
            }), 500

        # 解析币种数据
        coins = meta.get('universe', [])
        logger.info(f"获取到 {len(coins)} 个币种")

        # 保存到数据库
        saved_count = db.save_hyperliquid_coins(coins)

        logger.info(f"同步完成: 保存了 {saved_count} 个币种")

        # 返回保存后的列表
        coins_list = db.get_hyperliquid_coins(active_only=True)

        return jsonify({
            'success': True,
            'data': coins_list,
            'count': len(coins_list),
            'message': f'成功同步 {saved_count} 个币种'
        })

    except Exception as e:
        logger.error(f"同步 Hyperliquid 币种失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_stats_bp.route('/api/hyperliquid/coins/names', methods=['GET'])
def get_hyperliquid_coin_names():
    """获取Hyperliquid币种名称列表
    ---
    tags:
      - Traders - Stats
    responses:
      200:
        description: 币种名称列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: string
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        names = db.get_hyperliquid_coin_names()

        return jsonify({
            'success': True,
            'data': names,
            'count': len(names)
        })

    except Exception as e:
        logger.error(f"获取 Hyperliquid 币种名称列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== S级优选筛选 API ====================

# 预设配置
BEST_S_PRESETS = {
    'default': {
        'name': '默认（综合）',
        'description': '平衡各项指标的综合筛选',
        'params': {
            'min_sharpe': 0.5,
            'max_drawdown': 0.3,
            'min_profit_factor': 1.2,
            'min_closed_positions': 20,
            'min_position_win_rate': 0.45,
            'min_position_profit_factor': 1.0,
            'recent_days': 30,
            'min_recent_positions': 3,
            'require_recent_profit': True,
            'max_days_since_last_trade': 7,
            'sort_by': 'recent_pnl',
        }
    },
    'safe': {
        'name': '稳健型',
        'description': '低风险、高胜率、稳定盈利',
        'params': {
            'min_sharpe': 1.0,
            'max_drawdown': 0.2,
            'min_profit_factor': 1.5,
            'min_closed_positions': 30,
            'min_position_win_rate': 0.55,
            'min_position_profit_factor': 1.3,
            'recent_days': 30,
            'min_recent_positions': 5,
            'require_recent_profit': True,
            'max_days_since_last_trade': 5,
            'sort_by': 'sharpe_ratio',
        }
    },
    'aggressive': {
        'name': '激进型',
        'description': '高收益优先，容忍较高风险',
        'params': {
            'min_sharpe': 0.3,
            'max_drawdown': 0.4,
            'min_profit_factor': 1.0,
            'min_closed_positions': 15,
            'min_position_win_rate': 0.40,
            'min_position_profit_factor': 0.8,
            'recent_days': 14,
            'min_recent_positions': 2,
            'require_recent_profit': True,
            'max_days_since_last_trade': 7,
            'sort_by': 'recent_pnl',
        }
    },
    'scalper': {
        'name': '短线型',
        'description': '短线交易风格，平均持仓 < 24 小时',
        'params': {
            'min_sharpe': 0.5,
            'max_drawdown': 0.3,
            'min_profit_factor': 1.2,
            'min_closed_positions': 30,
            'min_position_win_rate': 0.50,
            'min_position_profit_factor': 1.0,
            'recent_days': 14,
            'min_recent_positions': 5,
            'require_recent_profit': True,
            'max_days_since_last_trade': 3,
            'max_holding_hours': 24,
            'sort_by': 'position_win_rate',
        }
    },
    'swing': {
        'name': '波段型',
        'description': '中线波段交易，持仓 1-7 天',
        'params': {
            'min_sharpe': 0.8,
            'max_drawdown': 0.25,
            'min_profit_factor': 1.3,
            'min_closed_positions': 20,
            'min_position_win_rate': 0.50,
            'min_position_profit_factor': 1.2,
            'recent_days': 30,
            'min_recent_positions': 3,
            'require_recent_profit': True,
            'max_days_since_last_trade': 10,
            'min_holding_hours': 24,
            'max_holding_hours': 168,
            'sort_by': 'position_profit_factor',
        }
    },
    'hot': {
        'name': '热门（近期表现）',
        'description': '重点关注近 7 天表现最好的交易员',
        'params': {
            'min_sharpe': 0.3,
            'max_drawdown': 0.35,
            'min_profit_factor': 1.0,
            'min_closed_positions': 10,
            'min_position_win_rate': 0.40,
            'min_position_profit_factor': 0.8,
            'recent_days': 7,
            'min_recent_positions': 2,
            'require_recent_profit': True,
            'max_days_since_last_trade': 3,
            'sort_by': 'recent_pnl',
        }
    },
}


@traders_stats_bp.route('/api/traders/best-s', methods=['GET'])
def get_best_s_traders():
    """获取S级优选交易员
    ---
    tags:
      - Traders - Stats
    parameters:
      - name: preset
        in: query
        type: string
        enum: [default, safe, aggressive, scalper, swing, hot]
        default: default
        description: 预设配置
      - name: min_sharpe
        in: query
        type: number
        description: 最小夏普比率
      - name: max_drawdown
        in: query
        type: number
        description: 最大回撤
      - name: min_profit_factor
        in: query
        type: number
        description: 最小盈亏比
      - name: min_positions
        in: query
        type: integer
        description: 最小已平仓位数
      - name: min_position_win_rate
        in: query
        type: number
        description: 最小仓位胜率 (0-1)
      - name: min_position_pf
        in: query
        type: number
        description: 最小仓位盈亏比
      - name: recent_days
        in: query
        type: integer
        description: 近期天数
      - name: min_recent_positions
        in: query
        type: integer
        description: 近期最小仓位数
      - name: require_recent_profit
        in: query
        type: boolean
        description: 是否要求近期盈利
      - name: max_inactive_days
        in: query
        type: integer
        description: 最大不活跃天数
      - name: min_holding_hours
        in: query
        type: number
        description: 最小平均持仓时长
      - name: max_holding_hours
        in: query
        type: number
        description: 最大平均持仓时长
      - name: sort_by
        in: query
        type: string
        description: 排序字段
      - name: limit
        in: query
        type: integer
        default: 20
        description: 返回数量
    responses:
      200:
        description: S级优选交易员列表
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
            preset:
              type: object
            params:
              type: object
      500:
        description: 服务器错误
    """
    try:
        # 获取预设配置
        preset_name = request.args.get('preset', 'default')
        preset = BEST_S_PRESETS.get(preset_name, BEST_S_PRESETS['default'])
        params = preset['params'].copy()
        
        # 覆盖用户指定的参数
        if request.args.get('min_sharpe') is not None:
            params['min_sharpe'] = float(request.args.get('min_sharpe'))
        if request.args.get('max_drawdown') is not None:
            params['max_drawdown'] = float(request.args.get('max_drawdown'))
        if request.args.get('min_profit_factor') is not None:
            params['min_profit_factor'] = float(request.args.get('min_profit_factor'))
        if request.args.get('min_positions') is not None:
            params['min_closed_positions'] = int(request.args.get('min_positions'))
        if request.args.get('min_position_win_rate') is not None:
            params['min_position_win_rate'] = float(request.args.get('min_position_win_rate'))
        if request.args.get('min_position_pf') is not None:
            params['min_position_profit_factor'] = float(request.args.get('min_position_pf'))
        if request.args.get('recent_days') is not None:
            params['recent_days'] = int(request.args.get('recent_days'))
        if request.args.get('min_recent_positions') is not None:
            params['min_recent_positions'] = int(request.args.get('min_recent_positions'))
        if request.args.get('require_recent_profit') is not None:
            params['require_recent_profit'] = request.args.get('require_recent_profit', 'true').lower() == 'true'
        if request.args.get('max_inactive_days') is not None:
            params['max_days_since_last_trade'] = int(request.args.get('max_inactive_days'))
        if request.args.get('min_holding_hours') is not None:
            params['min_holding_hours'] = float(request.args.get('min_holding_hours'))
        if request.args.get('max_holding_hours') is not None:
            params['max_holding_hours'] = float(request.args.get('max_holding_hours'))
        if request.args.get('sort_by') is not None:
            params['sort_by'] = request.args.get('sort_by')
        if request.args.get('limit') is not None:
            params['limit'] = int(request.args.get('limit'))
        else:
            params['limit'] = 20
        
        logger.info(f"S级优选筛选: preset={preset_name}, params={params}")
        
        # 执行筛选
        traders = db.get_best_s_traders(**params)
        
        return jsonify({
            'success': True,
            'data': traders,
            'count': len(traders),
            'preset': {
                'name': preset['name'],
                'description': preset['description'],
                'key': preset_name
            },
            'params': params
        })
        
    except Exception as e:
        logger.error(f"S级优选筛选失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_stats_bp.route('/api/traders/best-s/presets', methods=['GET'])
def get_best_s_presets():
    """获取S级优选筛选预设配置
    ---
    tags:
      - Traders - Stats
    responses:
      200:
        description: 预设配置列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  key:
                    type: string
                  name:
                    type: string
                  description:
                    type: string
                  params:
                    type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        presets = []
        for key, preset in BEST_S_PRESETS.items():
            presets.append({
                'key': key,
                'name': preset['name'],
                'description': preset['description'],
                'params': preset['params']
            })
        
        return jsonify({
            'success': True,
            'data': presets,
            'count': len(presets)
        })
        
    except Exception as e:
        logger.error(f"获取预设配置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
