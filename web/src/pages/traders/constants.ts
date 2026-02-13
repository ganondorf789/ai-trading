import type { Column, ColumnKey } from './types';

export const columns: Column[] = [
  // 基础
  { uid: 'star', name: '收藏', sortable: false, group: '基础' },
  { uid: 'rating', name: '评级', sortable: true, group: '基础' },
  { uid: 'address', name: '地址', sortable: false, group: '基础' },
  { uid: 'overall_score', name: '评分', sortable: true, group: '基础' },
  // 交易统计
  { uid: 'total_trades', name: '交易数', sortable: true, group: '统计' },
  { uid: 'win_rate', name: '胜率', sortable: true, group: '统计' },
  { uid: 'total_pnl', name: '总盈亏', sortable: true, group: '盈亏' },
  { uid: 'roi', name: 'ROI', sortable: true, group: '盈亏' },
  { uid: 'profit_factor', name: '盈亏比', sortable: true, group: '盈亏' },
  // 风险
  { uid: 'max_drawdown', name: '回撤', sortable: true, group: '风险' },
  { uid: 'sharpe_ratio', name: 'Sharpe', sortable: true, group: '风险' },
  { uid: 'sortino_ratio', name: 'Sortino', sortable: true, group: '风险' },
  { uid: 'calmar_ratio', name: 'Calmar', sortable: true, group: '风险' },
  // 活跃度
  { uid: 'active_days', name: '活跃天', sortable: true, group: '活跃' },
  { uid: 'current_equity', name: '权益', sortable: true, group: '活跃' },
  { uid: 'avg_leverage', name: '杠杆', sortable: true, group: '活跃' },
  { uid: 'current_positions', name: '持仓', sortable: true, group: '活跃' },
  { uid: 'last_trade_time', name: '最后交易', sortable: true, group: '活跃' },
  // 近期表现
  { uid: 'recent_7d_pnl', name: '7天PnL', sortable: true, group: '近期' },
  { uid: 'recent_7d_win_rate', name: '7天胜率', sortable: true, group: '近期' },
  // 交易特征
  { uid: 'max_consecutive_wins', name: '连赢', sortable: true, group: '特征' },
  { uid: 'max_consecutive_losses', name: '连亏', sortable: true, group: '特征' },
  { uid: 'unique_symbols', name: '品种数', sortable: true, group: '特征' },
  { uid: 'favorite_symbol', name: '常用品种', sortable: false, group: '特征' },
  { uid: 'long_short_ratio', name: '多空比', sortable: true, group: '特征' },
];

export const INITIAL_VISIBLE_COLUMNS: ColumnKey[] = [
  'star', 'rating', 'address', 'overall_score', 'total_trades', 'win_rate',
  'total_pnl', 'roi', 'profit_factor', 'max_drawdown', 'sharpe_ratio',
  'sortino_ratio', 'calmar_ratio', 'current_equity', 'active_days', 'avg_leverage',
  'current_positions', 'recent_7d_pnl', 'recent_7d_win_rate',
  'max_consecutive_wins', 'max_consecutive_losses', 'unique_symbols',
  'favorite_symbol', 'long_short_ratio', 'last_trade_time'
];

export const ROWS_PER_PAGE = 20;

export const RATING_OPTIONS = ['S', 'A', 'B', 'C', 'D', 'F'] as const;

// 周期选项
export const PERIOD_OPTIONS = [
  { key: '1d' as const, label: '1天', days: 1 },
  { key: '7d' as const, label: '1周', days: 7 },
  { key: '30d' as const, label: '1月', days: 30 },
  { key: 'all' as const, label: '全部', days: undefined },
];

// 标签选项 - key用于API传参，label用于显示
export const TAG_OPTIONS = {
  accountValue: [
    { key: 'small_capital', label: '小资金' },
    { key: 'medium_capital', label: '中等资金' },
    { key: 'whale', label: '巨鲸' },
  ],
  tradingRhythm: [
    { key: 'long_term', label: '长线' },
    { key: 'swing', label: '波段' },
    { key: 'short_term', label: '短线' },
    { key: 'ultra_short', label: '超短线' },
  ],
  profitStatus: [
    { key: 'consistent_profit', label: '持续盈利' },
    { key: 'volatile_profit', label: '波动盈利' },
    { key: 'break_even', label: '盈亏平衡' },
  ],
  directionPreference: [
    { key: 'bearish', label: '偏空头' },
    { key: 'neutral', label: '中性' },
    { key: 'bullish', label: '偏多头' },
  ],
  tradingStyle: [
    { key: 'high_freq_stable', label: '高频稳健' },
    { key: 'high_freq_aggressive', label: '高频激进' },
    { key: 'low_freq_stable', label: '低频稳健' },
    { key: 'stable_profit', label: '稳定盈利' },
    { key: 'high_risk_high_return', label: '高风险高回报' },
    { key: 'asymmetric_master', label: '非对称高手' },
  ],
} as const;

// 标签分组配置（用于 FilterSection 渲染）
export const TAG_GROUPS = [
  { key: 'accountValue', label: '账户总价值', filterKey: 'tagAccountValue', options: TAG_OPTIONS.accountValue },
  { key: 'directionPreference', label: '方向偏好', filterKey: 'tagDirectionPreference', options: TAG_OPTIONS.directionPreference },
  { key: 'tradingRhythm', label: '交易节奏', filterKey: 'tagTradingRhythm', options: TAG_OPTIONS.tradingRhythm },
  { key: 'profitStatus', label: '盈利状态', filterKey: 'tagProfitStatus', options: TAG_OPTIONS.profitStatus },
  { key: 'tradingStyle', label: '交易风格', filterKey: 'tagTradingStyle', options: TAG_OPTIONS.tradingStyle },
] as const;

// 高级筛选可用字段
export const ADVANCED_FILTER_FIELDS = [
  // 基础指标
  { key: 'overall_score', label: '评分' },
  { key: 'win_rate', label: '胜率' },
  { key: 'total_trades', label: '交易数' },
  { key: 'winning_trades', label: '盈利次数' },
  { key: 'active_days', label: '活跃天数' },
  // 盈亏指标
  { key: 'total_pnl', label: '总盈亏' },
  { key: 'realized_pnl', label: '已实现盈亏' },
  { key: 'unrealized_pnl', label: '未实现盈亏' },
  { key: 'roi', label: 'ROI' },
  { key: 'profit_factor', label: '盈亏比' },
  { key: 'recent_7d_pnl', label: '7天盈亏' },
  { key: 'recent_7d_win_rate', label: '7天胜率' },
  // 风险指标
  { key: 'max_drawdown', label: '最大回撤' },
  { key: 'sharpe_ratio', label: '夏普比率' },
  { key: 'sortino_ratio', label: 'Sortino' },
  { key: 'calmar_ratio', label: 'Calmar' },
  // 活跃度
  { key: 'current_equity', label: '权益' },
  { key: 'avg_leverage', label: '平均杠杆' },
  { key: 'current_positions', label: '当前持仓数' },
  // 多空分项
  { key: 'long_trades', label: '多仓数' },
  { key: 'long_realized_pnl', label: '多仓盈亏' },
  { key: 'long_win_rate', label: '多仓胜率' },
  { key: 'short_trades', label: '空仓数' },
  { key: 'short_realized_pnl', label: '空仓盈亏' },
  { key: 'short_win_rate', label: '空仓胜率' },
  { key: 'long_short_ratio', label: '多空比' },
  { key: 'long_position_ratio', label: '多仓比例' },
  // 账户和保证金
  { key: 'account_value', label: '账户价值' },
  { key: 'used_margin', label: '已用保证金' },
  { key: 'perp_total_value', label: '永续总价值' },
  { key: 'position_value', label: '持仓价值' },
  { key: 'long_position_value', label: '多仓价值' },
  { key: 'short_position_value', label: '空仓价值' },
  { key: 'margin_usage_rate', label: '保证金使用率' },
  // 其他
  { key: 'unique_symbols', label: '品种数' },
  { key: 'max_single_win', label: '最大单笔盈利' },
  { key: 'max_single_loss', label: '最大单笔亏损' },
  { key: 'max_consecutive_wins', label: '最大连赢' },
  { key: 'max_consecutive_losses', label: '最大连亏' },
];

// 筛选运算符
export const FILTER_OPERATORS = [
  { key: '>', label: '>' },
  { key: '>=', label: '>=' },
  { key: '<', label: '<' },
  { key: '<=', label: '<=' },
  { key: '=', label: '=' },
  { key: '!=', label: '!=' },
  { key: 'exist', label: '存在' },
];

// 字段名→中文标签映射
export const FIELD_LABELS: Record<string, string> = Object.fromEntries(
  ADVANCED_FILTER_FIELDS.map(f => [f.key, f.label])
);
