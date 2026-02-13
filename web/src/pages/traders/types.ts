export type ColumnKey =
  | 'star' | 'rating' | 'address' | 'overall_score' | 'total_trades' | 'win_rate'
  | 'total_pnl' | 'roi' | 'profit_factor' | 'max_drawdown' | 'sharpe_ratio'
  | 'sortino_ratio' | 'calmar_ratio' | 'current_equity' | 'active_days' | 'avg_leverage'
  | 'current_positions' | 'recent_7d_pnl' | 'recent_7d_win_rate'
  | 'max_consecutive_wins' | 'max_consecutive_losses' | 'unique_symbols'
  | 'favorite_symbol' | 'long_short_ratio' | 'last_trade_time';

export interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
  group?: string;
}

export interface FilterConfig {
  minWinRate?: number;
  maxWinRate?: number;
  minProfitFactor?: number;
  maxProfitFactor?: number;
  minPnl?: number;
  maxPnl?: number;
  minDrawdown?: number;
  maxDrawdown?: number;
  minSharpe?: number;
  maxSharpe?: number;
  minSortino?: number;
  maxSortino?: number;
  minCalmar?: number;
  maxCalmar?: number;
  minTrades?: number;
  maxTrades?: number;
  minActiveDays?: number;
  maxActiveDays?: number;
  hasRecentTrade?: number;
  // 标签筛选
  tagAccountValue?: string;
  tagTradingRhythm?: string;
  tagProfitStatus?: string;
  tagDirectionPreference?: string;
  tagTradingStyle?: string;
}
