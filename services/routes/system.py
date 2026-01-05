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
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })
