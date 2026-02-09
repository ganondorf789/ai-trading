"""
Trading API 路由
提供交易相关的 API 接口
"""
import sys
import os
import time

# 添加项目根目录到路径（用于导入 clients）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Blueprint, jsonify, request
import logging

from clients.hyperliquid_client import HyperliquidClient
from trading.settings import settings
from trading.grpc_client import GRPCClient
from .middleware import api_key_required

logger = logging.getLogger(__name__)

trading_bp = Blueprint('trading', __name__)

# 全局客户端实例（延迟初始化）
_client: HyperliquidClient = None
_grpc_client: GRPCClient = None


def _extract_order_data(result: dict) -> dict:
    """
    从 Hyperliquid API 响应中提取核心数据，简化嵌套结构
    """
    if result is None:
        return None
    
    try:
        if isinstance(result, dict):
            if 'response' in result and isinstance(result['response'], dict):
                response = result['response']
                if 'data' in response:
                    return response['data']
            if 'statuses' in result:
                return result
        return result
    except Exception:
        return result


def _extract_order_data_list(results: list) -> list:
    """批量提取订单数据"""
    if results is None:
        return []
    return [_extract_order_data(r) for r in results]


def get_client() -> HyperliquidClient:
    """
    获取 HyperliquidClient 实例（单例模式）
    """
    global _client
    if _client is None:
        private_key = settings.hyperliquid.private_key
        wallet_address = settings.hyperliquid.wallet_address
        testnet = settings.hyperliquid.testnet
        
        if not private_key:
            raise ValueError("未配置 HYPERLIQUID_PRIVATE_KEY 环境变量")
        
        _client = HyperliquidClient(
            private_key=private_key,
            wallet_address=wallet_address,
            testnet=testnet
        )
        logger.info(f"HyperliquidClient 初始化完成，钱包地址: {_client.wallet_address}")
    
    return _client


def get_grpc_client() -> GRPCClient:
    """
    获取 GRPCClient 实例（单例模式）
    """
    global _grpc_client
    if _grpc_client is None:
        _grpc_client = GRPCClient(
            host=settings.grpc.host,
            port=settings.grpc.port,
            api_key=settings.api.key
        )
        logger.info(f"GRPCClient 初始化完成，服务器地址: {settings.grpc.host}:{settings.grpc.port}")
    
    return _grpc_client


# ==================== 市场数据 API ====================

@trading_bp.route('/api/trading/meta', methods=['GET'])
@api_key_required
def get_market_meta():
    """获取市场元数据"""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        testnet = settings.hyperliquid.testnet
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
@api_key_required
def get_all_mids():
    """获取所有交易对中间价"""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        testnet = settings.hyperliquid.testnet
        api_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        info = Info(api_url, skip_ws=True)
        mids = info.all_mids()
        
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
@api_key_required
def get_mid_price(symbol: str):
    """获取指定交易对中间价"""
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        testnet = settings.hyperliquid.testnet
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
@api_key_required
def get_positions():
    """获取当前所有仓位"""
    try:
        client = get_client()
        positions = client.get_positions()
        
        # 获取所有交易对的中间价（标记价格）
        all_mids = client.get_all_mids()
        
        # 获取所有活跃的跟单记录，用于匹配仓位（通过 gRPC）
        grpc_client = get_grpc_client()
        active_trackings = grpc_client.db.get_active_position_trackings()
        
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
            
            # 获取当前价格（标记价格/中间价）
            current_price = float(all_mids.get(p.symbol, 0)) or p.current_price
            
            # 计算仓位价值（USDC）= 仓位数量 * 当前价格
            position_value = p.size * current_price
            
            position_info = {
                'symbol': p.symbol,
                'side': p.side.value,
                'size': p.size,
                'entry_price': p.entry_price,
                'current_price': current_price,
                'leverage': p.leverage,
                'unrealized_pnl': p.unrealized_pnl,
                'liquidation_price': p.liquidation_price,
                'position_value': position_value,
                'margin_used': p.margin_used,
                # 跟单相关字段
                'tracking_id': tracking.get('id') if tracking else None,
                'target_address': tracking.get('target_address') if tracking else None,
                'target_name': tracking.get('target_name') if tracking else None,
                'target_score': tracking.get('target_score') if tracking else None,
                'target_rating': tracking.get('target_rating') if tracking else None,
                'is_starred': tracking.get('target_is_starred', False) if tracking else False,
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
@api_key_required
def get_position(symbol: str):
    """获取指定交易对仓位"""
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


# ==================== 补仓 API ====================

@trading_bp.route('/api/trading/positions/<symbol>/add', methods=['POST'])
@api_key_required
def add_position(symbol: str):
    """市价补仓"""
    try:
        client = get_client()
        
        position = client.get_position(symbol)
        if position is None:
            return jsonify({
                'success': False,
                'error': f'未找到 {symbol} 的仓位，无法补仓'
            }), 404
        
        data = request.get_json() or {}
        slippage = data.get('slippage', 0.01)
        leverage = data.get('leverage')
        is_cross = data.get('is_cross', True)
        
        size = data.get('size')
        amount = data.get('amount')
        
        if size is None and amount is None:
            return jsonify({
                'success': False,
                'error': '必须提供 size（补仓数量）或 amount（补仓金额）'
            }), 400
        
        if size is not None and amount is not None:
            return jsonify({
                'success': False,
                'error': 'size 和 amount 只能二选一'
            }), 400
        
        if amount is not None:
            all_mids = client.get_all_mids()
            current_price = float(all_mids.get(symbol, 0))
            if current_price <= 0:
                return jsonify({
                    'success': False,
                    'error': f'无法获取 {symbol} 的当前价格'
                }), 400
            size = float(amount) / current_price
        else:
            size = float(size)
        
        if size <= 0:
            return jsonify({
                'success': False,
                'error': '补仓数量必须大于 0'
            }), 400
        
        leverage_result = None
        if leverage is not None:
            leverage = int(leverage)
            if leverage < 1:
                return jsonify({
                    'success': False,
                    'error': '杠杆倍数必须大于等于 1'
                }), 400
            leverage_result = client.set_leverage(symbol, leverage, is_cross)
        
        is_buy = position.side.value == 'long'
        
        result = client.market_order(
            symbol=symbol,
            is_buy=is_buy,
            size=size,
            slippage=slippage
        )
        
        response_data = {
            'success': True,
            'data': _extract_order_data(result),
            'position': {
                'symbol': position.symbol,
                'side': position.side.value,
                'size_before': position.size,
                'entry_price': position.entry_price,
                'leverage_before': position.leverage
            },
            'added_size': size,
            'message': f'{symbol} 市价补仓成功，补仓数量: {size}'
        }
        
        if leverage_result is not None:
            response_data['leverage'] = leverage
            response_data['leverage_result'] = leverage_result
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"市价补仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/positions/<symbol>/add-limit', methods=['POST'])
@api_key_required
def add_position_limit(symbol: str):
    """限价补仓"""
    try:
        client = get_client()
        
        position = client.get_position(symbol)
        if position is None:
            return jsonify({
                'success': False,
                'error': f'未找到 {symbol} 的仓位，无法补仓'
            }), 404
        
        data = request.get_json()
        if not data or 'price' not in data:
            return jsonify({
                'success': False,
                'error': '缺少必填参数 price'
            }), 400
        
        price = float(data['price'])
        post_only = data.get('post_only', False)
        leverage = data.get('leverage')
        is_cross = data.get('is_cross', True)
        
        size = data.get('size')
        amount = data.get('amount')
        
        if size is None and amount is None:
            return jsonify({
                'success': False,
                'error': '必须提供 size（补仓数量）或 amount（补仓金额）'
            }), 400
        
        if size is not None and amount is not None:
            return jsonify({
                'success': False,
                'error': 'size 和 amount 只能二选一'
            }), 400
        
        if amount is not None:
            size = float(amount) / price
        else:
            size = float(size)
        
        if size <= 0:
            return jsonify({
                'success': False,
                'error': '补仓数量必须大于 0'
            }), 400
        
        leverage_result = None
        if leverage is not None:
            leverage = int(leverage)
            if leverage < 1:
                return jsonify({
                    'success': False,
                    'error': '杠杆倍数必须大于等于 1'
                }), 400
            leverage_result = client.set_leverage(symbol, leverage, is_cross)
        
        is_buy = position.side.value == 'long'
        
        result = client.limit_order(
            symbol=symbol,
            is_buy=is_buy,
            size=size,
            price=price,
            reduce_only=False,
            post_only=post_only
        )
        
        response_data = {
            'success': True,
            'data': _extract_order_data(result),
            'position': {
                'symbol': position.symbol,
                'side': position.side.value,
                'size_before': position.size,
                'entry_price': position.entry_price,
                'leverage_before': position.leverage
            },
            'added_size': size,
            'price': price,
            'message': f'{symbol} 限价补仓订单已提交，数量: {size}，价格: {price}'
        }
        
        if leverage_result is not None:
            response_data['leverage'] = leverage
            response_data['leverage_result'] = leverage_result
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"限价补仓失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 平仓 API ====================

@trading_bp.route('/api/trading/positions/<symbol>/close', methods=['POST'])
@api_key_required
def close_position(symbol: str):
    """市价平仓"""
    try:
        client = get_client()
        
        data = request.get_json() or {}
        size = data.get('size')
        slippage = data.get('slippage', 0.01)
        
        result = client.close_position(symbol, size=size, slippage=slippage)
        
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
@api_key_required
def close_position_limit(symbol: str):
    """限价平仓"""
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
@api_key_required
def close_all_positions():
    """市价平掉所有仓位"""
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
@api_key_required
def set_position_tp_sl(symbol: str):
    """设置仓位止盈止损"""
    try:
        client = get_client()
        
        data = request.get_json() or {}
        
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
@api_key_required
def get_open_orders():
    """获取未成交订单"""
    try:
        client = get_client()
        orders = client.get_open_orders()
        
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
@api_key_required
def cancel_order(symbol: str, order_id: int):
    """取消订单"""
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
@api_key_required
def cancel_orders_by_symbol(symbol: str):
    """取消指定交易对所有订单"""
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
@api_key_required
def cancel_all_orders():
    """取消所有订单"""
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


# ==================== 历史数据 API ====================

@trading_bp.route('/api/trading/funding-history', methods=['GET'])
@api_key_required
def get_funding_history():
    """
    获取用户资金费历史
    
    Query Parameters:
        days (int): 查询最近 N 天，默认 7，最大 90
        start_time (int): 起始时间戳（毫秒），与 days 二选一
        end_time (int): 结束时间戳（毫秒），可选
        coin (str): 筛选指定币种，可选
        limit (int): 返回条数限制，默认 200，最大 2000
    """
    try:
        client = get_client()
        address = client.wallet_address

        # 解析时间范围
        now_ms = int(time.time() * 1000)
        start_time = request.args.get('start_time', type=int)
        end_time = request.args.get('end_time', type=int, default=now_ms)
        days = request.args.get('days', type=int, default=7)
        coin = request.args.get('coin', type=str)
        limit = request.args.get('limit', type=int, default=200)

        if limit > 2000:
            limit = 2000

        if start_time is None:
            if days > 90:
                days = 90
            start_time = now_ms - days * 24 * 60 * 60 * 1000

        # 调用 SDK
        records = client.info.user_funding_history(address, start_time, end_time)

        # 格式化数据
        funding_list = []
        for record in records:
            delta = record.get('delta', {})
            entry = {
                'time': record.get('time', 0),
                'coin': delta.get('coin', ''),
                'funding_rate': delta.get('fundingRate', '0'),
                'usdc': float(delta.get('usdc', 0)),
                'size': float(delta.get('szi', 0)),
                'hash': record.get('hash', ''),
            }
            # 按币种筛选
            if coin and entry['coin'].upper() != coin.upper():
                continue
            funding_list.append(entry)

        # 按时间倒序
        funding_list.sort(key=lambda x: x['time'], reverse=True)
        total_count = len(funding_list)
        funding_list = funding_list[:limit]

        # 按币种汇总
        coin_summary = {}
        for entry in funding_list:
            c = entry['coin']
            if c not in coin_summary:
                coin_summary[c] = {'count': 0, 'total_usdc': 0.0}
            coin_summary[c]['count'] += 1
            coin_summary[c]['total_usdc'] += entry['usdc']

        return jsonify({
            'success': True,
            'data': funding_list,
            'count': len(funding_list),
            'total_count': total_count,
            'summary': coin_summary
        })

    except Exception as e:
        logger.error(f"获取资金费历史失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@trading_bp.route('/api/trading/orders/history', methods=['GET'])
@api_key_required
def get_historical_orders():
    """
    获取历史委托记录（最近 2000 条）
    
    Query Parameters:
        coin (str): 筛选指定币种，可选
        status (str): 筛选状态 (open/filled/canceled/triggered/marginCanceled)，可选
        limit (int): 返回条数限制，默认 200，最大 2000
    """
    try:
        client = get_client()
        address = client.wallet_address

        coin = request.args.get('coin', type=str)
        status_filter = request.args.get('status', type=str)
        limit = request.args.get('limit', type=int, default=200)

        if limit > 2000:
            limit = 2000

        # 调用 SDK
        records = client.info.historical_orders(address)

        # 格式化数据
        orders_list = []
        for record in records:
            order = record.get('order', {})
            status = record.get('status', 'unknown')
            status_timestamp = record.get('statusTimestamp', 0)

            order_coin = order.get('coin', '')

            # 按币种筛选
            if coin and order_coin.upper() != coin.upper():
                continue
            # 按状态筛选
            if status_filter and status != status_filter:
                continue

            entry = {
                'oid': order.get('oid'),
                'coin': order_coin,
                'side': order.get('side', ''),
                'side_label': '买入' if order.get('side') == 'B' else '卖出',
                'limit_price': order.get('limitPx', ''),
                'size': order.get('sz', '0'),
                'orig_size': order.get('origSz', '0'),
                'order_type': order.get('orderType', ''),
                'status': status,
                'timestamp': order.get('timestamp', 0),
                'status_timestamp': status_timestamp,
                'reduce_only': order.get('reduceOnly', False),
                'is_trigger': order.get('isTrigger', False),
                'trigger_condition': order.get('triggerCondition', ''),
                'trigger_price': order.get('triggerPx', ''),
                'is_position_tpsl': order.get('isPositionTpsl', False),
                'tif': order.get('tif'),
                'cloid': order.get('cloid'),
            }
            orders_list.append(entry)

        # 按状态时间倒序
        orders_list.sort(key=lambda x: x['status_timestamp'] or x['timestamp'], reverse=True)
        total_count = len(orders_list)
        orders_list = orders_list[:limit]

        # 按状态汇总
        status_summary = {}
        coin_summary = {}
        for entry in orders_list:
            s = entry['status']
            status_summary[s] = status_summary.get(s, 0) + 1
            c = entry['coin']
            coin_summary[c] = coin_summary.get(c, 0) + 1

        return jsonify({
            'success': True,
            'data': orders_list,
            'count': len(orders_list),
            'total_count': total_count,
            'summary': {
                'by_status': status_summary,
                'by_coin': coin_summary
            }
        })

    except Exception as e:
        logger.error(f"获取历史委托失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 账户信息 API ====================

@trading_bp.route('/api/trading/account', methods=['GET'])
@api_key_required
def get_account_info():
    """获取账户信息"""
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
