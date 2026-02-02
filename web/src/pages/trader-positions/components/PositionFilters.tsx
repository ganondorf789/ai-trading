import { Select, SelectItem, Button, Autocomplete, AutocompleteItem, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import type { Selection, SortDescriptor, DateValue, RangeValue } from "@heroui/react";
import { Icon } from "@iconify/react";
import type { TraderPositionsStats } from "@/types/api";
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
  coinFilter: string;
  onCoinFilterChange: (value: string) => void;
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
  coinFilter,
  onCoinFilterChange,
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
  onReset,
  sortDescriptor,
  onSortChange,
  visibleColumns,
  onVisibleColumnsChange,
}: PositionFiltersProps) {
  // 构建币种选项
  const coinOptions = stats?.by_coin || [];

  return (
    <div className="flex flex-col gap-4 mb-6">
      {/* 筛选区域 */}
      <div className="bg-content1 rounded-xl shadow-small border border-divider overflow-hidden">
        {/* 主筛选行 */}
        <div className="p-4">
          <div className="flex flex-wrap justify-between gap-4">
            {/* 左侧：筛选组 */}
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

              {/* 币种筛选 */}
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

              {/* 重置按钮 */}
              {(_search || sideFilter !== "all" || coinFilter !== "all" || starFilter !== "all" || pnlFilter !== "all" || scoreFilter !== "all" || openTimeFilter !== "all") && (
                <Button
                  variant="light"
                  size="sm"
                  color="warning"
                  startContent={<Icon icon="solar:restart-linear" width={16} />}
                  onPress={onReset}
                >
                  重置
                </Button>
              )}
            </div>

            {/* 右侧：排序和列 */}
            <div className="flex items-end gap-2">
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
        </div>
      </div>
    </div>
  );
}
