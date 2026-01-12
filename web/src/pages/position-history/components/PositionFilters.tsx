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
  // 获取所有币种选项
  const coinOptions = ['all', ...byCoin.map(c => c.coin)];

  return (
    <div className="bg-content1/50 backdrop-blur-md rounded-xl mb-6">
      <div className="flex items-center justify-between gap-4">
        {/* 左侧：筛选条件 */}
        <div className="flex flex-wrap items-center gap-4 flex-1">
          {/* 搜索 */}
          <Input
            isClearable
            className="w-64"
            placeholder="搜索交易员地址..."
            startContent={<Icon icon="solar:magnifer-linear" className="text-default-400" />}
            value={search}
            onValueChange={onSearchChange}
            onClear={() => onSearchChange("")}
          />

          {/* 状态筛选 */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">状态</span>
            <Select
              className="min-w-[100px]"
              aria-label="状态筛选"
              selectedKeys={[statusFilter]}
              onSelectionChange={(keys) => onStatusFilterChange(Array.from(keys)[0] as string)}
            >
              <SelectItem key="all" textValue="全部">全部</SelectItem>
              <SelectItem key="closed" textValue="已平仓">已平仓</SelectItem>
              <SelectItem key="open" textValue="持仓中">持仓中</SelectItem>
            </Select>
          </div>

          {/* 方向筛选 */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">方向</span>
            <Select
              className="min-w-[100px]"
              aria-label="方向筛选"
              selectedKeys={[directionFilter]}
              onSelectionChange={(keys) => onDirectionFilterChange(Array.from(keys)[0] as string)}
            >
              <SelectItem key="all" textValue="全部">全部</SelectItem>
              <SelectItem key="long" textValue="多头">多头</SelectItem>
              <SelectItem key="short" textValue="空头">空头</SelectItem>
            </Select>
          </div>

          {/* 币种筛选 */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">币种</span>
            <Autocomplete
              className="min-w-[160px]"
              aria-label="币种筛选"
              selectedKey={coinFilter}
              onSelectionChange={(key) => onCoinFilterChange((key as string) || 'all')}
              allowsCustomValue={false}
              defaultItems={coinOptions.map((coin) => ({
                key: coin,
                label: coin === 'all' ? '全部' : coin,
              }))}
            >
              {(item) => (
                <AutocompleteItem key={item.key} textValue={item.label}>
                  {item.label}
                </AutocompleteItem>
              )}
            </Autocomplete>
          </div>

          {/* 盈亏筛选 */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">盈亏</span>
            <Select
              className="min-w-[100px]"
              aria-label="盈亏筛选"
              selectedKeys={[pnlFilter]}
              onSelectionChange={(keys) => onPnlFilterChange(Array.from(keys)[0] as string)}
            >
              <SelectItem key="all" textValue="全部">全部</SelectItem>
              <SelectItem key="profit" textValue="盈利">盈利</SelectItem>
              <SelectItem key="loss" textValue="亏损">亏损</SelectItem>
            </Select>
          </div>

          {/* 开仓时间筛选 */}
          <TimeRangeFilter
            label="开仓时间"
            value={openTimeFilter}
            dateRange={openTimeDateRange}
            onValueChange={onOpenTimeFilterChange}
            onDateRangeChange={onOpenTimeDateRangeChange}
          />

          {/* 重置按钮 */}
          <Button
            variant="flat"
            color="default"
            startContent={<Icon icon="solar:restart-bold" width={16} />}
            onPress={onReset}
          >
            重置
          </Button>
        </div>

        {/* 右侧：排序和列 */}
        <div className="flex items-center gap-2 shrink-0">
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
  );
}
