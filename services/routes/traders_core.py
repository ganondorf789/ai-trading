"""
交易者基础管理相关路由
包括：交易者列表、添加、详情、刷新、交易记录
"""
import json
import operator
from flask import Blueprint, jsonify, request
import logging

from screener import TraderScreener, ScreenerConfig
from screener.utils import now_shanghai, timestamp_to_pendulum
from .db import db
from .middleware import login_required, get_current_user_id

logger = logging.getLogger(__name__)

# 标签英文key到中文显示label的映射（标签已用英文存储在DB中）
TAG_DISPLAY_LABELS = {
    'account_value': {
        'small_capital': '小资金',
        'medium_capital': '中等资金',
        'whale': '巨鲸',
    },
    'trading_rhythm': {
        'long_term': '长线',
        'swing': '波段',
        'short_term': '短线',
        'ultra_short': '超短线',
    },
    'profit_status': {
        'consistent_profit': '持续盈利',
        'volatile_profit': '波动盈利',
        'break_even': '盈亏平衡',
    },
    'direction_preference': {
        'bearish': '偏空头',
        'neutral': '中性',
        'bullish': '偏多头',
    },
    'trading_style': {
        'high_freq_stable': '高频稳健',
        'high_freq_aggressive': '高频激进',
        'low_freq_stable': '低频稳健',
        'stable_profit': '稳定盈利',
        'high_risk_high_return': '高风险高回报',
        'asymmetric_master': '非对称高手',
    },
}

# ===== 高级筛选引擎 =====

FILTER_OPS = {
    '<': operator.lt,
    '>': operator.gt,
    '=': operator.eq,
    '>=': operator.ge,
    '<=': operator.le,
    '!=': operator.ne,
    '<>': operator.ne,
    'exist': lambda val, _: val is not None and val != 0,
}

FILTERABLE_FIELDS = {
    'sharpe_ratio', 'max_drawdown', 'current_positions', 'current_equity',
    'perp_total_value', 'position_value', 'long_position_value', 'short_position_value',
    'margin_usage_rate', 'used_margin', 'winning_trades', 'win_rate',
    'total_pnl', 'long_trades', 'long_realized_pnl', 'long_win_rate',
    'short_trades', 'short_realized_pnl', 'short_win_rate',
    'unrealized_pnl', 'avg_leverage', 'account_value', 'long_position_ratio',
    'overall_score', 'total_trades', 'profit_factor', 'sortino_ratio',
    'calmar_ratio', 'active_days', 'roi', 'recent_7d_pnl', 'recent_7d_win_rate',
    'max_drawdown_abs', 'losing_trades', 'total_volume',
    'max_single_win', 'max_single_loss', 'max_consecutive_wins', 'max_consecutive_losses',
    'avg_win_amount', 'avg_loss_amount', 'unique_symbols',
    'long_short_ratio',
}

SORTABLE_FIELDS = {
    'win_rate', 'current_equity', 'last_trade_time', 'current_positions',
    'used_margin', 'perp_total_value', 'avg_leverage',
    'long_realized_pnl', 'short_realized_pnl', 'total_pnl', 'long_position_ratio',
    'overall_score', 'rating', 'total_trades', 'roi', 'profit_factor',
    'max_drawdown', 'sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
    'active_days', 'recent_7d_pnl', 'recent_7d_win_rate', 'unique_symbols',
    'max_consecutive_wins', 'max_consecutive_losses', 'long_short_ratio',
    'account_value', 'margin_usage_rate', 'position_value',
    'long_position_value', 'short_position_value',
    'long_trades', 'short_trades', 'long_win_rate', 'short_win_rate',
}

# 旧版 min_/max_ 参数到字段名的映射
LEGACY_FILTER_MAP = {
    'min_win_rate': ('win_rate', '>='),
    'max_win_rate': ('win_rate', '<='),
    'min_profit_factor': ('profit_factor', '>='),
    'max_profit_factor': ('profit_factor', '<='),
    'min_pnl': ('total_pnl', '>='),
    'max_pnl': ('total_pnl', '<='),
    'min_drawdown': ('max_drawdown', '>='),
    'max_drawdown': ('max_drawdown', '<='),
    'min_sharpe': ('sharpe_ratio', '>='),
    'max_sharpe': ('sharpe_ratio', '<='),
    'min_sortino': ('sortino_ratio', '>='),
    'max_sortino': ('sortino_ratio', '<='),
    'min_calmar': ('calmar_ratio', '>='),
    'max_calmar': ('calmar_ratio', '<='),
    'min_trades': ('total_trades', '>='),
    'max_trades': ('total_trades', '<='),
    'min_active_days': ('active_days', '>='),
    'max_active_days': ('active_days', '<='),
}


def apply_advanced_filters(traders, filter_conditions):
    """
    应用高级筛选条件

    Args:
        traders: 交易者列表
        filter_conditions: 筛选条件列表，每个条件为 {'field': str, 'op': str, 'value': number}

    Returns:
        筛选后的交易者列表
    """
    for condition in filter_conditions:
        field = condition.get('field')
        op_str = condition.get('op')
        value = condition.get('value', 0)

        if field not in FILTERABLE_FIELDS:
            continue

        op_func = FILTER_OPS.get(op_str)
        if not op_func:
            continue

        if op_str == 'exist':
            traders = [t for t in traders if op_func(t.get(field), None)]
        else:
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            traders = [t for t in traders if op_func(t.get(field, 0) or 0, value)]

    return traders


traders_core_bp = Blueprint('traders_core', __name__)


@traders_core_bp.route('/api/traders', methods=['GET'])
@login_required
def get_traders():
    """获取交易者列表
    ---
    tags:
      - Traders
    parameters:
      - name: page
        in: query
        type: integer
        default: 1
        description: 页码
      - name: limit
        in: query
        type: integer
        default: 20
        description: 每页数量
      - name: rating
        in: query
        type: string
        enum: [S, A, B, C, D, F]
        description: 评级筛选
      - name: search
        in: query
        type: string
        description: 地址搜索
      - name: sort_by
        in: query
        type: string
        default: overall_score
        description: 排序字段
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
        default: desc
        description: 排序方向
      - name: min_win_rate
        in: query
        type: number
        description: 最小胜率
      - name: max_win_rate
        in: query
        type: number
        description: 最大胜率
      - name: min_profit_factor
        in: query
        type: number
        description: 最小盈亏比
      - name: max_profit_factor
        in: query
        type: number
        description: 最大盈亏比
      - name: min_pnl
        in: query
        type: number
        description: 最小PnL
      - name: max_pnl
        in: query
        type: number
        description: 最大PnL
      - name: min_drawdown
        in: query
        type: number
        description: 最小回撤
      - name: max_drawdown
        in: query
        type: number
        description: 最大回撤
      - name: min_sharpe
        in: query
        type: number
        description: 最小夏普比率
      - name: max_sharpe
        in: query
        type: number
        description: 最大夏普比率
      - name: min_trades
        in: query
        type: integer
        description: 最小交易数
      - name: max_trades
        in: query
        type: integer
        description: 最大交易数
      - name: has_recent_trade
        in: query
        type: integer
        description: 最近N天内有交易
      - name: filters
        in: query
        type: string
        description: 'JSON数组格式的高级筛选条件，例: [{"field":"win_rate","op":">","value":0.5}]。支持的操作符: <, >, =, >=, <=, !=, <>, exist'
    responses:
      200:
        description: 交易者列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            pagination:
              type: object
              properties:
                page:
                  type: integer
                limit:
                  type: integer
                total_count:
                  type: integer
                total_pages:
                  type: integer
      500:
        description: 服务器错误
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        rating = request.args.get('rating')
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'overall_score')
        sort_order = request.args.get('sort_order', 'desc')

        # 获取所有交易者
        all_traders = db.get_top_traders(limit=100000)

        # 应用精确评级筛选
        if rating:
            all_traders = [t for t in all_traders if t.get('rating') == rating]

        # 应用搜索过滤（支持地址和昵称）
        if search:
            search_lower = search.lower()
            all_traders = [
                t for t in all_traders
                if search_lower in t['address'].lower()
                or search_lower in (t.get('display_name') or '').lower()
            ]

        # ===== 构建筛选条件 =====
        filter_conditions = []

        # 1. 解析新的 filters JSON 参数
        filters_raw = request.args.get('filters')
        if filters_raw:
            try:
                parsed_filters = json.loads(filters_raw)
                if isinstance(parsed_filters, list):
                    filter_conditions.extend(parsed_filters)
            except (json.JSONDecodeError, TypeError):
                pass

        # 2. 向后兼容：将旧版 min_*/max_* 参数转换为筛选条件
        for param_name, (field, op) in LEGACY_FILTER_MAP.items():
            param_value = request.args.get(param_name, type=float)
            if param_value is not None:
                filter_conditions.append({'field': field, 'op': op, 'value': param_value})

        # 3. 应用高级筛选
        if filter_conditions:
            all_traders = apply_advanced_filters(all_traders, filter_conditions)

        # 4. 最近活跃筛选（特殊逻辑，不适合通用筛选引擎）
        has_recent_trade = request.args.get('has_recent_trade', type=int)
        if has_recent_trade is not None:
            cutoff = now_shanghai().subtract(days=has_recent_trade)
            def is_recent(t):
                last_trade = t.get('last_trade_time')
                if not last_trade:
                    return False
                try:
                    import pendulum
                    trade_time = pendulum.parse(last_trade)
                    return trade_time >= cutoff
                except Exception:
                    return False
            all_traders = [t for t in all_traders if is_recent(t)]

        # 5. 标签筛选（DB中已存储英文值，直接匹配）
        tag_account_value = request.args.get('tag_account_value')
        tag_trading_rhythm = request.args.get('tag_trading_rhythm')
        tag_profit_status = request.args.get('tag_profit_status')
        tag_direction_preference = request.args.get('tag_direction_preference')
        tag_trading_style = request.args.get('tag_trading_style')

        if tag_account_value:
            all_traders = [t for t in all_traders if t.get('tag_account_value') == tag_account_value]
        if tag_trading_rhythm:
            all_traders = [t for t in all_traders if t.get('tag_trading_rhythm') == tag_trading_rhythm]
        if tag_profit_status:
            all_traders = [t for t in all_traders if t.get('tag_profit_status') == tag_profit_status]
        if tag_direction_preference:
            all_traders = [t for t in all_traders if t.get('tag_direction_preference') == tag_direction_preference]
        if tag_trading_style:
            all_traders = [t for t in all_traders if tag_trading_style in (t.get('tag_trading_style') or '')]

        # ===== 应用排序 =====
        if sort_by in SORTABLE_FIELDS:
            reverse = sort_order.lower() != 'asc'
            # 处理 rating 特殊排序（S > A > B > C > D > F）
            if sort_by == 'rating':
                rating_order = {'S': 1, 'A': 2, 'B': 3, 'C': 4, 'D': 5, 'F': 6}
                all_traders.sort(
                    key=lambda x: rating_order.get(x.get('rating', 'F'), 6),
                    reverse=reverse
                )
            else:
                all_traders.sort(
                    key=lambda x: x.get(sort_by) or 0,
                    reverse=reverse
                )

        total_count = len(all_traders)
        total_pages = (total_count + limit - 1) // limit

        # 分页
        start = (page - 1) * limit
        end = start + limit
        traders = all_traders[start:end]

        # 获取当前用户的收藏列表
        user_id = get_current_user_id()
        user_starred_addresses = db.get_user_starred_addresses(user_id) if user_id else set()

        # 格式化数据（返回所有可用字段）
        result = []
        for trader in traders:
            result.append({
                'id': trader.get('id'),
                'address': trader.get('address'),
                'analyzed_at': trader.get('analyzed_at'),
                # 基础统计
                'total_trades': trader.get('total_trades', 0),
                'winning_trades': trader.get('winning_trades', 0),
                'losing_trades': trader.get('losing_trades', 0),
                'win_rate': trader.get('win_rate', 0),
                # 盈亏指标
                'total_pnl': trader.get('total_pnl', 0),
                'realized_pnl': trader.get('realized_pnl', 0),
                'unrealized_pnl': trader.get('unrealized_pnl', 0),
                'roi': trader.get('roi', 0),
                'profit_factor': trader.get('profit_factor', 0),
                # 风险指标
                'max_drawdown': trader.get('max_drawdown', 0),
                'max_drawdown_abs': trader.get('max_drawdown_abs', 0),
                'sharpe_ratio': trader.get('sharpe_ratio', 0),
                'sortino_ratio': trader.get('sortino_ratio', 0),
                'calmar_ratio': trader.get('calmar_ratio', 0),
                'var_95': trader.get('var_95', 0),
                'var_99': trader.get('var_99', 0),
                'cvar_95': trader.get('cvar_95', 0),
                # 评分
                'overall_score': trader.get('overall_score', 0),
                'rating': trader.get('rating', 'F'),
                'profitability_score': trader.get('profitability_score', 0),
                'risk_score': trader.get('risk_score', 0),
                'consistency_score': trader.get('consistency_score', 0),
                'activity_score': trader.get('activity_score', 0),
                # 活跃度
                'current_equity': trader.get('current_equity', 0),
                'current_positions': trader.get('current_positions', 0),
                'active_days': trader.get('active_days', 0),
                'avg_leverage': trader.get('avg_leverage', 1),
                'max_leverage': trader.get('max_leverage', 1),
                'last_trade_time': trader.get('last_trade_time'),
                'first_trade_time': trader.get('first_trade_time'),
                # 新增分析字段
                'avg_trade_price': trader.get('avg_trade_price', 0),
                'avg_trade_size': trader.get('avg_trade_size', 0),
                'max_single_win': trader.get('max_single_win', 0),
                'max_single_loss': trader.get('max_single_loss', 0),
                'max_consecutive_wins': trader.get('max_consecutive_wins', 0),
                'max_consecutive_losses': trader.get('max_consecutive_losses', 0),
                'avg_win_amount': trader.get('avg_win_amount', 0),
                'avg_loss_amount': trader.get('avg_loss_amount', 0),
                'unique_symbols': trader.get('unique_symbols', 0),
                'favorite_symbol': trader.get('favorite_symbol', ''),
                'recent_7d_pnl': trader.get('recent_7d_pnl', 0),
                'recent_7d_win_rate': trader.get('recent_7d_win_rate', 0),
                'long_short_ratio': trader.get('long_short_ratio', 0),
                # 账户和保证金
                'account_value': trader.get('account_value', 0),
                'used_margin': trader.get('used_margin', 0),
                'perp_total_value': trader.get('perp_total_value', 0),
                'position_value': trader.get('position_value', 0),
                'long_position_value': trader.get('long_position_value', 0),
                'short_position_value': trader.get('short_position_value', 0),
                'margin_usage_rate': trader.get('margin_usage_rate', 0),
                # 多空分项
                'long_trades': trader.get('long_trades', 0),
                'long_realized_pnl': trader.get('long_realized_pnl', 0),
                'long_win_rate': trader.get('long_win_rate', 0),
                'short_trades': trader.get('short_trades', 0),
                'short_realized_pnl': trader.get('short_realized_pnl', 0),
                'short_win_rate': trader.get('short_win_rate', 0),
                'long_position_ratio': trader.get('long_position_ratio', 0),
                # 用户收藏状态（用户维度）
                'is_starred': trader.get('address') in user_starred_addresses,
                # 标签
                'tag_account_value': trader.get('tag_account_value'),
                'tag_trading_rhythm': trader.get('tag_trading_rhythm'),
                'tag_profit_status': trader.get('tag_profit_status'),
                'tag_direction_preference': trader.get('tag_direction_preference'),
                'tag_trading_style': trader.get('tag_trading_style'),
            })

        return jsonify({
            'success': True,
            'data': result,
            'pagination': {
                'page': page,
                'limit': limit,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })

    except Exception as e:
        logger.error(f"获取交易者列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders', methods=['POST'])
@login_required
def add_trader():
    """新增交易者
    ---
    tags:
      - Traders
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - address
          properties:
            address:
              type: string
              description: 交易者地址（0x开头的42位以太坊地址）
              example: "0x1234567890abcdef1234567890abcdef12345678"
            lookback_days:
              type: integer
              default: 0
              description: 分析回溯天数，0表示全部
            max_fills:
              type: integer
              default: 0
              description: 最大获取交易记录数，0表示不限制
    responses:
      200:
        description: 添加成功
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
            message:
              type: string
      400:
        description: 请求参数错误
      404:
        description: 无法获取交易者数据
      409:
        description: 交易者已存在
      500:
        description: 服务器错误
    """
    try:
        data = request.get_json()
        if not data or not data.get('address'):
            return jsonify({
                'success': False,
                'error': '地址不能为空'
            }), 400

        address = data['address'].strip()
        lookback_days = int(data.get('lookback_days', 0))
        max_fills = int(data.get('max_fills', 0))

        # 验证地址格式
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        # 检查是否已存在
        existing = db.get_trader_by_address(address)
        if existing:
            return jsonify({
                'success': False,
                'error': '该交易者已存在，请使用刷新功能更新数据'
            }), 409

        logger.info(f"开始分析新交易者: {address}")

        # 初始化筛选器
        config = ScreenerConfig()
        config.data.lookback_days = lookback_days
        config.data.max_fills_per_trader = max_fills
        config.api.api_call_delay = 2.0
        config.api.max_retries = 3
        screener = TraderScreener(config)

        # 分析交易者
        metrics = screener.analyze_trader(address)

        if not metrics or metrics.total_trades == 0:
            return jsonify({
                'success': False,
                'error': '无法获取交易者数据或该交易者无交易记录'
            }), 404

        # 保存到数据库
        _, fills_saved = db.save_trader_with_fills(metrics, metrics.fills)

        # 保存持仓数据
        positions_saved = db.save_positions(address, metrics.asset_positions)

        logger.info(f"新交易者添加成功: {address}, 评分: {metrics.overall_score:.1f}, 评级: {metrics.rating.value}")

        # 返回新增的数据
        trader = db.get_trader_by_address(address)

        return jsonify({
            'success': True,
            'data': trader,
            'message': f'添加成功，保存了 {fills_saved} 条交易记录，{positions_saved} 个持仓'
        })

    except Exception as e:
        logger.error(f"添加交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>', methods=['GET'])
@login_required
def get_trader_detail(address: str):
    """获取交易者详情
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 交易者详情
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              properties:
                trader:
                  type: object
      404:
        description: 交易者不存在
      500:
        description: 服务器错误
    """
    try:
        # 获取交易者基本信息
        trader = db.get_trader_by_address(address)

        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 获取当前用户的收藏状态
        user_id = get_current_user_id()
        if user_id:
            trader['is_starred'] = db.is_user_starred(user_id, address)
        else:
            trader['is_starred'] = False

        return jsonify({
            'success': True,
            'data': {
                'trader': trader
            }
        })

    except Exception as e:
        logger.error(f"获取交易者详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/dashboard', methods=['GET'])
@login_required
def get_trader_dashboard(address: str):
    """获取交易者仪表盘汇总数据
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: start_date
        in: query
        type: string
        format: date
        description: 开始日期 (YYYY-MM-DD)
      - name: end_date
        in: query
        type: string
        format: date
        description: 结束日期 (YYYY-MM-DD)
    responses:
      200:
        description: 仪表盘数据
      404:
        description: 交易者不存在
      500:
        description: 服务器错误
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        data = db.get_trader_dashboard(address, start_date, end_date)

        if not data:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        logger.error(f"获取交易者仪表盘失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/closed-performance', methods=['GET'])
@login_required
def get_trader_closed_performance(address: str):
    """获取交易者平仓表现统计
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: start_date
        in: query
        type: string
        format: date
        description: 开始日期 (YYYY-MM-DD)
      - name: end_date
        in: query
        type: string
        format: date
        description: 结束日期 (YYYY-MM-DD)
    responses:
      200:
        description: 平仓表现数据
      404:
        description: 无平仓数据
      500:
        description: 服务器错误
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        data = db.get_trader_closed_performance(address, start_date, end_date)

        if not data:
            return jsonify({
                'success': False,
                'error': 'No closed positions found'
            }), 404

        return jsonify({
            'success': True,
            'data': data
        })

    except Exception as e:
        logger.error(f"获取交易者平仓表现失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/pnl-curve', methods=['GET'])
@login_required
def get_trader_pnl_curve(address: str):
    """获取交易者总盈亏曲线
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: start_date
        in: query
        type: string
        format: date
        description: 开始日期 (YYYY-MM-DD)，不传默认最近24小时
      - name: end_date
        in: query
        type: string
        format: date
        description: 结束日期 (YYYY-MM-DD)
    responses:
      200:
        description: 盈亏曲线数据
      500:
        description: 服务器错误
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        data = db.get_trader_pnl_curve(address, start_date, end_date)

        return jsonify({
            'success': True,
            'data': data,
            'count': len(data['points'])
        })

    except Exception as e:
        logger.error(f"获取交易者盈亏曲线失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/best-trades', methods=['GET'])
@login_required
def get_trader_best_trades(address: str):
    """获取交易者 Top N 最佳交易
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: start_date
        in: query
        type: string
        format: date
        description: 开始日期 (YYYY-MM-DD)
      - name: end_date
        in: query
        type: string
        format: date
        description: 结束日期 (YYYY-MM-DD)
      - name: limit
        in: query
        type: integer
        default: 10
        description: 返回数量
    responses:
      200:
        description: 最佳交易列表
      500:
        description: 服务器错误
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 10))

        data = db.get_trader_best_trades(address, start_date, end_date, limit)

        return jsonify({
            'success': True,
            'data': data,
            'count': len(data)
        })

    except Exception as e:
        logger.error(f"获取交易者最佳交易失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/refresh', methods=['POST'])
@login_required
def refresh_trader(address: str):
    """刷新交易者数据
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: lookback_days
        in: query
        type: integer
        default: 30
        description: 分析回溯天数
      - name: max_fills
        in: query
        type: integer
        default: 0
        description: 最大获取交易记录数，0表示不限制
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
            message:
              type: string
      404:
        description: 无法获取交易者数据
      500:
        description: 服务器错误
    """
    try:
        lookback_days = int(request.args.get('lookback_days', 30))
        max_fills = int(request.args.get('max_fills', 0))

        logger.info(f"开始重新分析交易者: {address}")

        # 初始化筛选器
        config = ScreenerConfig()
        config.data.lookback_days = lookback_days
        config.data.max_fills_per_trader = max_fills
        config.api.api_call_delay = 2.0
        config.api.max_retries = 3
        screener = TraderScreener(config)

        # 从 API 获取新的交易记录
        metrics = screener.analyze_trader(address)

        if not metrics:
            return jsonify({
                'success': False,
                'error': '无法获取交易者数据'
            }), 404

        # 保存新获取的 fills 到数据库
        fills_saved = db.save_fills(address, metrics.fills) if metrics.fills else 0

        # 保存持仓数据
        positions_saved = db.save_positions(address, metrics.asset_positions)

        # 从数据库获取所有交易记录，重新计算指标
        from screener.metrics_calculator import MetricsCalculator
        from screener.scorer import TraderScorer

        all_fills = db.get_fills_for_metrics(address, lookback_days=0)  # 获取所有记录

        if not all_fills:
            return jsonify({
                'success': False,
                'error': '该交易者无交易记录'
            }), 404

        # 使用数据库中的所有 fills 重新计算指标
        calculator = MetricsCalculator()
        user_state = {
            'assetPositions': metrics.asset_positions,
            'marginSummary': {
                'accountValue': metrics.current_equity,
                'totalMarginUsed': metrics.position.used_margin,
            }
        }
        recalculated_metrics = calculator.calculate(address, all_fills, user_state, store_fills=False)

        # 计算评分
        scorer = TraderScorer(config.scoring)
        recalculated_metrics = scorer.calculate_scores(recalculated_metrics)

        # 保存持仓信息到重新计算的指标
        recalculated_metrics.asset_positions = metrics.asset_positions

        # 保存重新计算的指标到数据库
        db.save_trader(recalculated_metrics)

        logger.info(f"交易者分析完成: {address}, 评分: {recalculated_metrics.overall_score:.1f}, 评级: {recalculated_metrics.rating.value}, 持仓: {positions_saved}, 数据库总记录: {len(all_fills)}")

        # 返回更新后的数据
        trader = db.get_trader_by_address(address)

        return jsonify({
            'success': True,
            'data': {
                'trader': trader,
                'fills_saved': fills_saved,
                'total_fills_in_db': len(all_fills)
            },
            'message': f'分析完成，新增 {fills_saved} 条交易记录，基于数据库中 {len(all_fills)} 条记录计算指标'
        })

    except Exception as e:
        logger.error(f"重新分析交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/fills', methods=['GET'])
@login_required
def get_trader_fills(address: str):
    """获取交易者历史交易记录
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
      - name: page
        in: query
        type: integer
        default: 1
        description: 页码
      - name: limit
        in: query
        type: integer
        default: 20
        description: 每页数量
      - name: coin
        in: query
        type: string
        description: 筛选特定币种
      - name: pnl_filter
        in: query
        type: string
        enum: [all, profit, loss]
        default: all
        description: 盈亏筛选
      - name: trade_type
        in: query
        type: string
        enum: [all, open_long, add_long, close_long, open_short, add_short, close_short]
        default: all
        description: 交易类型筛选
      - name: sort_by
        in: query
        type: string
        enum: [trade_time, coin, side, px, sz, value, closed_pnl, roi, fee]
        default: trade_time
        description: 排序字段
      - name: sort_order
        in: query
        type: string
        enum: [asc, desc]
        default: desc
        description: 排序方向
      - name: start_date
        in: query
        type: string
        format: date
        description: 开始日期 (YYYY-MM-DD)
      - name: end_date
        in: query
        type: string
        format: date
        description: 结束日期 (YYYY-MM-DD)
    responses:
      200:
        description: 交易记录列表
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
            stats:
              type: object
            pagination:
              type: object
      500:
        description: 服务器错误
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        coin = request.args.get('coin')
        pnl_filter = request.args.get('pnl_filter', 'all')
        trade_type = request.args.get('trade_type', 'all')
        sort_by = request.args.get('sort_by', 'trade_time')
        sort_order = request.args.get('sort_order', 'desc')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # 获取所有符合条件的交易记录（筛选在数据库层完成）
        all_fills = db.get_trader_fills(
            address,
            limit=100000,
            coin=coin,
            trade_type=trade_type if trade_type != 'all' else None,
            pnl_filter=pnl_filter if pnl_filter != 'all' else None,
            sort_by=sort_by,
            sort_order=sort_order,
            start_date=start_date,
            end_date=end_date
        )

        total_count = len(all_fills)
        total_pages = (total_count + limit - 1) // limit

        # 计算基于全部筛选数据的统计信息
        profitable_count = sum(1 for f in all_fills if f.get('closed_pnl', 0) > 0)
        losing_count = sum(1 for f in all_fills if f.get('closed_pnl', 0) < 0)
        total_pnl = sum(f.get('closed_pnl', 0) for f in all_fills)
        total_fees = sum(f.get('fee', 0) for f in all_fills)
        total_volume = sum(f.get('px', 0) * f.get('sz', 0) for f in all_fills)
        win_rate = (profitable_count / total_count * 100) if total_count > 0 else 0

        stats = {
            'total': total_count,
            'profitable': profitable_count,
            'losing': losing_count,
            'total_pnl': total_pnl,
            'total_fees': total_fees,
            'total_volume': total_volume,
            'win_rate': win_rate
        }

        # 分页
        start = (page - 1) * limit
        end = start + limit
        fills = all_fills[start:end]

        return jsonify({
            'success': True,
            'data': fills,
            'stats': stats,
            'pagination': {
                'page': page,
                'limit': limit,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })

    except Exception as e:
        logger.error(f"获取交易记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_core_bp.route('/api/traders/<address>/account-overview', methods=['GET'])
@login_required
def get_trader_account_overview(address: str):
    """获取交易者账户概览（实时数据）
    ---
    tags:
      - Traders
    parameters:
      - name: address
        in: path
        type: string
        required: true
        description: 交易者地址
    responses:
      200:
        description: 账户概览数据
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
      404:
        description: 无法获取用户状态
      500:
        description: 服务器错误
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        import pendulum

        info = Info(constants.MAINNET_API_URL, skip_ws=True)

        # 1. 获取合约账户状态
        user_state = info.user_state(address)
        if not user_state:
            return jsonify({
                'success': False,
                'error': '无法获取用户状态'
            }), 404

        margin_summary = user_state.get('marginSummary', {})
        perp_account_value = float(margin_summary.get('accountValue', 0))
        total_margin_used = float(margin_summary.get('totalMarginUsed', 0))
        total_ntl_pos = float(margin_summary.get('totalNtlPos', 0))
        withdrawable = float(user_state.get('withdrawable', 0))

        # 2. 获取现货账户状态
        spot_account_value = 0.0
        try:
            spot_state = info.spot_user_state(address)
            if spot_state:
                balances = spot_state.get('balances', [])
                all_mids = info.all_mids()
                for b in balances:
                    coin = b.get('coin', '')
                    total = float(b.get('total', 0))
                    if coin == 'USDC':
                        spot_account_value += total
                    else:
                        price = float(all_mids.get(coin, 0))
                        spot_account_value += total * price
        except Exception as e:
            logger.warning(f"获取现货账户失败: {e}")

        account_total_value = perp_account_value + spot_account_value

        # 3. 解析持仓数据
        asset_positions = user_state.get('assetPositions', [])
        total_position_value = 0.0
        long_value = 0.0
        short_value = 0.0
        total_upnl = 0.0
        margin_used_list = []

        for ap in asset_positions:
            pos = ap.get('position', {})
            szi = float(pos.get('szi', 0))
            if szi == 0:
                continue

            pos_value = abs(float(pos.get('positionValue', 0)))
            upnl = float(pos.get('unrealizedPnl', 0))
            margin_used = float(pos.get('marginUsed', 0))

            total_position_value += pos_value
            total_upnl += upnl

            if margin_used > 0:
                margin_used_list.append(margin_used)

            if szi > 0:
                long_value += pos_value
            else:
                short_value += pos_value

        # 杠杆率
        leverage_ratio = round(total_position_value / perp_account_value, 2) if perp_account_value > 0 else 0.0

        # 可提现比例
        withdrawable_pct = round(withdrawable / perp_account_value * 100, 2) if perp_account_value > 0 else 0.0

        # 方向偏好
        total_exposure = long_value + short_value
        long_exposure_pct = round(long_value / total_exposure * 100, 2) if total_exposure > 0 else 0.0
        short_exposure_pct = round(short_value / total_exposure * 100, 2) if total_exposure > 0 else 0.0

        if long_exposure_pct > 60:
            direction_bias = 'Long'
        elif short_exposure_pct > 60:
            direction_bias = 'Short'
        else:
            direction_bias = 'Neutral'

        # 平均保证金使用率
        total_margin_for_positions = sum(margin_used_list)
        avg_margin_used_ratio = round(total_margin_for_positions / perp_account_value * 100, 2) if perp_account_value > 0 else 0.0

        # ROE
        roe = round(total_upnl / perp_account_value * 100, 2) if perp_account_value > 0 else 0.0

        # 4. 从数据库获取最近一周的交易表现
        now = pendulum.now('Asia/Shanghai')
        one_week_ago = now.subtract(weeks=1)
        start_date = one_week_ago.format('YYYY-MM-DD')
        end_date = now.format('YYYY-MM-DD')

        # 交易次数（fills）
        start_ms = int(one_week_ago.timestamp() * 1000)
        end_ms = int(now.timestamp() * 1000)

        trades_count = 0
        win_rate_1w = 0.0
        closed_positions_1w = 0
        max_drawdown_1w = 0.0

        try:
            closed_perf = db.get_trader_closed_performance(address, start_date, end_date)
            if closed_perf:
                win_rate_1w = closed_perf['overview']['win_rate']
                closed_positions_1w = closed_perf['closed_stats']['closed_count']
        except Exception as e:
            logger.warning(f"获取平仓表现失败: {e}")

        try:
            # 获取交易者基础数据用于 max_drawdown
            trader = db.get_trader_by_address(address)
            if trader:
                max_drawdown_1w = float(trader.get('max_drawdown', 0)) * 100
                trades_count = int(trader.get('total_trades', 0))
        except Exception as e:
            logger.warning(f"获取交易者数据失败: {e}")

        return jsonify({
            'success': True,
            'data': {
                'account_total': {
                    'total_value': round(account_total_value, 2),
                    'perpetual_value': round(perp_account_value, 2),
                    'spot_value': round(spot_account_value, 2),
                },
                'margin': {
                    'free_margin': round(withdrawable, 2),
                    'withdrawable_pct': withdrawable_pct,
                },
                'positions': {
                    'total_position_value': round(total_position_value, 2),
                    'leverage_ratio': leverage_ratio,
                    'perp_total_value': round(total_position_value, 2),
                    'avg_margin_used_ratio': avg_margin_used_ratio,
                },
                'direction_bias': {
                    'bias': direction_bias,
                    'long_exposure_pct': long_exposure_pct,
                    'short_exposure_pct': short_exposure_pct,
                },
                'position_distribution': {
                    'long_value': round(long_value, 2),
                    'short_value': round(short_value, 2),
                },
                'profit_loss': {
                    'roe': roe,
                    'unrealized_pnl': round(total_upnl, 2),
                },
                'trading_performance_1w': {
                    'win_rate': win_rate_1w,
                    'max_drawdown': round(max_drawdown_1w, 2),
                    'trades': trades_count,
                    'closed_positions': closed_positions_1w,
                },
            }
        })

    except Exception as e:
        logger.error(f"获取账户概览失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
