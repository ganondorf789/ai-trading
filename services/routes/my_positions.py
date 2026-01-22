"""
我的仓位管理 API (C端API)
提供仓位查询、加仓减仓、平仓等操作

与跟单机器人通过 Redis 通信：
- 仓位数据从 Redis 缓存读取（由跟单机器人定期更新）
- 操作指令通过 Redis Pub/Sub 发送给跟单机器人执行
"""
from flask import Blueprint, jsonify, request
import logging
import json

from config.settings import settings
from .db import db

logger = logging.getLogger(__name__)

my_positions_bp = Blueprint('my_positions', __name__)

# Redis 相关常量（与 position_copy_trading.py 保持一致）
REDIS_ADJUST_CHANNEL = "position_tracking_adjust"
REDIS_CLOSE_CHANNEL = "position_tracking_close"
REDIS_MY_POSITIONS_KEY = "copy_trading:my_positions"
REDIS_MY_BALANCE_KEY = "copy_trading:my_balance"

# 全局 Redis 客户端
_redis_client = None


def get_redis_client():
    """
    获取 Redis 客户端（懒加载单例）
    """
    global _redis_client
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        import redis
        _redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=True
        )
        _redis_client.ping()
        logger.info(f"Redis 已连接: {settings.redis.host}:{settings.redis.port}")
        return _redis_client
    except ImportError:
        logger.warning("Redis 库未安装")
        return None
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}")
        _redis_client = None
        return None


def get_cached_positions():
    """
    从 Redis 缓存获取当前仓位（由跟单机器人定期更新）
    
    Returns:
        (positions_list, available_balance) 或 (None, None) 如果缓存不存在
    """
    redis_client = get_redis_client()
    
    if redis_client is None:
        return None, None
    
    try:
        # 读取仓位
        positions_json = redis_client.get(REDIS_MY_POSITIONS_KEY)
        balance_str = redis_client.get(REDIS_MY_BALANCE_KEY)
        
        if positions_json is None:
            return None, None
        
        positions = json.loads(positions_json)
        balance = float(balance_str) if balance_str else 0.0
        
        return positions, balance
    except Exception as e:
        logger.debug(f"从 Redis 读取仓位缓存失败: {e}")
        return None, None


def notify_adjust_position(tracking_id: int, ratio: float = None, size: float = None, direction: str = None):
    """
    发送加仓/减仓通知到 Redis，机器人收到后立即执行
    
    Args:
        tracking_id: 跟单记录ID
        ratio: 调整比例（百分比），如 50 表示调整当前仓位的 50%
        size: 调整数量（直接指定数量）
        direction: 下单方向 ('long' 或 'short')
                   - 与当前持仓同向 = 加仓
                   - 与当前持仓反向 = 减仓
        
    Returns:
        是否发送成功
    """
    redis_client = get_redis_client()
    
    if redis_client is None:
        logger.warning("Redis 未连接，无法发送调仓通知")
        return False
    
    if ratio is None and size is None:
        logger.warning("调仓通知需要指定 ratio 或 size")
        return False
    
    try:
        message = {
            "tracking_id": tracking_id,
        }
        if ratio is not None:
            message["ratio"] = ratio
        if size is not None:
            message["size"] = size
        if direction is not None:
            message["direction"] = direction
            
        redis_client.publish(REDIS_ADJUST_CHANNEL, json.dumps(message))
        logger.info(f"已发送调仓通知: tracking_id={tracking_id}, ratio={ratio}, size={size}, direction={direction}")
        return True
    except Exception as e:
        logger.warning(f"发送调仓通知失败: {e}")
        return False


def notify_close_position(symbol: str = None, tracking_id: int = None):
    """
    发送平仓通知到 Redis，机器人收到后立即执行平仓
    
    Args:
        symbol: 币种（直接指定要平仓的币种）
        tracking_id: 跟单记录ID（根据跟单记录平仓）
        
    Returns:
        是否发送成功
    """
    redis_client = get_redis_client()
    
    if redis_client is None:
        logger.warning("Redis 未连接，无法发送平仓通知")
        return False
    
    if symbol is None and tracking_id is None:
        logger.warning("平仓通知需要指定 symbol 或 tracking_id")
        return False
    
    try:
        message = {}
        if symbol is not None:
            message["symbol"] = symbol
        if tracking_id is not None:
            message["tracking_id"] = tracking_id
            
        redis_client.publish(REDIS_CLOSE_CHANNEL, json.dumps(message))
        logger.info(f"已发送平仓通知: symbol={symbol}, tracking_id={tracking_id}")
        return True
    except Exception as e:
        logger.warning(f"发送平仓通知失败: {e}")
        return False


# ==================== API 路由 ====================

@my_positions_bp.route('/api/my-positions', methods=['GET'])
def get_my_positions():
    """
    获取当前所有仓位
    
    从 Redis 缓存读取（由跟单机器人定期更新）
    
    Returns:
        {
            "success": true,
            "data": {
                "positions": [...],
                "available_balance": 1000.0,
                "stats": {
                    "total_positions": 3,
                    "total_value": 5000.0,
                    "total_unrealized_pnl": 100.0,
                    "long_count": 2,
                    "short_count": 1
                }
            }
        }
    """
    try:
        # 从 Redis 缓存获取仓位和余额
        positions, available_balance = get_cached_positions()
        
        if positions is None:
            return jsonify({
                'success': False,
                'error': '仓位缓存不可用，请确保跟单机器人正在运行'
            }), 503  # Service Unavailable
        
        # 获取当前活跃的跟单配置
        trackings = db.get_active_position_trackings()
        
        # 构建 symbol -> tracking 映射
        tracking_by_symbol = {}
        for t in trackings:
            symbol = t.get('symbol', '')
            if symbol:
                tracking_by_symbol[symbol] = t
        
        # 丰富仓位数据（关联跟单配置）
        enriched_positions = []
        total_value = 0.0
        total_unrealized_pnl = 0.0
        long_count = 0
        short_count = 0
        
        for pos in positions:
            symbol = pos.get('symbol', '')
            side = pos.get('side', 'long')
            size = pos.get('size', 0)
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', 0)
            unrealized_pnl = pos.get('unrealized_pnl', 0)
            margin_used = pos.get('margin_used', 0)
            leverage = pos.get('leverage', 1)
            
            # 计算仓位价值
            position_value = size * current_price if current_price else size * entry_price
            total_value += position_value
            total_unrealized_pnl += unrealized_pnl
            
            if side == 'long':
                long_count += 1
            else:
                short_count += 1
            
            # 查找对应的跟单配置
            tracking = tracking_by_symbol.get(symbol)
            
            enriched_pos = {
                'symbol': symbol,
                'side': side,
                'size': size,
                'entry_price': entry_price,
                'current_price': current_price,
                'leverage': leverage,
                'margin_used': margin_used,
                'unrealized_pnl': unrealized_pnl,
                'position_value': position_value,
                'pnl_percent': (unrealized_pnl / margin_used * 100) if margin_used > 0 else 0,
                # 跟单关联信息
                'tracking_id': tracking.get('id') if tracking else None,
                'target_address': tracking.get('target_address', '') if tracking else None,
                'target_name': tracking.get('target_name', '') if tracking else None,
                'has_tracking': tracking is not None,
            }
            enriched_positions.append(enriched_pos)
        
        return jsonify({
            'success': True,
            'data': {
                'positions': enriched_positions,
                'available_balance': available_balance,
                'stats': {
                    'total_positions': len(positions),
                    'total_value': total_value,
                    'total_unrealized_pnl': total_unrealized_pnl,
                    'long_count': long_count,
                    'short_count': short_count,
                }
            }
        })
    except Exception as e:
        logger.error(f"获取仓位失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@my_positions_bp.route('/api/my-positions/adjust', methods=['POST'])
def adjust_position():
    """
    加仓/减仓
    
    Body (JSON):
        - symbol: str, 币种（必填）
        - direction: str, 操作方向 'add' (加仓) 或 'reduce' (减仓)（必填）
        - ratio: float, 调整比例（百分比），如 50 表示调整当前仓位的 50%（与 size 二选一）
        - size: float, 调整数量（直接指定数量）（与 ratio 二选一）
        - tracking_id: int, 跟单记录ID（可选，不传则自动查找）
    
    Returns:
        {
            "success": true,
            "message": "加仓请求已提交"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400
        
        symbol = data.get('symbol', '').strip()
        direction = data.get('direction', '').strip().lower()
        ratio = data.get('ratio')
        size = data.get('size')
        tracking_id = data.get('tracking_id')
        
        # 参数验证
        if not symbol:
            return jsonify({
                'success': False,
                'error': '币种 (symbol) 不能为空'
            }), 400
        
        if direction not in ('add', 'reduce'):
            return jsonify({
                'success': False,
                'error': '操作方向 (direction) 必须是 "add" 或 "reduce"'
            }), 400
        
        if ratio is None and size is None:
            return jsonify({
                'success': False,
                'error': '请指定调整比例 (ratio) 或调整数量 (size)'
            }), 400
        
        # 如果没有提供 tracking_id，自动查找
        if tracking_id is None:
            # 获取当前活跃的跟单配置
            trackings = db.get_active_position_trackings()
            for t in trackings:
                if t.get('symbol') == symbol:
                    tracking_id = t.get('id')
                    break
            
            if tracking_id is None:
                return jsonify({
                    'success': False,
                    'error': f'未找到 {symbol} 的活跃跟单配置'
                }), 404
        
        # 获取跟单配置
        tracking = db.get_position_tracking(tracking_id)
        if not tracking:
            return jsonify({
                'success': False,
                'error': f'跟单记录 #{tracking_id} 不存在'
            }), 404
        
        # 检查跟单状态
        if tracking.get('status') != 'active':
            return jsonify({
                'success': False,
                'error': f'{symbol} 跟单状态为 {tracking.get("status")}，无法操作'
            }), 400
        
        # 计算实际下单方向：加仓=同向，减仓=反向
        current_side = tracking.get('my_side', 'long')
        if direction == 'add':
            order_direction = current_side  # 加仓：与当前仓位同向
        else:
            order_direction = 'short' if current_side == 'long' else 'long'  # 减仓：反向
        
        # 发送调仓通知到 Redis
        success = notify_adjust_position(
            tracking_id=tracking_id,
            ratio=float(ratio) if ratio is not None else None,
            size=float(size) if size is not None else None,
            direction=order_direction
        )
        
        action_name = "加仓" if direction == 'add' else "减仓"
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'tracking_id': tracking_id,
                    'symbol': symbol,
                    'action': action_name,
                    'ratio': ratio,
                    'size': size,
                    'order_direction': order_direction,
                },
                'message': f'{symbol} {action_name}请求已提交，机器人将立即执行'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Redis 未连接或发送失败，请检查配置'
            }), 503
        
    except Exception as e:
        logger.error(f"加仓减仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@my_positions_bp.route('/api/my-positions/<symbol>/close', methods=['POST'])
def close_position(symbol: str):
    """
    平仓指定币种的仓位
    
    Args:
        symbol: 币种
    
    Body (JSON, 可选):
        - tracking_id: int, 跟单记录ID（可选，不传则自动查找）
    
    Returns:
        {
            "success": true,
            "message": "平仓请求已提交"
        }
    """
    try:
        data = request.get_json() or {}
        tracking_id = data.get('tracking_id')
        
        if not symbol:
            return jsonify({
                'success': False,
                'error': '币种不能为空'
            }), 400
        
        # 发送平仓通知到 Redis（优先使用 symbol）
        success = notify_close_position(symbol=symbol, tracking_id=tracking_id)
        
        if success:
            return jsonify({
                'success': True,
                'data': {
                    'symbol': symbol,
                    'tracking_id': tracking_id,
                },
                'message': f'{symbol} 平仓请求已提交，机器人将立即执行'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Redis 未连接或发送失败，请检查配置'
            }), 503
        
    except Exception as e:
        logger.error(f"平仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@my_positions_bp.route('/api/my-positions/close-all', methods=['POST'])
def close_all_positions():
    """
    全部平仓
    
    Body (JSON, 可选):
        - symbols: list, 要平仓的币种列表（可选，不传则平仓所有）
    
    Returns:
        {
            "success": true,
            "data": {
                "success_count": 3,
                "fail_count": 0,
                "closed_symbols": ["BTC", "ETH", "SOL"]
            },
            "message": "全部平仓请求已提交"
        }
    """
    try:
        data = request.get_json() or {}
        specified_symbols = data.get('symbols')  # 可选：指定要平仓的币种
        
        # 从 Redis 缓存获取仓位
        positions, _ = get_cached_positions()
        
        if positions is None:
            return jsonify({
                'success': False,
                'error': '仓位缓存不可用，请确保跟单机器人正在运行'
            }), 503
        
        if not positions:
            return jsonify({
                'success': True,
                'data': {
                    'success_count': 0,
                    'fail_count': 0,
                    'closed_symbols': []
                },
                'message': '当前没有可平仓的仓位'
            })
        
        # 筛选要平仓的仓位
        symbols_to_close = []
        for pos in positions:
            symbol = pos.get('symbol', '')
            if specified_symbols:
                # 如果指定了币种列表，只平仓指定的
                if symbol in specified_symbols:
                    symbols_to_close.append(symbol)
            else:
                # 否则平仓所有
                symbols_to_close.append(symbol)
        
        if not symbols_to_close:
            return jsonify({
                'success': True,
                'data': {
                    'success_count': 0,
                    'fail_count': 0,
                    'closed_symbols': []
                },
                'message': '没有找到匹配的仓位'
            })
        
        # 逐个发送平仓通知
        success_count = 0
        fail_count = 0
        closed_symbols = []
        failed_symbols = []
        
        for symbol in symbols_to_close:
            success = notify_close_position(symbol=symbol)
            if success:
                success_count += 1
                closed_symbols.append(symbol)
            else:
                fail_count += 1
                failed_symbols.append(symbol)
        
        if success_count > 0:
            return jsonify({
                'success': True,
                'data': {
                    'success_count': success_count,
                    'fail_count': fail_count,
                    'closed_symbols': closed_symbols,
                    'failed_symbols': failed_symbols if failed_symbols else None,
                },
                'message': f'已提交 {success_count} 个平仓请求，机器人将立即执行'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Redis 未连接或发送失败，请检查配置'
            }), 503
        
    except Exception as e:
        logger.error(f"全部平仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@my_positions_bp.route('/api/my-positions/balance', methods=['GET'])
def get_my_balance():
    """
    获取账户余额
    
    Returns:
        {
            "success": true,
            "data": {
                "available_balance": 1000.0
            }
        }
    """
    try:
        # 从 Redis 缓存获取余额
        _, available_balance = get_cached_positions()
        
        if available_balance is None:
            return jsonify({
                'success': False,
                'error': '余额缓存不可用，请确保跟单机器人正在运行'
            }), 503
        
        return jsonify({
            'success': True,
            'data': {
                'available_balance': available_balance
            }
        })
    except Exception as e:
        logger.error(f"获取余额失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
