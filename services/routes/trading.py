"""
C端交易 API 路由
提供用户交易相关的 API 接口
"""
from flask import Blueprint, jsonify, request
import logging

from clients.hyperliquid_client import HyperliquidClient
from services.routes.db import db
from config.settings import settings

logger = logging.getLogger(__name__)

trading_bp = Blueprint('trading', __name__)

# 全局客户端实例（延迟初始化）
_client: HyperliquidClient = None


def _extract_order_data(result: dict) -> dict:
    """
    从 Hyperliquid API 响应中提取核心数据，简化嵌套结构
    
    原始响应格式:
    {
        "status": "ok",
        "response": {
            "type": "order",
            "data": {
                "statuses": [...]
            }
        }
    }
    
    提取后:
    {
        "statuses": [...]
    }
    """
    if result is None:
        return None
    
    try:
        # 提取 response.data
        if isinstance(result, dict):
            if 'response' in result and isinstance(result['response'], dict):
                response = result['response']
                if 'data' in response:
                    return response['data']
            # 如果已经是简化格式，直接返回
            if 'statuses' in result:
                return result
        return result
    except Exception:
        return result


def _extract_order_data_list(results: list) -> list:
    """
    批量提取订单数据
    """
    if results is None:
        return []
    return [_extract_order_data(r) for r in results]


def get_client() -> HyperliquidClient:
    """
    获取 HyperliquidClient 实例（单例模式）
    使用 config/settings.py 中的配置:
        - HYPERLIQUID_PRIVATE_KEY: 钱包私钥
        - HYPERLIQUID_WALLET_ADDRESS: 钱包地址（可选）
        - TESTNET_MODE: 是否使用测试网（可选，默认 false）
    """
    global _client
    if _client is None:
        private_key = settings.hyperliquid.private_key
        wallet_address = settings.hyperliquid.wallet_address
        testnet = settings.system.testnet_mode
        
        if not private_key:
            raise ValueError("未配置 HYPERLIQUID_PRIVATE_KEY 环境变量")
        
        _client = HyperliquidClient(
            private_key=private_key,
            wallet_address=wallet_address,
            testnet=testnet
        )
        logger.info(f"HyperliquidClient 初始化完成，钱包地址: {_client.wallet_address}")
    
    return _client


# ==================== 市场数据 API ====================

@trading_bp.route('/api/trading/meta', methods=['GET'])
def get_market_meta():
    """获取市场元数据
    ---
    tags:
      - Trading - Market
    responses:
      200:
        description: 市场元数据
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        testnet = settings.system.testnet_mode
        api_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        info = Info(api_url, skip_ws=True)
        meta = info.meta()
        
        return jsonify({
            'success': True,
            'data': meta,
            'count': len(meta.get('universe', []))
        })
        
    except Exception as e:
        logger.error(f"获取市场元数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/mids', methods=['GET'])
def get_all_mids():
    """获取所有交易对中间价
    ---
    tags:
      - Trading - Market
    responses:
      200:
        description: 中间价字典
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        # 使用只读客户端，无需私钥
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        testnet = settings.system.testnet_mode
        api_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        info = Info(api_url, skip_ws=True)
        mids = info.all_mids()
        
        # 转换为 float
        mids_float = {k: float(v) for k, v in mids.items()}
        
        return jsonify({
            'success': True,
            'data': mids_float,
            'count': len(mids_float)
        })
        
    except Exception as e:
        logger.error(f"获取中间价失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/mids/<symbol>', methods=['GET'])
def get_mid_price(symbol: str):
    """获取指定交易对中间价
    ---
    tags:
      - Trading - Market
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
    responses:
      200:
        description: 中间价
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      404:
        description: 交易对不存在
      500:
        description: 服务器错误
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        testnet = settings.system.testnet_mode
        api_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        info = Info(api_url, skip_ws=True)
        mids = info.all_mids()
        
        if symbol not in mids:
            return jsonify({
                'success': False,
                'error': f'未找到交易对 {symbol}'
            }), 404
        
        return jsonify({
            'success': True,
            'data': {
                'symbol': symbol,
                'mid_price': float(mids[symbol])
            }
        })
        
    except Exception as e:
        logger.error(f"获取中间价失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 仓位 API ====================

@trading_bp.route('/api/trading/positions', methods=['GET'])
def get_positions():
    """获取当前所有仓位
    ---
    tags:
      - Trading - Positions
    responses:
      200:
        description: 仓位列表
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
                  symbol:
                    type: string
                  side:
                    type: string
                  size:
                    type: number
                  entry_price:
                    type: number
                  current_price:
                    type: number
                  mark_price:
                    type: number
                    description: 标记价格（中间价）
                  leverage:
                    type: integer
                  unrealized_pnl:
                    type: number
                  liquidation_price:
                    type: number
                  liquidation_price_usdc:
                    type: number
                    description: 清算价格（USDC）
                  position_value:
                    type: number
                    description: 仓位价值（USDC）
                  margin_used:
                    type: number
                  tracking_id:
                    type: integer
                    description: 跟单ID
                  target_address:
                    type: string
                    description: 跟单目标地址
                  target_name:
                    type: string
                    description: 跟单目标名称
                  has_tracking:
                    type: boolean
                    description: 是否有跟单
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        positions = client.get_positions()
        
        # 获取所有交易对的中间价（标记价格）
        all_mids = client.get_all_mids()
        
        # 获取所有活跃的跟单记录，用于匹配仓位
        active_trackings = db.get_active_position_trackings()
        
        # 构建 symbol -> tracking 的映射（只取活跃的跟单）
        tracking_map = {}
        for tracking in active_trackings:
            symbol = tracking.get('symbol')
            if symbol and symbol not in tracking_map:
                tracking_map[symbol] = tracking
        
        positions_data = []
        for p in positions:
            # 查找该仓位对应的跟单记录
            tracking = tracking_map.get(p.symbol)
            
            # 获取标记价格（中间价）
            mark_price = float(all_mids.get(p.symbol, 0))
            
            # 计算仓位价值（USDC）= 仓位数量 * 标记价格
            position_value = p.size * mark_price if mark_price > 0 else p.size * p.current_price
            
            # 清算价格（USDC）- 直接使用API返回的清算价格
            liquidation_price_usdc = p.liquidation_price
            
            position_info = {
                'symbol': p.symbol,
                'side': p.side.value,
                'size': p.size,
                'entry_price': p.entry_price,
                'current_price': p.current_price,
                'mark_price': mark_price,
                'leverage': p.leverage,
                'unrealized_pnl': p.unrealized_pnl,
                'liquidation_price': p.liquidation_price,
                'liquidation_price_usdc': liquidation_price_usdc,
                'position_value': position_value,
                'margin_used': p.margin_used,
                # 跟单相关字段
                'tracking_id': tracking.get('id') if tracking else None,
                'target_address': tracking.get('target_address') if tracking else None,
                'target_name': tracking.get('target_name') if tracking else None,
                'has_tracking': tracking is not None
            }
            positions_data.append(position_info)
        
        return jsonify({
            'success': True,
            'data': positions_data,
            'count': len(positions_data)
        })
        
    except Exception as e:
        logger.error(f"获取仓位失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/positions/<symbol>', methods=['GET'])
def get_position(symbol: str):
    """获取指定交易对仓位
    ---
    tags:
      - Trading - Positions
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
    responses:
      200:
        description: 仓位信息
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        position = client.get_position(symbol)
        
        if position is None:
            return jsonify({
                'success': True,
                'data': None,
                'message': f'未找到 {symbol} 的仓位'
            })
        
        position_data = {
            'symbol': position.symbol,
            'side': position.side.value,
            'size': position.size,
            'entry_price': position.entry_price,
            'current_price': position.current_price,
            'leverage': position.leverage,
            'unrealized_pnl': position.unrealized_pnl,
            'liquidation_price': position.liquidation_price,
            'margin_used': position.margin_used
        }
        
        return jsonify({
            'success': True,
            'data': position_data
        })
        
    except Exception as e:
        logger.error(f"获取仓位失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 平仓 API ====================

@trading_bp.route('/api/trading/positions/<symbol>/close', methods=['POST'])
def close_position(symbol: str):
    """市价平仓
    ---
    tags:
      - Trading - Positions
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            slippage:
              type: number
              default: 0.01
              description: 滑点容忍度
    responses:
      200:
        description: 平仓成功
      404:
        description: 仓位不存在
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        
        data = request.get_json() or {}
        slippage = data.get('slippage', 0.01)
        
        result = client.close_position(symbol, slippage=slippage)
        
        if result is None:
            return jsonify({
                'success': False,
                'error': f'未找到 {symbol} 的仓位'
            }), 404
        
        return jsonify({
            'success': True,
            'data': _extract_order_data(result),
            'message': f'{symbol} 市价平仓成功'
        })
        
    except Exception as e:
        logger.error(f"市价平仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/positions/<symbol>/close-limit', methods=['POST'])
def close_position_limit(symbol: str):
    """限价平仓
    ---
    tags:
      - Trading - Positions
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - price
          properties:
            price:
              type: number
              description: 限价
            size:
              type: number
              description: 平仓数量
            post_only:
              type: boolean
              default: false
              description: 是否只做maker
    responses:
      200:
        description: 平仓订单已提交
      400:
        description: 缺少必填参数
      404:
        description: 仓位不存在
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        
        data = request.get_json()
        if not data or 'price' not in data:
            return jsonify({
                'success': False,
                'error': '缺少必填参数 price'
            }), 400
        
        price = float(data['price'])
        size = float(data['size']) if 'size' in data else None
        post_only = data.get('post_only', False)
        
        result = client.close_position_limit(
            symbol=symbol,
            price=price,
            size=size,
            post_only=post_only
        )
        
        if result is None:
            return jsonify({
                'success': False,
                'error': f'未找到 {symbol} 的仓位'
            }), 404
        
        return jsonify({
            'success': True,
            'data': _extract_order_data(result),
            'message': f'{symbol} 限价平仓订单已提交'
        })
        
    except Exception as e:
        logger.error(f"限价平仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/positions/close-all', methods=['POST'])
def close_all_positions():
    """市价平掉所有仓位
    ---
    tags:
      - Trading - Positions
    responses:
      200:
        description: 平仓结果列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        results = client.close_all_positions()
        
        return jsonify({
            'success': True,
            'data': _extract_order_data_list(results),
            'count': len(results),
            'message': f'已平掉 {len(results)} 个仓位'
        })
        
    except Exception as e:
        logger.error(f"平掉所有仓位失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 止盈止损 API ====================

@trading_bp.route('/api/trading/positions/<symbol>/tp-sl', methods=['POST'])
def set_position_tp_sl(symbol: str):
    """设置仓位止盈止损
    ---
    tags:
      - Trading - Positions
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            tp_trigger_price:
              type: number
              description: 止盈触发价格
            tp_limit_price:
              type: number
              description: 止盈限价
            tp_size:
              type: number
              description: 止盈数量
            sl_trigger_price:
              type: number
              description: 止损触发价格
            sl_limit_price:
              type: number
              description: 止损限价
            sl_size:
              type: number
              description: 止损数量
    responses:
      200:
        description: 设置成功
      400:
        description: 参数错误
      404:
        description: 仓位不存在
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        
        data = request.get_json() or {}
        
        # 至少需要设置一个 TP 或 SL
        if 'tp_trigger_price' not in data and 'sl_trigger_price' not in data:
            return jsonify({
                'success': False,
                'error': '至少需要设置 tp_trigger_price 或 sl_trigger_price'
            }), 400
        
        result = client.set_position_tp_sl(
            symbol=symbol,
            tp_trigger_price=float(data['tp_trigger_price']) if 'tp_trigger_price' in data else None,
            tp_limit_price=float(data['tp_limit_price']) if 'tp_limit_price' in data else None,
            tp_size=float(data['tp_size']) if 'tp_size' in data else None,
            sl_trigger_price=float(data['sl_trigger_price']) if 'sl_trigger_price' in data else None,
            sl_limit_price=float(data['sl_limit_price']) if 'sl_limit_price' in data else None,
            sl_size=float(data['sl_size']) if 'sl_size' in data else None
        )
        
        # 简化响应结构
        simplified_result = {
            'tp': _extract_order_data(result.get('tp')) if result.get('tp') else None,
            'sl': _extract_order_data(result.get('sl')) if result.get('sl') else None
        }
        
        return jsonify({
            'success': True,
            'data': simplified_result,
            'message': f'{symbol} 止盈止损设置成功'
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"设置止盈止损失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 订单 API ====================

@trading_bp.route('/api/trading/orders', methods=['GET'])
def get_open_orders():
    """获取未成交订单
    ---
    tags:
      - Trading - Orders
    parameters:
      - name: symbol
        in: query
        type: string
        description: 筛选特定交易对
    responses:
      200:
        description: 订单列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        orders = client.get_open_orders()
        
        # 可选：按 symbol 筛选
        symbol = request.args.get('symbol')
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        orders_data = [{
            'id': o.id,
            'symbol': o.symbol,
            'side': o.side.value,
            'order_type': o.order_type.value,
            'size': o.size,
            'price': o.price,
            'status': o.status.value,
            'created_at': o.created_at.isoformat() if o.created_at else None
        } for o in orders]
        
        return jsonify({
            'success': True,
            'data': orders_data,
            'count': len(orders_data)
        })
        
    except Exception as e:
        logger.error(f"获取未成交订单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/orders/<symbol>/<int:order_id>', methods=['DELETE'])
def cancel_order(symbol: str, order_id: int):
    """取消订单
    ---
    tags:
      - Trading - Orders
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
      - name: order_id
        in: path
        type: integer
        required: true
        description: 订单ID
    responses:
      200:
        description: 取消成功
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        result = client.cancel_order(symbol, order_id)
        
        return jsonify({
            'success': True,
            'data': _extract_order_data(result),
            'message': f'订单 {order_id} 已取消'
        })
        
    except Exception as e:
        logger.error(f"取消订单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/orders/<symbol>', methods=['DELETE'])
def cancel_orders_by_symbol(symbol: str):
    """取消指定交易对所有订单
    ---
    tags:
      - Trading - Orders
    parameters:
      - name: symbol
        in: path
        type: string
        required: true
        description: 交易对符号
    responses:
      200:
        description: 取消成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        results = client.cancel_orders_by_symbol(symbol)
        
        return jsonify({
            'success': True,
            'data': _extract_order_data_list(results),
            'count': len(results),
            'message': f'{symbol} 的 {len(results)} 个订单已取消'
        })
        
    except Exception as e:
        logger.error(f"取消订单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/orders', methods=['DELETE'])
def cancel_all_orders():
    """取消所有订单
    ---
    tags:
      - Trading - Orders
    responses:
      200:
        description: 取消成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            count:
              type: integer
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        results = client.cancel_all_orders()
        
        return jsonify({
            'success': True,
            'data': _extract_order_data_list(results),
            'count': len(results),
            'message': f'已取消 {len(results)} 个订单'
        })
        
    except Exception as e:
        logger.error(f"取消所有订单失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 账户信息 API ====================

@trading_bp.route('/api/trading/account', methods=['GET'])
def get_account_info():
    """获取账户信息
    ---
    tags:
      - Trading - Account
    responses:
      200:
        description: 账户信息
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                balance:
                  type: number
                equity:
                  type: number
                available_margin:
                  type: number
                used_margin:
                  type: number
                unrealized_pnl:
                  type: number
                realized_pnl:
                  type: number
                positions_count:
                  type: integer
      500:
        description: 服务器错误
    """
    try:
        client = get_client()
        account = client.get_account_info()
        
        account_data = {
            'balance': account.balance,
            'equity': account.equity,
            'available_margin': account.available_margin,
            'used_margin': account.used_margin,
            'unrealized_pnl': account.unrealized_pnl,
            'realized_pnl': account.realized_pnl,
            'positions_count': len(account.positions)
        }
        
        return jsonify({
            'success': True,
            'data': account_data
        })
        
    except Exception as e:
        logger.error(f"获取账户信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
