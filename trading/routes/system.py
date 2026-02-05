"""
系统相关路由
包括：健康检查等
"""
from flask import Blueprint, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

system_bp = Blueprint('system', __name__)


@system_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查
    ---
    tags:
      - System
    responses:
      200:
        description: 服务正常运行
        schema:
          type: object
          properties:
            status:
              type: string
              example: healthy
            service:
              type: string
              example: trading
            timestamp:
              type: string
              format: date-time
              example: "2024-01-01T12:00:00"
    """
    return jsonify({
        'status': 'healthy',
        'service': 'trading',
        'timestamp': datetime.now().isoformat()
    })
