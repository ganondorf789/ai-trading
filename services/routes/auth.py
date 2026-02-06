"""
用户认证相关路由
包括：注册、登录、修改密码、Hyperliquid 设置、秘钥管理
"""
from flask import Blueprint, jsonify, request, g
import logging
from datetime import datetime, timedelta

from config.settings import settings
from .db import db
from .middleware import generate_tokens, verify_token, login_required, admin_required, get_current_user_id

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# 用户身份常量
ROLE_USER = 'user'
ROLE_MEMBER = 'member'
ROLE_ADMIN = 'admin'


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - account
            - password
            - secret_key
          properties:
            account:
              type: string
              description: 账号
              example: "user123"
            password:
              type: string
              description: 密码
              example: "password123"
            secret_key:
              type: string
              description: 注册秘钥
              example: "your-secret-key"
    responses:
      200:
        description: 注册成功
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
                account:
                  type: string
                role:
                  type: string
            message:
              type: string
      400:
        description: 请求参数错误
      409:
        description: 账号已存在
      403:
        description: 秘钥验证失败
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        account = data.get('account', '').strip()
        password = data.get('password', '')
        secret_key = data.get('secret_key', '').strip()
        
        if not account:
            return jsonify({
                'success': False,
                'error': '账号不能为空'
            }), 400
        
        if not password:
            return jsonify({
                'success': False,
                'error': '密码不能为空'
            }), 400
        
        if not secret_key:
            return jsonify({
                'success': False,
                'error': '秘钥不能为空'
            }), 400
        
        # 验证账号格式（字母、数字、下划线，4-32位）
        import re
        if not re.match(r'^[a-zA-Z0-9_]{4,32}$', account):
            return jsonify({
                'success': False,
                'error': '账号格式不正确（4-32位字母、数字或下划线）'
            }), 400
        
        # 验证密码长度
        if len(password) < 6 or len(password) > 64:
            return jsonify({
                'success': False,
                'error': '密码长度必须在6-64位之间'
            }), 400
        
        # 验证秘钥（从秘钥表验证）
        secret_key_info = db.validate_secret_key(secret_key)
        if not secret_key_info:
            logger.warning(f"注册失败: 秘钥验证失败 - account={account}")
            return jsonify({
                'success': False,
                'error': '秘钥无效或已过期'
            }), 403
        
        # 根据秘钥配置计算用户过期时间
        expires_at = None
        if secret_key_info['expires_days'] > 0:
            expires_at = datetime.now() + timedelta(days=secret_key_info['expires_days'])
        
        # 创建用户
        user = db.create_user(
            account=account,
            password=password,
            secret_key_id=secret_key_info['id'],
            role=secret_key_info['user_role'],
            expires_at=expires_at
        )
        
        if not user:
            return jsonify({
                'success': False,
                'error': '账号已存在'
            }), 409
        
        # 更新秘钥使用次数并记录用户ID
        db.use_secret_key(secret_key_info['id'], user['id'])
        
        logger.info(f"用户注册成功: {account}, 身份: {secret_key_info['user_role']}")
        
        return jsonify({
            'success': True,
            'data': {
                'id': user['id'],
                'account': user['account'],
                'role': user['role']
            },
            'message': '注册成功'
        })
        
    except Exception as e:
        logger.error(f"用户注册失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/init-account', methods=['POST'])
def create_init_account():
    """创建初始管理员账号
    
    仅在系统中没有任何用户时可用，用于系统初始化
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - account
            - password
          properties:
            account:
              type: string
              description: 账号
              example: "admin"
            password:
              type: string
              description: 密码
              example: "admin123"
    responses:
      200:
        description: 创建成功
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
                account:
                  type: string
                role:
                  type: string
            message:
              type: string
      400:
        description: 请求参数错误
      403:
        description: 系统中已存在用户，无法创建初始账号
      500:
        description: 服务器错误
    """
    try:
        # 检查是否已存在用户
        user_stats = db.get_user_stats()
        if user_stats and user_stats.get('total', 0) > 0:
            logger.warning("尝试创建初始账号失败: 系统中已存在用户")
            return jsonify({
                'success': False,
                'error': '系统中已存在用户，无法创建初始账号'
            }), 403
        
        data = request.get_json()
        
        # 验证必填字段
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        account = data.get('account', '').strip()
        password = data.get('password', '')
        
        if not account:
            return jsonify({
                'success': False,
                'error': '账号不能为空'
            }), 400
        
        if not password:
            return jsonify({
                'success': False,
                'error': '密码不能为空'
            }), 400
        
        # 验证账号格式（字母、数字、下划线，4-32位）
        import re
        if not re.match(r'^[a-zA-Z0-9_]{4,32}$', account):
            return jsonify({
                'success': False,
                'error': '账号格式不正确（4-32位字母、数字或下划线）'
            }), 400
        
        # 验证密码长度
        if len(password) < 6 or len(password) > 64:
            return jsonify({
                'success': False,
                'error': '密码长度必须在6-64位之间'
            }), 400
        
        # 创建管理员用户（无过期时间）
        user = db.create_user(
            account=account,
            password=password,
            secret_key_id=None,
            role=ROLE_ADMIN,
            expires_at=None
        )
        
        if not user:
            return jsonify({
                'success': False,
                'error': '账号创建失败'
            }), 500
        
        logger.info(f"初始管理员账号创建成功: {account}")
        
        return jsonify({
            'success': True,
            'data': {
                'id': user['id'],
                'account': user['account'],
                'role': user['role']
            },
            'message': '初始管理员账号创建成功'
        })
        
    except Exception as e:
        logger.error(f"创建初始账号失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - account
            - password
          properties:
            account:
              type: string
              description: 账号
              example: "user123"
            password:
              type: string
              description: 密码
              example: "password123"
    responses:
      200:
        description: 登录成功
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
                account:
                  type: string
                api_wallet:
                  type: string
                wallet_address:
                  type: string
                expires_at:
                  type: string
                  format: date-time
            message:
              type: string
      400:
        description: 请求参数错误
      401:
        description: 账号或密码错误
      403:
        description: 账户未激活或已过期
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        account = data.get('account', '').strip()
        password = data.get('password', '')
        
        if not account:
            return jsonify({
                'success': False,
                'error': '账号不能为空'
            }), 400
        
        if not password:
            return jsonify({
                'success': False,
                'error': '密码不能为空'
            }), 400
        
        # 验证用户
        user = db.authenticate_user(account, password)
        
        if not user:
            return jsonify({
                'success': False,
                'error': '账号或密码错误'
            }), 401
        
        # 检查非管理员用户是否已过期
        if user.get('role') != 'admin':
            expires_at = user.get('expires_at')
            if expires_at and expires_at < datetime.now():
                logger.warning(f"用户登录失败: 账户已过期 - account={account}")
                return jsonify({
                    'success': False,
                    'error': '您的账户已过期，请联系管理员续期',
                    'code': 'USER_EXPIRED'
                }), 403
            
            # 检查用户是否被禁用
            if not user.get('is_active', True):
                logger.warning(f"用户登录失败: 账户已禁用 - account={account}")
                return jsonify({
                    'success': False,
                    'error': '您的账户已被禁用，请联系管理员',
                    'code': 'USER_INACTIVE'
                }), 403
        
        logger.info(f"用户登录成功: {account}")
        
        # 生成 JWT 令牌（将用户过期时间写入 token）
        access_token, refresh_token = generate_tokens(
            user_id=user['id'],
            account=user['account'],
            role=user.get('role', 'user'),
            user_expires_at=user.get('expires_at')
        )
        
        # 格式化返回数据
        response_data = {
            'id': user['id'],
            'account': user['account'],
            'role': user.get('role', 'user'),
            'api_wallet': user.get('api_wallet', ''),
            'wallet_address': user.get('wallet_address', ''),
            'expires_at': user['expires_at'].isoformat() if user.get('expires_at') else None,
            'is_active': user.get('is_active', True),
            'last_login_at': user['last_login_at'].isoformat() if user.get('last_login_at') else None,
            'access_token': access_token,
            'refresh_token': refresh_token
        }
        
        return jsonify({
            'success': True,
            'data': response_data,
            'message': '登录成功'
        })
        
    except Exception as e:
        logger.error(f"用户登录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/refresh-token', methods=['POST'])
def refresh_token():
    """刷新访问令牌
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - refresh_token
          properties:
            refresh_token:
              type: string
              description: 刷新令牌
    responses:
      200:
        description: 刷新成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                access_token:
                  type: string
                refresh_token:
                  type: string
      400:
        description: 请求参数错误
      401:
        description: 刷新令牌无效或已过期
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('refresh_token'):
            return jsonify({
                'success': False,
                'error': '刷新令牌不能为空'
            }), 400
        
        # 验证刷新令牌
        payload = verify_token(data['refresh_token'], 'refresh')
        
        if not payload:
            return jsonify({
                'success': False,
                'error': '刷新令牌无效或已过期',
                'code': 'TOKEN_INVALID'
            }), 401
        
        user_id = payload.get('user_id')
        
        # 获取用户信息
        user = db.get_user_by_id(user_id)
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 401
        
        # 检查用户状态（非管理员检查过期）
        role = user.get('role', 'user')
        expires_at = user.get('expires_at')
        
        if role != 'admin':
            if expires_at and expires_at < datetime.now():
                return jsonify({
                    'success': False,
                    'error': '您的账户已过期，请联系管理员续期',
                    'code': 'USER_EXPIRED'
                }), 403
            
            if not user.get('is_active', True):
                return jsonify({
                    'success': False,
                    'error': '您的账户已被禁用，请联系管理员',
                    'code': 'USER_INACTIVE'
                }), 403
        
        # 生成新的令牌（将用户过期时间写入 token）
        access_token, new_refresh_token = generate_tokens(
            user_id=user['id'],
            account=user['account'],
            role=role,
            user_expires_at=expires_at
        )
        
        logger.info(f"Token 刷新成功: user_id={user_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'access_token': access_token,
                'refresh_token': new_refresh_token
            },
            'message': 'Token 刷新成功'
        })
        
    except Exception as e:
        logger.error(f"Token 刷新失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/verify-token', methods=['GET'])
def verify_token_endpoint():
    """验证访问令牌是否有效
    ---
    tags:
      - Auth
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
    responses:
      200:
        description: 令牌有效
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                user_id:
                  type: integer
                account:
                  type: string
                role:
                  type: string
      401:
        description: 令牌无效或已过期
    """
    from .middleware import get_token_from_request
    
    try:
        token = get_token_from_request()
        
        if not token:
            return jsonify({
                'success': False,
                'error': '未提供认证令牌',
                'code': 'TOKEN_MISSING'
            }), 401
        
        payload = verify_token(token, 'access')
        
        if not payload:
            return jsonify({
                'success': False,
                'error': '认证令牌无效或已过期',
                'code': 'TOKEN_INVALID'
            }), 401
        
        user_id = payload.get('user_id')
        role = payload.get('role')
        user_expires_at = payload.get('user_expires_at')
        
        # 非管理员用户检查账户是否过期（从 JWT 中获取过期时间）
        if role != 'admin' and user_expires_at:
            if datetime.utcnow().timestamp() > user_expires_at:
                return jsonify({
                    'success': False,
                    'error': '您的账户已过期，请联系管理员续期',
                    'code': 'USER_EXPIRED'
                }), 403
        
        return jsonify({
            'success': True,
            'data': {
                'user_id': user_id,
                'account': payload.get('account'),
                'role': role
            }
        })
        
    except Exception as e:
        logger.error(f"Token 验证失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@login_required
def change_password():
    """修改密码
    ---
    tags:
      - Auth
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
            - old_password
            - new_password
          properties:
            old_password:
              type: string
              description: 原密码
              example: "old_password123"
            new_password:
              type: string
              description: 新密码
              example: "new_password456"
    responses:
      200:
        description: 修改成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      400:
        description: 请求参数错误
      401:
        description: 原密码错误
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        # 从 token 获取当前用户 ID
        user_id = get_current_user_id()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password:
            return jsonify({
                'success': False,
                'error': '原密码不能为空'
            }), 400
        
        if not new_password:
            return jsonify({
                'success': False,
                'error': '新密码不能为空'
            }), 400
        
        # 验证新密码长度
        if len(new_password) < 6 or len(new_password) > 64:
            return jsonify({
                'success': False,
                'error': '新密码长度必须在6-64位之间'
            }), 400
        
        # 修改密码
        success = db.change_password(user_id, old_password, new_password)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '原密码错误'
            }), 401
        
        logger.info(f"用户密码修改成功: user_id={user_id}")
        
        return jsonify({
            'success': True,
            'message': '密码修改成功'
        })
        
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/hyperliquid-settings', methods=['GET'])
@login_required
def get_hyperliquid_settings():
    """获取 Hyperliquid API 设置
    ---
    tags:
      - Auth
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
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
                api_wallet:
                  type: string
                wallet_address:
                  type: string
      404:
        description: 用户不存在
      500:
        description: 服务器错误
    """
    try:
        # 从 token 获取当前用户 ID
        user_id = get_current_user_id()
        
        # 获取设置
        settings_data = db.get_hyperliquid_settings(user_id)
        
        if settings_data is None:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': settings_data
        })
        
    except Exception as e:
        logger.error(f"获取 Hyperliquid 设置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/hyperliquid-settings', methods=['POST'])
@login_required
def update_hyperliquid_settings():
    """更新 Hyperliquid API 设置
    ---
    tags:
      - Auth
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
            api_wallet:
              type: string
              description: API 钱包地址
              example: "0x1234567890abcdef1234567890abcdef12345678"
            wallet_address:
              type: string
              description: 钱包地址
              example: "0xabcdef1234567890abcdef1234567890abcdef12"
    responses:
      200:
        description: 更新成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                api_wallet:
                  type: string
                wallet_address:
                  type: string
            message:
              type: string
      400:
        description: 请求参数错误
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        # 从 token 获取当前用户 ID
        user_id = get_current_user_id()
        api_wallet = data.get('api_wallet')
        wallet_address = data.get('wallet_address')
        
        if api_wallet is None and wallet_address is None:
            return jsonify({
                'success': False,
                'error': '至少需要提供 api_wallet 或 wallet_address'
            }), 400
        
        # 验证地址格式（如果提供）
        import re
        eth_address_pattern = r'^0x[a-fA-F0-9]{40}$'
        
        if api_wallet and api_wallet.strip():
            api_wallet = api_wallet.strip()
            if not re.match(eth_address_pattern, api_wallet):
                return jsonify({
                    'success': False,
                    'error': 'API 钱包地址格式不正确'
                }), 400
        
        if wallet_address and wallet_address.strip():
            wallet_address = wallet_address.strip()
            if not re.match(eth_address_pattern, wallet_address):
                return jsonify({
                    'success': False,
                    'error': '钱包地址格式不正确'
                }), 400
        
        # 更新设置
        updated_user = db.update_hyperliquid_settings(
            user_id=user_id,
            api_wallet=api_wallet,
            wallet_address=wallet_address
        )
        
        if not updated_user:
            return jsonify({
                'success': False,
                'error': '更新失败'
            }), 500
        
        logger.info(f"Hyperliquid 设置更新成功: user_id={user_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'api_wallet': updated_user.get('api_wallet', ''),
                'wallet_address': updated_user.get('wallet_address', '')
            },
            'message': '设置更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新 Hyperliquid 设置失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/user', methods=['GET'])
@login_required
def get_current_user_info():
    """获取当前登录用户信息
    ---
    tags:
      - Auth
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
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
                account:
                  type: string
                api_wallet:
                  type: string
                wallet_address:
                  type: string
                expires_at:
                  type: string
                  format: date-time
                is_active:
                  type: boolean
      404:
        description: 用户不存在
      500:
        description: 服务器错误
    """
    try:
        # 从 token 获取当前用户 ID
        user_id = get_current_user_id()
        user = db.get_user_by_id(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 404
        
        # 格式化返回数据
        response_data = {
            'id': user['id'],
            'account': user['account'],
            'role': user.get('role', 'user'),
            'api_wallet': user.get('api_wallet', ''),
            'wallet_address': user.get('wallet_address', ''),
            'expires_at': user['expires_at'].isoformat() if user.get('expires_at') else None,
            'is_active': user.get('is_active', True),
            'created_at': user['created_at'].isoformat() if user.get('created_at') else None,
            'last_login_at': user['last_login_at'].isoformat() if user.get('last_login_at') else None
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/user/<int:user_id>', methods=['GET'])
@login_required
@admin_required
def get_user_info(user_id: int):
    """获取指定用户信息（管理员）
    ---
    tags:
      - Auth
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: user_id
        in: path
        type: integer
        required: true
        description: 用户 ID
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
                account:
                  type: string
                api_wallet:
                  type: string
                wallet_address:
                  type: string
                expires_at:
                  type: string
                  format: date-time
                is_active:
                  type: boolean
      403:
        description: 无权限
      404:
        description: 用户不存在
      500:
        description: 服务器错误
    """
    try:
        user = db.get_user_by_id(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 404
        
        # 格式化返回数据
        response_data = {
            'id': user['id'],
            'account': user['account'],
            'role': user.get('role', 'user'),
            'api_wallet': user.get('api_wallet', ''),
            'wallet_address': user.get('wallet_address', ''),
            'expires_at': user['expires_at'].isoformat() if user.get('expires_at') else None,
            'is_active': user.get('is_active', True),
            'created_at': user['created_at'].isoformat() if user.get('created_at') else None,
            'last_login_at': user['last_login_at'].isoformat() if user.get('last_login_at') else None
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 用户兑换秘钥 API ====================

@auth_bp.route('/api/auth/redeem-key', methods=['POST'])
@login_required
def redeem_secret_key():
    """用户兑换秘钥
    
    用户可以使用秘钥来延长账户有效期或升级身份。
    - 如果用户身份与秘钥身份一致：追加有效期到现有的 expires_at
    - 如果用户已过期：从当前时间开始追加
    - 如果用户是普通用户，秘钥身份是会员：升级为会员并从当前时间开始追加
    ---
    tags:
      - Auth
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
            - secret_key
          properties:
            secret_key:
              type: string
              description: 兑换秘钥
              example: "your-secret-key"
    responses:
      200:
        description: 兑换成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                role:
                  type: string
                  description: 用户当前身份
                expires_at:
                  type: string
                  format: date-time
                  description: 新的过期时间
                added_days:
                  type: integer
                  description: 增加的天数
                role_upgraded:
                  type: boolean
                  description: 是否升级了身份
            message:
              type: string
      400:
        description: 请求参数错误
      403:
        description: 秘钥无效或不适用
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        secret_key = data.get('secret_key', '').strip()
        
        if not secret_key:
            return jsonify({
                'success': False,
                'error': '秘钥不能为空'
            }), 400
        
        # 获取当前用户信息
        user_id = get_current_user_id()
        user = db.get_user_by_id(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 404
        
        user_role = user.get('role', ROLE_USER)
        user_expires_at = user.get('expires_at')
        
        # 管理员不需要兑换秘钥
        if user_role == ROLE_ADMIN:
            return jsonify({
                'success': False,
                'error': '管理员账户无需兑换秘钥'
            }), 400
        
        # 验证秘钥
        secret_key_info = db.validate_secret_key(secret_key)
        if not secret_key_info:
            logger.warning(f"秘钥兑换失败: 秘钥验证失败 - user_id={user_id}")
            return jsonify({
                'success': False,
                'error': '秘钥无效或已被使用'
            }), 403
        
        key_role = secret_key_info['user_role']
        key_expires_days = secret_key_info['expires_days']
        
        # 管理员秘钥不能通过兑换获得
        if key_role == ROLE_ADMIN:
            return jsonify({
                'success': False,
                'error': '此秘钥不支持兑换'
            }), 403
        
        # 计算新的过期时间
        now = datetime.now()
        role_upgraded = False
        new_role = user_role
        
        # 判断是否需要升级身份
        # 普通用户 -> 会员（秘钥身份比用户身份高）
        if user_role == ROLE_USER and key_role == ROLE_MEMBER:
            # 升级为会员，从当前时间开始计算
            role_upgraded = True
            new_role = ROLE_MEMBER
            base_time = now
        elif user_role == key_role:
            # 身份一致，追加到现有过期时间
            # 如果已过期或没有过期时间，从当前时间开始
            if user_expires_at is None or user_expires_at < now:
                base_time = now
            else:
                base_time = user_expires_at
        elif user_role == ROLE_MEMBER and key_role == ROLE_USER:
            # 会员使用普通用户秘钥，仍然追加时间但不降级身份
            if user_expires_at is None or user_expires_at < now:
                base_time = now
            else:
                base_time = user_expires_at
        else:
            # 其他情况（理论上不会发生）
            return jsonify({
                'success': False,
                'error': '秘钥与当前账户身份不匹配'
            }), 403
        
        # 计算新的过期时间
        if key_expires_days > 0:
            new_expires_at = base_time + timedelta(days=key_expires_days)
        else:
            # expires_days 为 0 表示永不过期
            new_expires_at = None
        
        # 更新用户信息
        # 如果需要升级身份
        if role_upgraded:
            db.update_user_role(user_id, new_role)
        
        # 更新过期时间
        db.update_user_expiry(user_id, new_expires_at)
        
        # 标记秘钥为已使用
        db.use_secret_key(secret_key_info['id'], user_id)
        
        logger.info(f"用户兑换秘钥成功: user_id={user_id}, added_days={key_expires_days}, role_upgraded={role_upgraded}")
        
        return jsonify({
            'success': True,
            'data': {
                'role': new_role,
                'expires_at': new_expires_at.isoformat() if new_expires_at else None,
                'added_days': key_expires_days,
                'role_upgraded': role_upgraded
            },
            'message': '秘钥兑换成功' + ('，已升级为会员' if role_upgraded else '')
        })
        
    except Exception as e:
        logger.error(f"秘钥兑换失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 秘钥管理 API ====================

@auth_bp.route('/api/auth/secret-keys', methods=['GET'])
@login_required
@admin_required
def get_secret_keys():
    """获取秘钥列表（管理员权限）
    ---
    tags:
      - SecretKeys
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: is_active
        in: query
        type: boolean
        description: 是否启用筛选
      - name: is_used
        in: query
        type: boolean
        description: 是否已使用筛选
      - name: user_role
        in: query
        type: string
        enum: [user, member, admin]
        description: 用户身份筛选
      - name: limit
        in: query
        type: integer
        default: 100
        description: 每页数量
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
        is_active = request.args.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        
        is_used = request.args.get('is_used')
        if is_used is not None:
            is_used = is_used.lower() == 'true'
        
        user_role = request.args.get('user_role')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        keys = db.get_secret_keys(
            is_active=is_active,
            is_used=is_used,
            user_role=user_role,
            limit=limit,
            offset=offset
        )
        
        # 格式化返回数据
        result = []
        for key in keys:
            result.append({
                'id': key['id'],
                'key_value': key['key_value'],
                'key_name': key.get('key_name', ''),
                'user_role': key['user_role'],
                'expires_days': key['expires_days'],
                'is_used': key.get('is_used', False),
                'used_by_user_id': key.get('used_by_user_id'),
                'is_active': key['is_active'],
                'expires_at': key['expires_at'].isoformat() if key.get('expires_at') else None,
                'created_at': key['created_at'].isoformat() if key.get('created_at') else None
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"获取秘钥列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/secret-keys', methods=['POST'])
@login_required
@admin_required
def create_secret_key():
    """创建秘钥（管理员权限）
    ---
    tags:
      - SecretKeys
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
            key_name:
              type: string
              description: 秘钥名称/备注
            user_role:
              type: string
              enum: [user, member, admin]
              default: user
              description: 使用此秘钥注册的用户身份
            expires_days:
              type: integer
              default: 30
              description: 注册用户的有效天数（0表示永不过期）
            key_value:
              type: string
              description: 指定秘钥值（可选，不指定则自动生成）
    responses:
      200:
        description: 创建成功
      403:
        description: 无权限
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data:
            data = {}
        
        # 从 token 获取当前用户 ID
        user_id = get_current_user_id()
        
        key_name = data.get('key_name', '')
        user_role = data.get('user_role', 'user')
        expires_days = data.get('expires_days', 30)
        key_value = data.get('key_value')
        
        # 验证用户身份
        if user_role not in [ROLE_USER, ROLE_MEMBER, ROLE_ADMIN]:
            return jsonify({
                'success': False,
                'error': '无效的用户身份'
            }), 400
        
        key = db.create_secret_key(
            key_name=key_name,
            user_role=user_role,
            expires_days=expires_days,
            created_by=user_id,
            key_value=key_value
        )
        
        if not key:
            return jsonify({
                'success': False,
                'error': '创建失败，秘钥可能已存在'
            }), 400
        
        logger.info(f"秘钥创建成功: {key_name or key['key_value'][:8]}...")
        
        return jsonify({
            'success': True,
            'data': {
                'id': key['id'],
                'key_value': key['key_value'],
                'key_name': key.get('key_name', ''),
                'user_role': key['user_role'],
                'expires_days': key['expires_days'],
                'is_used': key.get('is_used', False),
                'is_active': key['is_active']
            },
            'message': '秘钥创建成功'
        })
        
    except Exception as e:
        logger.error(f"创建秘钥失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/secret-keys/batch', methods=['POST'])
@login_required
@admin_required
def batch_create_secret_keys():
    """批量创建秘钥（管理员权限）
    ---
    tags:
      - SecretKeys
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
            - count
          properties:
            count:
              type: integer
              description: 创建数量
            key_name_prefix:
              type: string
              description: 名称前缀
            user_role:
              type: string
              enum: [user, member, admin]
              default: user
            expires_days:
              type: integer
              default: 30
    responses:
      200:
        description: 批量创建成功
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
        
        # 从 token 获取当前用户 ID
        user_id = get_current_user_id()
        count = data.get('count')
        
        if not count or count < 1:
            return jsonify({
                'success': False,
                'error': '创建数量必须大于0'
            }), 400
        
        if count > 100:
            return jsonify({
                'success': False,
                'error': '单次创建数量不能超过100'
            }), 400
        
        keys = db.batch_create_secret_keys(
            count=count,
            key_name_prefix=data.get('key_name_prefix', ''),
            user_role=data.get('user_role', 'user'),
            expires_days=data.get('expires_days', 30),
            created_by=user_id
        )
        
        logger.info(f"批量创建秘钥成功: {len(keys)}/{count}")
        
        return jsonify({
            'success': True,
            'data': [{
                'id': k['id'],
                'key_value': k['key_value'],
                'key_name': k.get('key_name', ''),
                'user_role': k['user_role']
            } for k in keys],
            'message': f'成功创建 {len(keys)} 个秘钥'
        })
        
    except Exception as e:
        logger.error(f"批量创建秘钥失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/secret-keys/<int:key_id>', methods=['GET'])
@login_required
@admin_required
def get_secret_key(key_id: int):
    """获取秘钥详情（管理员权限）
    ---
    tags:
      - SecretKeys
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: key_id
        in: path
        type: integer
        required: true
        description: 秘钥 ID
    responses:
      200:
        description: 获取成功
      403:
        description: 无权限
      404:
        description: 秘钥不存在
      500:
        description: 服务器错误
    """
    try:
        key = db.get_secret_key(key_id)
        
        if not key:
            return jsonify({
                'success': False,
                'error': '秘钥不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'id': key['id'],
                'key_value': key['key_value'],
                'key_name': key.get('key_name', ''),
                'user_role': key['user_role'],
                'expires_days': key['expires_days'],
                'is_used': key.get('is_used', False),
                'used_by_user_id': key.get('used_by_user_id'),
                'is_active': key['is_active'],
                'expires_at': key['expires_at'].isoformat() if key.get('expires_at') else None,
                'created_by': key.get('created_by'),
                'created_at': key['created_at'].isoformat() if key.get('created_at') else None
            }
        })
        
    except Exception as e:
        logger.error(f"获取秘钥详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/secret-keys/<int:key_id>', methods=['PUT'])
@login_required
@admin_required
def update_secret_key(key_id: int):
    """更新秘钥（管理员权限）
    ---
    tags:
      - SecretKeys
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: key_id
        in: path
        type: integer
        required: true
        description: 秘钥 ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            key_name:
              type: string
            user_role:
              type: string
              enum: [user, member, admin]
            expires_days:
              type: integer
            is_active:
              type: boolean
    responses:
      200:
        description: 更新成功
      403:
        description: 无权限
      404:
        description: 秘钥不存在
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        
        if not data:
            data = {}
        
        key = db.update_secret_key(
            key_id=key_id,
            key_name=data.get('key_name'),
            user_role=data.get('user_role'),
            expires_days=data.get('expires_days'),
            is_active=data.get('is_active')
        )
        
        if not key:
            return jsonify({
                'success': False,
                'error': '秘钥不存在或更新失败'
            }), 404
        
        logger.info(f"秘钥更新成功: id={key_id}")
        
        return jsonify({
            'success': True,
            'data': {
                'id': key['id'],
                'key_value': key['key_value'],
                'key_name': key.get('key_name', ''),
                'user_role': key['user_role'],
                'expires_days': key['expires_days'],
                'is_used': key.get('is_used', False),
                'used_by_user_id': key.get('used_by_user_id'),
                'is_active': key['is_active']
            },
            'message': '更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新秘钥失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/secret-keys/<int:key_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_secret_key(key_id: int):
    """删除秘钥（管理员权限）
    ---
    tags:
      - SecretKeys
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: key_id
        in: path
        type: integer
        required: true
        description: 秘钥 ID
    responses:
      200:
        description: 删除成功
      403:
        description: 无权限
      404:
        description: 秘钥不存在
      500:
        description: 服务器错误
    """
    try:
        success = db.delete_secret_key(key_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '秘钥不存在'
            }), 404
        
        logger.info(f"秘钥删除成功: id={key_id}")
        
        return jsonify({
            'success': True,
            'message': '删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除秘钥失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/secret-keys/stats', methods=['GET'])
@login_required
@admin_required
def get_secret_key_stats():
    """获取秘钥统计信息（管理员权限）
    ---
    tags:
      - SecretKeys
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
        stats = db.get_secret_key_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"获取秘钥统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 用户管理 API（管理员） ====================

@auth_bp.route('/api/auth/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    """获取用户列表（管理员权限）
    ---
    tags:
      - UserManagement
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: role
        in: query
        type: string
        enum: [user, member, admin]
        description: 身份筛选
      - name: is_active
        in: query
        type: boolean
        description: 激活状态筛选
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
        is_active = request.args.get('is_active')
        if is_active is not None:
            is_active = is_active.lower() == 'true'
        
        role = request.args.get('role')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        users = db.get_users(
            role=role,
            is_active=is_active,
            limit=limit,
            offset=offset
        )
        
        # 格式化返回数据
        result = []
        for u in users:
            result.append({
                'id': u['id'],
                'account': u['account'],
                'role': u.get('role', 'user'),
                'api_wallet': u.get('api_wallet', ''),
                'wallet_address': u.get('wallet_address', ''),
                'expires_at': u['expires_at'].isoformat() if u.get('expires_at') else None,
                'is_active': u.get('is_active', True),
                'created_at': u['created_at'].isoformat() if u.get('created_at') else None,
                'last_login_at': u['last_login_at'].isoformat() if u.get('last_login_at') else None
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/users/<int:target_user_id>/role', methods=['PUT'])
@login_required
@admin_required
def update_user_role(target_user_id: int):
    """更新用户身份（管理员权限）
    ---
    tags:
      - UserManagement
    parameters:
      - name: Authorization
        in: header
        type: string
        required: true
        description: Bearer Token
      - name: target_user_id
        in: path
        type: integer
        required: true
        description: 目标用户 ID
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - role
          properties:
            role:
              type: string
              enum: [user, member, admin]
              description: 新身份
    responses:
      200:
        description: 更新成功
      403:
        description: 无权限
      404:
        description: 用户不存在
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
        
        role = data.get('role')
        
        if not role:
            return jsonify({
                'success': False,
                'error': '角色不能为空'
            }), 400
        
        success = db.update_user_role(target_user_id, role)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '用户不存在或更新失败'
            }), 404
        
        logger.info(f"用户身份更新成功: user_id={target_user_id}, role={role}")
        
        return jsonify({
            'success': True,
            'message': '用户身份更新成功'
        })
        
    except Exception as e:
        logger.error(f"更新用户身份失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@auth_bp.route('/api/auth/users/stats', methods=['GET'])
@login_required
@admin_required
def get_user_stats():
    """获取用户统计信息（管理员权限）
    ---
    tags:
      - UserManagement
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
        stats = db.get_user_stats()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"获取用户统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
