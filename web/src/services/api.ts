import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

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
  sharpe_ratio: number;
  sortino_ratio?: number;
  // 交易特征
  avg_holding_time_hours?: number;
  trade_frequency_per_day?: number;
  avg_leverage?: number;
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
  calmar_ratio?: number;
  daily_pnl?: number;
  weekly_pnl?: number;
  monthly_pnl?: number;
  daily_roi?: number;
  weekly_roi?: number;
  monthly_roi?: number;
  daily_volume?: number;
  weekly_volume?: number;
  monthly_volume?: number;
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

export interface FillsSummary {
  total_fills: number;
  total_pnl: number;
  by_coin: Array<{
    coin: string;
    count: number;
    total_pnl: number;
  }>;
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

// 跟单分组
export interface CopyTradingGroup {
  id: number;
  name: string;
  description: string;
  color: string;
  sort_order: number;
  address_count: number;
  created_at: string;
}

// 跟单地址
export interface CopyTradingAddress {
  id: number;
  address: string;
  name: string;
  group_id: number | null;
  group_name?: string;
  group_color?: string;
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
  sync_position: boolean;
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
}

// API 方法
export const traderApi = {
  // 新增交易者
  addTrader: (data: {
    address: string;
    lookback_days?: number;
    max_fills?: number;
  }) =>
    api.post<any, ApiResponse<Trader> & { message?: string }>('/traders', data, {
      timeout: 120000, // 分析可能需要较长时间
    }),

  // 获取交易者列表（支持分页、排序和高级筛选）
  getTraders: (params?: {
    page?: number;
    limit?: number;
    min_rating?: string;
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    // 高级筛选
    min_win_rate?: number;
    min_profit_factor?: number;
    min_pnl?: number;
    max_drawdown?: number;
    min_sharpe?: number;
    min_trades?: number;
    min_active_days?: number;
    has_recent_trade?: number;
  }) =>
    api.get<any, ApiResponse<Trader[]>>('/traders', { params }),

  // 获取交易者详情
  getTraderDetail: (address: string) =>
    api.get<any, ApiResponse<{ trader: Trader; fills_summary: FillsSummary }>>(`/traders/${address}`),

  // 获取交易记录（支持分页和排序）
  getTraderFills: (address: string, params?: {
    page?: number;
    limit?: number;
    coin?: string;
    pnl_filter?: 'all' | 'profit' | 'loss';
    trade_type?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    position_type?: 'all' | 'open' | 'closed';
    start_date?: string;
    end_date?: string;
  }) =>
    api.get<any, ApiResponse<TraderFill[]>>(`/traders/${address}/fills`, { params }),

  // 获取币种列表
  getCoins: (params?: {
    address?: string;
    exclude_user_perps?: boolean;
    include_stats?: boolean;
  }) =>
    api.get<any, ApiResponse<string[] | Array<{ coin: string; count: number; total_pnl: number; is_user_perp: boolean }>>>('/coins', { params }),

  // 获取当前持仓（来自 assetPositions）
  getTraderPositions: (address: string) =>
    api.get<any, ApiResponse<AssetPosition[]>>(`/traders/${address}/positions`),

  // 刷新当前持仓（从 Hyperliquid API 获取最新数据）
  refreshTraderPositions: (address: string) =>
    api.post<any, ApiResponse<AssetPosition[]> & { message?: string }>(`/traders/${address}/positions/refresh`),

  // 获取历史图表数据
  getTraderHistory: (address: string, params?: { days?: number }) =>
    api.get<any, ApiResponse<TraderHistory>>(`/traders/${address}/history`, { params }),

  // 按评级筛选（支持分页）
  getTradersByRating: (rating: string, params?: {
    page?: number;
    limit?: number;
    search?: string;
  }) =>
    api.get<any, ApiResponse<Trader[]>>(`/traders/rating/${rating}`, { params }),

  // 获取统计信息
  getStatistics: () =>
    api.get<any, ApiResponse<{
      total_records: number;
      unique_addresses: number;
      rating_distribution: Record<string, number>;
      total_sessions: number;
    }>>('/stats'),

  // 获取筛选会话
  getSessions: (params?: { limit?: number }) =>
    api.get<any, ApiResponse<any[]>>('/sessions', { params }),

  // 获取会话的交易者
  getSessionTraders: (sessionId: number) =>
    api.get<any, ApiResponse<Trader[]>>(`/sessions/${sessionId}/traders`),

  // 重新分析交易者（分析可能需要较长时间，设置更长超时）
  refreshTrader: (address: string, params?: {
    lookback_days?: number;
    max_fills?: number;
  }) =>
    api.post<any, ApiResponse<{ trader: Trader; fills_summary: FillsSummary; fills_saved: number }> & { message?: string }>(
      `/traders/${address}/refresh`,
      null,
      { params, timeout: 120000 }  // 2分钟超时
    ),

  // AI分析交易者（可能需要较长时间）
  aiAnalyzeTrader: (address: string, params?: { provider?: string }) =>
    api.post<any, ApiResponse<TraderAIAnalysis> & { message?: string }>(
      `/traders/${address}/ai-analysis`,
      null,
      { params, timeout: 60000 }  // 60秒超时
    ),

  // 获取AI分析结果
  getTraderAIAnalysis: (address: string) =>
    api.get<any, ApiResponse<TraderAIAnalysis>>(`/traders/${address}/ai-analysis`),
};

// 跟单地址管理 API
export const copyTradingApi = {
  // ==================== 分组管理 ====================

  // 获取分组列表
  getGroups: () =>
    api.get<any, ApiResponse<CopyTradingGroup[]>>('/copy-trading/groups'),

  // 创建分组
  createGroup: (data: { name: string; description?: string; color?: string }) =>
    api.post<any, ApiResponse<{ id: number }> & { message?: string }>('/copy-trading/groups', data),

  // 更新分组
  updateGroup: (groupId: number, data: Partial<CopyTradingGroup>) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/copy-trading/groups/${groupId}`, data),

  // 删除分组
  deleteGroup: (groupId: number) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/copy-trading/groups/${groupId}`),

  // ==================== 地址管理 ====================

  // 获取跟单地址列表
  getAddresses: (params?: {
    page?: number;
    limit?: number;
    group_id?: number;
    is_enabled?: boolean;
    search?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) =>
    api.get<any, ApiResponse<CopyTradingAddress[]>>('/copy-trading/addresses', { params }),

  // 获取单个跟单地址详情
  getAddress: (address: string) =>
    api.get<any, ApiResponse<CopyTradingAddress>>(`/copy-trading/addresses/${address}`),

  // 添加跟单地址
  createAddress: (data: Partial<CopyTradingAddress>) =>
    api.post<any, ApiResponse<{ id: number }> & { message?: string }>('/copy-trading/addresses', data),

  // 更新跟单地址
  updateAddress: (address: string, data: Partial<CopyTradingAddress>) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/copy-trading/addresses/${address}`, data),

  // 删除跟单地址
  deleteAddress: (address: string) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/copy-trading/addresses/${address}`),

  // 启用/禁用跟单地址
  toggleAddress: (address: string, isEnabled: boolean) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/copy-trading/addresses/${address}/toggle`, { is_enabled: isEnabled }),

  // 批量操作
  batchAction: (action: 'enable' | 'disable' | 'delete' | 'move_group', addresses: string[], groupId?: number) =>
    api.post<any, ApiResponse<void> & { affected_count?: number; message?: string }>('/copy-trading/addresses/batch', {
      action,
      addresses,
      group_id: groupId,
    }),
};

// 跟单订单
export interface CopyTradingOrder {
  id: number;
  target_address: string;
  target_name?: string;
  symbol: string;
  side: string;
  action: string;
  size: number;
  price: number | null;
  leverage: number;
  copy_ratio: number | null;
  target_size: number | null;
  target_entry_price: number | null;
  status: string;
  error_message: string | null;
  pnl: number;
  is_dry_run: boolean;
  created_at: string;
  executed_at: string | null;
}

export interface CopyOrderStats {
  total_orders: number;
  successful_orders: number;
  failed_orders: number;
  pending_orders: number;
  total_pnl: number;
  by_symbol: Array<{
    symbol: string;
    count: number;
    pnl: number;
  }>;
  by_target: Array<{
    target_address: string;
    count: number;
    pnl: number;
  }>;
}

// Hyperliquid 币种信息
export interface HyperliquidCoin {
  id: number;
  name: string;
  sz_decimals: number;
  max_leverage: number;
  only_isolated: boolean;
  is_active: boolean;
  updated_at: string;
}

// Hyperliquid 币种 API
export const hyperliquidApi = {
  // 获取币种列表
  getCoins: (activeOnly: boolean = true) =>
    api.get<any, ApiResponse<HyperliquidCoin[]>>('/hyperliquid/coins', { params: { active_only: activeOnly } }),

  // 获取币种名称列表
  getCoinNames: () =>
    api.get<any, ApiResponse<string[]>>('/hyperliquid/coins/names'),

  // 同步币种（从 Hyperliquid API）
  syncCoins: () =>
    api.post<any, ApiResponse<HyperliquidCoin[]> & { message?: string }>('/hyperliquid/coins/sync'),
};

// 跟单订单 API
export const copyTradingOrdersApi = {
  // 获取订单列表
  getOrders: (params?: {
    page?: number;
    limit?: number;
    target_address?: string;
    symbol?: string;
    status?: string;
    action?: string;
    is_dry_run?: boolean;
    days?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) =>
    api.get<any, ApiResponse<CopyTradingOrder[]>>('/copy-trading/orders', { params }),

  // 获取订单统计
  getStats: (params?: {
    target_address?: string;
    days?: number;
  }) =>
    api.get<any, ApiResponse<CopyOrderStats>>('/copy-trading/orders/stats', { params }),

  // 清理旧订单
  cleanup: (days: number = 30) =>
    api.post<any, ApiResponse<{ deleted_count: number }> & { message?: string }>(
      '/copy-trading/orders/cleanup',
      null,
      { params: { days } }
    ),
};

export default api;
