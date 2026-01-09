"""
交易者管理相关路由
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

from database import TraderDatabase
from screener import TraderScreener, ScreenerConfig
from services.ai_analysis import generate_trader_analysis

logger = logging.getLogger(__name__)

traders_bp = Blueprint('traders', __name__)
db = TraderDatabase()


@traders_bp.route('/api/traders', methods=['GET'])
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
        has_recent_trade = request.args.get('has_recent_trade', type=int)

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
                # 用户标记
                'is_starred': trader.get('is_starred', False),
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


@traders_bp.route('/api/traders', methods=['POST'])
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
        config = ScreenerConfig()
        config.data.lookback_days = lookback_days
        config.data.max_fills_per_trader = max_fills
        config.api.api_call_delay = 0.5
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


@traders_bp.route('/api/traders/<address>', methods=['GET'])
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


@traders_bp.route('/api/traders/<address>/refresh', methods=['POST'])
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
        config = ScreenerConfig()
        config.data.lookback_days = lookback_days
        config.data.max_fills_per_trader = max_fills
        config.api.api_call_delay = 0.5
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


@traders_bp.route('/api/traders/<address>/fills', methods=['GET'])
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
        total_pages = (total_count + limit - 1) // limit

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


@traders_bp.route('/api/traders/<address>/positions', methods=['GET'])
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


@traders_bp.route('/api/traders/<address>/positions/refresh', methods=['POST'])
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


@traders_bp.route('/api/traders/<address>/star', methods=['POST'])
def toggle_trader_star(address: str):
    """
    切换交易者的收藏状态
    Request Body:
        - is_starred: bool, 是否收藏
    """
    try:
        data = request.get_json() or {}
        is_starred = data.get('is_starred', True)

        logger.info(f"切换收藏状态: {address}, is_starred={is_starred}")

        # 检查交易者是否存在
        trader = db.get_trader_by_address(address)
        if not trader:
            return jsonify({
                'success': False,
                'error': 'Trader not found'
            }), 404

        # 切换收藏状态
        success = db.toggle_star(address, is_starred)

        if success:
            return jsonify({
                'success': True,
                'data': {'is_starred': is_starred},
                'message': '已收藏' if is_starred else '已取消收藏'
            })
        else:
            return jsonify({
                'success': False,
                'error': '更新失败'
            }), 500

    except Exception as e:
        logger.error(f"切换收藏状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@traders_bp.route('/api/traders/<address>/ai-analysis', methods=['POST'])
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

        # 获取币种统计数据
        fills_summary = db.get_fills_summary(address, exclude_user_perps=True)
        coin_stats = fills_summary.get('by_coin', []) if fills_summary else []

        # 获取当前持仓数据
        positions = db.get_positions(address)

        # 生成AI分析（传入币种统计和持仓数据）
        analysis = generate_trader_analysis(
            trader,
            provider=provider,
            coin_stats=coin_stats,
            positions=positions
        )

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


@traders_bp.route('/api/traders/<address>/ai-analysis', methods=['GET'])
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


@traders_bp.route('/api/traders/<address>/history', methods=['GET'])
def get_trader_history(address: str):
    """
    获取交易者的历史分析记录（用于生成历史图表）
    Query Parameters:
        - days: int, 时间范围（天数），默认30，0表示全部
    """
    try:
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
            initial_equity = 10000

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


@traders_bp.route('/api/traders/rating/<rating>', methods=['GET'])
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


@traders_bp.route('/api/stats', methods=['GET'])
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


@traders_bp.route('/api/coins', methods=['GET'])
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


@traders_bp.route('/api/hyperliquid/coins', methods=['GET'])
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


@traders_bp.route('/api/hyperliquid/coins/sync', methods=['POST'])
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


@traders_bp.route('/api/hyperliquid/coins/names', methods=['GET'])
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


@traders_bp.route('/api/sessions', methods=['GET'])
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


@traders_bp.route('/api/sessions/<int:session_id>/traders', methods=['GET'])
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
