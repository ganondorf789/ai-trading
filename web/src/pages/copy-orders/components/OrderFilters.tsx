import { Input, Select, SelectItem, Button } from "@heroui/react";
import { Icon } from "@iconify/react";
import { useState } from "react";
import { RangeFilter, MetricFilterConfig } from "@/components/filters";

interface OrderFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  sideFilter: string;
  onSideFilterChange: (value: string) => void;
  actionFilter: string;
  onActionFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  targetFilter: string;
  onTargetFilterChange: (value: string) => void;
  daysFilter: number;
  onDaysFilterChange: (value: number) => void;
  targets: Array<{ address: string; name: string | null }>;
  onRefresh: () => void;
  loading: boolean;
  // 指标筛选
  metricFilters: MetricFilterConfig;
  onMetricFiltersChange: (filters: MetricFilterConfig) => void;
  onReset: () => void;
}

export function OrderFilters({
  search,
  onSearchChange,
  sideFilter,
  onSideFilterChange,
  actionFilter,
  onActionFilterChange,
  statusFilter,
  onStatusFilterChange,
  targetFilter,
  onTargetFilterChange,
  daysFilter,
  onDaysFilterChange,
  targets,
  onRefresh,
  loading,
  metricFilters,
  onMetricFiltersChange,
  onReset,
}: OrderFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 检查是否有活跃的指标筛选
  const hasActiveMetricFilters = Object.values(metricFilters).some(v => v !== undefined);

  // 检查是否有任何筛选条件
  const hasAnyFilter = hasActiveMetricFilters || search || sideFilter || actionFilter || statusFilter || targetFilter;

  return (
    <div className="mb-6 flex flex-col gap-4">
      {/* 第一行：基础筛选 */}
      <div className="flex flex-wrap gap-4 items-end">
        {/* Search */}
        <Input
          className="w-64"
          placeholder="搜索币种..."
          startContent={<Icon icon="solar:magnifer-linear" className="text-default-400" width={18} />}
          value={search}
          onValueChange={onSearchChange}
          isClearable
          onClear={() => onSearchChange("")}
        />

        {/* Target Address Filter */}
        <Select
          className="w-48"
          label="交易员"
          placeholder="全部交易员"
          selectedKeys={targetFilter ? [targetFilter] : []}
          size="sm"
          onChange={(e) => onTargetFilterChange(e.target.value)}
        >
          {[
            <SelectItem key="" textValue="全部交易员">
              全部交易员
            </SelectItem>,
            ...targets.map((t) => (
              <SelectItem key={t.address} textValue={t.name || formatAddress(t.address)}>
                {t.name || formatAddress(t.address)}
              </SelectItem>
            )),
          ]}
        </Select>

        {/* Side Filter */}
        <Select
          className="w-32"
          label="方向"
          placeholder="全部"
          selectedKeys={sideFilter ? [sideFilter] : []}
          size="sm"
          onChange={(e) => onSideFilterChange(e.target.value)}
        >
          <SelectItem key="" textValue="全部">全部</SelectItem>
          <SelectItem key="long" textValue="多头">
            <span className="text-success">多头</span>
          </SelectItem>
          <SelectItem key="short" textValue="空头">
            <span className="text-danger">空头</span>
          </SelectItem>
        </Select>

        {/* Action Filter */}
        <Select
          className="w-32"
          label="操作"
          placeholder="全部"
          selectedKeys={actionFilter ? [actionFilter] : []}
          size="sm"
          onChange={(e) => onActionFilterChange(e.target.value)}
        >
          <SelectItem key="" textValue="全部">全部</SelectItem>
          <SelectItem key="open" textValue="开仓">开仓</SelectItem>
          <SelectItem key="close" textValue="平仓">平仓</SelectItem>
        </Select>

        {/* Status Filter */}
        <Select
          className="w-32"
          label="状态"
          placeholder="全部"
          selectedKeys={statusFilter ? [statusFilter] : []}
          size="sm"
          onChange={(e) => onStatusFilterChange(e.target.value)}
        >
          <SelectItem key="" textValue="全部">全部</SelectItem>
          <SelectItem key="success" textValue="成功">
            <span className="text-success">成功</span>
          </SelectItem>
          <SelectItem key="failed" textValue="失败">
            <span className="text-danger">失败</span>
          </SelectItem>
          <SelectItem key="pending" textValue="等待中">
            <span className="text-warning">等待中</span>
          </SelectItem>
        </Select>

        {/* Days Filter */}
        <Select
          className="w-32"
          label="时间范围"
          placeholder="7天"
          selectedKeys={[String(daysFilter)]}
          size="sm"
          onChange={(e) => onDaysFilterChange(Number(e.target.value))}
        >
          <SelectItem key="1" textValue="1天">1天</SelectItem>
          <SelectItem key="3" textValue="3天">3天</SelectItem>
          <SelectItem key="7" textValue="7天">7天</SelectItem>
          <SelectItem key="14" textValue="14天">14天</SelectItem>
          <SelectItem key="30" textValue="30天">30天</SelectItem>
        </Select>

        {/* Advanced Filter Toggle */}
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

        {/* Reset Button */}
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

        {/* Refresh Button */}
        <Button
          color="primary"
          isLoading={loading}
          startContent={!loading && <Icon icon="solar:refresh-linear" width={18} />}
          variant="flat"
          onPress={onRefresh}
        >
          刷新
        </Button>
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
