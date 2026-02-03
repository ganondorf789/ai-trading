import { Input, Select, SelectItem, Button, Autocomplete, AutocompleteItem, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import type { Selection, SortDescriptor, DateValue, RangeValue } from "@heroui/react";
import { Icon } from "@iconify/react";
import { PositionHistoryByCoin } from "@/services/api";
import { TimeRangeFilter } from "@/components/TimeRangeFilter";

// 表格列配置
export type PositionHistoryColumnKey = 'trader' | 'rating' | 'coin' | 'direction' | 'open_time' | 'close_time' | 'max_size' | 'avg_entry_price' | 'avg_close_price' | 'position_value' | 'holding_hours' | 'realized_pnl' | 'status';

export interface PositionHistoryColumn {
  uid: PositionHistoryColumnKey;
  name: string;
  sortable?: boolean;
}

export const positionHistoryColumns: PositionHistoryColumn[] = [
  { uid: 'trader', name: '交易员', sortable: true },
  { uid: 'rating', name: '评级', sortable: true },
  { uid: 'coin', name: '币种', sortable: true },
  { uid: 'direction', name: '方向', sortable: true },
  { uid: 'open_time', name: '开仓时间', sortable: true },
  { uid: 'close_time', name: '平仓时间', sortable: true },
  { uid: 'max_size', name: '最大仓位', sortable: true },
  { uid: 'avg_entry_price', name: '开仓均价', sortable: true },
  { uid: 'avg_close_price', name: '平仓均价', sortable: true },
  { uid: 'position_value', name: '仓位价值', sortable: true },
  { uid: 'holding_hours', name: '持仓时长', sortable: true },
  { uid: 'realized_pnl', name: '盈亏', sortable: true },
  { uid: 'status', name: '状态', sortable: true },
];

export const INITIAL_VISIBLE_COLUMNS: PositionHistoryColumnKey[] = [
  'trader', 'rating', 'coin', 'direction', 'open_time', 'close_time', 'max_size', 'avg_entry_price', 'avg_close_price', 'position_value', 'holding_hours', 'realized_pnl', 'status'
];

interface PositionFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  directionFilter: string;
  onDirectionFilterChange: (value: string) => void;
  coinFilter: string;
  onCoinFilterChange: (value: string) => void;
  pnlFilter: string;
  onPnlFilterChange: (value: string) => void;
  // 评级筛选
  scoreFilter: string;
  onScoreFilterChange: (value: string) => void;
  // 收藏筛选
  starFilter: string;
  onStarFilterChange: (value: string) => void;
  // 开仓时间筛选
  openTimeFilter: string;
  onOpenTimeFilterChange: (value: string) => void;
  openTimeDateRange: RangeValue<DateValue> | null;
  onOpenTimeDateRangeChange: (range: RangeValue<DateValue> | null) => void;
  byCoin: PositionHistoryByCoin[];
  onReset: () => void;
  // 排序相关
  sortDescriptor: SortDescriptor;
  onSortChange: (descriptor: SortDescriptor) => void;
  // 列可见性相关
  visibleColumns: Selection;
  onVisibleColumnsChange: (columns: Selection) => void;
}

export function PositionFilters({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  directionFilter,
  onDirectionFilterChange,
  coinFilter,
  onCoinFilterChange,
  pnlFilter,
  onPnlFilterChange,
  scoreFilter,
  onScoreFilterChange,
  starFilter,
  onStarFilterChange,
  openTimeFilter,
  onOpenTimeFilterChange,
  openTimeDateRange,
  onOpenTimeDateRangeChange,
  byCoin,
  onReset,
  sortDescriptor,
  onSortChange,
  visibleColumns,
  onVisibleColumnsChange,
}: PositionFiltersProps) {
  // 检查是否有活跃筛选
  const hasActiveFilters = search || statusFilter || directionFilter || 
    coinFilter || pnlFilter || scoreFilter || 
    starFilter || openTimeFilter;

  return (
    <div className="flex flex-col gap-4 mb-6">
      {/* 筛选区域 */}
      <div className="bg-content1 rounded-xl shadow-small overflow-hidden">
        {/* 主筛选行 */}
        <div className="p-4">
          <div className="flex flex-wrap gap-x-6 gap-y-4 items-end">
            {/* 搜索框 */}
            <Input
              isClearable
              size="sm"
              className="w-[200px]"
              placeholder="交易员地址..."
              startContent={<Icon icon="solar:magnifer-linear" className="text-default-400" width={16} />}
              value={search}
              onValueChange={onSearchChange}
              onClear={() => onSearchChange("")}
            />

            {/* 分隔线 */}
            <div className="h-8 w-px bg-divider hidden sm:block" />

            {/* 状态/方向筛选组 */}
            <div className="flex flex-wrap items-end gap-3">
              <Select
                className="w-[110px]"
                size="sm"
                placeholder="状态"
                aria-label="状态筛选"
                selectedKeys={statusFilter ? [statusFilter] : []}
                onSelectionChange={(keys) => onStatusFilterChange(Array.from(keys)[0] as string || "")}
              >
                <SelectItem key="" textValue="全部">全部</SelectItem>
                <SelectItem key="closed" textValue="已平仓">
                  <span className="text-default-600">已平仓</span>
                </SelectItem>
                <SelectItem key="open" textValue="持仓中">
                  <span className="text-primary">持仓中</span>
                </SelectItem>
              </Select>

              <Select
                className="w-[100px]"
                size="sm"
                placeholder="方向"
                aria-label="方向筛选"
                selectedKeys={directionFilter ? [directionFilter] : []}
                onSelectionChange={(keys) => onDirectionFilterChange(Array.from(keys)[0] as string || "")}
              >
                <SelectItem key="" textValue="全部">全部</SelectItem>
                <SelectItem key="long" textValue="多头">
                  <span className="text-success">多头</span>
                </SelectItem>
                <SelectItem key="short" textValue="空头">
                  <span className="text-danger">空头</span>
                </SelectItem>
              </Select>

              <Select
                className="w-[110px]"
                size="sm"
                placeholder="盈亏"
                aria-label="盈亏筛选"
                selectedKeys={pnlFilter ? [pnlFilter] : []}
                onSelectionChange={(keys) => onPnlFilterChange(Array.from(keys)[0] as string || "")}
              >
                <SelectItem key="" textValue="全部">全部</SelectItem>
                <SelectItem key="profit" textValue="盈利">
                  <span className="text-success">盈利 📈</span>
                </SelectItem>
                <SelectItem key="loss" textValue="亏损">
                  <span className="text-danger">亏损 📉</span>
                </SelectItem>
              </Select>
            </div>

            {/* 分隔线 */}
            <div className="h-8 w-px bg-divider hidden sm:block" />

            {/* 评级/收藏筛选组 */}
            <div className="flex flex-wrap items-end gap-3">
              <Select
                className="w-[90px]"
                size="sm"
                placeholder="评级"
                aria-label="评级筛选"
                selectedKeys={scoreFilter ? [scoreFilter] : []}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  onScoreFilterChange(selected || '');
                }}
              >
                <SelectItem key="" textValue="全部">全部</SelectItem>
                <SelectItem key="S" textValue="S"><span className="font-semibold text-warning">S</span></SelectItem>
                <SelectItem key="A" textValue="A"><span className="font-semibold text-success">A</span></SelectItem>
                <SelectItem key="B" textValue="B"><span className="font-semibold text-primary">B</span></SelectItem>
                <SelectItem key="C" textValue="C"><span className="font-semibold text-default-600">C</span></SelectItem>
                <SelectItem key="D" textValue="D"><span className="font-semibold text-default-400">D</span></SelectItem>
                <SelectItem key="F" textValue="F"><span className="font-semibold text-danger">F</span></SelectItem>
              </Select>

              <Select
                className="w-[110px]"
                size="sm"
                placeholder="收藏"
                aria-label="收藏筛选"
                selectedKeys={starFilter ? [starFilter] : []}
                onSelectionChange={(keys) => onStarFilterChange(Array.from(keys)[0] as string || "")}
              >
                <SelectItem key="" textValue="全部">全部</SelectItem>
                <SelectItem key="starred" textValue="已收藏">已收藏 ⭐</SelectItem>
                <SelectItem key="unstarred" textValue="未收藏">未收藏</SelectItem>
              </Select>
            </div>

            {/* 分隔线 */}
            <div className="h-8 w-px bg-divider hidden sm:block" />

            {/* 币种/时间筛选组 */}
            <div className="flex flex-wrap items-end gap-3">
              <Autocomplete
                className="w-[140px]"
                size="sm"
                placeholder="币种"
                aria-label="币种筛选"
                selectedKey={coinFilter || null}
                onSelectionChange={(key) => onCoinFilterChange((key as string) || '')}
                allowsCustomValue={false}
                defaultItems={[
                  { key: '', label: '全部' },
                  ...byCoin.map((c) => ({
                    key: c.coin,
                    label: c.coin,
                  })),
                ]}
              >
                {(item) => (
                  <AutocompleteItem key={item.key} textValue={item.label}>
                    {item.label}
                  </AutocompleteItem>
                )}
              </Autocomplete>

              <TimeRangeFilter
                placeholder="开仓时间"
                value={openTimeFilter}
                dateRange={openTimeDateRange}
                onValueChange={onOpenTimeFilterChange}
                onDateRangeChange={onOpenTimeDateRangeChange}
                selectClassName="w-[120px]"
              />
            </div>
          </div>
        </div>

        {/* 操作栏 */}
        <div className="px-4 py-3 bg-default-50 border-t border-divider flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {hasActiveFilters && (
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
                items={positionHistoryColumns.filter((c) => c.sortable)}
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
                items={positionHistoryColumns}
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
  );
}
