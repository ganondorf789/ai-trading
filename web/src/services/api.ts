import axios from 'axios';
import type {
  Trader,
  TraderFill,
  AssetPosition,
  TraderHistory,
  TraderAIAnalysis,
  ApiResponse,
  CopyTradingAddress,
  HyperliquidCoin,
  TraderPosition,
  TraderPositionsStats,
  PaginationInfo,
  FillsStats,
  ChartDataPoint,
  DefaultCopyTradingConfig,
  ImmediateCopyConfig,
  PositionHistoryRecord,
  PositionHistoryStats,
  PositionHistoryByCoin,
  GlobalPositionHistoryRecord,
  GlobalPositionHistoryStats,
  PositionsAIAnalysis,
  DefaultCopyConfigRule,
  ImmediateCopyConfigRule,
  CopyConfigRule,
  CopyConfigRuleCreateData,
  ConfigRuleMatchResult,
} from '@/types/api';

// Re-export all types for backward compatibility
export type {
  Trader,
  TraderFill,
  AssetPosition,
  TraderHistory,
  TraderAIAnalysis,
  ApiResponse,
  CopyTradingAddress,
  HyperliquidCoin,
  TraderPosition,
  TraderPositionsStats,
  PaginationInfo,
  FillsStats,
  ChartDataPoint,
  DefaultCopyTradingConfig,
  ImmediateCopyConfig,
  PositionHistoryRecord,
  PositionHistoryStats,
  PositionHistoryByCoin,
  GlobalPositionHistoryRecord,
  GlobalPositionHistoryStats,
  PositionsAIAnalysis,
  DefaultCopyConfigRule,
  ImmediateCopyConfigRule,
  CopyConfigRule,
  CopyConfigRuleCreateData,
  ConfigRuleMatchResult,
};

// Forward declaration for User type (defined later in the file)
export interface User {
  id: string;
  account: string;
  role: 'user' | 'member' | 'admin';
  api_wallet: string;
  wallet_address: string;
  allowed_ip: string;
  allowed_port: string;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

// ==================== Token 管理 ====================

const TOKEN_KEY = 'access_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const USER_KEY = 'current_user';

export const tokenManager = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  removeToken: () => localStorage.removeItem(TOKEN_KEY),
  
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setRefreshToken: (token: string) => localStorage.setItem(REFRESH_TOKEN_KEY, token),
  removeRefreshToken: () => localStorage.removeItem(REFRESH_TOKEN_KEY),
  
  getUser: (): User | null => {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
  },
  setUser: (user: User) => localStorage.setItem(USER_KEY, JSON.stringify(user)),
  removeUser: () => localStorage.removeItem(USER_KEY),
  
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
  
  isLoggedIn: () => !!localStorage.getItem(TOKEN_KEY),
  
  // 获取登录后返回的 URL
  getReturnUrl: () => {
    const url = sessionStorage.getItem('returnUrl');
    sessionStorage.removeItem('returnUrl');
    return url || '/';
  },
};

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 自动附加 Token
api.interceptors.request.use(
  (config) => {
    const token = tokenManager.getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 是否正在刷新 token
let isRefreshing = false;
// 待重试的请求队列
let refreshSubscribers: ((token: string) => void)[] = [];

const subscribeTokenRefresh = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback);
};

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach(callback => callback(token));
  refreshSubscribers = [];
};

/**
 * 处理认证失败，清除 token 并跳转到登录页
 */
const handleAuthFailure = (reason: string) => {
  console.warn(`[Auth] 认证失败: ${reason}`);
  isRefreshing = false;
  refreshSubscribers = [];
  tokenManager.clear();
  
  // 避免在登录页或注册页重复跳转
  const currentPath = window.location.pathname;
  if (!currentPath.includes('/login') && !currentPath.includes('/register')) {
    // 保存当前页面路径，登录后可以跳转回来
    const returnUrl = window.location.pathname + window.location.search;
    if (returnUrl && returnUrl !== '/') {
      sessionStorage.setItem('returnUrl', returnUrl);
    }
    window.location.href = '/login';
  }
};

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config;
    
    // 处理 403 错误（用户已禁用或已过期）
    if (error.response?.status === 403) {
      const errorCode = error.response?.data?.code;
      // USER_INACTIVE: 用户被禁用, USER_EXPIRED: 用户已过期
      if (errorCode === 'USER_INACTIVE' || errorCode === 'USER_EXPIRED') {
        // 如果是登录请求，直接抛出错误让登录页面处理
        if (originalRequest.url?.includes('/auth/login')) {
          return Promise.reject(error);
        }
        // 其他请求，清除 token 并跳转到登录页
        handleAuthFailure(errorCode);
        return Promise.reject(error);
      }
    }
    
    // 处理 401 错误（token 无效或过期）
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 如果是登录或刷新 token 请求失败，直接抛出错误
      if (originalRequest.url?.includes('/auth/login') || 
          originalRequest.url?.includes('/auth/refresh-token') ||
          originalRequest.url?.includes('/auth/register')) {
        return Promise.reject(error);
      }
      
      // 如果正在刷新 token，将请求加入队列等待
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          subscribeTokenRefresh((token: string) => {
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
              resolve(api(originalRequest));
            } else {
              reject(error);
            }
          });
        });
      }
      
      originalRequest._retry = true;
      isRefreshing = true;
      
      const refreshToken = tokenManager.getRefreshToken();
      if (!refreshToken) {
        // 没有 refresh token，跳转到登录页
        handleAuthFailure('TOKEN_MISSING');
        return Promise.reject(error);
      }
      
      try {
        // 尝试刷新 token
        const response = await axios.post(`${API_BASE_URL}/auth/refresh-token`, {
          refresh_token: refreshToken
        });
        
        if (response.data.success && response.data.data?.access_token) {
          const newToken = response.data.data.access_token;
          tokenManager.setToken(newToken);
          isRefreshing = false;
          
          // 通知所有等待的请求
          onTokenRefreshed(newToken);
          
          // 重试原始请求
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        } else {
          throw new Error('Token refresh failed');
        }
      } catch (refreshError) {
        // 刷新失败，跳转到登录页
        handleAuthFailure('REFRESH_FAILED');
        return Promise.reject(refreshError);
      }
    }
    
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

// ==================== 交易者 API ====================

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
    // 标签筛选
    tag_capital_scale?: string;
    tag_trading_direction?: string;
    tag_trading_cycle?: string;
    tag_frequency_style?: string;
    tag_return_risk?: string;
    tag_strategy_capability?: string;
  }) =>
    api.get<any, ApiResponse<Trader[]>>('/traders', { params }),

  // 获取交易者详情
  getTraderDetail: (address: string) =>
    api.get<any, ApiResponse<{ trader: Trader }>>(`/traders/${address}`),

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
    api.post<any, ApiResponse<{ trader: Trader; fills_saved: number }> & { message?: string }>(
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

  // 切换收藏状态
  toggleStar: (address: string, isStarred: boolean) =>
    api.post<any, ApiResponse<{ is_starred: boolean }> & { message?: string }>(
      `/traders/${address}/star`,
      { is_starred: isStarred }
    ),

  // ==================== 仓位历史 ====================

  // 获取仓位历史列表
  getPositionHistory: (address: string, params?: {
    coin?: string;
    status?: 'open' | 'closed';
    direction?: 'long' | 'short';
    start_time?: string;
    end_time?: string;
    pnl_filter?: 'profit' | 'loss';
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    limit?: number;
  }) =>
    api.get<any, ApiResponse<PositionHistoryRecord[]>>(`/traders/${address}/position-history`, { params }),

  // 重建仓位历史（从 fills 重新计算）
  rebuildPositionHistory: (address: string) =>
    api.post<any, ApiResponse<{ count: number }> & { message?: string }>(
      `/traders/${address}/position-history/rebuild`,
      null,
      { timeout: 60000 }  // 60秒超时
    ),

  // 获取仓位历史统计
  getPositionHistoryStats: (address: string) =>
    api.get<any, ApiResponse<PositionHistoryStats>>(`/traders/${address}/position-history/stats`),

  // 获取按币种汇总的仓位历史
  getPositionHistoryByCoin: (address: string) =>
    api.get<any, ApiResponse<PositionHistoryByCoin[]>>(`/traders/${address}/position-history/by-coin`),
};

// ==================== 全局仓位历史 API ====================

export const positionHistoryApi = {
  // 获取所有交易员的仓位历史
  getAll: (params?: {
    coin?: string;
    status?: 'open' | 'closed';
    direction?: 'long' | 'short';
    min_pnl?: number;
    max_pnl?: number;
    page?: number;
    limit?: number;
  }) =>
    api.get<any, ApiResponse<GlobalPositionHistoryRecord[]> & { stats?: GlobalPositionHistoryStats }>('/position-history', { params }),

  // 获取全局仓位历史统计
  getStats: () =>
    api.get<any, ApiResponse<GlobalPositionHistoryStats>>('/position-history/stats'),

  // 获取按币种汇总的全局仓位历史
  getByCoin: () =>
    api.get<any, ApiResponse<PositionHistoryByCoin[]>>('/position-history/by-coin'),
};

// ==================== 跟单地址管理 API ====================

export const copyTradingApi = {
  // ==================== 地址管理 ====================

  // 获取跟单地址列表
  getAddresses: (params?: {
    page?: number;
    limit?: number;
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
    api.post<any, ApiResponse<{ id: string }> & { message?: string }>('/copy-trading/addresses', data),

  // 快速添加跟单地址（使用默认配置）
  quickAddAddress: (data: { address: string; name?: string }) =>
    api.post<any, ApiResponse<{ id: string }> & { message?: string; exists?: boolean }>('/copy-trading/addresses/quick-add', data),

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
  batchAction: (action: 'enable' | 'disable' | 'delete', addresses: string[]) =>
    api.post<any, ApiResponse<void> & { affected_count?: number; message?: string }>('/copy-trading/addresses/batch', {
      action,
      addresses,
    }),
};

// ==================== Hyperliquid 币种 API ====================

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

// ==================== 跟单交易员实时持仓 API ====================

export const traderPositionsApi = {
  // 获取最近N分钟内更新的所有跟单交易员的当前持仓（纯前端筛选和统计）
  getPositions: (params?: {
    minutes?: number;  // 获取最近N分钟内更新的数据，默认10分钟
  }) =>
    api.get<any, ApiResponse<TraderPosition[]> & { cached?: boolean }>('/copy-trading/trader-positions', { params: { minutes: params?.minutes ?? 10 } }),

  // 刷新所有跟单交易员的持仓数据
  refresh: (enabledOnly: boolean = true) =>
    api.post<any, ApiResponse<{ refreshed_count: number; total_positions: number; errors?: Array<{ address: string; error: string }> }> & { message?: string }>(
      '/copy-trading/trader-positions/refresh',
      null,
      { params: { enabled_only: enabledOnly }, timeout: 120000 }  // 2分钟超时
    ),

  // AI分析：整体持仓分析
  aiAnalyzeAll: (data: {
    positions?: TraderPosition[];
    stats?: TraderPositionsStats;
    provider?: string;
    filters?: Record<string, any>;
    force_refresh?: boolean;
  }) =>
    api.post<any, ApiResponse<PositionsAIAnalysis> & { message?: string; cached?: boolean; analyzed_at?: string }>(
      '/copy-trading/trader-positions/ai-analysis',
      data,
      { timeout: 90000 }  // 90秒超时
    ),

  // AI分析：单币种分析
  aiAnalyzeCoin: (data: {
    coin: string;
    positions?: TraderPosition[];
    provider?: string;
    force_refresh?: boolean;
  }) =>
    api.post<any, ApiResponse<PositionsAIAnalysis> & { message?: string; cached?: boolean; analyzed_at?: string }>(
      '/copy-trading/trader-positions/ai-analysis/coin',
      data,
      { timeout: 90000 }
    ),

  // AI分析：单仓位分析
  aiAnalyzeSingle: (data: {
    position: TraderPosition;
    provider?: string;
    force_refresh?: boolean;
  }) =>
    api.post<any, ApiResponse<PositionsAIAnalysis> & { message?: string; cached?: boolean; analyzed_at?: string }>(
      '/copy-trading/trader-positions/ai-analysis/single',
      data,
      { timeout: 60000 }
    ),

  // 检查是否已有 AI 分析结果
  checkAIAnalysis: (data: {
    analysis_type: 'overall' | 'coin' | 'single';
    positions: TraderPosition[];
    coin?: string;
    address?: string;
  }) =>
    api.post<any, ApiResponse<PositionsAIAnalysis | null> & { exists: boolean; analyzed_at?: string }>(
      '/copy-trading/trader-positions/ai-analysis/check',
      data,
      { timeout: 10000 }
    ),
};

// ==================== 仓位级别跟单 API（第二种跟单模式） ====================

export interface PositionTracking {
  id: string;
  target_address: string;
  target_name: string;
  target_display_name?: string;
  target_is_starred: boolean;
  symbol: string;
  is_enabled: boolean;
  copy_ratio: number;
  max_position_size_usd: number;
  min_position_size_usd: number;
  copy_leverage: boolean;
  max_leverage: number;
  default_leverage: number;
  slippage: number;
  // 自动补仓配置
  auto_replenish: boolean;
  replenish_ratio: number;
  replenish_min_value_usd: number;
  replenish_max_value_usd: number;
  // 目标仓位快照
  target_initial_size: number | null;
  target_initial_side: string | null;
  target_initial_entry_price: number | null;
  target_initial_leverage: number | null;
  my_size: number;
  my_side: string | null;
  my_entry_price: number | null;
  status: 'pending' | 'active' | 'closed' | 'stopped';
  closed_pnl: number | null;
  close_reason: string | null;
  created_at: string;
  started_at: string | null;
  closed_at: string | null;
  updated_at: string;
}

export interface PositionTrackingStats {
  total_count: number;
  pending_count: number;
  active_count: number;
  closed_count: number;
  stopped_count: number;
  enabled_count: number;
  unique_traders: number;
  unique_symbols: number;
  total_closed_pnl: number;
}

export const positionTrackingApi = {
  // 获取仓位跟单列表
  getTrackings: (params?: {
    page?: number;
    limit?: number;
    status?: 'pending' | 'active' | 'closed' | 'stopped';
    is_enabled?: boolean;
    target_address?: string;
    symbol?: string;
  }) =>
    api.get<any, ApiResponse<PositionTracking[]>>('/copy-trading/position-tracking', { params }),

  // 获取统计信息
  getStats: () =>
    api.get<any, ApiResponse<PositionTrackingStats>>('/copy-trading/position-tracking/stats'),

  // 获取单个跟单详情
  getTracking: (trackingId: number) =>
    api.get<any, ApiResponse<PositionTracking>>(`/copy-trading/position-tracking/${trackingId}`),

  // 创建仓位跟单
  createTracking: (data: {
    target_address: string;
    symbol: string;
    target_name?: string;
    copy_ratio?: number;
    max_position_size_usd?: number;
    min_position_size_usd?: number;
    copy_leverage?: boolean;
    max_leverage?: number;
    default_leverage?: number;
    slippage?: number;
  }) =>
    api.post<any, ApiResponse<{ id: string }> & { message?: string }>('/copy-trading/position-tracking', data),

  // 快速添加仓位跟单（使用默认配置）
  quickAdd: (data: { target_address: string; symbol: string; target_name?: string }) =>
    api.post<any, ApiResponse<{ id: string }> & { message?: string; exists?: boolean }>('/copy-trading/position-tracking/quick-add', data),

  // 更新仓位跟单配置
  updateTracking: (trackingId: string, data: Partial<PositionTracking>) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/copy-trading/position-tracking/${trackingId}`, data),

  // 删除仓位跟单
  deleteTracking: (trackingId: string) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/copy-trading/position-tracking/${trackingId}`),

  // 启用/禁用仓位跟单
  toggleTracking: (trackingId: string, isEnabled: boolean) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/copy-trading/position-tracking/${trackingId}/toggle`, { is_enabled: isEnabled }),

  // 停止仓位跟单
  stopTracking: (trackingId: string) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/copy-trading/position-tracking/${trackingId}/stop`),
};

// ==================== 跟单配置 API ====================

export const riskControlApi = {
  // 获取默认跟单配置
  getDefaultCopyConfig: () =>
    api.get<any, ApiResponse<DefaultCopyTradingConfig>>('/copy-trading/default-config'),

  // 更新默认跟单配置
  updateDefaultCopyConfig: (data: Partial<DefaultCopyTradingConfig>) =>
    api.put<any, ApiResponse<DefaultCopyTradingConfig> & { message?: string }>('/copy-trading/default-config', data),

  // 获取立即跟单配置
  getImmediateCopyConfig: () =>
    api.get<any, ApiResponse<ImmediateCopyConfig>>('/copy-trading/immediate-config'),

  // 更新立即跟单配置
  updateImmediateCopyConfig: (data: Partial<ImmediateCopyConfig>) =>
    api.put<any, ApiResponse<ImmediateCopyConfig> & { message?: string }>('/copy-trading/immediate-config', data),

  // ==================== 默认跟单配置规则 ====================
  
  // 获取所有默认跟单配置规则
  getDefaultConfigRules: (enabledOnly?: boolean) =>
    api.get<any, ApiResponse<DefaultCopyConfigRule[]>>('/copy-trading/default-config-rules', {
      params: { enabled_only: enabledOnly },
    }),

  // 获取单个默认跟单配置规则
  getDefaultConfigRule: (ruleId: string) =>
    api.get<any, ApiResponse<DefaultCopyConfigRule>>(`/copy-trading/default-config-rules/${ruleId}`),

  // 创建默认跟单配置规则
  createDefaultConfigRule: (data: CopyConfigRuleCreateData) =>
    api.post<any, ApiResponse<DefaultCopyConfigRule> & { message?: string }>('/copy-trading/default-config-rules', data),

  // 更新默认跟单配置规则
  updateDefaultConfigRule: (ruleId: string, data: Partial<CopyConfigRuleCreateData> & { id?: string }) =>
    api.put<any, ApiResponse<DefaultCopyConfigRule> & { message?: string }>(`/copy-trading/default-config-rules/${ruleId}`, data),

  // 删除默认跟单配置规则
  deleteDefaultConfigRule: (ruleId: string) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/copy-trading/default-config-rules/${ruleId}`),

  // ==================== 立即跟单配置规则 ====================
  
  // 获取所有立即跟单配置规则
  getImmediateConfigRules: (enabledOnly?: boolean) =>
    api.get<any, ApiResponse<ImmediateCopyConfigRule[]>>('/copy-trading/immediate-config-rules', {
      params: { enabled_only: enabledOnly },
    }),

  // 获取单个立即跟单配置规则
  getImmediateConfigRule: (ruleId: string) =>
    api.get<any, ApiResponse<ImmediateCopyConfigRule>>(`/copy-trading/immediate-config-rules/${ruleId}`),

  // 创建立即跟单配置规则
  createImmediateConfigRule: (data: CopyConfigRuleCreateData) =>
    api.post<any, ApiResponse<ImmediateCopyConfigRule> & { message?: string }>('/copy-trading/immediate-config-rules', data),

  // 更新立即跟单配置规则
  updateImmediateConfigRule: (ruleId: string, data: Partial<CopyConfigRuleCreateData> & { id?: string }) =>
    api.put<any, ApiResponse<ImmediateCopyConfigRule> & { message?: string }>(`/copy-trading/immediate-config-rules/${ruleId}`, data),

  // 删除立即跟单配置规则
  deleteImmediateConfigRule: (ruleId: string) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/copy-trading/immediate-config-rules/${ruleId}`),

  // ==================== 配置规则匹配测试 ====================
  
  // 根据杠杆匹配配置规则（测试/预览）
  matchConfigRule: (configType: 'default' | 'immediate', leverage: number) =>
    api.get<any, ApiResponse<ConfigRuleMatchResult>>('/copy-trading/config-rules/match', {
      params: { config_type: configType, leverage },
    }),
};

// ==================== 用户认证 API ====================

export interface SecretKey {
  id: number;
  key_value: string;
  key_name: string;
  user_role: 'user' | 'member' | 'admin';
  expires_days: number;
  is_used: boolean;
  used_by_user_id: string | null;
  is_active: boolean;
  expires_at: string | null;
  created_by: number | null;
  created_at: string;
}

export interface UserStats {
  total_count: number;
  active_count: number;
  inactive_count: number;
  user_count: number;
  member_count: number;
  admin_count: number;
  expired_count: number;
}

export interface SecretKeyStats {
  total_count: number;
  active_count: number;
  inactive_count: number;
  used_count: number;
  available_count: number;
  user_role_count: number;
  member_role_count: number;
  admin_role_count: number;
}

export interface LoginResponse {
  id: string;
  account: string;
  role: 'user' | 'member' | 'admin';
  api_wallet: string;
  wallet_address: string;
  expires_at: string | null;
  is_active: boolean;
  last_login_at: string | null;
  access_token: string;
  refresh_token: string;
}

export const authApi = {
  // 用户登录
  login: async (data: { account: string; password: string }) => {
    const response = await api.post<any, ApiResponse<LoginResponse> & { message?: string; error?: string }>('/auth/login', data);
    if (response.success && response.data) {
      // 保存 token 和用户信息
      tokenManager.setToken(response.data.access_token);
      tokenManager.setRefreshToken(response.data.refresh_token);
      // 提取用户信息（不包含 token）
      const { access_token, refresh_token, ...user } = response.data;
      tokenManager.setUser(user as User);
    }
    return response;
  },

  // 用户注册
  register: (data: { account: string; password: string; secret_key: string }) =>
    api.post<any, ApiResponse<{ id: string; account: string; role: string }> & { message?: string }>('/auth/register', data),

  // 修改密码（不再需要 user_id，从 token 获取）
  changePassword: (data: { old_password: string; new_password: string }) =>
    api.post<any, ApiResponse<void> & { message?: string }>('/auth/change-password', data),

  // 获取当前登录用户信息
  getCurrentUser: () =>
    api.get<any, ApiResponse<User>>('/auth/me'),

  // 获取指定用户信息（管理员）
  getUserInfo: (userId: string) =>
    api.get<any, ApiResponse<User>>(`/auth/user/${userId}`),

  // 验证 token 有效性
  verifyToken: () =>
    api.get<any, ApiResponse<{ valid: boolean; user_id: string; account: string; role: string; expires_at: string }>>('/auth/verify-token'),

  // 刷新 token
  refreshToken: async (refreshToken: string) => {
    const response = await api.post<any, ApiResponse<{ access_token: string; expires_in: number }> & { message?: string }>('/auth/refresh-token', { refresh_token: refreshToken });
    if (response.success && response.data) {
      tokenManager.setToken(response.data.access_token);
    }
    return response;
  },

  // 登出
  logout: () => {
    tokenManager.clear();
  },

  // 获取 Hyperliquid 设置（不再需要 user_id）
  getHyperliquidSettings: () =>
    api.get<any, ApiResponse<{ api_wallet: string; wallet_address: string }>>('/auth/hyperliquid-settings'),

  // 更新 Hyperliquid 设置（不再需要 user_id）
  updateHyperliquidSettings: (data: { api_wallet?: string; wallet_address?: string }) =>
    api.post<any, ApiResponse<{ api_wallet: string; wallet_address: string }> & { message?: string }>('/auth/hyperliquid-settings', data),
};

export const userManagementApi = {
  // 获取用户列表（管理员）
  getUsers: (params?: { role?: string; is_active?: boolean; limit?: number; offset?: number }) =>
    api.get<any, ApiResponse<User[]>>('/auth/users', { params }),

  // 更新用户身份（管理员）
  updateUserRole: (targetUserId: string, data: { role: string }) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/auth/users/${targetUserId}/role`, data),

  // 更新用户信息（管理员）- 过期时间、IP、端口
  updateUserInfo: (targetUserId: string, data: { role?: string; expires_at?: string | null; allowed_ip?: string; allowed_port?: string }) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/auth/users/${targetUserId}/info`, data),

  // 获取用户统计（管理员）
  getUserStats: () =>
    api.get<any, ApiResponse<UserStats>>('/auth/users/stats'),

  // 获取指定用户的 API Key（管理员）
  getUserApiKey: (targetUserId: string) =>
    api.get<any, ApiResponse<{ user_id: string; api_key: string | null }>>(`/auth/users/${targetUserId}/api-key`),

  // 刷新指定用户的 API Key（管理员）
  refreshUserApiKey: (targetUserId: string) =>
    api.post<any, ApiResponse<{ user_id: string; api_key: string }> & { message?: string }>(`/auth/users/${targetUserId}/api-key/refresh`),
};

export const secretKeyApi = {
  // 获取秘钥列表（管理员）
  getSecretKeys: (params?: { is_active?: boolean; is_used?: boolean; user_role?: string; limit?: number; offset?: number }) =>
    api.get<any, ApiResponse<SecretKey[]>>('/auth/secret-keys', { params }),

  // 创建秘钥（管理员）
  createSecretKey: (data: { key_name?: string; user_role?: string; expires_days?: number; key_value?: string }) =>
    api.post<any, ApiResponse<SecretKey> & { message?: string }>('/auth/secret-keys', data),

  // 批量创建秘钥（管理员）
  batchCreateSecretKeys: (data: { count: number; key_name_prefix?: string; user_role?: string; expires_days?: number }) =>
    api.post<any, ApiResponse<SecretKey[]> & { message?: string }>('/auth/secret-keys/batch', data),

  // 获取秘钥详情（管理员）
  getSecretKey: (keyId: number) =>
    api.get<any, ApiResponse<SecretKey>>(`/auth/secret-keys/${keyId}`),

  // 更新秘钥（管理员）
  updateSecretKey: (keyId: number, data: { key_name?: string; user_role?: string; expires_days?: number; is_active?: boolean }) =>
    api.put<any, ApiResponse<SecretKey> & { message?: string }>(`/auth/secret-keys/${keyId}`, data),

  // 删除秘钥（管理员）
  deleteSecretKey: (keyId: number) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/auth/secret-keys/${keyId}`),

  // 获取秘钥统计（管理员）
  getSecretKeyStats: () =>
    api.get<any, ApiResponse<SecretKeyStats>>('/auth/secret-keys/stats'),
};

// ==================== 应用版本管理 API ====================

export interface AppVersion {
  id: number;
  version: string;
  version_name: string;
  description: string;
  release_notes: string;
  download_url: string;
  is_force_update: boolean;
  is_visible: boolean;
  min_supported_version: string;
  platform: 'all' | 'android' | 'ios' | 'web';
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppVersionStats {
  total_count: number;
  visible_count: number;
  hidden_count: number;
  force_update_count: number;
  all_platform_count: number;
  android_count: number;
  ios_count: number;
  web_count: number;
}

export const appVersionApi = {
  // 获取最新版本（公开接口）
  getLatestVersion: (platform?: string) =>
    api.get<any, ApiResponse<AppVersion | null>>('/app-versions/latest', { params: { platform } }),

  // 检查版本更新（公开接口）
  checkUpdate: (currentVersion: string, platform?: string) =>
    api.get<any, ApiResponse<{ has_update: boolean; is_force_update?: boolean; latest_version?: AppVersion }>>('/app-versions/check-update', {
      params: { current_version: currentVersion, platform },
    }),

  // 获取版本列表（管理员）
  getVersions: (params?: { is_visible?: boolean; platform?: string; limit?: number; offset?: number }) =>
    api.get<any, ApiResponse<AppVersion[]>>('/app-versions', { params }),

  // 创建版本（管理员）
  createVersion: (data: {
    version: string;
    version_name?: string;
    description?: string;
    release_notes?: string;
    download_url?: string;
    is_force_update?: boolean;
    is_visible?: boolean;
    min_supported_version?: string;
    platform?: string;
  }) =>
    api.post<any, ApiResponse<AppVersion> & { message?: string }>('/app-versions', data),

  // 获取版本详情（管理员）
  getVersion: (versionId: number) =>
    api.get<any, ApiResponse<AppVersion>>(`/app-versions/${versionId}`),

  // 更新版本（管理员）
  updateVersion: (versionId: number, data: {
    version_name?: string;
    description?: string;
    release_notes?: string;
    download_url?: string;
    is_force_update?: boolean;
    is_visible?: boolean;
    min_supported_version?: string;
  }) =>
    api.put<any, ApiResponse<AppVersion> & { message?: string }>(`/app-versions/${versionId}`, data),

  // 删除版本（管理员）
  deleteVersion: (versionId: number) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/app-versions/${versionId}`),

  // 切换版本可见性（管理员）
  toggleVisibility: (versionId: number, isVisible: boolean) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/app-versions/${versionId}/toggle`, { is_visible: isVisible }),

  // 获取版本统计（管理员）
  getVersionStats: () =>
    api.get<any, ApiResponse<AppVersionStats>>('/app-versions/stats'),
};

// ==================== 公告管理 API ====================

export interface Announcement {
  id: number;
  type: 'announcement';
  title: string;
  content: string;
  is_read: boolean;
  created_at: string;
}

export interface AnnouncementStats {
  total_count: number;
}

export const announcementApi = {
  // 发布公告（管理员）
  create: (data: { title: string; content: string }) =>
    api.post<any, ApiResponse<void> & { message?: string }>('/announcements', data),

  // 获取公告列表（管理员）
  getList: (params?: { limit?: number; offset?: number }) =>
    api.get<any, ApiResponse<Announcement[]> & { pagination?: { total: number; limit: number; offset: number; has_more: boolean } }>('/announcements', { params }),

  // 获取公告详情（管理员）
  getDetail: (id: number) =>
    api.get<any, ApiResponse<Announcement>>(`/announcements/${id}`),

  // 更新公告（管理员）
  update: (id: number, data: { title?: string; content?: string }) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/announcements/${id}`, data),

  // 删除公告（管理员）
  delete: (id: number) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/announcements/${id}`),

  // 获取公告统计（管理员）
  getStats: () =>
    api.get<any, ApiResponse<AnnouncementStats>>('/announcements/stats'),
};

// ==================== 地址跟踪 API ====================

export interface AddressTracking {
  id: string;
  user_id: string;
  tracking_address: string;
  address_remark: string;
  is_enabled: boolean;
  enable_notification: boolean;
  monitor_events: ('open' | 'close' | 'add' | 'reduce')[];
  created_at: string;
  updated_at: string;
}

export interface AddressTrackingStats {
  total_count: number;
  enabled_count: number;
  disabled_count: number;
  notification_enabled_count: number;
}

// ==================== 巨鲸锚点 API ====================

export interface WhaleAnchorItem {
  coin: string;
  mark_price: number;
  price_change_24h_pct: number;
  day_volume_usd: number;
  open_interest_usd: number;
  depth_1pct_usd: number;
  volume_component: number;
  oi_component: number;
  depth_component: number;
  whale_threshold: number;
  dominant_factor: 'volume' | 'oi' | 'depth' | 'none';
  max_leverage: number;
}

export const whaleAnchorApi = {
  // 获取巨鲸锚点数据（从数据库读取，所有用户可访问）
  getData: () =>
    api.get<any, ApiResponse<WhaleAnchorItem[]> & { total?: number; updated_at?: string }>('/whale-anchor'),

  // 刷新巨鲸锚点数据（从 Hyperliquid API 拉取，仅管理员）
  refresh: () =>
    api.post<any, ApiResponse<void> & { message?: string; total?: number }>('/whale-anchor/refresh'),
};

export const addressTrackingApi = {
  // 获取地址跟踪列表
  getTrackings: (params?: {
    page?: number;
    limit?: number;
    is_enabled?: boolean;
    search?: string;
  }) =>
    api.get<any, ApiResponse<AddressTracking[]>>('/address-tracking', { params }),

  // 获取统计信息
  getStats: () =>
    api.get<any, ApiResponse<AddressTrackingStats>>('/address-tracking/stats'),

  // 获取单个跟踪详情
  getTracking: (trackingId: string) =>
    api.get<any, ApiResponse<AddressTracking>>(`/address-tracking/${trackingId}`),

  // 创建地址跟踪
  createTracking: (data: {
    tracking_address: string;
    address_remark?: string;
    is_enabled?: boolean;
    enable_notification?: boolean;
    monitor_events?: ('open' | 'close' | 'add' | 'reduce')[];
  }) =>
    api.post<any, ApiResponse<{ id: string }> & { message?: string }>('/address-tracking', data),

  // 更新地址跟踪配置
  updateTracking: (trackingId: string, data: Partial<AddressTracking>) =>
    api.put<any, ApiResponse<void> & { message?: string }>(`/address-tracking/${trackingId}`, data),

  // 删除地址跟踪
  deleteTracking: (trackingId: string) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/address-tracking/${trackingId}`),

  // 启用/禁用地址跟踪
  toggleTracking: (trackingId: string, isEnabled: boolean) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/address-tracking/${trackingId}/toggle`, { is_enabled: isEnabled }),

  // 启用/禁用地址跟踪通知
  toggleNotification: (trackingId: string, enableNotification: boolean) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/address-tracking/${trackingId}/toggle-notification`, { enable_notification: enableNotification }),

  // 批量删除地址跟踪
  batchDelete: (trackingIds: string[]) =>
    api.post<any, ApiResponse<{ deleted_count: number }> & { message?: string }>('/address-tracking/batch-delete', { tracking_ids: trackingIds }),
};

export default api;
