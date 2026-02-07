"""
公告管理路由
包括：发布公告、获取公告列表、更新、删除
公告通过 WebSocket 广播给所有用户
"""
import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request

from .db import db
from .middleware import login_required, admin_required, get_current_user_id
from ..shared import get_redis_client

logger = logging.getLogger(__name__)

announcements_bp = Blueprint('announcements', __name__)

# Redis 通知 channel（与 websocket.py 一致）
REDIS_NOTIFICATIONS_CHANNEL = "notifications"


def _publish_announcement(data: dict) -> bool:
    """
    通过 Redis Pub/Sub 发布公告
    
    Args:
        data: 公告数据
        
    Returns:
        是否发布成功
    """
    try:
        redis_client = get_redis_client()
        if redis_client is None:
            logger.error("无法获取 Redis 客户端")
            return False
        
        # 发布到 notifications 频道
        redis_client.publish(REDIS_NOTIFICATIONS_CHANNEL, json.dumps(data))
        logger.info(f"公告已发布到 Redis: {data.get('title')}")
        return True
    except Exception as e:
        logger.error(f"发布公告到 Redis 失败: {e}")
        return False


# ==================== 管理员 API ====================

@announcements_bp.route('/api/announcements', methods=['POST'])
@login_required
@admin_required
def create_announcement():
    """发布公告（管理员权限）
    ---
    tags:
      - Announcements
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - title
            - content
          properties:
            title:
              type: string
              description: 公告标题
            content:
              type: string
              description: 公告内容（支持 Markdown）
    responses:
      200:
        description: 发布成功
      400:
        description: 参数错误
      403:
        description: 无权限
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        title = data.get('title', '').strip()
        content = data.get('content', '').strip()
        
        if not title:
            return jsonify({
                'success': False,
                'error': '公告标题不能为空'
            }), 400
        
        if not content:
            return jsonify({
                'success': False,
                'error': '公告内容不能为空'
            }), 400
        
        # 构造公告消息（不设置 user_id，将广播给所有用户）
        announcement_data = {
            'type': 'announcement',
            'title': title,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # 通过 Redis 发布公告（WebSocket 会接收并保存到数据库、广播给客户端）
        if not _publish_announcement(announcement_data):
            return jsonify({
                'success': False,
                'error': '发布公告失败，请稍后重试'
            }), 500
        
        logger.info(f"公告发布成功: {title}")
        
        return jsonify({
            'success': True,
            'message': '公告发布成功'
        })
        
    except Exception as e:
        logger.error(f"发布公告失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@announcements_bp.route('/api/announcements', methods=['GET'])
@login_required
@admin_required
def get_announcements():
    """获取公告列表（管理员权限）
    ---
    tags:
      - Announcements
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: limit
        in: query
        type: integer
        default: 50
        description: 返回数量限制
      - name: offset
        in: query
        type: integer
        default: 0
        description: 偏移量
    responses:
      200:
        description: 获取成功
      403:
        description: 无权限
      500:
        description: 服务器错误
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # 限制范围
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
        
        # 通过现有通知接口获取公告类型的通知
        announcements, total_count = db.get_notifications(
            notification_type='announcement',
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'success': True,
            'data': [_format_announcement(a) for a in announcements],
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(announcements) < total_count
            }
        })
        
    except Exception as e:
        logger.error(f"获取公告列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@announcements_bp.route('/api/announcements/<int:announcement_id>', methods=['GET'])
@login_required
@admin_required
def get_announcement(announcement_id: int):
    """获取公告详情（管理员权限）
    ---
    tags:
      - Announcements
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: announcement_id
        in: path
        type: integer
        required: true
        description: 公告ID
    responses:
      200:
        description: 获取成功
      403:
        description: 无权限
      404:
        description: 公告不存在
      500:
        description: 服务器错误
    """
    try:
        announcement = db.get_notification(announcement_id)
        
        if not announcement:
            return jsonify({
                'success': False,
                'error': '公告不存在'
            }), 404
        
        # 验证是公告类型
        if announcement.get('type') != 'announcement':
            return jsonify({
                'success': False,
                'error': '公告不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': _format_announcement(announcement)
        })
        
    except Exception as e:
        logger.error(f"获取公告详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@announcements_bp.route('/api/announcements/<int:announcement_id>', methods=['PUT'])
@login_required
@admin_required
def update_announcement(announcement_id: int):
    """更新公告（管理员权限）
    ---
    tags:
      - Announcements
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: announcement_id
        in: path
        type: integer
        required: true
        description: 公告ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
              description: 公告标题
            content:
              type: string
              description: 公告内容
    responses:
      200:
        description: 更新成功
      403:
        description: 无权限
      404:
        description: 公告不存在
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        # 检查公告是否存在
        announcement = db.get_notification(announcement_id)
        
        if not announcement or announcement.get('type') != 'announcement':
            return jsonify({
                'success': False,
                'error': '公告不存在'
            }), 404
        
        # 更新公告
        title = data.get('title')
        content = data.get('content')
        
        success = db.update_notification(
            announcement_id,
            title=title,
            content=content
        )
        
        if not success:
            return jsonify({
                'success': False,
                'error': '更新失败'
            }), 500
        
        logger.info(f"公告更新成功: id={announcement_id}")
        
        return jsonify({
            'success': True,
            'message': '更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新公告失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@announcements_bp.route('/api/announcements/<int:announcement_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_announcement(announcement_id: int):
    """删除公告（管理员权限）
    ---
    tags:
      - Announcements
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: announcement_id
        in: path
        type: integer
        required: true
        description: 公告ID
    responses:
      200:
        description: 删除成功
      403:
        description: 无权限
      404:
        description: 公告不存在
      500:
        description: 服务器错误
    """
    try:
        # 检查公告是否存在
        announcement = db.get_notification(announcement_id)
        
        if not announcement or announcement.get('type') != 'announcement':
            return jsonify({
                'success': False,
                'error': '公告不存在'
            }), 404
        
        success = db.delete_notification(announcement_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '删除失败'
            }), 500
        
        logger.info(f"公告删除成功: id={announcement_id}")
        
        return jsonify({
            'success': True,
            'message': '删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除公告失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@announcements_bp.route('/api/announcements/stats', methods=['GET'])
@login_required
@admin_required
def get_announcement_stats():
    """获取公告统计信息（管理员权限）
    ---
    tags:
      - Announcements
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
    responses:
      200:
        description: 获取成功
      403:
        description: 无权限
      500:
        description: 服务器错误
    """
    try:
        # 获取公告总数
        _, total_count = db.get_notifications(
            notification_type='announcement',
            limit=1,
            offset=0
        )
        
        return jsonify({
            'success': True,
            'data': {
                'total_count': total_count
            }
        })
        
    except Exception as e:
        logger.error(f"获取公告统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 辅助函数 ====================

def _format_announcement(announcement: dict) -> dict:
    """格式化公告数据"""
    if not announcement:
        return None
    
    return {
        'id': announcement['id'],
        'type': announcement['type'],
        'title': announcement.get('title', ''),
        'content': announcement.get('content', ''),
        'is_read': announcement.get('is_read', False),
        'created_at': announcement['created_at'].isoformat() if announcement.get('created_at') else None
    }
