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
  total_trades: number;
  winning_trades?: number;
  losing_trades?: number;
  win_rate: number;
  total_pnl: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  total_volume?: number;
  roi: number;
  avg_profit_per_trade?: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe_ratio: number;
  sortino_ratio?: number;
  avg_holding_time_hours?: number;
  trade_frequency_per_day?: number;
  avg_leverage?: number;
  active_days: number;
  last_trade_time: string;
  first_trade_time?: string;
  current_positions?: number;
  current_equity: number;
  overall_score: number;
  rating: string;
  profitability_score?: number;
  risk_score?: number;
  consistency_score?: number;
  activity_score?: number;
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

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  count?: number;
  pagination?: PaginationInfo;
}

// API 方法
export const traderApi = {
  // 获取交易者列表（支持分页）
  getTraders: (params?: {
    page?: number;
    limit?: number;
    min_rating?: string;
    search?: string;
  }) =>
    api.get<any, ApiResponse<Trader[]>>('/traders', { params }),

  // 获取交易者详情
  getTraderDetail: (address: string) =>
    api.get<any, ApiResponse<{ trader: Trader; fills_summary: FillsSummary }>>(`/traders/${address}`),

  // 获取交易记录（支持分页）
  getTraderFills: (address: string, params?: {
    page?: number;
    limit?: number;
    coin?: string;
    pnl_filter?: 'all' | 'profit' | 'loss';
  }) =>
    api.get<any, ApiResponse<TraderFill[]>>(`/traders/${address}/fills`, { params }),

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
