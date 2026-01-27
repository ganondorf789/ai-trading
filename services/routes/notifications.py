"""
通知相关路由
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db

logger = logging.getLogger(__name__)

notifications_bp = Blueprint('notifications', __name__)


# ==================== 通知 API ====================

@notifications_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    """获取通知列表（游标分页）
    ---
    tags:
      - Notifications
    parameters:
      - name: limit
        in: query
        type: integer
        default: 50
        description: 返回数量限制
      - name: before
        in: query
        type: integer
        description: 游标ID，获取此ID之前的记录
      - name: after
        in: query
        type: integer
        description: 游标ID，获取此ID之后的记录（用于获取更新的数据）
      - name: type
        in: query
        type: string
        enum: [open, close, adjust, error]
        description: 通知类型筛选
      - name: is_read
        in: query
        type: boolean
        description: 已读状态筛选
      - name: symbol
        in: query
        type: string
        description: 交易对筛选
      - name: target_address
        in: query
        type: string
        description: 目标交易员地址筛选
    responses:
      200:
        description: 通知列表
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
                  id:
                    type: integer
                  type:
                    type: string
                  title:
                    type: string
                  content:
                    type: string
                    description: Markdown 格式内容
                  target_address:
                    type: string
                  symbol:
                    type: string
                  side:
                    type: string
                  size:
                    type: number
                  pnl:
                    type: number
                  is_read:
                    type: boolean
                  created_at:
                    type: string
            pagination:
              type: object
              properties:
                has_more:
                  type: boolean
                next_cursor:
                  type: integer
      500:
        description: 服务器错误
    """
    try:
        limit = int(request.args.get('limit', 50))
        before = request.args.get('before')
        after = request.args.get('after')
        notification_type = request.args.get('type')
        is_read = request.args.get('is_read')
        symbol = request.args.get('symbol')
        target_address = request.args.get('target_address')

        # 转换参数类型
        if before is not None:
            before = int(before)
        if after is not None:
            after = int(after)
        if is_read is not None:
            is_read = is_read.lower() == 'true'

        # 限制 limit 范围
        limit = min(max(1, limit), 100)

        notifications = db.get_notifications_cursor(
            limit=limit + 1,  # 多取一条用于判断是否还有更多
            before=before,
            after=after,
            notification_type=notification_type,
            is_read=is_read,
            symbol=symbol,
            target_address=target_address
        )

        # 判断是否有更多数据
        has_more = len(notifications) > limit
        if has_more:
            notifications = notifications[:limit]

        # 计算下一个游标
        next_cursor = notifications[-1]['id'] if notifications and has_more else None

        return jsonify({
            'success': True,
            'data': notifications,
            'pagination': {
                'has_more': has_more,
                'next_cursor': next_cursor
            }
        })
    except Exception as e:
        logger.error(f"获取通知列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
