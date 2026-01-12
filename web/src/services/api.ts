import axios from 'axios';
import type {
  Trader,
  TraderFill,
  FillsSummary,
  AssetPosition,
  TraderHistory,
  TraderAIAnalysis,
  ApiResponse,
  CopyTradingGroup,
  CopyTradingAddress,
  CopyTradingOrder,
  CopyOrderStats,
  HyperliquidCoin,
  CopyPositionState,
  CopyPositionStats,
  TraderPosition,
  TraderPositionsStats,
  GroupComparisonSession,
  GroupComparisonGroup,
  GroupComparisonTrader,
  GroupComparisonStats,
  PaginationInfo,
  FillsStats,
  ChartDataPoint,
  RiskControlConfig,
  DefaultCopyTradingConfig,
  PositionHistoryRecord,
  PositionHistoryStats,
  PositionHistoryByCoin,
  GlobalPositionHistoryRecord,
  GlobalPositionHistoryStats,
  PositionsAIAnalysis,
} from '@/types/api';

// Re-export all types for backward compatibility
export type {
  Trader,
  TraderFill,
  FillsSummary,
  AssetPosition,
  TraderHistory,
  TraderAIAnalysis,
  ApiResponse,
  CopyTradingGroup,
  CopyTradingAddress,
  CopyTradingOrder,
  CopyOrderStats,
  HyperliquidCoin,
  CopyPositionState,
  CopyPositionStats,
  TraderPosition,
  TraderPositionsStats,
  GroupComparisonSession,
  GroupComparisonGroup,
  GroupComparisonTrader,
  GroupComparisonStats,
  PaginationInfo,
  FillsStats,
  ChartDataPoint,
  RiskControlConfig,
  DefaultCopyTradingConfig,
  PositionHistoryRecord,
  PositionHistoryStats,
  PositionHistoryByCoin,
  GlobalPositionHistoryRecord,
  GlobalPositionHistoryStats,
  PositionsAIAnalysis,
};

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

  // 切换同步仓位状态
  toggleSyncPosition: (address: string, syncPosition: boolean) =>
    api.post<any, ApiResponse<void> & { message?: string }>(`/copy-trading/addresses/${address}/sync-position`, { sync_position: syncPosition }),

  // 批量操作
  batchAction: (action: 'enable' | 'disable' | 'delete' | 'move_group', addresses: string[], groupId?: number) =>
    api.post<any, ApiResponse<void> & { affected_count?: number; message?: string }>('/copy-trading/addresses/batch', {
      action,
      addresses,
      group_id: groupId,
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

// ==================== 跟单订单 API ====================

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

// ==================== 跟单仓位状态 API ====================

export const copyPositionStatesApi = {
  // 获取所有仓位状态
  getPositions: (params?: { target_address?: string }) =>
    api.get<any, ApiResponse<CopyPositionState[]>>('/copy-trading/positions', { params }),

  // 获取统计信息
  getStats: () =>
    api.get<any, ApiResponse<CopyPositionStats>>('/copy-trading/positions/stats'),

  // 获取特定目标的仓位
  getTargetPositions: (targetAddress: string) =>
    api.get<any, ApiResponse<CopyPositionState[]>>(`/copy-trading/positions/${targetAddress}`),

  // 删除单个仓位状态
  deletePosition: (targetAddress: string, symbol: string) =>
    api.delete<any, ApiResponse<void> & { message?: string }>(`/copy-trading/positions/${targetAddress}/${symbol}`),

  // 清空目标所有仓位状态
  clearTargetPositions: (targetAddress: string) =>
    api.delete<any, ApiResponse<{ deleted_count: number }> & { message?: string }>(`/copy-trading/positions/${targetAddress}`),

  // 清空所有仓位状态
  clearAll: () =>
    api.post<any, ApiResponse<{ deleted_count: number }> & { message?: string }>('/copy-trading/positions/clear-all'),
};

// ==================== 跟单交易员实时持仓 API ====================

export const traderPositionsApi = {
  // 获取所有跟单交易员的当前持仓
  getPositions: (params?: {
    enabled_only?: boolean;
    group_id?: number;
    // 指标筛选
    min_win_rate?: number;
    max_win_rate?: number;
    min_profit_factor?: number;
    max_profit_factor?: number;
    min_pnl?: number;
    max_pnl?: number;
    min_drawdown?: number;
    max_drawdown?: number;
    min_sharpe?: number;
    max_sharpe?: number;
    min_sortino?: number;
    max_sortino?: number;
    min_trades?: number;
    max_trades?: number;
    min_score?: number;
    max_score?: number;
  }) =>
    api.get<any, ApiResponse<TraderPosition[]> & { stats?: TraderPositionsStats }>('/copy-trading/trader-positions', { params }),

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

// ==================== 分组对比分析 API ====================

export const groupComparisonApi = {
  // 获取会话列表
  getSessions: (params?: { limit?: number; status?: string }) =>
    api.get<any, ApiResponse<GroupComparisonSession[]>>('/group-comparison/sessions', { params }),

  // 获取会话详情
  getSession: (sessionId: number) =>
    api.get<any, ApiResponse<GroupComparisonSession>>(`/group-comparison/sessions/${sessionId}`),

  // 获取会话晋级者
  getFinalists: (sessionId: number) =>
    api.get<any, ApiResponse<GroupComparisonTrader[]>>(`/group-comparison/sessions/${sessionId}/finalists`),

  // 获取会话分组信息
  getGroups: (sessionId: number) =>
    api.get<any, ApiResponse<GroupComparisonGroup[]>>(`/group-comparison/sessions/${sessionId}/groups`),

  // 获取统计信息
  getStats: () =>
    api.get<any, ApiResponse<GroupComparisonStats>>('/group-comparison/stats'),
};

// ==================== 风控配置 API ====================

export const riskControlApi = {
  // 获取风控配置
  getConfig: () =>
    api.get<any, ApiResponse<RiskControlConfig>>('/copy-trading/risk-control'),

  // 更新风控配置
  updateConfig: (data: Partial<RiskControlConfig>) =>
    api.put<any, ApiResponse<RiskControlConfig> & { message?: string }>('/copy-trading/risk-control', data),

  // 获取默认跟单配置
  getDefaultCopyConfig: () =>
    api.get<any, ApiResponse<DefaultCopyTradingConfig>>('/copy-trading/default-config'),

  // 更新默认跟单配置
  updateDefaultCopyConfig: (data: Partial<DefaultCopyTradingConfig>) =>
    api.put<any, ApiResponse<DefaultCopyTradingConfig> & { message?: string }>('/copy-trading/default-config', data),
};

// ==================== S级优选筛选 API ====================

export interface BestSTraderParams {
  preset?: string;
  min_sharpe?: number;
  max_drawdown?: number;
  min_profit_factor?: number;
  min_positions?: number;
  min_position_win_rate?: number;
  min_position_pf?: number;
  recent_days?: number;
  min_recent_positions?: number;
  require_recent_profit?: boolean;
  max_inactive_days?: number;
  min_holding_hours?: number;
  max_holding_hours?: number;
  sort_by?: string;
  limit?: number;
}

export interface BestSTrader {
  address: string;
  overall_score: number;
  rating: string;
  trade_win_rate: number;
  trade_profit_factor: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  total_pnl: number;
  total_trades: number;
  recent_7d_pnl: number;
  last_trade_time: string;
  current_positions: number;
  is_starred: boolean;
  // 仓位统计
  total_positions: number;
  closed_positions: number;
  winning_positions: number;
  losing_positions: number;
  position_win_rate: number | null;
  position_profit_factor: number | null;
  avg_holding_hours: number;
  avg_build_trades: number;
  position_total_pnl: number;
  // 近期仓位表现
  recent_positions: number;
  recent_pnl: number;
  recent_wins: number;
  recent_position_win_rate: number | null;
  // 跟单信息
  trader_name: string | null;
  group_name: string | null;
}

export interface BestSPreset {
  key: string;
  name: string;
  description: string;
  params: BestSTraderParams;
}

export const bestSTradersApi = {
  // 获取S级优选交易员
  getBestSTraders: (params?: BestSTraderParams) =>
    api.get<any, ApiResponse<BestSTrader[]> & { 
      preset?: { name: string; description: string; key: string };
      params?: BestSTraderParams;
    }>('/traders/best-s', { params }),

  // 获取预设列表
  getPresets: () =>
    api.get<any, ApiResponse<BestSPreset[]>>('/traders/best-s/presets'),

  // 获取交易员仓位分析
  getPositionAnalysis: (address: string) =>
    api.get<any, ApiResponse<{
      trader: Partial<Trader>;
      position_analysis: {
        total_positions: number;
        closed_positions: number;
        open_positions: number;
        winning_positions: number;
        losing_positions: number;
        total_pnl: number;
        avg_pnl: number;
        avg_win_pnl: number;
        avg_loss_pnl: number;
        best_position: number;
        worst_position: number;
        avg_holding_hours: number;
        avg_build_trades: number;
        total_fees: number;
        unique_coins: number;
        position_win_rate: number;
        position_profit_factor: number;
        by_coin: Array<{
          coin: string;
          positions: number;
          wins: number;
          total_pnl: number;
          avg_holding: number;
        }>;
        recent_30d: {
          positions: number;
          wins: number;
          total_pnl: number;
          win_rate: number;
        };
      };
    }>>(`/traders/${address}/position-analysis`),
};

export default api;
