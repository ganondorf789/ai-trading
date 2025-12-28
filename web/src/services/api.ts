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

export interface ChartDataPoint {
  timestamp: string;
  value: number;
}

export interface TraderHistory {
  roi: ChartDataPoint[];
  pnl: ChartDataPoint[];
  equity: ChartDataPoint[];
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

// API 方法
export const traderApi = {
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
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    position_type?: 'all' | 'open' | 'closed';
  }) =>
    api.get<any, ApiResponse<TraderFill[]>>(`/traders/${address}/fills`, { params }),

  // 获取交易者交易过的所有币种
  getTraderCoins: (address: string) =>
    api.get<any, ApiResponse<string[]>>(`/traders/${address}/coins`),

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
};

export default api;
