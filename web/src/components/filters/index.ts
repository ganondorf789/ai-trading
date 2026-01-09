export { RangeFilter } from './RangeFilter';

// 通用指标筛选配置类型
export interface MetricFilterConfig {
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
  minTrades?: number;
  maxTrades?: number;
  minScore?: number;
  maxScore?: number;
}

// 空的筛选配置
export const emptyMetricFilters: MetricFilterConfig = {};
