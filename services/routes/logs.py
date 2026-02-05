"""
日志相关路由
包括：跟单机器人日志查询等
"""
import re
import gzip
from pathlib import Path
from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

from .middleware import login_required

logger = logging.getLogger(__name__)

logs_bp = Blueprint('logs', __name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"


# ==================== 日志 API ====================

@logs_bp.route('/api/logs/copy-trading', methods=['GET'])
@login_required
def get_copy_trading_logs():
    """获取跟单机器人日志文件列表
    ---
    tags:
      - Logs
    responses:
      200:
        description: 日志文件列表
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
                  filename:
                    type: string
                  size:
                    type: integer
                  modified:
                    type: string
                  compressed:
                    type: boolean
    """
    try:
        if not LOGS_DIR.exists():
            return jsonify({
                'success': True,
                'data': [],
                'message': '日志目录不存在'
            })
        
        log_files = []
        # 匹配 position_copy_*.log 和 position_copy_*.log.gz
        for f in LOGS_DIR.iterdir():
            if f.is_file() and f.name.startswith('position_copy_'):
                stat = f.stat()
                log_files.append({
                    'filename': f.name,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'compressed': f.name.endswith('.gz')
                })
        
        # 按修改时间倒序排列（最新的在前面）
        log_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': log_files
        })
        
    except Exception as e:
        logger.error(f"获取日志列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/copy-trading/<filename>', methods=['GET'])
@login_required
def get_copy_trading_log_content(filename: str):
    """获取指定日志文件内容
    ---
    tags:
      - Logs
    parameters:
      - name: filename
        in: path
        type: string
        required: true
        description: 日志文件名
      - name: lines
        in: query
        type: integer
        default: 500
        description: 返回的行数（从末尾开始）
      - name: offset
        in: query
        type: integer
        default: 0
        description: 偏移量（跳过末尾多少行）
      - name: level
        in: query
        type: string
        description: 过滤日志级别 (DEBUG, INFO, WARNING, ERROR)
      - name: search
        in: query
        type: string
        description: 搜索关键词
    responses:
      200:
        description: 日志内容
      404:
        description: 文件不存在
    """
    try:
        # 安全检查：防止路径穿越
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({
                'success': False,
                'error': '无效的文件名'
            }), 400
        
        # 只允许访问 position_copy_*.log 文件
        if not filename.startswith('position_copy_'):
            return jsonify({
                'success': False,
                'error': '不允许访问该文件'
            }), 403
        
        log_path = LOGS_DIR / filename
        if not log_path.exists():
            return jsonify({
                'success': False,
                'error': '文件不存在'
            }), 404
        
        # 获取参数
        lines_limit = request.args.get('lines', 500, type=int)
        offset = request.args.get('offset', 0, type=int)
        level_filter = request.args.get('level', '').upper()
        search_keyword = request.args.get('search', '')
        
        # 限制最大行数
        lines_limit = min(lines_limit, 2000)
        
        # 读取文件内容
        if filename.endswith('.gz'):
            with gzip.open(log_path, 'rt', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
        else:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines = f.readlines()
        
        # 过滤日志级别
        if level_filter and level_filter in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            # 日志格式: 2024-01-01 12:00:00 | INFO     | ...
            level_pattern = re.compile(rf'\|\s*{level_filter}\s*\|', re.IGNORECASE)
            all_lines = [line for line in all_lines if level_pattern.search(line)]
        
        # 搜索关键词
        if search_keyword:
            all_lines = [line for line in all_lines if search_keyword.lower() in line.lower()]
        
        total_lines = len(all_lines)
        
        # 从末尾取指定行数（支持分页）
        if offset > 0:
            end_idx = max(0, total_lines - offset)
            start_idx = max(0, end_idx - lines_limit)
        else:
            start_idx = max(0, total_lines - lines_limit)
            end_idx = total_lines
        
        selected_lines = all_lines[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'data': {
                'filename': filename,
                'total_lines': total_lines,
                'start_line': start_idx + 1,
                'end_line': end_idx,
                'lines': [line.rstrip('\n\r') for line in selected_lines]
            }
        })
        
    except Exception as e:
        logger.error(f"读取日志文件失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@logs_bp.route('/api/logs/copy-trading/latest', methods=['GET'])
@login_required
def get_latest_copy_trading_logs():
    """获取最新的跟单机器人日志
    ---
    tags:
      - Logs
    parameters:
      - name: lines
        in: query
        type: integer
        default: 100
        description: 返回的行数
      - name: level
        in: query
        type: string
        description: 过滤日志级别 (DEBUG, INFO, WARNING, ERROR)
      - name: search
        in: query
        type: string
        description: 搜索关键词
    responses:
      200:
        description: 最新日志内容
    """
    try:
        if not LOGS_DIR.exists():
            return jsonify({
                'success': True,
                'data': {
                    'filename': None,
                    'total_lines': 0,
                    'lines': []
                },
                'message': '日志目录不存在'
            })
        
        # 查找最新的未压缩日志文件
        latest_log = None
        latest_mtime = 0
        
        for f in LOGS_DIR.iterdir():
            if f.is_file() and f.name.startswith('position_copy_') and f.name.endswith('.log'):
                mtime = f.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_log = f
        
        if not latest_log:
            return jsonify({
                'success': True,
                'data': {
                    'filename': None,
                    'total_lines': 0,
                    'lines': []
                },
                'message': '没有找到日志文件'
            })
        
        # 获取参数
        lines_limit = request.args.get('lines', 100, type=int)
        level_filter = request.args.get('level', '').upper()
        search_keyword = request.args.get('search', '')
        
        # 限制最大行数
        lines_limit = min(lines_limit, 2000)
        
        # 读取文件内容
        with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        
        # 过滤日志级别
        if level_filter and level_filter in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            level_pattern = re.compile(rf'\|\s*{level_filter}\s*\|', re.IGNORECASE)
            all_lines = [line for line in all_lines if level_pattern.search(line)]
        
        # 搜索关键词
        if search_keyword:
            all_lines = [line for line in all_lines if search_keyword.lower() in line.lower()]
        
        total_lines = len(all_lines)
        
        # 取最后 N 行
        selected_lines = all_lines[-lines_limit:] if lines_limit < total_lines else all_lines
        
        return jsonify({
            'success': True,
            'data': {
                'filename': latest_log.name,
                'total_lines': total_lines,
                'lines': [line.rstrip('\n\r') for line in selected_lines]
            }
        })
        
    except Exception as e:
        logger.error(f"获取最新日志失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
