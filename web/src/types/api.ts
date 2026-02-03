// ==================== 交易者相关类型 ====================

export interface Trader {
  id: number;
  address: string;
  analyzed_at: string;
  // 基础统计
  total_trades: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate: number;
  // 盈亏指标
  total_pnl: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  total_volume?: number;
  roi: number;
  avg_profit_per_trade?: number;
  profit_factor: number;
  // 风险指标
  max_drawdown: number;
  max_drawdown_abs?: number;  // 最大回撤绝对值
  sharpe_ratio: number;
  sortino_ratio?: number;
  calmar_ratio?: number;
  var_95?: number;  // 95% VaR
  var_99?: number;  // 99% VaR
  cvar_95?: number;  // 95% CVaR (Expected Shortfall)
  // 交易特征
  avg_holding_time_hours?: number;
  trade_frequency_per_day?: number;
  avg_leverage?: number;
  max_leverage?: number;  // 最大杠杆
  // 活跃度
  active_days: number;
  last_trade_time: string;
  first_trade_time?: string;
  current_positions?: number;
  current_equity: number;
  // 评分
  overall_score: number;
  rating: string;
  profitability_score?: number;
  risk_score?: number;
  consistency_score?: number;
  activity_score?: number;
  // 新增分析字段
  avg_trade_price?: number;
  avg_trade_size?: number;
  max_single_win?: number;
  max_single_loss?: number;
  max_consecutive_wins?: number;
  max_consecutive_losses?: number;
  avg_win_amount?: number;
  avg_loss_amount?: number;
  unique_symbols?: number;
  favorite_symbol?: string;
  recent_7d_pnl?: number;
  recent_7d_win_rate?: number;
  long_short_ratio?: number;
  // 时间周期统计
  daily_pnl?: number;
  weekly_pnl?: number;
  monthly_pnl?: number;
  daily_roi?: number;
  weekly_roi?: number;
  monthly_roi?: number;
  daily_volume?: number;
  weekly_volume?: number;
  monthly_volume?: number;
  // 用户标记
  is_starred?: boolean;
}

export interface TraderFill {
  id: number;
  address: string;
  coin: string;
  side: string;
  px: number;
  sz: number;
  time: number;
  trade_time: string;
  closed_pnl: number;
  hash?: string;
  start_position?: number;
  dir?: string;
  crossed?: boolean;
  fee: number;
  oid?: number;
  tid?: number;
  trade_type?: string;  // 交易类型：open_long, add_long, close_long, open_short, add_short, close_short
}

export interface AssetPosition {
  id: number;
  address: string;
  updated_at: string;
  coin: string;
  szi: number;  // 持仓数量（正=多，负=空）
  entry_px: number;  // 开仓均价
  position_value: number;  // 持仓价值
  unrealized_pnl: number;  // 未实现盈亏
  return_on_equity: number;  // 权益回报率
  liquidation_px: number | null;  // 清算价格
  margin_used: number;  // 使用保证金
  max_leverage: number;  // 最大杠杆
  leverage_type: string;  // 杠杆类型
  leverage_value: number;  // 当前杠杆
  open_time?: string;  // 开仓时间
}

// 仓位历史记录
export interface PositionHistoryRecord {
  id: number;
  address: string;
  coin: string;
  direction: 'long' | 'short';
  open_time: string;
  close_time: string | null;
  max_size: number;
  avg_entry_price: number;
  avg_close_price: number | null;
  position_value: number;
  total_volume: number;
  realized_pnl: number;
  total_fee: number;
  open_trades: number;
  close_trades: number;
  holding_hours: number | null;
  status: 'open' | 'closed';
  created_at: string;
  updated_at: string;
}

// 仓位历史统计
export interface PositionHistoryStats {
  total_positions: number;
  closed_positions: number;
  open_positions: number;
  winning_positions: number;
  losing_positions: number;
  win_rate: number;
  total_pnl: number;
  total_profit: number;
  total_loss: number;
  avg_holding_hours: number;
  avg_pnl: number;
  total_fees: number;
  unique_coins: number;
}

// 按币种汇总的仓位历史
export interface PositionHistoryByCoin {
  coin: string;
  total_positions: number;
  closed_positions: number;
  open_positions: number;
  winning_positions: number;
  losing_positions: number;
  win_rate: number;
  total_pnl: number;
  avg_holding_hours: number;
  total_volume: number;
  // 全局统计额外字段
  trader_count?: number;
  long_count?: number;
  short_count?: number;
}

// 全局仓位历史记录（包含交易员信息）
export interface GlobalPositionHistoryRecord extends PositionHistoryRecord {
  rating?: string;
  overall_score?: number;
  trader_win_rate?: number;
  trader_pnl?: number;
  is_starred?: boolean;
  trader_name?: string;
}

// 全局仓位历史统计
export interface GlobalPositionHistoryStats {
  total_positions: number;
  total_traders: number;
  closed_positions: number;
  open_positions: number;
  long_count: number;
  short_count: number;
  winning_positions: number;
  losing_positions: number;
  win_rate: number;
  total_pnl: number;
  total_profit: number;
  total_loss: number;
  avg_holding_hours: number;
  avg_pnl: number;
  total_fees: number;
  total_volume: number;
  unique_coins: number;
  by_coin: Array<{
    coin: string;
    total_positions: number;
    long_count: number;
    short_count: number;
    total_pnl: number;
    total_volume: number;
  }>;
  by_trader: Array<{
    address: string;
    trader_name: string | null;
    total_positions: number;
    total_pnl: number;
    total_volume: number;
  }>;
}

export interface ChartDataPoint {
  timestamp: string;
  value: number;
}

export interface TraderHistory {
  roi: ChartDataPoint[];
  pnl: ChartDataPoint[];
  equity: ChartDataPoint[];
}

export interface TraderAIAnalysis {
  id: number;
  address: string;
  analyzed_at: string;
  rating: string;
  overall_score: number;
  analysis_text: string;
  summary: string;
  strengths: string;
  risks: string;
  trading_style: string;
  copy_trading_advice: string;
  improvement_suggestions: string;
  ai_provider: string;
  updated_at: string;
}

// ==================== 通用响应类型 ====================

export interface PaginationInfo {
  page: number;
  limit: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface FillsStats {
  total: number;
  profitable: number;
  losing: number;
  total_pnl: number;
  total_fees: number;
  total_volume: number;
  win_rate: number;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  count?: number;
  pagination?: PaginationInfo;
  stats?: FillsStats;
}

// ==================== 跟单交易类型 ====================

export interface CopyTradingAddress {
  id: number;
  address: string;
  name: string;
  is_enabled: boolean;
  // 跟单配置
  copy_ratio: number;
  max_position_size_usd: number;
  min_position_size_usd: number;
  copy_leverage: boolean;
  max_leverage: number;
  default_leverage: number;
  max_total_positions: number;
  max_daily_trades: number;
  slippage: number;
  symbols_whitelist: string[];
  symbols_blacklist: string[];
  check_interval: number;
  dry_run: boolean;
  // 自动补仓配置
  auto_replenish: boolean;
  replenish_ratio: number;
  replenish_min_value_usd: number;
  replenish_max_value_usd: number;
  // 时间戳
  created_at: string;
  updated_at: string;
  // 关联的交易者指标
  win_rate?: number;
  trader_pnl?: number;
  rating?: string;
  overall_score?: number;
  total_trades?: number;
  profit_factor?: number;
  max_drawdown?: number;
  sharpe_ratio?: number;
  analyzed_at?: string;
  is_starred?: boolean;
}

// 跟单交易员的实时持仓
export interface TraderPosition {
  id: number;
  address: string;
  coin: string;
  szi: number;
  entry_px: number;
  position_value: number;
  unrealized_pnl: number;
  return_on_equity: number;
  liquidation_px: number | null;
  margin_used: number;
  max_leverage: number;
  leverage_type: string;
  leverage_value: number;
  open_time: string;
  updated_at: string;
  // 关联字段
  trader_name: string | null;
  // 用户标记
  is_starred?: boolean;
  // 交易员指标
  overall_score?: number;
  rating?: string;
  trader_pnl?: number;
}

export interface TraderPositionsStats {
  total_positions: number;
  total_traders: number;
  total_notional: number;
  long_count: number;
  short_count: number;
  long_notional: number;
  short_notional: number;
  // 盈亏统计
  total_unrealized_pnl?: number;
  profit_count?: number;
  loss_count?: number;
  profit_pnl?: number;
  loss_pnl?: number;
  by_coin: Array<{
    coin: string;
    count: number;
    notional: number;
    long: number;
    short: number;
  }>;
  by_trader: Array<{
    address: string;
    name: string | null;
    count: number;
    notional: number;
  }>;
}

// ==================== Hyperliquid 类型 ====================

export interface HyperliquidCoin {
  id: number;
  name: string;
  sz_decimals: number;
  max_leverage: number;
  only_isolated: boolean;
  is_active: boolean;
  updated_at: string;
}

// ==================== 持仓AI分析类型 ====================

export interface PositionsAIAnalysis {
  analysis_type: 'overall' | 'coin' | 'single';
  position_count?: number;
  coin?: string;
  address?: string;
  analysis_text: string;
  sections: {
    // 整体分析
    market_sentiment?: string;
    long_short_analysis?: string;
    hot_coins?: string;
    risk_warning?: string;
    key_points?: string;
    suggestions?: string;
    // 币种分析
    long_short_comparison?: string;
    key_levels?: string;
    trader_consensus?: string;
    risk_assessment?: string;
    // 单仓位分析
    risk_level?: string;
    key_risks?: string;
    pnl_analysis?: string;
  };
}

// ==================== 默认跟单配置类型 ====================

export interface DefaultCopyTradingConfig {
  // 跟单参数
  copy_ratio: number;
  max_position_size_usd: number;
  min_position_size_usd: number;
  max_leverage: number;
  default_leverage: number;
  slippage: number;
  
  // 币种限制
  symbols_whitelist: string[];
  symbols_blacklist: string[];
  
  // 功能开关
  copy_leverage: boolean;
  
  // 自动补仓配置
  auto_replenish: boolean;
  replenish_ratio: number;
  replenish_min_value_usd: number;
  replenish_max_value_usd: number;
}

// ==================== 立即跟单配置类型 ====================

export interface ImmediateCopyConfig {
  // 跟单参数
  copy_ratio: number;
  max_position_size_usd: number;
  min_position_size_usd: number;
  max_leverage: number;
  default_leverage: number;
  slippage: number;
  copy_leverage: boolean;
  
  // 跟单条件
  min_trader_overall_score: number;  // 最低评分 0-100，0表示不限制
  min_trader_leverage: number;  // 目标交易员最小杠杆，>=此值才跟单
  max_trader_leverage: number;  // 目标交易员最大杠杆，<=此值才跟单，0表示不限制
  min_position_value_usd: number;  // 目标仓位最小价值
  max_position_value_usd: number;  // 目标仓位最大价值，0表示不限制
  min_coin_price: number;  // 币种最低价格，0表示不限制
  max_coin_price: number;  // 币种最高价格，0表示不限制
  
  // 自动补仓配置
  auto_replenish: boolean;
  replenish_ratio: number;
  replenish_min_value_usd: number;
  replenish_max_value_usd: number;
}

// ==================== 跟单配置规则类型（多配置支持） ====================

export interface CopyConfigRuleBase {
  id?: number;
  config_type: 'default' | 'immediate';
  name: string;
  description?: string;
  leverage_min: number;  // 杠杆下限（不包含）
  leverage_max: number;  // 杠杆上限（包含）
  priority: number;      // 优先级，数字越小优先级越高
  is_enabled: boolean;
  is_default: boolean;   // 是否为默认配置（兜底规则）
  created_at?: string;
  updated_at?: string;
}

export interface DefaultCopyConfigRule extends CopyConfigRuleBase {
  config_type: 'default';
  config_data: Partial<DefaultCopyTradingConfig>;
}

// 立即跟单配置规则（按币种配置，每个币种最多一个配置）
export interface ImmediateCopyConfigRule {
  id?: number;
  config_type: 'immediate';
  name: string;
  description?: string;
  symbol: string;  // 币种，每个币种最多一个配置
  is_enabled: boolean;
  config_data: Partial<ImmediateCopyConfig>;
  created_at?: string;
  updated_at?: string;
}

export type CopyConfigRule = DefaultCopyConfigRule | ImmediateCopyConfigRule;

export interface CopyConfigRuleCreateData {
  name: string;
  description?: string;
  leverage_min?: number;  // 默认跟单用
  leverage_max?: number;  // 默认跟单用
  symbol?: string;  // 立即跟单用
  config_data: Partial<DefaultCopyTradingConfig> | Partial<ImmediateCopyConfig>;
  priority?: number;
  is_enabled?: boolean;
  is_default?: boolean;
}

export interface ConfigRuleMatchResult {
  matched_rule: CopyConfigRule | null;
  effective_config: Partial<DefaultCopyTradingConfig> | Partial<ImmediateCopyConfig>;
}
