"""
Flask API Server for Trader Analytics
提供交易者数据查询和分析接口
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
from typing import Optional
import logging

from screener.database import TraderDatabase

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 初始化数据库
db = TraderDatabase()


@app.route('/api/traders', methods=['GET'])
def get_traders():
    """
    获取交易者列表
    Query Parameters:
        - limit: int, 返回数量，默认50
        - min_rating: str, 最低评级 (S/A/B/C/D/F)
        - offset: int, 分页偏移量，默认0
    """
    try:
        limit = int(request.args.get('limit', 50))
        min_rating = request.args.get('min_rating')
        offset = int(request.args.get('offset', 0))

        # 获取交易者列表
        traders = db.get_top_traders(limit=limit + offset, min_rating=min_rating)

        # 应用分页
        traders = traders[offset:offset + limit]

        # 格式化数据
        result = []
        for trader in traders:
            result.append({
                'id': trader['id'],
                'address': trader['address'],
                'analyzed_at': trader['analyzed_at'],
                'total_trades': trader['total_trades'],
                'win_rate': trader['win_rate'],
                'total_pnl': trader['total_pnl'],
                'roi': trader['roi'],
                'profit_factor': trader['profit_factor'],
                'max_drawdown': trader['max_drawdown'],
                'sharpe_ratio': trader['sharpe_ratio'],
                'overall_score': trader['overall_score'],
                'rating': trader['rating'],
                'current_equity': trader['current_equity'],
                'active_days': trader['active_days'],
                'last_trade_time': trader['last_trade_time']
            })

        return jsonify({
            'success': True,
            'data': result,
            'count': len(result)
        })

    except Exception as e:
        logger.error(f"获取交易者列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>', methods=['GET'])
def get_trader_detail(address: str):
    """
    获取交易者详细信息
    """
    try:
        # 获取交易者基本信息
        trader = db.get_trader_by_address(address)

        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 获取交易记录汇总
        fills_summary = db.get_fills_summary(address)

        return jsonify({
            'success': True,
            'data': {
                'trader': trader,
                'fills_summary': fills_summary
            }
        })

    except Exception as e:
        logger.error(f"获取交易者详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/fills', methods=['GET'])
def get_trader_fills(address: str):
    """
    获取交易者的历史交易记录
    Query Parameters:
        - limit: int, 返回数量，默认100
        - coin: str, 筛选特定币种
    """
    try:
        limit = int(request.args.get('limit', 100))
        coin = request.args.get('coin')

        fills = db.get_trader_fills(address, limit=limit, coin=coin)

        return jsonify({
            'success': True,
            'data': fills,
            'count': len(fills)
        })

    except Exception as e:
        logger.error(f"获取交易记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/history', methods=['GET'])
def get_trader_history(address: str):
    """
    获取交易者的历史分析记录（用于生成历史图表）
    Query Parameters:
        - limit: int, 返回数量，默认30
    """
    try:
        limit = int(request.args.get('limit', 30))

        history = db.get_trader_history(address, limit=limit)

        # 格式化为图表数据
        chart_data = {
            'roi': [],
            'pnl': [],
            'equity': []
        }

        for record in reversed(history):  # 按时间顺序
            timestamp = record['analyzed_at']
            chart_data['roi'].append({
                'timestamp': timestamp,
                'value': record['roi']
            })
            chart_data['pnl'].append({
                'timestamp': timestamp,
                'value': record['total_pnl']
            })
            chart_data['equity'].append({
                'timestamp': timestamp,
                'value': record['current_equity']
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


@app.route('/api/traders/rating/<rating>', methods=['GET'])
def get_traders_by_rating(rating: str):
    """
    根据评级获取交易者
    Path Parameters:
        - rating: str, 评级 (S/A/B/C/D/F)
    """
    try:
        if rating not in ['S', 'A', 'B', 'C', 'D', 'F']:
            return jsonify({
                'success': False,
                'error': 'Invalid rating. Must be S/A/B/C/D/F'
            }), 400

        traders = db.get_traders_by_rating(rating)

        return jsonify({
            'success': True,
            'data': traders,
            'count': len(traders)
        })

    except Exception as e:
        logger.error(f"获取交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """
    获取数据库统计信息
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


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """
    获取最近的筛选会话
    Query Parameters:
        - limit: int, 返回数量，默认10
    """
    try:
        limit = int(request.args.get('limit', 10))
        sessions = db.get_recent_sessions(limit=limit)

        return jsonify({
            'success': True,
            'data': sessions,
            'count': len(sessions)
        })

    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sessions/<int:session_id>/traders', methods=['GET'])
def get_session_traders(session_id: int):
    """
    获取指定会话的交易者
    """
    try:
        traders = db.get_session_traders(session_id)

        return jsonify({
            'success': True,
            'data': traders,
            'count': len(traders)
        })

    except Exception as e:
        logger.error(f"获取会话交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    logger.info("启动 Trader Analytics API Server...")
    logger.info("API 文档:")
    logger.info("  GET  /api/traders - 获取交易者列表")
    logger.info("  GET  /api/traders/<address> - 获取交易者详情")
    logger.info("  GET  /api/traders/<address>/fills - 获取历史交易")
    logger.info("  GET  /api/traders/<address>/history - 获取历史图表数据")
    logger.info("  GET  /api/traders/rating/<rating> - 按评级筛选")
    logger.info("  GET  /api/stats - 获取统计信息")
    logger.info("  GET  /api/sessions - 获取筛选会话")
    logger.info("  GET  /health - 健康检查")

    app.run(host='0.0.0.0', port=5000, debug=True)
