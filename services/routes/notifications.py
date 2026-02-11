"""
通知相关路由
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required, get_current_user_id

logger = logging.getLogger(__name__)

notifications_bp = Blueprint('notifications', __name__)


# ==================== 通知分类定义 ====================
# 将通知 type 映射到 5 个大类：公告、行情、交易、跟踪、错误
NOTIFICATION_CATEGORIES = {
    'announcement': ['announcement'],           # 公告
    'market':       ['market', 'price_alert'],  # 行情
    'trading':      ['open', 'close', 'adjust'],# 交易
    'tracking':     ['tracking_open', 'tracking_close', 'tracking_add', 'tracking_reduce'],  # 地址跟踪
    'error':        ['error'],                  # 错误
}

# 反向映射：type -> category
TYPE_TO_CATEGORY = {}
for category, types in NOTIFICATION_CATEGORIES.items():
    for t in types:
        TYPE_TO_CATEGORY[t] = category

ALL_CATEGORY_NAMES = list(NOTIFICATION_CATEGORIES.keys())


# ==================== 通知 API ====================

@notifications_bp.route('/api/notifications', methods=['GET'])
@login_required
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
      - name: category
        in: query
        type: string
        enum: [announcement, market, trading, tracking, error]
        description: 通知大类筛选（公告/行情/交易/跟踪/错误），与 type 互斥
      - name: type
        in: query
        type: string
        enum: [open, close, adjust, tracking_open, tracking_close, tracking_add, tracking_reduce, error, announcement, market, price_alert]
        description: 通知类型筛选（细分类型）
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
        category = request.args.get('category')
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

        # 如果指定了 category，展开为对应的 type 列表
        notification_types = None
        if category and category in NOTIFICATION_CATEGORIES:
            notification_types = NOTIFICATION_CATEGORIES[category]
        elif notification_type:
            notification_types = [notification_type]

        user_id = get_current_user_id()

        notifications = db.get_notifications_cursor(
            user_id=user_id,
            limit=limit + 1,  # 多取一条用于判断是否还有更多
            before=before,
            after=after,
            notification_types=notification_types,
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


@notifications_bp.route('/api/notifications/unread-summary', methods=['GET'])
@login_required
def get_unread_summary():
    """获取各分类未读消息数量
    ---
    tags:
      - Notifications
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
    responses:
      200:
        description: 各分类未读数量
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                total:
                  type: integer
                  description: 未读总数
                categories:
                  type: object
                  properties:
                    announcement:
                      type: integer
                      description: 公告未读数
                    market:
                      type: integer
                      description: 行情未读数
                    trading:
                      type: integer
                      description: 交易未读数
                    tracking:
                      type: integer
                      description: 跟踪未读数
                    error:
                      type: integer
                      description: 错误未读数
      500:
        description: 服务器错误
    """
    try:
        user_id = get_current_user_id()
        unread_by_type = db.get_unread_count_by_type(user_id)

        # 将细分 type 的未读数聚合到大类
        categories = {}
        total = 0
        for cat_name, types in NOTIFICATION_CATEGORIES.items():
            count = sum(unread_by_type.get(t, 0) for t in types)
            categories[cat_name] = count
            total += count

        # 处理未归类的 type（归入 error）
        categorized_types = set(TYPE_TO_CATEGORY.keys())
        for t, cnt in unread_by_type.items():
            if t not in categorized_types:
                categories['error'] = categories.get('error', 0) + cnt
                total += cnt

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'categories': categories
            }
        })
    except Exception as e:
        logger.error(f"获取未读消息摘要失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notifications_bp.route('/api/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    """标记通知为已读
    ---
    tags:
      - Notifications
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
          properties:
            category:
              type: string
              enum: [all, announcement, market, trading, tracking, error]
              description: >
                要标记已读的分类。
                传 'all' 标记所有通知为已读；
                传具体分类名标记该分类下所有通知为已读。
    responses:
      200:
        description: 标记成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                category:
                  type: string
                read_before_id:
                  type: integer
                  description: 已读水位线（id <= 此值的通知视为已读）
      400:
        description: 参数错误
      500:
        description: 服务器错误
    """
    try:
        user_id = get_current_user_id()
        data = request.get_json() or {}
        category = data.get('category', '').strip()

        if not category:
            return jsonify({
                'success': False,
                'error': '请指定要标记已读的分类 (category)'
            }), 400

        if category == 'all':
            read_before_id = db.mark_all_read_for_user(user_id)
        elif category in NOTIFICATION_CATEGORIES:
            types = NOTIFICATION_CATEGORIES[category]
            read_before_id = db.mark_category_read(user_id, category, types)
        else:
            return jsonify({
                'success': False,
                'error': f"无效的分类: {category}，可选值: all, {', '.join(ALL_CATEGORY_NAMES)}"
            }), 400

        return jsonify({
            'success': True,
            'data': {
                'category': category,
                'read_before_id': read_before_id
            }
        })
    except Exception as e:
        logger.error(f"标记通知已读失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@notifications_bp.route('/api/notifications/<int:notification_id>', methods=['GET'])
@login_required
def get_notification(notification_id: int):
    """获取通知详情
    ---
    tags:
      - Notifications
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: notification_id
        in: path
        type: integer
        required: true
        description: 通知ID
    responses:
      200:
        description: 获取成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
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
      404:
        description: 通知不存在
      500:
        description: 服务器错误
    """
    try:
        notification = db.get_notification(notification_id)

        if not notification:
            return jsonify({
                'success': False,
                'error': '通知不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': notification
        })
    except Exception as e:
        logger.error(f"获取通知详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
