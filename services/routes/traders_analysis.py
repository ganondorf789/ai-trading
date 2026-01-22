"""
交易者分析相关路由
包括：收藏、AI分析、历史图表、评级筛选
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

from services.ai_analysis import generate_trader_analysis
from .db import db

logger = logging.getLogger(__name__)

traders_analysis_bp = Blueprint('traders_analysis', __name__)


# ==================== 收藏功能 ====================

@traders_analysis_bp.route('/api/traders/<address>/star', methods=['POST'])
def toggle_trader_star(address: str):
    """
    切换交易者的收藏状态
    Request Body:
        - is_starred: bool, 是否收藏
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
    """
    使用AI分析交易者表现并保存到数据库
    Query Parameters:
        - provider: str, AI提供商 (zhipu/qwen/deepseek/openrouter)，可选
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
    """
    获取交易者的AI分析结果
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
    """
    获取交易者的历史分析记录（用于生成历史图表）
    Query Parameters:
        - days: int, 时间范围（天数），默认30，0表示全部
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
        now = datetime.now()
        if days > 0:
            start_time = now - timedelta(days=days)
            # 过滤时间范围内的交易
            fills = [f for f in fills if datetime.fromtimestamp(f['time'] / 1000) >= start_time]

        if not fills:
            return jsonify({
                'success': True,
                'data': {
                    'roi': [],
                    'pnl': [],
                    'equity': []
                }
            })

        # 计算累积数据
        initial_equity = trader.get('current_equity', 0) - trader.get('total_pnl', 0)
        if initial_equity <= 0:
            initial_equity = 10000

        cumulative_pnl = 0
        current_equity = initial_equity

        chart_data = {
            'roi': [],
            'pnl': [],
            'equity': []
        }

        # 添加起始点
        first_time = datetime.fromtimestamp(fills[0]['time'] / 1000)
        chart_data['roi'].append({
            'timestamp': first_time.isoformat(),
            'value': 0
        })
        chart_data['pnl'].append({
            'timestamp': first_time.isoformat(),
            'value': 0
        })
        chart_data['equity'].append({
            'timestamp': first_time.isoformat(),
            'value': initial_equity
        })

        # 按天聚合数据（避免数据点过多）
        daily_data = {}
        for fill in fills:
            trade_time = datetime.fromtimestamp(fill['time'] / 1000)
            day_key = trade_time.strftime('%Y-%m-%d')

            if day_key not in daily_data:
                daily_data[day_key] = {
                    'timestamp': trade_time,
                    'pnl': 0,
                    'fees': 0
                }

            daily_data[day_key]['pnl'] += fill.get('closed_pnl', 0)
            daily_data[day_key]['fees'] += fill.get('fee', 0)

        # 生成每日累积数据
        for day_key in sorted(daily_data.keys()):
            day_info = daily_data[day_key]
            cumulative_pnl += day_info['pnl']
            current_equity = initial_equity + cumulative_pnl

            # 计算ROI
            roi = (cumulative_pnl / initial_equity) if initial_equity > 0 else 0

            chart_data['roi'].append({
                'timestamp': day_info['timestamp'].isoformat(),
                'value': roi
            })
            chart_data['pnl'].append({
                'timestamp': day_info['timestamp'].isoformat(),
                'value': cumulative_pnl
            })
            chart_data['equity'].append({
                'timestamp': day_info['timestamp'].isoformat(),
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
    """
    根据评级获取交易者（支持分页）
    Path Parameters:
        - rating: str, 评级 (S/A/B/C/D/F)
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - search: str, 地址搜索
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
    """
    获取交易员的仓位分析详情（综合统计）
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
