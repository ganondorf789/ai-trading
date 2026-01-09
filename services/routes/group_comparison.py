"""
分组对比分析相关路由
"""
from flask import Blueprint, jsonify, request
import logging

from database import TraderDatabase

logger = logging.getLogger(__name__)

group_comparison_bp = Blueprint('group_comparison', __name__)
db = TraderDatabase()


@group_comparison_bp.route('/api/group-comparison/sessions', methods=['GET'])
def get_group_comparison_sessions():
    """
    获取分组对比会话列表
    Query Parameters:
        - limit: int, 返回数量，默认20
        - status: str, 状态筛选 (pending/running/completed/failed)
    """
    try:
        limit = int(request.args.get('limit', 20))
        status = request.args.get('status')

        sessions = db.get_group_comparison_sessions(limit=limit, status=status)

        return jsonify({
            'success': True,
            'data': sessions,
            'count': len(sessions)
        })
    except Exception as e:
        logger.error(f"获取分组对比会话列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@group_comparison_bp.route('/api/group-comparison/sessions/<int:session_id>', methods=['GET'])
def get_group_comparison_session(session_id: int):
    """
    获取单个分组对比会话详情
    """
    try:
        session = db.get_group_comparison_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': '会话不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': session
        })
    except Exception as e:
        logger.error(f"获取分组对比会话详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@group_comparison_bp.route('/api/group-comparison/sessions/<int:session_id>/finalists', methods=['GET'])
def get_group_comparison_finalists(session_id: int):
    """
    获取分组对比会话的晋级者列表
    """
    try:
        session = db.get_group_comparison_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': '会话不存在'
            }), 404

        finalists = session.get('finalists', [])

        # 关联交易员详细信息
        enriched_finalists = []
        for f in finalists:
            trader = db.get_trader_by_address(f['address'])
            if trader:
                enriched_finalists.append({
                    **f,
                    'trader_info': trader
                })
            else:
                enriched_finalists.append(f)

        return jsonify({
            'success': True,
            'data': enriched_finalists,
            'count': len(enriched_finalists)
        })
    except Exception as e:
        logger.error(f"获取分组对比晋级者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@group_comparison_bp.route('/api/group-comparison/sessions/<int:session_id>/groups', methods=['GET'])
def get_group_comparison_groups(session_id: int):
    """
    获取分组对比会话的分组信息
    """
    try:
        session = db.get_group_comparison_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': '会话不存在'
            }), 404

        groups = session.get('groups', [])

        # 为每个分组添加交易员信息
        all_traders = session.get('traders', [])
        for group in groups:
            group_id = group.get('id')
            group['traders'] = [t for t in all_traders if t.get('group_id') == group_id]

        return jsonify({
            'success': True,
            'data': groups,
            'count': len(groups)
        })
    except Exception as e:
        logger.error(f"获取分组对比分组信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@group_comparison_bp.route('/api/group-comparison/stats', methods=['GET'])
def get_group_comparison_stats():
    """
    获取分组对比统计信息
    """
    try:
        stats = db.get_group_comparison_stats()

        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取分组对比统计信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
