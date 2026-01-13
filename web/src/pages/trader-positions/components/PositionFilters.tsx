import { Select, SelectItem, Button, Autocomplete, AutocompleteItem, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import type { Selection, SortDescriptor, DateValue, RangeValue } from "@heroui/react";
import { Icon } from "@iconify/react";
import { useState } from "react";
import { TraderPositionsStats, CopyTradingGroup } from "@/services/api";
import { RangeFilter, MetricFilterConfig } from "@/components/filters";
import { TimeRangeFilter } from "@/components/TimeRangeFilter";

// 表格列配置
export type TraderPositionColumnKey = 'star' | 'trader' | 'rating' | 'coin' | 'direction' | 'size' | 'entry_px' | 'position_value' | 'unrealized_pnl' | 'roe' | 'leverage' | 'open_time' | 'updated_at' | 'actions';

export interface TraderPositionColumn {
  uid: TraderPositionColumnKey;
  name: string;
  sortable?: boolean;
}

export const traderPositionColumns: TraderPositionColumn[] = [
  { uid: 'star', name: '收藏', sortable: true },
  { uid: 'trader', name: '交易员', sortable: true },
  { uid: 'rating', name: '评级', sortable: true },
  { uid: 'coin', name: '币种', sortable: true },
  { uid: 'direction', name: '方向', sortable: true },
  { uid: 'size', name: '数量', sortable: true },
  { uid: 'entry_px', name: '开仓均价', sortable: true },
  { uid: 'position_value', name: '仓位价值', sortable: true },
  { uid: 'unrealized_pnl', name: '未实现盈亏', sortable: true },
  { uid: 'roe', name: 'ROE', sortable: true },
  { uid: 'leverage', name: '杠杆', sortable: true },
  { uid: 'open_time', name: '开仓时间', sortable: true },
  { uid: 'updated_at', name: '更新时间', sortable: true },
  { uid: 'actions', name: '操作', sortable: false },
];

export const INITIAL_VISIBLE_COLUMNS: TraderPositionColumnKey[] = [
  'star', 'trader', 'rating', 'coin', 'direction', 'size', 'entry_px', 'position_value', 'unrealized_pnl', 'roe', 'leverage', 'open_time', 'updated_at', 'actions'
];

interface PositionFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  sideFilter: string;
  onSideFilterChange: (value: string) => void;
  traderFilter: string;
  onTraderFilterChange: (value: string) => void;
  coinFilter: string;
  onCoinFilterChange: (value: string) => void;
  groupFilter: string;
  onGroupFilterChange: (value: string) => void;
  starFilter: string;
  onStarFilterChange: (value: string) => void;
  pnlFilter: string;
  onPnlFilterChange: (value: string) => void;
  scoreFilter: string;
  onScoreFilterChange: (value: string) => void;
  // 开仓时间筛选
  openTimeFilter: string;
  onOpenTimeFilterChange: (value: string) => void;
  openTimeDateRange: RangeValue<DateValue> | null;
  onOpenTimeDateRangeChange: (range: RangeValue<DateValue> | null) => void;
  stats: TraderPositionsStats | null;
  groups: CopyTradingGroup[];
  // 指标筛选
  metricFilters: MetricFilterConfig;
  onMetricFiltersChange: (filters: MetricFilterConfig) => void;
  onReset: () => void;
  // 排序相关
  sortDescriptor: SortDescriptor;
  onSortChange: (descriptor: SortDescriptor) => void;
  // 列可见性相关
  visibleColumns: Selection;
  onVisibleColumnsChange: (columns: Selection) => void;
}

export function PositionFilters({
  search: _search,
  onSearchChange: _onSearchChange,
  sideFilter,
  onSideFilterChange,
  traderFilter,
  onTraderFilterChange,
  coinFilter,
  onCoinFilterChange,
  groupFilter,
  onGroupFilterChange,
  starFilter,
  onStarFilterChange,
  pnlFilter,
  onPnlFilterChange,
  scoreFilter,
  onScoreFilterChange,
  openTimeFilter,
  onOpenTimeFilterChange,
  openTimeDateRange,
  onOpenTimeDateRangeChange,
  stats,
  groups,
  metricFilters,
  onMetricFiltersChange,
  onReset,
  sortDescriptor,
  onSortChange,
  visibleColumns,
  onVisibleColumnsChange,
}: PositionFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 构建交易员选项
  const traderOptions = stats?.by_trader || [];
  const coinOptions = stats?.by_coin || [];

  // 检查是否有活跃的指标筛选
  const hasActiveMetricFilters = Object.values(metricFilters).some(v => v !== undefined);

  return (
    <div className="flex flex-col gap-4 mb-6">
      {/* 筛选区域 */}
      <div className="bg-content1 rounded-xl shadow-small border border-divider overflow-hidden">
        {/* 主筛选行 */}
        <div className="p-4">
          <div className="flex flex-wrap gap-x-6 gap-y-4 items-end">
            {/* 仓位筛选组 */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">方向</span>
                <Select
                  className="w-[100px]"
                  size="sm"
                  selectedKeys={[sideFilter]}
                  onSelectionChange={(keys) => onSideFilterChange(Array.from(keys)[0] as string)}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="long" textValue="多头">
                    <span className="text-success">多头</span>
                  </SelectItem>
                  <SelectItem key="short" textValue="空头">
                    <span className="text-danger">空头</span>
                  </SelectItem>
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">盈亏</span>
                <Select
                  className="w-[110px]"
                  size="sm"
                  selectedKeys={[pnlFilter]}
                  onSelectionChange={(keys) => onPnlFilterChange(Array.from(keys)[0] as string)}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="profit" textValue="盈利">
                    <span className="text-success">盈利 📈</span>
                  </SelectItem>
                  <SelectItem key="loss" textValue="亏损">
                    <span className="text-danger">亏损 📉</span>
                  </SelectItem>
                </Select>
              </div>
            </div>

            {/* 分隔线 */}
            <div className="h-8 w-px bg-divider hidden sm:block" />

            {/* 交易员/币种筛选组 */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">分组</span>
                <Select
                  className="w-[130px]"
                  size="sm"
                  selectedKeys={[groupFilter]}
                  onSelectionChange={(keys) => onGroupFilterChange(Array.from(keys)[0] as string)}
                >
                  {[
                    <SelectItem key="all" textValue="全部">全部</SelectItem>,
                    ...groups.map((group) => (
                      <SelectItem key={group.id.toString()} textValue={group.name}>{group.name}</SelectItem>
                    )),
                  ]}
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">交易员</span>
                <Autocomplete
                  className="w-[180px]"
                  size="sm"
                  selectedKey={traderFilter}
                  onSelectionChange={(key) => onTraderFilterChange((key as string) || 'all')}
                  allowsCustomValue={false}
                  defaultItems={[
                    { key: 'all', label: '全部', count: null as number | null },
                    ...traderOptions.map((trader) => ({
                      key: trader.address,
                      label: trader.name || `${trader.address.slice(0, 6)}...${trader.address.slice(-4)}`,
                      count: trader.count as number | null,
                    })),
                  ]}
                >
                  {(item) => (
                    <AutocompleteItem key={item.key} textValue={item.label}>
                      <div className="flex justify-between items-center w-full">
                        <span className="truncate">{item.label}</span>
                        {item.count && <span className="text-default-400 text-xs ml-2">{item.count}</span>}
                      </div>
                    </AutocompleteItem>
                  )}
                </Autocomplete>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">币种</span>
                <Autocomplete
                  className="w-[140px]"
                  size="sm"
                  selectedKey={coinFilter}
                  onSelectionChange={(key) => onCoinFilterChange((key as string) || 'all')}
                  allowsCustomValue={false}
                  defaultItems={[
                    { key: 'all', label: '全部', count: null as number | null },
                    ...coinOptions.map((coin) => ({
                      key: coin.coin,
                      label: coin.coin,
                      count: coin.count as number | null,
                    })),
                  ]}
                >
                  {(item) => (
                    <AutocompleteItem key={item.key} textValue={item.label}>
                      <div className="flex justify-between items-center w-full">
                        <span>{item.label}</span>
                        {item.count && <span className="text-default-400 text-xs ml-2">{item.count}</span>}
                      </div>
                    </AutocompleteItem>
                  )}
                </Autocomplete>
              </div>
            </div>

            {/* 分隔线 */}
            <div className="h-8 w-px bg-divider hidden sm:block" />

            {/* 评级/收藏筛选组 */}
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">评级</span>
                <Select
                  className="w-[90px]"
                  size="sm"
                  selectedKeys={scoreFilter ? [scoreFilter] : []}
                  onSelectionChange={(keys) => {
                    const selected = Array.from(keys)[0] as string;
                    onScoreFilterChange(selected || 'all');
                  }}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="S" textValue="S"><span className="font-semibold text-warning">S</span></SelectItem>
                  <SelectItem key="A" textValue="A"><span className="font-semibold text-success">A</span></SelectItem>
                  <SelectItem key="B" textValue="B"><span className="font-semibold text-primary">B</span></SelectItem>
                  <SelectItem key="C" textValue="C"><span className="font-semibold text-default-600">C</span></SelectItem>
                  <SelectItem key="D" textValue="D"><span className="font-semibold text-default-400">D</span></SelectItem>
                  <SelectItem key="F" textValue="F"><span className="font-semibold text-danger">F</span></SelectItem>
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-default-500 font-medium">收藏</span>
                <Select
                  className="w-[110px]"
                  size="sm"
                  selectedKeys={[starFilter]}
                  onSelectionChange={(keys) => onStarFilterChange(Array.from(keys)[0] as string)}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="starred" textValue="已收藏">已收藏 ⭐</SelectItem>
                  <SelectItem key="unstarred" textValue="未收藏">未收藏</SelectItem>
                </Select>
              </div>

              <TimeRangeFilter
                label="开仓时间"
                value={openTimeFilter}
                dateRange={openTimeDateRange}
                onValueChange={onOpenTimeFilterChange}
                onDateRangeChange={onOpenTimeDateRangeChange}
                selectClassName="w-[120px]"
                layout="vertical"
              />
            </div>
          </div>
        </div>

        {/* 操作栏 */}
        <div className="px-4 py-3 bg-default-50 border-t border-divider flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Button
              variant="flat"
              size="sm"
              startContent={<Icon icon={showAdvanced ? "solar:alt-arrow-up-linear" : "solar:tuning-2-linear"} width={16} />}
              onPress={() => setShowAdvanced(!showAdvanced)}
              color={hasActiveMetricFilters ? "primary" : "default"}
            >
              {showAdvanced ? "收起" : "高级筛选"}
              {hasActiveMetricFilters && !showAdvanced && (
                <span className="ml-1 text-xs bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full">
                  {Object.values(metricFilters).filter(v => v !== undefined).length}
                </span>
              )}
            </Button>

            {(hasActiveMetricFilters || _search || sideFilter !== "all" || groupFilter !== "all" || traderFilter !== "all" || coinFilter !== "all" || starFilter !== "all" || pnlFilter !== "all" || scoreFilter !== "all" || openTimeFilter !== "all") && (
              <Button
                variant="light"
                size="sm"
                color="warning"
                startContent={<Icon icon="solar:restart-linear" width={16} />}
                onPress={onReset}
              >
                重置全部
              </Button>
            )}
          </div>

          {/* 右侧：排序和列 */}
          <div className="flex items-center gap-2">
            {/* Sort 下拉 */}
            <Dropdown>
              <DropdownTrigger>
                <Button
                  variant="flat"
                  size="sm"
                  className="bg-default-100"
                  startContent={
                    <Icon className="text-default-500" icon="solar:sort-linear" width={16} />
                  }
                >
                  排序
                  {sortDescriptor.column && (
                    <Icon
                      icon={sortDescriptor.direction === 'ascending' ? 'solar:alt-arrow-up-linear' : 'solar:alt-arrow-down-linear'}
                      className="ml-1 text-primary"
                      width={14}
                    />
                  )}
                </Button>
              </DropdownTrigger>
              <DropdownMenu
                aria-label="Sort"
                items={traderPositionColumns.filter((c) => c.sortable)}
              >
                {(item) => (
                  <DropdownItem
                    key={item.uid}
                    onPress={() => {
                      onSortChange({
                        column: item.uid,
                        direction:
                          sortDescriptor.column === item.uid && sortDescriptor.direction === 'ascending' 
                            ? 'descending' 
                            : 'ascending',
                      });
                    }}
                    endContent={
                      sortDescriptor.column === item.uid ? (
                        <Icon
                          icon={sortDescriptor.direction === 'ascending' ? 'solar:alt-arrow-up-linear' : 'solar:alt-arrow-down-linear'}
                          className="text-primary"
                          width={14}
                        />
                      ) : null
                    }
                  >
                    {item.name}
                  </DropdownItem>
                )}
              </DropdownMenu>
            </Dropdown>

            {/* Columns 下拉 */}
            <Dropdown closeOnSelect={false}>
              <DropdownTrigger>
                <Button
                  variant="flat"
                  size="sm"
                  className="bg-default-100"
                  startContent={
                    <Icon
                      className="text-default-500"
                      icon="solar:checklist-minimalistic-linear"
                      width={16}
                    />
                  }
                >
                  列
                </Button>
              </DropdownTrigger>
              <DropdownMenu
                disallowEmptySelection
                aria-label="Columns"
                items={traderPositionColumns}
                selectedKeys={visibleColumns}
                selectionMode="multiple"
                onSelectionChange={onVisibleColumnsChange}
              >
                {(item) => <DropdownItem key={item.uid}>{item.name}</DropdownItem>}
              </DropdownMenu>
            </Dropdown>
          </div>
        </div>

        {/* 高级指标筛选（可折叠） */}
        {showAdvanced && (
          <div className="border-t border-divider">
            <div className="p-4 bg-default-50/50">
              <div className="flex items-center gap-2 mb-4">
                <Icon icon="solar:chart-2-linear" className="text-primary" width={18} />
                <span className="text-sm text-default-700 font-medium">交易员指标筛选</span>
                <span className="text-xs text-default-400">（基于跟单地址关联的交易员数据）</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
          </div>
        )}
      </div>
    </div>
  );
}
