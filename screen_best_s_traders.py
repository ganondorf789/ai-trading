"""
S级交易员优选筛选工具

从 S 级交易员中筛选出最优秀的交易员，结合:
- trader_metrics: 基础评分、风险指标
- position_history: 仓位级别胜率、持仓风格、近期表现

筛选维度:
1. 基础质量: 夏普比率、最大回撤、盈亏比
2. 仓位表现: 仓位级别胜率、仓位盈亏比
3. 近期状态: 近期仓位盈利、活跃度
4. 持仓风格: 持仓时长（短线/中线/长线）
"""
import sys
import argparse
from pathlib import Path
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from database import TraderDatabase


# 预设筛选配置
PRESETS = {
    'default': {
        'name': '默认（综合）',
        'description': '平衡各项指标的综合筛选',
        'params': {
            'min_sharpe': 0.5,
            'max_drawdown': 0.3,
            'min_profit_factor': 1.2,
            'min_closed_positions': 20,
            'min_position_win_rate': 0.45,
            'min_position_profit_factor': 1.0,
            'recent_days': 30,
            'min_recent_positions': 3,
            'require_recent_profit': True,
            'max_days_since_last_trade': 7,
            'sort_by': 'recent_pnl',
        }
    },
    'safe': {
        'name': '稳健型',
        'description': '低风险、高胜率、稳定盈利',
        'params': {
            'min_sharpe': 1.0,
            'max_drawdown': 0.2,
            'min_profit_factor': 1.5,
            'min_closed_positions': 30,
            'min_position_win_rate': 0.55,
            'min_position_profit_factor': 1.3,
            'recent_days': 30,
            'min_recent_positions': 5,
            'require_recent_profit': True,
            'max_days_since_last_trade': 5,
            'sort_by': 'sharpe_ratio',
        }
    },
    'aggressive': {
        'name': '激进型',
        'description': '高收益优先，容忍较高风险',
        'params': {
            'min_sharpe': 0.3,
            'max_drawdown': 0.4,
            'min_profit_factor': 1.0,
            'min_closed_positions': 15,
            'min_position_win_rate': 0.40,
            'min_position_profit_factor': 0.8,
            'recent_days': 14,
            'min_recent_positions': 2,
            'require_recent_profit': True,
            'max_days_since_last_trade': 7,
            'sort_by': 'recent_pnl',
        }
    },
    'scalper': {
        'name': '短线型',
        'description': '短线交易风格，平均持仓 < 24 小时',
        'params': {
            'min_sharpe': 0.5,
            'max_drawdown': 0.3,
            'min_profit_factor': 1.2,
            'min_closed_positions': 30,
            'min_position_win_rate': 0.50,
            'min_position_profit_factor': 1.0,
            'recent_days': 14,
            'min_recent_positions': 5,
            'require_recent_profit': True,
            'max_days_since_last_trade': 3,
            'max_holding_hours': 24,
            'sort_by': 'position_win_rate',
        }
    },
    'swing': {
        'name': '波段型',
        'description': '中线波段交易，持仓 1-7 天',
        'params': {
            'min_sharpe': 0.8,
            'max_drawdown': 0.25,
            'min_profit_factor': 1.3,
            'min_closed_positions': 20,
            'min_position_win_rate': 0.50,
            'min_position_profit_factor': 1.2,
            'recent_days': 30,
            'min_recent_positions': 3,
            'require_recent_profit': True,
            'max_days_since_last_trade': 10,
            'min_holding_hours': 24,
            'max_holding_hours': 168,
            'sort_by': 'position_profit_factor',
        }
    },
    'hot': {
        'name': '热门（近期表现）',
        'description': '重点关注近 7 天表现最好的交易员',
        'params': {
            'min_sharpe': 0.3,
            'max_drawdown': 0.35,
            'min_profit_factor': 1.0,
            'min_closed_positions': 10,
            'min_position_win_rate': 0.40,
            'min_position_profit_factor': 0.8,
            'recent_days': 7,
            'min_recent_positions': 2,
            'require_recent_profit': True,
            'max_days_since_last_trade': 3,
            'sort_by': 'recent_pnl',
        }
    },
}


def format_pnl(value: float) -> str:
    """格式化 PnL 显示"""
    if value >= 0:
        return f"+${value:,.0f}"
    return f"-${abs(value):,.0f}"


def format_percent(value: float) -> str:
    """格式化百分比显示"""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def format_holding_style(hours: float) -> str:
    """根据持仓时长判断交易风格"""
    if hours is None or hours == 0:
        return "未知"
    if hours < 4:
        return "超短线"
    if hours < 24:
        return "短线"
    if hours < 168:
        return "中线"
    return "长线"


def print_trader_summary(traders: List[Dict], detailed: bool = False):
    """打印交易员摘要"""
    if not traders:
        logger.warning("没有找到符合条件的交易员")
        return
    
    logger.info("")
    logger.info("=" * 140)
    logger.info("S级优选交易员列表")
    logger.info("=" * 140)
    
    # 表头
    header = (
        f"{'#':>2} {'评分':>5} {'地址':<14} "
        f"{'仓位胜率':>8} {'仓位盈亏比':>10} "
        f"{'近期PnL':>12} {'近期胜率':>8} "
        f"{'总PnL':>14} {'夏普':>6} {'回撤':>6} "
        f"{'风格':<6} {'持仓数':>6} {'收藏':>4}"
    )
    logger.info(header)
    logger.info("-" * 140)
    
    for i, t in enumerate(traders, 1):
        addr = t['address'][:12] + "..."
        score = t.get('overall_score', 0)
        
        # 仓位指标
        pos_win_rate = format_percent(t.get('position_win_rate'))
        pos_pf = t.get('position_profit_factor')
        pos_pf_str = f"{pos_pf:.2f}" if pos_pf else "N/A"
        
        # 近期表现
        recent_pnl = format_pnl(t.get('recent_pnl', 0))
        recent_win_rate = format_percent(t.get('recent_position_win_rate'))
        
        # 其他指标
        total_pnl = format_pnl(t.get('total_pnl', 0))
        sharpe = f"{t.get('sharpe_ratio', 0):.2f}"
        drawdown = f"{t.get('max_drawdown', 0)*100:.1f}%"
        
        # 持仓风格
        holding_hours = t.get('avg_holding_hours', 0)
        style = format_holding_style(holding_hours)
        
        # 仓位数
        positions = t.get('closed_positions', 0)
        
        # 收藏状态
        starred = "⭐" if t.get('is_starred') else ""
        
        row = (
            f"{i:>2} {score:>5.1f} {addr:<14} "
            f"{pos_win_rate:>8} {pos_pf_str:>10} "
            f"{recent_pnl:>12} {recent_win_rate:>8} "
            f"{total_pnl:>14} {sharpe:>6} {drawdown:>6} "
            f"{style:<6} {positions:>6} {starred:>4}"
        )
        logger.info(row)
    
    logger.info("=" * 140)
    
    # 详细信息
    if detailed:
        print_detailed_info(traders)


def print_detailed_info(traders: List[Dict]):
    """打印详细信息"""
    logger.info("")
    logger.info("详细信息:")
    logger.info("-" * 100)
    
    for i, t in enumerate(traders, 1):
        name = t.get('trader_name') or t['address'][:16] + "..."
        group = t.get('group_name') or "未分组"
        
        logger.info(f"\n[{i}] {name} ({group})")
        logger.info(f"    地址: {t['address']}")
        
        # 基础指标
        logger.info(
            f"    基础: 评分={t.get('overall_score', 0):.1f}, "
            f"交易胜率={t.get('trade_win_rate', 0)*100:.1f}%, "
            f"交易盈亏比={t.get('trade_profit_factor', 0):.2f}, "
            f"总PnL={format_pnl(t.get('total_pnl', 0))}"
        )
        
        # 风险指标
        logger.info(
            f"    风险: 夏普={t.get('sharpe_ratio', 0):.2f}, "
            f"索提诺={t.get('sortino_ratio', 0):.2f}, "
            f"最大回撤={t.get('max_drawdown', 0)*100:.1f}%"
        )
        
        # 仓位指标
        logger.info(
            f"    仓位: 总仓位={t.get('total_positions', 0)}, "
            f"已平仓={t.get('closed_positions', 0)}, "
            f"胜率={format_percent(t.get('position_win_rate'))}, "
            f"盈亏比={t.get('position_profit_factor') or 'N/A'}"
        )
        
        # 持仓风格
        holding = t.get('avg_holding_hours', 0)
        build_trades = t.get('avg_build_trades', 1)
        logger.info(
            f"    风格: 平均持仓={holding:.1f}小时 ({format_holding_style(holding)}), "
            f"平均建仓次数={build_trades:.1f}"
        )
        
        # 近期表现
        recent_pos = t.get('recent_positions', 0)
        recent_wins = t.get('recent_wins', 0)
        recent_pnl = t.get('recent_pnl', 0)
        logger.info(
            f"    近期: 仓位={recent_pos}, "
            f"盈利={recent_wins}, "
            f"PnL={format_pnl(recent_pnl)}, "
            f"胜率={format_percent(t.get('recent_position_win_rate'))}"
        )
        
        # 当前状态
        current_pos = t.get('current_positions', 0)
        last_trade = t.get('last_trade_time')
        last_trade_str = last_trade.strftime('%Y-%m-%d %H:%M') if last_trade else 'N/A'
        logger.info(
            f"    状态: 当前持仓={current_pos}, 最后交易={last_trade_str}"
        )


def print_addresses_only(traders: List[Dict]):
    """只打印地址列表"""
    logger.info("")
    logger.info("符合条件的交易员地址:")
    logger.info("-" * 50)
    for t in traders:
        name = t.get('trader_name')
        if name:
            logger.info(f"  {t['address']}  # {name}")
        else:
            logger.info(f"  {t['address']}")


def list_presets():
    """列出所有预设配置"""
    logger.info("")
    logger.info("可用的筛选预设:")
    logger.info("=" * 60)
    for key, preset in PRESETS.items():
        logger.info(f"  {key:<12} - {preset['name']}")
        logger.info(f"               {preset['description']}")
        logger.info("")


def main():
    parser = argparse.ArgumentParser(
        description="S级交易员优选筛选工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python screen_best_s_traders.py                    # 使用默认配置
  python screen_best_s_traders.py --preset safe      # 使用稳健型预设
  python screen_best_s_traders.py --preset scalper   # 筛选短线交易员
  python screen_best_s_traders.py --preset hot       # 近期表现最好
  python screen_best_s_traders.py --list-presets     # 列出所有预设
  python screen_best_s_traders.py --detailed         # 显示详细信息
  python screen_best_s_traders.py --addresses-only   # 只显示地址
  
自定义筛选:
  python screen_best_s_traders.py --min-sharpe 1.5 --max-drawdown 0.2
        """
    )
    
    # 预设选择
    parser.add_argument(
        "--preset", "-p",
        type=str,
        default="default",
        choices=list(PRESETS.keys()),
        help="使用预设配置 (default: default)"
    )
    parser.add_argument(
        "--list-presets", "-l",
        action="store_true",
        help="列出所有可用预设"
    )
    
    # 基础筛选参数
    parser.add_argument("--min-sharpe", type=float, help="最小夏普比率")
    parser.add_argument("--max-drawdown", type=float, help="最大回撤")
    parser.add_argument("--min-profit-factor", type=float, help="最小盈亏比")
    
    # 仓位筛选参数
    parser.add_argument("--min-positions", type=int, help="最小已平仓位数")
    parser.add_argument("--min-position-win-rate", type=float, help="最小仓位胜率 (0-1)")
    parser.add_argument("--min-position-pf", type=float, help="最小仓位盈亏比")
    
    # 近期表现
    parser.add_argument("--recent-days", type=int, help="近期天数")
    parser.add_argument("--min-recent-positions", type=int, help="近期最小仓位数")
    parser.add_argument("--no-require-profit", action="store_true", help="不要求近期盈利")
    
    # 活跃度
    parser.add_argument("--max-inactive-days", type=int, help="最大不活跃天数")
    
    # 持仓风格
    parser.add_argument("--min-holding-hours", type=float, help="最小平均持仓时长（小时）")
    parser.add_argument("--max-holding-hours", type=float, help="最大平均持仓时长（小时）")
    
    # 排序和输出
    parser.add_argument(
        "--sort-by", "-s",
        type=str,
        choices=['recent_pnl', 'position_win_rate', 'overall_score', 'sharpe_ratio', 'position_profit_factor', 'total_pnl'],
        help="排序字段"
    )
    parser.add_argument("--limit", "-n", type=int, default=20, help="返回数量 (default: 20)")
    
    # 输出格式
    parser.add_argument("--detailed", "-d", action="store_true", help="显示详细信息")
    parser.add_argument("--addresses-only", "-a", action="store_true", help="只显示地址")
    
    args = parser.parse_args()
    
    # 列出预设
    if args.list_presets:
        list_presets()
        return
    
    # 获取预设配置
    preset = PRESETS.get(args.preset, PRESETS['default'])
    params = preset['params'].copy()
    
    # 覆盖用户指定的参数
    if args.min_sharpe is not None:
        params['min_sharpe'] = args.min_sharpe
    if args.max_drawdown is not None:
        params['max_drawdown'] = args.max_drawdown
    if args.min_profit_factor is not None:
        params['min_profit_factor'] = args.min_profit_factor
    if args.min_positions is not None:
        params['min_closed_positions'] = args.min_positions
    if args.min_position_win_rate is not None:
        params['min_position_win_rate'] = args.min_position_win_rate
    if args.min_position_pf is not None:
        params['min_position_profit_factor'] = args.min_position_pf
    if args.recent_days is not None:
        params['recent_days'] = args.recent_days
    if args.min_recent_positions is not None:
        params['min_recent_positions'] = args.min_recent_positions
    if args.no_require_profit:
        params['require_recent_profit'] = False
    if args.max_inactive_days is not None:
        params['max_days_since_last_trade'] = args.max_inactive_days
    if args.min_holding_hours is not None:
        params['min_holding_hours'] = args.min_holding_hours
    if args.max_holding_hours is not None:
        params['max_holding_hours'] = args.max_holding_hours
    if args.sort_by is not None:
        params['sort_by'] = args.sort_by
    
    params['limit'] = args.limit
    
    # 显示筛选配置
    logger.info("=" * 80)
    logger.info(f"S级交易员优选筛选 - 预设: {preset['name']}")
    logger.info("=" * 80)
    logger.info(f"描述: {preset['description']}")
    logger.info("")
    logger.info("筛选条件:")
    logger.info(f"  基础: 夏普≥{params['min_sharpe']}, 回撤≤{params['max_drawdown']*100:.0f}%, 盈亏比≥{params['min_profit_factor']}")
    logger.info(f"  仓位: 已平仓≥{params['min_closed_positions']}, 胜率≥{params['min_position_win_rate']*100:.0f}%, 盈亏比≥{params['min_position_profit_factor']}")
    logger.info(f"  近期: {params['recent_days']}天内≥{params['min_recent_positions']}仓位, 要求盈利={params['require_recent_profit']}")
    logger.info(f"  活跃: 最后交易≤{params['max_days_since_last_trade']}天")
    if params.get('min_holding_hours') or params.get('max_holding_hours'):
        min_h = params.get('min_holding_hours', 0)
        max_h = params.get('max_holding_hours', '∞')
        logger.info(f"  风格: 持仓时长 {min_h} - {max_h} 小时")
    logger.info(f"  排序: {params['sort_by']}, 数量: {params['limit']}")
    logger.info("")
    
    # 初始化数据库
    logger.info("连接数据库...")
    db = TraderDatabase()
    
    # 执行筛选
    logger.info("执行筛选查询...")
    traders = db.get_best_s_traders(**params)
    
    logger.info(f"找到 {len(traders)} 个符合条件的交易员")
    
    # 输出结果
    if args.addresses_only:
        print_addresses_only(traders)
    else:
        print_trader_summary(traders, detailed=args.detailed)
    
    db.close()


if __name__ == "__main__":
    main()
