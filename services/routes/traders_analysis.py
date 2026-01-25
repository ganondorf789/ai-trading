"""
交易者分析相关路由
包括：收藏、AI分析、历史图表、评级筛选
"""
from flask import Blueprint, jsonify, request
import logging

from services.ai_analysis import generate_trader_analysis
from screener.utils import now_shanghai, timestamp_to_pendulum
from .db import db

logger = logging.getLogger(__name__)

traders_analysis_bp = Blueprint('traders_analysis', __name__)


# ==================== 收藏功能 ====================

@traders_analysis_bp.route('/api/traders/<address>/star', methods=['POST'])
def toggle_trader_star(address: str):
    """切换交易者收藏状态
    ---
    tags:
      - Traders - Analysis
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            is_starred:
              type: boolean
              description: 是否收藏
              example: true
    responses:
      200:
        description: 操作成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      404:
        description: 交易者不存在
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json() or {}
        is_starred = data.get('is_starred', True)

        logger.info(f"切换收藏状态: {address}, is_starred={is_starred}")

        # 检查交易者是否存在
        trader = db.get_trader_by_address(address)
        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 切换收藏状态
        success = db.toggle_star(address, is_starred)

        if success:
            return jsonify({
                'success': True,
                'data': {'is_starred': is_starred},
                'message': '已收藏' if is_starred else '已取消收藏'
            })
        else:
            return jsonify({
                'success': False,
                'error': '更新失败'
            }), 500

    except Exception as e:
        logger.error(f"切换收藏状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== AI 分析 ====================

@traders_analysis_bp.route('/api/traders/<address>/ai-analysis', methods=['POST'])
def ai_analyze_trader(address: str):
    """AI分析交易者
    ---
    tags:
      - Traders - Analysis
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: provider
        in: query
        type: string
        enum: [zhipu, qwen, deepseek, openrouter]
        description: AI提供商
    responses:
      200:
        description: 分析成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      404:
        description: 交易者不存在
      500:
        description: 服务器错误
    """
    try:
        provider = request.args.get('provider')

        logger.info(f"开始AI分析交易者: {address}, 提供商: {provider or '默认'}")

        # 获取交易者数据
        trader = db.get_trader_by_address(address)

        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 获取币种统计数据
        fills_summary = db.get_fills_summary(address, exclude_user_perps=True)
        coin_stats = fills_summary.get('by_coin', []) if fills_summary else []

        # 获取当前持仓数据
        positions = db.get_positions(address)

        # 生成AI分析（传入币种统计和持仓数据）
        analysis = generate_trader_analysis(
            trader,
            provider=provider,
            coin_stats=coin_stats,
            positions=positions
        )

        # 保存AI分析结果到数据库
        db.save_trader_ai_analysis(address, analysis)

        logger.info(f"AI分析完成并已保存: {address}")

        return jsonify({
            'success': True,
            'data': analysis,
            'message': 'AI分析完成并已保存'
        })

    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_analysis_bp.route('/api/traders/<address>/ai-analysis', methods=['GET'])
def get_trader_ai_analysis(address: str):
    """获取交易者AI分析结果
    ---
    tags:
      - Traders - Analysis
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
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
      404:
        description: AI分析不存在
      500:
        description: 服务器错误
    """
    try:
        analysis = db.get_trader_ai_analysis(address)

        if not analysis:
            return jsonify({
                'success': False,
                'error': 'AI分析不存在，请先进行分析'
            }), 404

        return jsonify({
            'success': True,
            'data': analysis
        })

    except Exception as e:
        logger.error(f"获取AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 历史图表数据 ====================

@traders_analysis_bp.route('/api/traders/<address>/history', methods=['GET'])
def get_trader_history(address: str):
    """获取交易者历史图表数据
    ---
    tags:
      - Traders - Analysis
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: days
        in: query
        type: integer
        default: 30
        description: 时间范围（天数），0表示全部
    responses:
      200:
        description: 历史图表数据
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                roi:
                  type: array
                  items:
                    type: object
                pnl:
                  type: array
                  items:
                    type: object
                equity:
                  type: array
                  items:
                    type: object
      404:
        description: 交易者不存在
      500:
        description: 服务器错误
    """
    try:
        days = int(request.args.get('days', 30))

        # 获取交易者当前信息
        trader = db.get_trader_by_address(address)
        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 获取所有交易记录
        fills = db.get_trader_fills(address, limit=10000)

        if not fills:
            return jsonify({
                'success': True,
                'data': {
                    'roi': [],
                    'pnl': [],
                    'equity': []
                }
            })

        # 按时间排序（从旧到新）
        fills.sort(key=lambda x: x['time'])

        # 计算时间范围
        now = now_shanghai()
        if days > 0:
            start_time = now.subtract(days=days)
            # 过滤时间范围内的交易
            fills = [f for f in fills if timestamp_to_pendulum(f['time']) >= start_time]

        if not fills:
            return jsonify({
                'success': True,
                'data': {
                    'roi': [],
                    'pnl': [],
                    'equity': []
                }
            })

        # 计算累积数据（显式转换为 float，避免 Decimal 类型问题）
        current_equity_val = float(trader.get('current_equity', 0) or 0)
        total_pnl_val = float(trader.get('total_pnl', 0) or 0)
        initial_equity = current_equity_val - total_pnl_val
        if initial_equity <= 0:
            initial_equity = 10000.0

        cumulative_pnl = 0.0
        current_equity = initial_equity

        chart_data = {
            'roi': [],
            'pnl': [],
            'equity': []
        }

        # 添加起始点
        first_time = timestamp_to_pendulum(fills[0]['time'])
        chart_data['roi'].append({
            'timestamp': first_time.to_iso8601_string(),
            'value': 0
        })
        chart_data['pnl'].append({
            'timestamp': first_time.to_iso8601_string(),
            'value': 0
        })
        chart_data['equity'].append({
            'timestamp': first_time.to_iso8601_string(),
            'value': initial_equity
        })

        # 按天聚合数据（避免数据点过多）
        daily_data = {}
        for fill in fills:
            trade_time = timestamp_to_pendulum(fill['time'])
            day_key = trade_time.format('YYYY-MM-DD')

            if day_key not in daily_data:
                daily_data[day_key] = {
                    'timestamp': trade_time,
                    'pnl': 0.0,
                    'fees': 0.0
                }

            # 显式转换为 float，避免 Decimal 类型问题
            daily_data[day_key]['pnl'] += float(fill.get('closed_pnl', 0) or 0)
            daily_data[day_key]['fees'] += float(fill.get('fee', 0) or 0)

        # 生成每日累积数据
        for day_key in sorted(daily_data.keys()):
            day_info = daily_data[day_key]
            cumulative_pnl += day_info['pnl']
            current_equity = initial_equity + cumulative_pnl

            # 计算ROI
            roi = (cumulative_pnl / initial_equity) if initial_equity > 0 else 0

            chart_data['roi'].append({
                'timestamp': day_info['timestamp'].to_iso8601_string(),
                'value': roi
            })
            chart_data['pnl'].append({
                'timestamp': day_info['timestamp'].to_iso8601_string(),
                'value': cumulative_pnl
            })
            chart_data['equity'].append({
                'timestamp': day_info['timestamp'].to_iso8601_string(),
                'value': current_equity
            })

        return jsonify({
            'success': True,
            'data': chart_data
        })

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 按评级筛选 ====================

@traders_analysis_bp.route('/api/traders/rating/<rating>', methods=['GET'])
def get_traders_by_rating(rating: str):
    """按评级获取交易者
    ---
    tags:
      - Traders - Analysis
    parameters:
      - name: rating
        in: path
        type: string
        required: true
        enum: [S, A, B, C, D, F]
        description: 评级
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
      - name: search
        in: query
        type: string
        description: 地址搜索
    responses:
      200:
        description: 交易者列表
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
      400:
        description: 无效的评级
      500:
        description: 服务器错误
    """
    try:
        if rating not in ['S', 'A', 'B', 'C', 'D', 'F']:
            return jsonify({
                'success': False,
                'error': 'Invalid rating. Must be S/A/B/C/D/F'
            }), 400

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '').strip()

        # 获取所有符合评级的交易者
        all_traders = db.get_traders_by_rating(rating)

        # 应用搜索过滤
        if search:
            all_traders = [t for t in all_traders if search.lower() in t['address'].lower()]

        total_count = len(all_traders)
        total_pages = (total_count + limit - 1) // limit

        # 分页
        start = (page - 1) * limit
        end = start + limit
        traders = all_traders[start:end]

        return jsonify({
            'success': True,
            'data': traders,
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
        logger.error(f"获取交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 仓位分析 ====================

@traders_analysis_bp.route('/api/traders/<address>/position-analysis', methods=['GET'])
def get_trader_position_analysis(address: str):
    """获取交易员仓位分析详情
    ---
    tags:
      - Traders - Analysis
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 仓位分析详情
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                trader:
                  type: object
                position_analysis:
                  type: object
      404:
        description: 交易者不存在
      500:
        description: 服务器错误
    """
    try:
        # 获取基础信息
        trader = db.get_trader_by_address(address)
        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404
        
        # 获取仓位分析
        analysis = db.get_position_analysis_for_trader(address)
        
        return jsonify({
            'success': True,
            'data': {
                'trader': {
                    'address': trader.get('address'),
                    'rating': trader.get('rating'),
                    'overall_score': trader.get('overall_score'),
                    'total_pnl': trader.get('total_pnl'),
                    'win_rate': trader.get('win_rate'),
                    'profit_factor': trader.get('profit_factor'),
                    'sharpe_ratio': trader.get('sharpe_ratio'),
                    'max_drawdown': trader.get('max_drawdown'),
                },
                'position_analysis': analysis
            }
        })
        
    except Exception as e:
        logger.error(f"获取仓位分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
