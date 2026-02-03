"""
交易者统计和币种相关路由
包括：统计信息、币种列表、S级优选筛选
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required

logger = logging.getLogger(__name__)

traders_stats_bp = Blueprint('traders_stats', __name__)


# ==================== 统计信息 ====================

@traders_stats_bp.route('/api/stats', methods=['GET'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
