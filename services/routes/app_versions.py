"""
应用版本管理路由
包括：版本列表、创建、更新、删除、可见性控制
"""
from flask import Blueprint, jsonify, request
import logging

from .db import db
from .middleware import login_required, admin_required, get_current_user_id

logger = logging.getLogger(__name__)

app_versions_bp = Blueprint('app_versions', __name__)


# ==================== 公开 API（用于客户端检查更新） ====================

@app_versions_bp.route('/api/app-versions/latest', methods=['GET'])
def get_latest_version():
    """获取最新版本（公开接口，用于客户端检查更新）
    ---
    tags:
      - AppVersions
    parameters:
      - name: platform
        in: query
        type: string
        default: all
        description: 平台 (all/android/ios/web)
    responses:
      200:
        description: 获取成功
      500:
        description: 服务器错误
    """
    try:
        platform = request.args.get('platform', 'all')
        
        latest = db.get_latest_version(platform, visible_only=True)
        
        return jsonify({
            'success': True,
            'data': _format_version(latest) if latest else None
        })
        
    except Exception as e:
        logger.error(f"获取最新版本失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions/check-update', methods=['GET'])
def check_update():
    """检查版本更新（公开接口，用于客户端检查更新）
    ---
    tags:
      - AppVersions
    parameters:
      - name: current_version
        in: query
        type: string
        required: true
        description: 当前版本号
      - name: platform
        in: query
        type: string
        default: all
        description: 平台
    responses:
      200:
        description: 检查成功
      400:
        description: 缺少参数
      500:
        description: 服务器错误
    """
    try:
        current_version = request.args.get('current_version')
        platform = request.args.get('platform', 'all')
        
        if not current_version:
            return jsonify({
                'success': False,
                'error': '缺少 current_version 参数'
            }), 400
        
        result = db.check_version_update(current_version, platform)
        
        if result and result.get('has_update'):
            return jsonify({
                'success': True,
                'data': {
                    'has_update': True,
                    'is_force_update': result.get('is_force_update', False),
                    'latest_version': _format_version(result.get('latest_version'))
                }
            })
        
        return jsonify({
            'success': True,
            'data': {
                'has_update': False
            }
        })
        
    except Exception as e:
        logger.error(f"检查版本更新失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 管理员 API ====================

@app_versions_bp.route('/api/app-versions', methods=['GET'])
@login_required
@admin_required
def get_versions():
    """获取版本列表（管理员权限）
    ---
    tags:
      - AppVersions
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: is_visible
        in: query
        type: boolean
        description: 是否可见筛选
      - name: platform
        in: query
        type: string
        description: 平台筛选
      - name: limit
        in: query
        type: integer
        default: 100
      - name: offset
        in: query
        type: integer
        default: 0
    responses:
      200:
        description: 获取成功
      403:
        description: 无权限
      500:
        description: 服务器错误
    """
    try:
        is_visible = request.args.get('is_visible')
        if is_visible is not None:
            is_visible = is_visible.lower() == 'true'
        
        platform = request.args.get('platform')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        versions = db.get_app_versions(
            is_visible=is_visible,
            platform=platform,
            limit=limit,
            offset=offset
        )
        
        return jsonify({
            'success': True,
            'data': [_format_version(v) for v in versions]
        })
        
    except Exception as e:
        logger.error(f"获取版本列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions', methods=['POST'])
@login_required
@admin_required
def create_version():
    """创建版本（管理员权限）
    ---
    tags:
      - AppVersions
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
            - version
          properties:
            version:
              type: string
              description: 版本号
            version_name:
              type: string
              description: 版本名称
            description:
              type: string
              description: 版本描述
            release_notes:
              type: string
              description: 更新日志
            download_url:
              type: string
              description: 下载链接
            is_force_update:
              type: boolean
              default: false
            is_visible:
              type: boolean
              default: true
            min_supported_version:
              type: string
            platform:
              type: string
              default: all
    responses:
      200:
        description: 创建成功
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
        
        version = data.get('version', '').strip()
        
        if not version:
            return jsonify({
                'success': False,
                'error': '版本号不能为空'
            }), 400
        
        user_id = get_current_user_id()
        
        app_version = db.create_app_version(
            version=version,
            version_name=data.get('version_name', ''),
            description=data.get('description', ''),
            release_notes=data.get('release_notes', ''),
            download_url=data.get('download_url', ''),
            is_force_update=data.get('is_force_update', False),
            is_visible=data.get('is_visible', True),
            min_supported_version=data.get('min_supported_version', ''),
            platform=data.get('platform', 'all'),
            created_by=user_id
        )
        
        if not app_version:
            return jsonify({
                'success': False,
                'error': '创建失败，版本号可能已存在'
            }), 400
        
        logger.info(f"版本创建成功: {version}")
        
        return jsonify({
            'success': True,
            'data': _format_version(app_version),
            'message': '版本创建成功'
        })
        
    except Exception as e:
        logger.error(f"创建版本失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions/<int:version_id>', methods=['GET'])
@login_required
@admin_required
def get_version(version_id: int):
    """获取版本详情（管理员权限）
    ---
    tags:
      - AppVersions
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: version_id
        in: path
        type: integer
        required: true
        description: 版本ID
    responses:
      200:
        description: 获取成功
      403:
        description: 无权限
      404:
        description: 版本不存在
      500:
        description: 服务器错误
    """
    try:
        app_version = db.get_app_version(version_id)
        
        if not app_version:
            return jsonify({
                'success': False,
                'error': '版本不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': _format_version(app_version)
        })
        
    except Exception as e:
        logger.error(f"获取版本详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions/<int:version_id>', methods=['PUT'])
@login_required
@admin_required
def update_version(version_id: int):
    """更新版本（管理员权限）
    ---
    tags:
      - AppVersions
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: version_id
        in: path
        type: integer
        required: true
        description: 版本ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            version_name:
              type: string
            description:
              type: string
            release_notes:
              type: string
            download_url:
              type: string
            is_force_update:
              type: boolean
            is_visible:
              type: boolean
            min_supported_version:
              type: string
    responses:
      200:
        description: 更新成功
      403:
        description: 无权限
      404:
        description: 版本不存在
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data:
            data = {}
        
        app_version = db.update_app_version(
            version_id=version_id,
            version_name=data.get('version_name'),
            description=data.get('description'),
            release_notes=data.get('release_notes'),
            download_url=data.get('download_url'),
            is_force_update=data.get('is_force_update'),
            is_visible=data.get('is_visible'),
            min_supported_version=data.get('min_supported_version')
        )
        
        if not app_version:
            return jsonify({
                'success': False,
                'error': '版本不存在或更新失败'
            }), 404
        
        logger.info(f"版本更新成功: id={version_id}")
        
        return jsonify({
            'success': True,
            'data': _format_version(app_version),
            'message': '更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新版本失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions/<int:version_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_version(version_id: int):
    """删除版本（管理员权限）
    ---
    tags:
      - AppVersions
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: version_id
        in: path
        type: integer
        required: true
        description: 版本ID
    responses:
      200:
        description: 删除成功
      403:
        description: 无权限
      404:
        description: 版本不存在
      500:
        description: 服务器错误
    """
    try:
        success = db.delete_app_version(version_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '版本不存在'
            }), 404
        
        logger.info(f"版本删除成功: id={version_id}")
        
        return jsonify({
            'success': True,
            'message': '删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除版本失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions/<int:version_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_visibility(version_id: int):
    """切换版本可见性（管理员权限）
    ---
    tags:
      - AppVersions
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: version_id
        in: path
        type: integer
        required: true
        description: 版本ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - is_visible
          properties:
            is_visible:
              type: boolean
    responses:
      200:
        description: 切换成功
      403:
        description: 无权限
      404:
        description: 版本不存在
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data or 'is_visible' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 is_visible 参数'
            }), 400
        
        is_visible = data.get('is_visible')
        
        success = db.toggle_version_visibility(version_id, is_visible)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '版本不存在'
            }), 404
        
        logger.info(f"版本可见性切换成功: id={version_id}, is_visible={is_visible}")
        
        return jsonify({
            'success': True,
            'message': f"版本已{'显示' if is_visible else '隐藏'}"
        })
        
    except Exception as e:
        logger.error(f"切换版本可见性失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app_versions_bp.route('/api/app-versions/stats', methods=['GET'])
@login_required
@admin_required
def get_version_stats():
    """获取版本统计信息（管理员权限）
    ---
    tags:
      - AppVersions
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
        stats = db.get_app_version_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"获取版本统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 辅助函数 ====================

def _format_version(version: dict) -> dict:
    """格式化版本数据"""
    if not version:
        return None
    
    return {
        'id': version['id'],
        'version': version['version'],
        'version_name': version.get('version_name', ''),
        'description': version.get('description', ''),
        'release_notes': version.get('release_notes', ''),
        'download_url': version.get('download_url', ''),
        'is_force_update': version.get('is_force_update', False),
        'is_visible': version.get('is_visible', True),
        'min_supported_version': version.get('min_supported_version', ''),
        'platform': version.get('platform', 'all'),
        'created_by': version.get('created_by'),
        'created_at': version['created_at'].isoformat() if version.get('created_at') else None,
        'updated_at': version['updated_at'].isoformat() if version.get('updated_at') else None
    }
