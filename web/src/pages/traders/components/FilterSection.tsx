import type { Selection, SortDescriptor } from '@heroui/react';
import { Input } from '@heroui/input';
import { Button } from '@heroui/button';
import { Select, SelectItem } from '@heroui/select';
import { Form } from '@heroui/form';
import { SearchIcon } from '@heroui/shared-icons';
import { Icon } from '@iconify/react';
import { RangeFilter } from './RangeFilter';
import { columns, RATING_OPTIONS, TAG_OPTIONS } from '../constants';
import type { FilterConfig } from '../types';

interface FilterSectionProps {
  searchAddress: string;
  onSearchChange: (value?: string) => void;
  selectedRating: string;
  onRatingChange: (rating: string) => void;
  sortDescriptor: SortDescriptor;
  onSortChange: (descriptor: SortDescriptor) => void;
  visibleColumns: Selection;
  onVisibleColumnsChange: (columns: Selection) => void;
  filters: FilterConfig;
  onFiltersChange: (filters: FilterConfig) => void;
  onSearch: () => void;
  onReset: () => void;
  onAddTrader: () => void;
}

export function FilterSection({
  searchAddress,
  onSearchChange,
  selectedRating,
  onRatingChange,
  sortDescriptor,
  onSortChange,
  visibleColumns,
  onVisibleColumnsChange,
  filters,
  onFiltersChange,
  onSearch,
  onReset,
  onAddTrader,
}: FilterSectionProps) {
  return (
    <div className="flex flex-col gap-4">
      <Form className="flex flex-col gap-4">
        {/* 第一行：地址搜索 + 评级 + 排序 + 列选择 */}
        <div className="flex flex-wrap items-end gap-3">
          <Input
            className="w-[260px]"
            endContent={<SearchIcon className="text-default-400" width={16} />}
            label="搜索"
            labelPlacement="outside"
            placeholder="搜索昵称或地址..."
            size="sm"
            value={searchAddress}
            onValueChange={onSearchChange}
            isClearable
            onClear={() => onSearchChange('')}
          />

          <Select
            className="w-[120px]"
            label="评级"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={selectedRating ? [selectedRating] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onRatingChange(selected || '');
            }}
          >
            {RATING_OPTIONS.map((rating) => (
              <SelectItem key={rating} textValue={rating}>{rating}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[140px]"
            label="排序"
            labelPlacement="outside"
            placeholder="选择排序"
            size="sm"
            selectedKeys={sortDescriptor.column ? [sortDescriptor.column as string] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              if (selected) {
                onSortChange({
                  column: selected,
                  direction: sortDescriptor.column === selected && sortDescriptor.direction === 'descending'
                    ? 'ascending'
                    : 'descending',
                });
              }
            }}
          >
            {columns.filter((c) => c.sortable).map((col) => (
              <SelectItem key={col.uid} textValue={col.name}>{col.name}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[160px]"
            label="显示列"
            labelPlacement="outside"
            placeholder="选择列"
            size="sm"
            selectionMode="multiple"
            selectedKeys={visibleColumns}
            onSelectionChange={onVisibleColumnsChange}
          >
            {columns.map((col) => (
              <SelectItem key={col.uid} textValue={col.name}>{col.name}</SelectItem>
            ))}
          </Select>
        </div>

        {/* 第二行：数值筛选条件（区间查询） */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <RangeFilter
            label="胜率"
            minValue={filters.minWinRate}
            maxValue={filters.maxWinRate}
            onMinChange={(v) => onFiltersChange({ ...filters, minWinRate: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxWinRate: v })}
            endContent={<span className="text-xs text-default-400">%</span>}
          />

          <RangeFilter
            label="盈亏比"
            minValue={filters.minProfitFactor}
            maxValue={filters.maxProfitFactor}
            onMinChange={(v) => onFiltersChange({ ...filters, minProfitFactor: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxProfitFactor: v })}
          />

          <RangeFilter
            label="总盈亏 ($)"
            minValue={filters.minPnl}
            maxValue={filters.maxPnl}
            onMinChange={(v) => onFiltersChange({ ...filters, minPnl: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxPnl: v })}
          />

          <RangeFilter
            label="回撤"
            minValue={filters.minDrawdown}
            maxValue={filters.maxDrawdown}
            onMinChange={(v) => onFiltersChange({ ...filters, minDrawdown: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxDrawdown: v })}
            endContent={<span className="text-xs text-default-400">%</span>}
          />

          <RangeFilter
            label="Sharpe"
            minValue={filters.minSharpe}
            maxValue={filters.maxSharpe}
            onMinChange={(v) => onFiltersChange({ ...filters, minSharpe: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxSharpe: v })}
          />

          <RangeFilter
            label="Sortino"
            minValue={filters.minSortino}
            maxValue={filters.maxSortino}
            onMinChange={(v) => onFiltersChange({ ...filters, minSortino: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxSortino: v })}
          />

          <RangeFilter
            label="Calmar"
            minValue={filters.minCalmar}
            maxValue={filters.maxCalmar}
            onMinChange={(v) => onFiltersChange({ ...filters, minCalmar: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxCalmar: v })}
          />

          <RangeFilter
            label="交易数"
            minValue={filters.minTrades}
            maxValue={filters.maxTrades}
            onMinChange={(v) => onFiltersChange({ ...filters, minTrades: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxTrades: v })}
            isInteger
          />

          <RangeFilter
            label="活跃天数"
            minValue={filters.minActiveDays}
            maxValue={filters.maxActiveDays}
            onMinChange={(v) => onFiltersChange({ ...filters, minActiveDays: v })}
            onMaxChange={(v) => onFiltersChange({ ...filters, maxActiveDays: v })}
            isInteger
          />

          {/* 最近活跃 */}
          <div className="flex flex-col gap-1">
            <span className="text-xs text-default-600">最近活跃</span>
            <div className="flex items-center gap-1">
              <Input
                type="number"
                size="sm"
                placeholder="N天内"
                value={filters.hasRecentTrade?.toString() || ''}
                onValueChange={(v) => onFiltersChange({ ...filters, hasRecentTrade: v ? parseInt(v) : undefined })}
                endContent={<span className="text-xs text-default-400">天</span>}
              />
            </div>
          </div>
        </div>

        {/* 第三行：标签筛选 */}
        <div className="flex flex-wrap gap-3">
          <Select
            className="w-[140px]"
            label="资金规模"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={filters.tagCapitalScale ? [filters.tagCapitalScale] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onFiltersChange({ ...filters, tagCapitalScale: selected || undefined });
            }}
          >
            {TAG_OPTIONS.capitalScale.map((tag) => (
              <SelectItem key={tag.key} textValue={tag.label}>{tag.label}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[140px]"
            label="交易方向"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={filters.tagTradingDirection ? [filters.tagTradingDirection] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onFiltersChange({ ...filters, tagTradingDirection: selected || undefined });
            }}
          >
            {TAG_OPTIONS.tradingDirection.map((tag) => (
              <SelectItem key={tag.key} textValue={tag.label}>{tag.label}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[140px]"
            label="交易周期"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={filters.tagTradingCycle ? [filters.tagTradingCycle] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onFiltersChange({ ...filters, tagTradingCycle: selected || undefined });
            }}
          >
            {TAG_OPTIONS.tradingCycle.map((tag) => (
              <SelectItem key={tag.key} textValue={tag.label}>{tag.label}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[140px]"
            label="频率风格"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={filters.tagFrequencyStyle ? [filters.tagFrequencyStyle] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onFiltersChange({ ...filters, tagFrequencyStyle: selected || undefined });
            }}
          >
            {TAG_OPTIONS.frequencyStyle.map((tag) => (
              <SelectItem key={tag.key} textValue={tag.label}>{tag.label}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[160px]"
            label="收益风险"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={filters.tagReturnRisk ? [filters.tagReturnRisk] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onFiltersChange({ ...filters, tagReturnRisk: selected || undefined });
            }}
          >
            {TAG_OPTIONS.returnRisk.map((tag) => (
              <SelectItem key={tag.key} textValue={tag.label}>{tag.label}</SelectItem>
            ))}
          </Select>

          <Select
            className="w-[140px]"
            label="策略能力"
            labelPlacement="outside"
            placeholder="全部"
            size="sm"
            selectedKeys={filters.tagStrategyCapability ? [filters.tagStrategyCapability] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onFiltersChange({ ...filters, tagStrategyCapability: selected || undefined });
            }}
          >
            {TAG_OPTIONS.strategyCapability.map((tag) => (
              <SelectItem key={tag.key} textValue={tag.label}>{tag.label}</SelectItem>
            ))}
          </Select>
        </div>

        {/* 第四行：搜索、重置、新增按钮 */}
        <div className="flex gap-2">
          <Button
            color="primary"
            size="sm"
            startContent={<SearchIcon width={16} />}
            onPress={onSearch}
          >
            搜索
          </Button>
          <Button
            variant="flat"
            size="sm"
            startContent={<Icon icon="solar:restart-linear" width={16} />}
            onPress={onReset}
          >
            重置
          </Button>
          <Button
            color="success"
            size="sm"
            startContent={<Icon icon="solar:add-circle-linear" width={16} />}
            onPress={onAddTrader}
          >
            新增
          </Button>
        </div>
      </Form>
    </div>
  );
}
