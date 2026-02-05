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

// 标签选项 - key用于API传参，label用于显示
export const TAG_OPTIONS = {
  capitalScale: [
    { key: 'small', label: '小资金' },
    { key: 'medium', label: '中等资金' },
    { key: 'large', label: '大资金' },
  ],
  tradingDirection: [
    { key: 'bearish', label: '偏空头' },
    { key: 'neutral', label: '中性' },
    { key: 'bullish', label: '偏多头' },
  ],
  tradingCycle: [
    { key: 'long_term', label: '长线' },
    { key: 'swing', label: '波段' },
    { key: 'short_term', label: '短线' },
    { key: 'ultra_short', label: '超短线' },
  ],
  frequencyStyle: [
    { key: 'high_freq_aggressive', label: '高频激进' },
    { key: 'low_freq_stable', label: '低频稳健' },
    { key: 'low_freq_aggressive', label: '低频激进' },
  ],
  returnRisk: [
    { key: 'stable_profit', label: '稳定盈利' },
    { key: 'continuous_profit', label: '持续盈利' },
    { key: 'volatile_profit', label: '波动盈利' },
    { key: 'break_even', label: '盈亏平衡' },
    { key: 'high_risk_high_return', label: '高风险高回报' },
    { key: 'low_drawdown', label: '低回撤' },
  ],
  strategyCapability: [
    { key: 'volatility_strategy', label: '波动策略' },
    { key: 'asymmetric_master', label: '非对称高手' },
  ],
} as const;
