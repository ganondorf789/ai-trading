"""
Flask API Server for Trader Analytics
提供交易者数据查询和分析接口
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
from typing import Optional
import logging

from screener.database import TraderDatabase
from screener.trader_screener import TraderScreener, ScreenerConfig
from services.ai_analysis import generate_trader_analysis

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 初始化数据库
db = TraderDatabase()


@app.route('/api/traders', methods=['GET'])
def get_traders():
    """
    获取交易者列表（支持分页和排序）
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - rating: str, 精确评级筛选 (S/A/B/C/D/F)
        - search: str, 地址搜索
        - sort_by: str, 排序字段
        - sort_order: str, 排序方向 (asc/desc)
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

        # 应用搜索过滤
        if search:
            all_traders = [t for t in all_traders if search.lower() in t['address'].lower()]

        # 应用高级筛选（区间查询）
        min_win_rate = request.args.get('min_win_rate', type=float)
        max_win_rate = request.args.get('max_win_rate', type=float)
        min_profit_factor = request.args.get('min_profit_factor', type=float)
        max_profit_factor = request.args.get('max_profit_factor', type=float)
        min_pnl = request.args.get('min_pnl', type=float)
        max_pnl = request.args.get('max_pnl', type=float)
        min_drawdown = request.args.get('min_drawdown', type=float)
        max_drawdown = request.args.get('max_drawdown', type=float)
        min_sharpe = request.args.get('min_sharpe', type=float)
        max_sharpe = request.args.get('max_sharpe', type=float)
        min_sortino = request.args.get('min_sortino', type=float)
        max_sortino = request.args.get('max_sortino', type=float)
        min_calmar = request.args.get('min_calmar', type=float)
        max_calmar = request.args.get('max_calmar', type=float)
        min_trades = request.args.get('min_trades', type=int)
        max_trades = request.args.get('max_trades', type=int)
        min_active_days = request.args.get('min_active_days', type=int)
        max_active_days = request.args.get('max_active_days', type=int)
        has_recent_trade = request.args.get('has_recent_trade', type=int)  # 最近N天有交易

        # 胜率区间
        if min_win_rate is not None:
            all_traders = [t for t in all_traders if t.get('win_rate', 0) >= min_win_rate]
        if max_win_rate is not None:
            all_traders = [t for t in all_traders if t.get('win_rate', 0) <= max_win_rate]
        # 盈亏比区间
        if min_profit_factor is not None:
            all_traders = [t for t in all_traders if t.get('profit_factor', 0) >= min_profit_factor]
        if max_profit_factor is not None:
            all_traders = [t for t in all_traders if t.get('profit_factor', 0) <= max_profit_factor]
        # PnL区间
        if min_pnl is not None:
            all_traders = [t for t in all_traders if t.get('total_pnl', 0) >= min_pnl]
        if max_pnl is not None:
            all_traders = [t for t in all_traders if t.get('total_pnl', 0) <= max_pnl]
        # 回撤区间
        if min_drawdown is not None:
            all_traders = [t for t in all_traders if t.get('max_drawdown', 0) >= min_drawdown]
        if max_drawdown is not None:
            all_traders = [t for t in all_traders if t.get('max_drawdown', 1) <= max_drawdown]
        # Sharpe区间
        if min_sharpe is not None:
            all_traders = [t for t in all_traders if t.get('sharpe_ratio', 0) >= min_sharpe]
        if max_sharpe is not None:
            all_traders = [t for t in all_traders if t.get('sharpe_ratio', 0) <= max_sharpe]
        # Sortino区间
        if min_sortino is not None:
            all_traders = [t for t in all_traders if t.get('sortino_ratio', 0) >= min_sortino]
        if max_sortino is not None:
            all_traders = [t for t in all_traders if t.get('sortino_ratio', 0) <= max_sortino]
        # Calmar区间
        if min_calmar is not None:
            all_traders = [t for t in all_traders if t.get('calmar_ratio', 0) >= min_calmar]
        if max_calmar is not None:
            all_traders = [t for t in all_traders if t.get('calmar_ratio', 0) <= max_calmar]
        # 交易数区间
        if min_trades is not None:
            all_traders = [t for t in all_traders if t.get('total_trades', 0) >= min_trades]
        if max_trades is not None:
            all_traders = [t for t in all_traders if t.get('total_trades', 0) <= max_trades]
        # 活跃天区间
        if min_active_days is not None:
            all_traders = [t for t in all_traders if t.get('active_days', 0) >= min_active_days]
        if max_active_days is not None:
            all_traders = [t for t in all_traders if t.get('active_days', 0) <= max_active_days]
        # 最近活跃
        if has_recent_trade is not None:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=has_recent_trade)
            def is_recent(t):
                last_trade = t.get('last_trade_time')
                if not last_trade:
                    return False
                try:
                    trade_time = datetime.fromisoformat(last_trade.replace('Z', '+00:00'))
                    return trade_time.replace(tzinfo=None) >= cutoff
                except:
                    return False
            all_traders = [t for t in all_traders if is_recent(t)]

        # 应用排序
        valid_sort_fields = {
            'overall_score', 'rating', 'total_trades', 'win_rate',
            'total_pnl', 'roi', 'profit_factor', 'max_drawdown',
            'sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'current_equity', 'active_days',
            'last_trade_time', 'avg_leverage', 'current_positions',
            'recent_7d_pnl', 'recent_7d_win_rate', 'unique_symbols',
            'max_consecutive_wins', 'max_consecutive_losses', 'long_short_ratio'
        }
        if sort_by in valid_sort_fields:
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
                'sharpe_ratio': trader.get('sharpe_ratio', 0),
                'sortino_ratio': trader.get('sortino_ratio', 0),
                'calmar_ratio': trader.get('calmar_ratio', 0),
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


@app.route('/api/traders', methods=['POST'])
def add_trader():
    """
    新增交易者（分析并保存到数据库）
    Body:
        - address: str, 交易者地址
        - lookback_days: int, 分析回溯天数，默认0（全部）
        - max_fills: int, 最大获取交易记录数，默认0（不限制）
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
        config = ScreenerConfig(
            lookback_days=lookback_days,
            max_fills_per_trader=max_fills,
            api_call_delay=0.5,
            max_retries=3,
        )
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


@app.route('/api/traders/<address>', methods=['GET'])
def get_trader_detail(address: str):
    """
    获取交易者详细信息
    """
    try:
        # 获取交易者基本信息
        trader = db.get_trader_by_address(address)

        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 获取交易记录汇总
        fills_summary = db.get_fills_summary(address)

        return jsonify({
            'success': True,
            'data': {
                'trader': trader,
                'fills_summary': fills_summary
            }
        })

    except Exception as e:
        logger.error(f"获取交易者详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/refresh', methods=['POST'])
def refresh_trader(address: str):
    """
    重新分析交易者数据
    Query Parameters:
        - lookback_days: int, 分析回溯天数，默认30
        - max_fills: int, 最大获取交易记录数，默认0（不限制）
    """
    try:
        lookback_days = int(request.args.get('lookback_days', 30))
        max_fills = int(request.args.get('max_fills', 0))

        logger.info(f"开始重新分析交易者: {address}")

        # 初始化筛选器
        config = ScreenerConfig(
            lookback_days=lookback_days,
            max_fills_per_trader=max_fills,
            api_call_delay=0.5,
            max_retries=3,
        )
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

        logger.info(f"交易者分析完成: {address}, 评分: {metrics.overall_score:.1f}, 评级: {metrics.rating.value}, 持仓: {positions_saved}")

        # 返回更新后的数据
        trader = db.get_trader_by_address(address)
        fills_summary = db.get_fills_summary(address)

        return jsonify({
            'success': True,
            'data': {
                'trader': trader,
                'fills_summary': fills_summary,
                'fills_saved': fills_saved
            },
            'message': f'分析完成，保存了 {fills_saved} 条交易记录'
        })

    except Exception as e:
        logger.error(f"重新分析交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/fills', methods=['GET'])
def get_trader_fills(address: str):
    """
    获取交易者的历史交易记录（支持分页和排序）
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - coin: str, 筛选特定币种
        - pnl_filter: str, 盈亏筛选 (all/profit/loss)
        - trade_type: str, 交易类型筛选 (all/open_long/add_long/close_long/open_short/add_short/close_short)
        - sort_by: str, 排序字段 (trade_time/coin/side/px/sz/value/closed_pnl/roi/fee)
        - sort_order: str, 排序方向 (asc/desc)
        - start_date: str, 开始日期 (YYYY-MM-DD)
        - end_date: str, 结束日期 (YYYY-MM-DD)
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
        total_pages = (total_count + limit - 1) // limit  # 向上取整

        # 计算基于全部筛选数据的统计信息
        profitable_count = sum(1 for f in all_fills if f.get('closed_pnl', 0) > 0)
        losing_count = sum(1 for f in all_fills if f.get('closed_pnl', 0) < 0)
        total_pnl = sum(f.get('closed_pnl', 0) for f in all_fills)
        total_fees = sum(f.get('fee', 0) for f in all_fills)
        win_rate = (profitable_count / total_count * 100) if total_count > 0 else 0

        stats = {
            'total': total_count,
            'profitable': profitable_count,
            'losing': losing_count,
            'total_pnl': total_pnl,
            'total_fees': total_fees,
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


@app.route('/api/traders/<address>/positions', methods=['GET'])
def get_trader_positions(address: str):
    """
    获取交易者的当前持仓（来自 assetPositions）
    """
    try:
        positions = db.get_positions(address)

        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions)
        })

    except Exception as e:
        logger.error(f"获取持仓数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/positions/refresh', methods=['POST'])
def refresh_trader_positions(address: str):
    """
    刷新交易者的当前持仓（从 Hyperliquid API 获取最新数据）
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants

        logger.info(f"刷新持仓数据: {address}")

        # 获取最新持仓
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        user_state = info.user_state(address)

        if not user_state:
            return jsonify({
                'success': False,
                'error': '无法获取用户状态'
            }), 404

        # 保存持仓数据
        asset_positions = user_state.get('assetPositions', [])
        positions_saved = db.save_positions(address, asset_positions)

        # 返回更新后的数据
        positions = db.get_positions(address)

        logger.info(f"持仓数据刷新完成: {address}, 持仓数: {positions_saved}")

        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions),
            'message': f'已更新 {positions_saved} 个持仓'
        })

    except Exception as e:
        logger.error(f"刷新持仓数据失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/ai-analysis', methods=['POST'])
def ai_analyze_trader(address: str):
    """
    使用AI分析交易者表现并保存到数据库
    Query Parameters:
        - provider: str, AI提供商 (zhipu/qwen/deepseek/openrouter)，可选
    """
    try:
        provider = request.args.get('provider')

        logger.info(f"开始AI分析交易者: {address}, 提供商: {provider or '默认'}")

        # 获取交易者数据
        trader = db.get_trader_by_address(address)

        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 生成AI分析
        analysis = generate_trader_analysis(trader, provider=provider)

        # 保存AI分析结果到数据库
        db.save_trader_ai_analysis(address, analysis)

        logger.info(f"AI分析完成并已保存: {address}")

        return jsonify({
            'success': True,
            'data': analysis,
            'message': 'AI分析完成并已保存'
        })

    except Exception as e:
        logger.error(f"AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/ai-analysis', methods=['GET'])
def get_trader_ai_analysis(address: str):
    """
    获取交易者的AI分析结果
    """
    try:
        analysis = db.get_trader_ai_analysis(address)

        if not analysis:
            return jsonify({
                'success': False,
                'error': 'AI分析不存在，请先进行分析'
            }), 404

        return jsonify({
            'success': True,
            'data': analysis
        })

    except Exception as e:
        logger.error(f"获取AI分析失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/<address>/history', methods=['GET'])
def get_trader_history(address: str):
    """
    获取交易者的历史分析记录（用于生成历史图表）
    Query Parameters:
        - days: int, 时间范围（天数），默认30，0表示全部
    """
    try:
        from datetime import datetime, timedelta

        days = int(request.args.get('days', 30))

        # 获取交易者当前信息
        trader = db.get_trader_by_address(address)
        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 获取所有交易记录
        fills = db.get_trader_fills(address, limit=10000)

        if not fills:
            return jsonify({
                'success': True,
                'data': {
                    'roi': [],
                    'pnl': [],
                    'equity': []
                }
            })

        # 按时间排序（从旧到新）
        fills.sort(key=lambda x: x['time'])

        # 计算时间范围
        now = datetime.now()
        if days > 0:
            start_time = now - timedelta(days=days)
            # 过滤时间范围内的交易
            fills = [f for f in fills if datetime.fromtimestamp(f['time'] / 1000) >= start_time]

        if not fills:
            return jsonify({
                'success': True,
                'data': {
                    'roi': [],
                    'pnl': [],
                    'equity': []
                }
            })

        # 计算累积数据
        initial_equity = trader.get('current_equity', 0) - trader.get('total_pnl', 0)
        if initial_equity <= 0:
            initial_equity = 10000  # 默认初始资金

        cumulative_pnl = 0
        current_equity = initial_equity

        chart_data = {
            'roi': [],
            'pnl': [],
            'equity': []
        }

        # 添加起始点
        first_time = datetime.fromtimestamp(fills[0]['time'] / 1000)
        chart_data['roi'].append({
            'timestamp': first_time.isoformat(),
            'value': 0
        })
        chart_data['pnl'].append({
            'timestamp': first_time.isoformat(),
            'value': 0
        })
        chart_data['equity'].append({
            'timestamp': first_time.isoformat(),
            'value': initial_equity
        })

        # 按天聚合数据（避免数据点过多）
        daily_data = {}
        for fill in fills:
            trade_time = datetime.fromtimestamp(fill['time'] / 1000)
            day_key = trade_time.strftime('%Y-%m-%d')

            if day_key not in daily_data:
                daily_data[day_key] = {
                    'timestamp': trade_time,
                    'pnl': 0,
                    'fees': 0
                }

            daily_data[day_key]['pnl'] += fill.get('closed_pnl', 0)
            daily_data[day_key]['fees'] += fill.get('fee', 0)

        # 生成每日累积数据
        for day_key in sorted(daily_data.keys()):
            day_info = daily_data[day_key]
            cumulative_pnl += day_info['pnl']
            current_equity = initial_equity + cumulative_pnl

            # 计算ROI
            roi = (cumulative_pnl / initial_equity) if initial_equity > 0 else 0

            chart_data['roi'].append({
                'timestamp': day_info['timestamp'].isoformat(),
                'value': roi
            })
            chart_data['pnl'].append({
                'timestamp': day_info['timestamp'].isoformat(),
                'value': cumulative_pnl
            })
            chart_data['equity'].append({
                'timestamp': day_info['timestamp'].isoformat(),
                'value': current_equity
            })

        return jsonify({
            'success': True,
            'data': chart_data
        })

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/traders/rating/<rating>', methods=['GET'])
def get_traders_by_rating(rating: str):
    """
    根据评级获取交易者（支持分页）
    Path Parameters:
        - rating: str, 评级 (S/A/B/C/D/F)
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - search: str, 地址搜索
    """
    try:
        if rating not in ['S', 'A', 'B', 'C', 'D', 'F']:
            return jsonify({
                'success': False,
                'error': 'Invalid rating. Must be S/A/B/C/D/F'
            }), 400

        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        search = request.args.get('search', '').strip()

        # 获取所有符合评级的交易者
        all_traders = db.get_traders_by_rating(rating)

        # 应用搜索过滤
        if search:
            all_traders = [t for t in all_traders if search.lower() in t['address'].lower()]

        total_count = len(all_traders)
        total_pages = (total_count + limit - 1) // limit

        # 分页
        start = (page - 1) * limit
        end = start + limit
        traders = all_traders[start:end]

        return jsonify({
            'success': True,
            'data': traders,
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
        logger.error(f"获取交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_statistics():
    """
    获取数据库统计信息
    """
    try:
        stats = db.get_statistics()

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/coins', methods=['GET'])
def get_coins():
    """
    获取所有币种列表
    Query Parameters:
        - address: str, 可选，筛选特定交易者的币种
        - exclude_user_perps: bool, 是否排除用户创建的永续合约(@数字格式)，默认true
        - include_stats: bool, 是否包含统计信息，默认false
    """
    try:
        address = request.args.get('address')
        exclude_user_perps = request.args.get('exclude_user_perps', 'true').lower() == 'true'
        include_stats = request.args.get('include_stats', 'false').lower() == 'true'

        coins_data = db.get_all_coins(
            exclude_user_perps=exclude_user_perps,
            address=address
        )

        if include_stats:
            # 返回完整的统计信息
            return jsonify({
                'success': True,
                'data': coins_data,
                'count': len(coins_data)
            })
        else:
            # 只返回币种名称列表
            coins = [c['coin'] for c in coins_data]
            return jsonify({
                'success': True,
                'data': coins,
                'count': len(coins)
            })

    except Exception as e:
        logger.error(f"获取币种列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hyperliquid/coins', methods=['GET'])
def get_hyperliquid_coins():
    """
    获取 Hyperliquid 可交易币种列表（从数据库）
    Query Parameters:
        - active_only: bool, 是否只返回活跃币种，默认true
    """
    try:
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        coins = db.get_hyperliquid_coins(active_only=active_only)

        return jsonify({
            'success': True,
            'data': coins,
            'count': len(coins)
        })

    except Exception as e:
        logger.error(f"获取 Hyperliquid 币种列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hyperliquid/coins/sync', methods=['POST'])
def sync_hyperliquid_coins():
    """
    从 Hyperliquid API 同步币种列表到数据库
    """
    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants

        logger.info("开始同步 Hyperliquid 币种列表...")

        # 获取市场元数据
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        meta = info.meta()

        if not meta or 'universe' not in meta:
            return jsonify({
                'success': False,
                'error': '无法获取 Hyperliquid 市场数据'
            }), 500

        # 解析币种数据
        coins = meta.get('universe', [])
        logger.info(f"获取到 {len(coins)} 个币种")

        # 保存到数据库
        saved_count = db.save_hyperliquid_coins(coins)

        logger.info(f"同步完成: 保存了 {saved_count} 个币种")

        # 返回保存后的列表
        coins_list = db.get_hyperliquid_coins(active_only=True)

        return jsonify({
            'success': True,
            'data': coins_list,
            'count': len(coins_list),
            'message': f'成功同步 {saved_count} 个币种'
        })

    except Exception as e:
        logger.error(f"同步 Hyperliquid 币种失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/hyperliquid/coins/names', methods=['GET'])
def get_hyperliquid_coin_names():
    """
    获取 Hyperliquid 币种名称列表（仅名称，用于下拉选择）
    """
    try:
        names = db.get_hyperliquid_coin_names()

        return jsonify({
            'success': True,
            'data': names,
            'count': len(names)
        })

    except Exception as e:
        logger.error(f"获取 Hyperliquid 币种名称列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """
    获取最近的筛选会话
    Query Parameters:
        - limit: int, 返回数量，默认10
    """
    try:
        limit = int(request.args.get('limit', 10))
        sessions = db.get_recent_sessions(limit=limit)

        return jsonify({
            'success': True,
            'data': sessions,
            'count': len(sessions)
        })

    except Exception as e:
        logger.error(f"获取会话列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/sessions/<int:session_id>/traders', methods=['GET'])
def get_session_traders(session_id: int):
    """
    获取指定会话的交易者
    """
    try:
        traders = db.get_session_traders(session_id)

        return jsonify({
            'success': True,
            'data': traders,
            'count': len(traders)
        })

    except Exception as e:
        logger.error(f"获取会话交易者失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


# ==================== 跟单地址管理 API ====================

@app.route('/api/copy-trading/groups', methods=['GET'])
def get_copy_trading_groups():
    """获取跟单分组列表"""
    try:
        groups = db.get_copy_trading_groups()
        return jsonify({
            'success': True,
            'data': groups
        })
    except Exception as e:
        logger.error(f"获取跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/groups', methods=['POST'])
def create_copy_trading_group():
    """创建跟单分组"""
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({
                'success': False,
                'error': '分组名称不能为空'
            }), 400

        group_id = db.save_copy_trading_group(data)
        return jsonify({
            'success': True,
            'data': {'id': group_id},
            'message': '分组创建成功'
        })
    except Exception as e:
        logger.error(f"创建跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/groups/<int:group_id>', methods=['PUT'])
def update_copy_trading_group(group_id: int):
    """更新跟单分组"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        data['id'] = group_id
        db.save_copy_trading_group(data)
        return jsonify({
            'success': True,
            'message': '分组更新成功'
        })
    except Exception as e:
        logger.error(f"更新跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/groups/<int:group_id>', methods=['DELETE'])
def delete_copy_trading_group(group_id: int):
    """删除跟单分组"""
    try:
        if group_id == 1:
            return jsonify({
                'success': False,
                'error': '默认分组不能删除'
            }), 400

        success = db.delete_copy_trading_group(group_id)
        if success:
            return jsonify({
                'success': True,
                'message': '分组删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '分组不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除跟单分组失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses', methods=['GET'])
def get_copy_trading_addresses():
    """
    获取跟单地址列表
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - group_id: int, 分组ID筛选
        - is_enabled: bool, 状态筛选
        - search: str, 搜索地址或名称
        - sort_by: str, 排序字段
        - sort_order: str, 排序方向
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        group_id = request.args.get('group_id', type=int)
        is_enabled = request.args.get('is_enabled')
        search = request.args.get('search', '').strip()
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')

        # 处理 is_enabled 参数
        if is_enabled is not None:
            is_enabled = is_enabled.lower() == 'true'

        offset = (page - 1) * limit
        addresses, total_count = db.get_copy_trading_addresses(
            group_id=group_id,
            is_enabled=is_enabled,
            search=search,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )

        total_pages = (total_count + limit - 1) // limit

        return jsonify({
            'success': True,
            'data': addresses,
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
        logger.error(f"获取跟单地址列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses/<address>', methods=['GET'])
def get_copy_trading_address(address: str):
    """获取单个跟单地址详情"""
    try:
        data = db.get_copy_trading_address(address)
        if not data:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        logger.error(f"获取跟单地址详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses', methods=['POST'])
def create_copy_trading_address():
    """添加跟单地址"""
    try:
        data = request.get_json()
        if not data or not data.get('address'):
            return jsonify({
                'success': False,
                'error': '地址不能为空'
            }), 400

        # 验证地址格式
        address = data['address'].strip()
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({
                'success': False,
                'error': '无效的以太坊地址格式'
            }), 400

        data['address'] = address
        record_id = db.save_copy_trading_address(data)

        return jsonify({
            'success': True,
            'data': {'id': record_id},
            'message': '跟单地址添加成功'
        })
    except Exception as e:
        logger.error(f"添加跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses/<address>', methods=['PUT'])
def update_copy_trading_address(address: str):
    """更新跟单地址配置"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        # 检查地址是否存在
        existing = db.get_copy_trading_address(address)
        if not existing:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404

        data['address'] = address
        db.save_copy_trading_address(data)

        return jsonify({
            'success': True,
            'message': '更新成功'
        })
    except Exception as e:
        logger.error(f"更新跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses/<address>', methods=['DELETE'])
def delete_copy_trading_address(address: str):
    """删除跟单地址"""
    try:
        success = db.delete_copy_trading_address(address)
        if success:
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses/<address>/toggle', methods=['POST'])
def toggle_copy_trading_address(address: str):
    """启用/禁用跟单地址"""
    try:
        data = request.get_json()
        if data is None or 'is_enabled' not in data:
            return jsonify({
                'success': False,
                'error': '缺少 is_enabled 参数'
            }), 400

        is_enabled = bool(data['is_enabled'])
        success = db.toggle_copy_trading_address(address, is_enabled)

        if success:
            return jsonify({
                'success': True,
                'message': '已启用' if is_enabled else '已禁用'
            })
        else:
            return jsonify({
                'success': False,
                'error': '地址不存在'
            }), 404
    except Exception as e:
        logger.error(f"切换跟单地址状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/addresses/batch', methods=['POST'])
def batch_update_copy_trading_addresses():
    """
    批量操作跟单地址
    Body:
        - action: str, 操作类型 (enable/disable/delete/move_group)
        - addresses: List[str], 地址列表
        - group_id: int, 目标分组ID（仅 move_group 时需要）
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求数据不能为空'
            }), 400

        action = data.get('action')
        addresses = data.get('addresses', [])
        group_id = data.get('group_id')

        if action not in ('enable', 'disable', 'delete', 'move_group'):
            return jsonify({
                'success': False,
                'error': '无效的操作类型'
            }), 400

        if not addresses:
            return jsonify({
                'success': False,
                'error': '地址列表不能为空'
            }), 400

        if action == 'move_group' and group_id is None:
            return jsonify({
                'success': False,
                'error': '移动分组需要指定目标分组ID'
            }), 400

        affected_count = db.batch_update_copy_trading_addresses(
            addresses=addresses,
            action=action,
            group_id=group_id
        )

        return jsonify({
            'success': True,
            'affected_count': affected_count,
            'message': f'批量操作完成，影响 {affected_count} 条记录'
        })
    except Exception as e:
        logger.error(f"批量操作跟单地址失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 跟单订单管理 API ====================

@app.route('/api/copy-trading/orders', methods=['GET'])
def get_copy_trading_orders():
    """
    获取跟单订单列表
    Query Parameters:
        - page: int, 页码，默认1
        - limit: int, 每页数量，默认20
        - target_address: str, 筛选目标地址
        - symbol: str, 筛选交易对
        - status: str, 筛选状态 (pending/success/failed)
        - action: str, 筛选操作类型 (open/close)
        - is_dry_run: bool, 筛选模拟/实盘
        - days: int, 最近N天，默认7
        - sort_by: str, 排序字段，默认created_at
        - sort_order: str, 排序方向，默认desc
    """
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        target_address = request.args.get('target_address')
        symbol = request.args.get('symbol')
        status = request.args.get('status')
        action = request.args.get('action')
        is_dry_run = request.args.get('is_dry_run')
        days = int(request.args.get('days', 7))
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')

        # 处理 is_dry_run 参数
        if is_dry_run is not None:
            is_dry_run = is_dry_run.lower() == 'true'

        offset = (page - 1) * limit
        orders, total_count = db.get_copy_orders(
            target_address=target_address,
            symbol=symbol,
            status=status,
            action=action,
            is_dry_run=is_dry_run,
            days=days,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order
        )

        total_pages = (total_count + limit - 1) // limit

        return jsonify({
            'success': True,
            'data': orders,
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
        logger.error(f"获取跟单订单列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/orders/stats', methods=['GET'])
def get_copy_trading_order_stats():
    """
    获取跟单订单统计
    Query Parameters:
        - target_address: str, 筛选目标地址
        - days: int, 统计天数，默认7
    """
    try:
        target_address = request.args.get('target_address')
        days = int(request.args.get('days', 7))

        stats = db.get_copy_order_stats(
            target_address=target_address,
            days=days
        )

        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取跟单订单统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/orders/cleanup', methods=['POST'])
def cleanup_copy_trading_orders():
    """
    清理旧订单记录
    Query Parameters:
        - days: int, 保留最近N天的记录，默认30
    """
    try:
        days = int(request.args.get('days', 30))
        deleted_count = db.delete_old_copy_orders(days)

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'已清理 {deleted_count} 条旧订单记录'
        })
    except Exception as e:
        logger.error(f"清理旧订单记录失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== 跟单仓位状态管理 API ====================

@app.route('/api/copy-trading/positions', methods=['GET'])
def get_copy_position_states():
    """
    获取所有跟单仓位状态（用于重启后恢复的持久化状态）
    Query Parameters:
        - target_address: str, 筛选目标地址
    """
    try:
        target_address = request.args.get('target_address')

        with db._get_connection() as conn:
            cursor = conn.cursor()

            if target_address:
                cursor.execute("""
                    SELECT cps.*, cta.name as target_name
                    FROM copy_position_states cps
                    LEFT JOIN copy_trading_addresses cta ON cps.target_address = cta.address
                    WHERE cps.target_address = ?
                    ORDER BY cps.updated_at DESC
                """, (target_address,))
            else:
                cursor.execute("""
                    SELECT cps.*, cta.name as target_name
                    FROM copy_position_states cps
                    LEFT JOIN copy_trading_addresses cta ON cps.target_address = cta.address
                    ORDER BY cps.updated_at DESC
                """)

            positions = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            'success': True,
            'data': positions,
            'count': len(positions)
        })
    except Exception as e:
        logger.error(f"获取跟单仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/positions/stats', methods=['GET'])
def get_copy_position_stats():
    """
    获取跟单仓位统计
    """
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()

            # 总仓位数
            cursor.execute("SELECT COUNT(*) FROM copy_position_states")
            total_positions = cursor.fetchone()[0]

            # 按目标地址分组统计
            cursor.execute("""
                SELECT
                    cps.target_address,
                    cta.name as target_name,
                    COUNT(*) as position_count,
                    SUM(cps.notional) as total_notional
                FROM copy_position_states cps
                LEFT JOIN copy_trading_addresses cta ON cps.target_address = cta.address
                GROUP BY cps.target_address
                ORDER BY position_count DESC
            """)
            by_target = [dict(row) for row in cursor.fetchall()]

            # 按币种统计
            cursor.execute("""
                SELECT
                    symbol,
                    side,
                    COUNT(*) as count,
                    SUM(ABS(size)) as total_size,
                    SUM(notional) as total_notional
                FROM copy_position_states
                GROUP BY symbol, side
                ORDER BY total_notional DESC
            """)
            by_symbol = [dict(row) for row in cursor.fetchall()]

            # 多空统计
            cursor.execute("""
                SELECT
                    side,
                    COUNT(*) as count,
                    SUM(notional) as total_notional
                FROM copy_position_states
                GROUP BY side
            """)
            by_side = {row['side']: {'count': row['count'], 'notional': row['total_notional']} for row in cursor.fetchall()}

        return jsonify({
            'success': True,
            'data': {
                'total_positions': total_positions,
                'by_target': by_target,
                'by_symbol': by_symbol,
                'by_side': by_side
            }
        })
    except Exception as e:
        logger.error(f"获取跟单仓位统计失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/positions/<target_address>', methods=['GET'])
def get_target_position_states(target_address: str):
    """
    获取特定目标的仓位状态
    """
    try:
        positions = db.get_copied_positions(target_address)

        return jsonify({
            'success': True,
            'data': list(positions.values()),
            'count': len(positions)
        })
    except Exception as e:
        logger.error(f"获取目标仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/positions/<target_address>/<symbol>', methods=['DELETE'])
def delete_position_state(target_address: str, symbol: str):
    """
    删除单个仓位状态
    """
    try:
        success = db.delete_copied_position(target_address, symbol)

        if success:
            return jsonify({
                'success': True,
                'message': f'已删除 {target_address[:10]}... 的 {symbol} 仓位状态'
            })
        else:
            return jsonify({
                'success': False,
                'error': '仓位状态不存在'
            }), 404
    except Exception as e:
        logger.error(f"删除仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/positions/<target_address>', methods=['DELETE'])
def clear_target_position_states(target_address: str):
    """
    清空目标的所有仓位状态
    """
    try:
        deleted_count = db.clear_copied_positions(target_address)

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'已清空 {target_address[:10]}... 的 {deleted_count} 个仓位状态'
        })
    except Exception as e:
        logger.error(f"清空仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/copy-trading/positions/clear-all', methods=['POST'])
def clear_all_position_states():
    """
    清空所有仓位状态（谨慎使用）
    """
    try:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM copy_position_states")
            deleted_count = cursor.rowcount

        return jsonify({
            'success': True,
            'data': {'deleted_count': deleted_count},
            'message': f'已清空所有 {deleted_count} 个仓位状态'
        })
    except Exception as e:
        logger.error(f"清空所有仓位状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    logger.info("启动 Trader Analytics API Server...")
    logger.info("API 文档:")
    logger.info("  GET  /api/traders - 获取交易者列表")
    logger.info("  GET  /api/traders/<address> - 获取交易者详情")
    logger.info("  POST /api/traders/<address>/refresh - 刷新分析")
    logger.info("  GET  /api/traders/<address>/fills - 获取历史交易")
    logger.info("  GET  /api/traders/<address>/positions - 获取当前持仓")
    logger.info("  GET  /api/traders/<address>/history - 获取历史图表数据")
    logger.info("  GET  /api/traders/rating/<rating> - 按评级筛选")
    logger.info("  GET  /api/coins - 获取币种列表")
    logger.info("  GET  /api/stats - 获取统计信息")
    logger.info("  GET  /api/sessions - 获取筛选会话")
    logger.info("  GET  /api/copy-trading/orders - 获取跟单订单")
    logger.info("  GET  /api/copy-trading/orders/stats - 订单统计")
    logger.info("  GET  /health - 健康检查")

    app.run(host='0.0.0.0', port=5000, debug=True)
