import { Input, Select, SelectItem, Button } from "@heroui/react";
import { Icon } from "@iconify/react";
import { useState } from "react";
import { CopyPositionStats } from "@/services/api";
import { RangeFilter, MetricFilterConfig } from "@/components/filters";

interface PositionFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  sideFilter: string;
  onSideFilterChange: (value: string) => void;
  targetFilter: string;
  onTargetFilterChange: (value: string) => void;
  stats: CopyPositionStats | null;
  // 指标筛选
  metricFilters: MetricFilterConfig;
  onMetricFiltersChange: (filters: MetricFilterConfig) => void;
  onReset: () => void;
}

export function PositionFilters({
  search,
  onSearchChange,
  sideFilter,
  onSideFilterChange,
  targetFilter,
  onTargetFilterChange,
  stats,
  metricFilters,
  onMetricFiltersChange,
  onReset,
}: PositionFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 检查是否有活跃的指标筛选
  const hasActiveMetricFilters = Object.values(metricFilters).some(v => v !== undefined);

  // 检查是否有任何筛选条件
  const hasAnyFilter = hasActiveMetricFilters || search || sideFilter !== "all" || targetFilter !== "all";

  return (
    <div className="flex flex-col gap-4 mb-4">
      {/* 第一行：基础筛选 */}
      <div className="flex flex-wrap items-center gap-4">
        <Input
          className="w-64"
          placeholder="搜索币种或地址..."
          startContent={<Icon icon="solar:magnifer-linear" width={18} className="text-default-400" />}
          value={search}
          onValueChange={onSearchChange}
          isClearable
          onClear={() => onSearchChange("")}
        />

        <div className="flex items-center gap-2">
          <span className="text-sm text-default-500 whitespace-nowrap">方向:</span>
          <Select
            className="w-28"
            aria-label="Side"
            selectedKeys={[sideFilter]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string;
              onSideFilterChange(value);
            }}
          >
            <SelectItem key="all">全部</SelectItem>
            <SelectItem key="long">多头</SelectItem>
            <SelectItem key="short">空头</SelectItem>
          </Select>
        </div>

        {stats && stats.by_target && stats.by_target.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-500 whitespace-nowrap">目标:</span>
            <Select
              className="w-40"
              aria-label="Target"
              selectedKeys={[targetFilter]}
              size="sm"
              items={[
                { key: "all", label: "全部目标" },
                ...stats.by_target.map((t) => ({
                  key: t.target_address,
                  label: `${t.target_name || formatAddress(t.target_address)} (${t.position_count})`,
                })),
              ]}
              onSelectionChange={(keys) => {
                const value = Array.from(keys)[0] as string;
                onTargetFilterChange(value);
              }}
            >
              {(item) => <SelectItem key={item.key}>{item.label}</SelectItem>}
            </Select>
          </div>
        )}

        <Button
          variant="flat"
          size="sm"
          startContent={<Icon icon={showAdvanced ? "solar:alt-arrow-up-linear" : "solar:alt-arrow-down-linear"} width={16} />}
          onPress={() => setShowAdvanced(!showAdvanced)}
          color={hasActiveMetricFilters ? "primary" : "default"}
        >
          {showAdvanced ? "收起筛选" : "高级筛选"}
          {hasActiveMetricFilters && !showAdvanced && (
            <span className="ml-1 text-xs bg-primary-100 text-primary-700 px-1.5 py-0.5 rounded-full">
              有筛选
            </span>
          )}
        </Button>

        {hasAnyFilter && (
          <Button
            variant="flat"
            size="sm"
            color="warning"
            startContent={<Icon icon="solar:restart-linear" width={16} />}
            onPress={onReset}
          >
            重置
          </Button>
        )}
      </div>

      {/* 第二行：高级指标筛选（可折叠） */}
      {showAdvanced && (
        <div className="bg-default-50 rounded-lg p-4 border border-default-200">
          <div className="mb-3 text-sm text-default-600 font-medium">
            交易员指标筛选（基于跟单地址关联的交易员数据）
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <RangeFilter
              label="胜率"
              minValue={metricFilters.minWinRate}
              maxValue={metricFilters.maxWinRate}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minWinRate: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxWinRate: v })}
              endContent={<span className="text-xs text-default-400">%</span>}
            />

            <RangeFilter
              label="盈亏比"
              minValue={metricFilters.minProfitFactor}
              maxValue={metricFilters.maxProfitFactor}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minProfitFactor: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxProfitFactor: v })}
            />

            <RangeFilter
              label="总盈亏 ($)"
              minValue={metricFilters.minPnl}
              maxValue={metricFilters.maxPnl}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minPnl: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxPnl: v })}
            />

            <RangeFilter
              label="回撤"
              minValue={metricFilters.minDrawdown}
              maxValue={metricFilters.maxDrawdown}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minDrawdown: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxDrawdown: v })}
              endContent={<span className="text-xs text-default-400">%</span>}
            />

            <RangeFilter
              label="Sharpe"
              minValue={metricFilters.minSharpe}
              maxValue={metricFilters.maxSharpe}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minSharpe: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxSharpe: v })}
            />

            <RangeFilter
              label="Sortino"
              minValue={metricFilters.minSortino}
              maxValue={metricFilters.maxSortino}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minSortino: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxSortino: v })}
            />

            <RangeFilter
              label="交易数"
              minValue={metricFilters.minTrades}
              maxValue={metricFilters.maxTrades}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minTrades: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxTrades: v })}
              isInteger
            />

            <RangeFilter
              label="综合评分"
              minValue={metricFilters.minScore}
              maxValue={metricFilters.maxScore}
              onMinChange={(v) => onMetricFiltersChange({ ...metricFilters, minScore: v })}
              onMaxChange={(v) => onMetricFiltersChange({ ...metricFilters, maxScore: v })}
            />
          </div>
        </div>
      )}
    </div>
  );
}
