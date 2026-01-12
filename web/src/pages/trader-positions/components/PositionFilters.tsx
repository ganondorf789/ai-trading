import { Select, SelectItem, Button, Autocomplete, AutocompleteItem, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import type { Selection, SortDescriptor } from "@heroui/react";
import { Icon } from "@iconify/react";
import { useState } from "react";
import { TraderPositionsStats, CopyTradingGroup } from "@/services/api";
import { RangeFilter, MetricFilterConfig } from "@/components/filters";

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
      {/* 第一行：基础筛选 */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">方向</span>
          <Select
            className="min-w-[100px]"
            selectedKeys={[sideFilter]}
            onSelectionChange={(keys) => onSideFilterChange(Array.from(keys)[0] as string)}
          >
            <SelectItem key="all" textValue="全部">全部</SelectItem>
            <SelectItem key="long" textValue="多头">多头</SelectItem>
            <SelectItem key="short" textValue="空头">空头</SelectItem>
          </Select>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">分组</span>
          <Select
            className="min-w-[120px]"
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

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">交易员</span>
          <Autocomplete
            className="min-w-[200px]"
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
                {item.label}{item.count ? ` (${item.count})` : ''}
              </AutocompleteItem>
            )}
          </Autocomplete>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">币种</span>
          <Autocomplete
            className="min-w-[160px]"
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
                {item.label}{item.count ? ` (${item.count})` : ''}
              </AutocompleteItem>
            )}
          </Autocomplete>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">收藏</span>
          <Select
            className="min-w-[100px]"
            selectedKeys={[starFilter]}
            onSelectionChange={(keys) => onStarFilterChange(Array.from(keys)[0] as string)}
          >
            <SelectItem key="all" textValue="全部">全部</SelectItem>
            <SelectItem key="starred" textValue="已收藏">已收藏 ⭐</SelectItem>
            <SelectItem key="unstarred" textValue="未收藏">未收藏</SelectItem>
          </Select>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">盈亏</span>
          <Select
            className="min-w-[100px]"
            selectedKeys={[pnlFilter]}
            onSelectionChange={(keys) => onPnlFilterChange(Array.from(keys)[0] as string)}
          >
            <SelectItem key="all" textValue="全部">全部</SelectItem>
            <SelectItem key="profit" textValue="盈利">盈利 📈</SelectItem>
            <SelectItem key="loss" textValue="亏损">亏损 📉</SelectItem>
          </Select>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">评级</span>
          <Select
            className="min-w-[80px]"
            selectedKeys={scoreFilter ? [scoreFilter] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onScoreFilterChange(selected || 'all');
            }}
          >
            <SelectItem key="all" textValue="全部">全部</SelectItem>
            <SelectItem key="S" textValue="S">S</SelectItem>
            <SelectItem key="A" textValue="A">A</SelectItem>
            <SelectItem key="B" textValue="B">B</SelectItem>
            <SelectItem key="C" textValue="C">C</SelectItem>
            <SelectItem key="D" textValue="D">D</SelectItem>
            <SelectItem key="F" textValue="F">F</SelectItem>
          </Select>
        </div>

        <Button
          variant="flat"
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

        {(hasActiveMetricFilters || _search || sideFilter !== "all" || groupFilter !== "all" || traderFilter !== "all" || coinFilter !== "all" || starFilter !== "all" || pnlFilter !== "all" || scoreFilter !== "all") && (
          <Button
            variant="flat"
            color="warning"
            startContent={<Icon icon="solar:restart-linear" width={16} />}
            onPress={onReset}
          >
            重置
          </Button>
        )}

        {/* 右侧：排序和列 */}
        <div className="flex items-center gap-2 shrink-0 ml-auto">
          {/* Sort 下拉 */}
          <Dropdown>
            <DropdownTrigger>
              <Button
                className="bg-default-100 text-default-800"
                startContent={
                  <Icon className="text-default-400" icon="solar:sort-linear" width={16} />
                }
              >
                排序
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
                >
                  {item.name}
                  {sortDescriptor.column === item.uid && (
                    <Icon
                      icon={sortDescriptor.direction === 'ascending' ? 'solar:alt-arrow-up-linear' : 'solar:alt-arrow-down-linear'}
                      className="ml-1 inline"
                      width={14}
                    />
                  )}
                </DropdownItem>
              )}
            </DropdownMenu>
          </Dropdown>

          {/* Columns 下拉 */}
          <Dropdown closeOnSelect={false}>
            <DropdownTrigger>
              <Button
                className="bg-default-100 text-default-800"
                startContent={
                  <Icon
                    className="text-default-400"
                    icon="solar:sort-horizontal-linear"
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
