import { useState } from 'react';
import type { SortDescriptor } from '@heroui/react';
import { useDisclosure } from '@heroui/react';
import { Input } from '@heroui/input';
import { Button } from '@heroui/button';
import { Select, SelectItem } from '@heroui/select';
import { Chip } from '@heroui/chip';
import { SearchIcon } from '@heroui/shared-icons';
import { Icon } from '@iconify/react';
import { AdvancedFilterDrawer } from './AdvancedFilterDrawer';
import {
  columns,
  RATING_OPTIONS,
  PERIOD_OPTIONS,
  TAG_GROUPS,
  FIELD_LABELS,
} from '../constants';
import type { FilterConfig, AdvancedFilterCondition } from '../types';

interface FilterSectionProps {
  totalCount: number;
  searchAddress: string;
  onSearchChange: (value?: string) => void;
  selectedRating: string;
  onRatingChange: (rating: string) => void;
  sortDescriptor: SortDescriptor;
  onSortChange: (descriptor: SortDescriptor) => void;
  filters: FilterConfig;
  onFiltersChange: (filters: FilterConfig) => void;
  onSearch: () => void;
  onReset: () => void;
  onAddTrader: () => void;
}

export function FilterSection({
  totalCount,
  searchAddress,
  onSearchChange,
  selectedRating,
  onRatingChange,
  sortDescriptor,
  onSortChange,
  filters,
  onFiltersChange,
  onSearch,
  onReset,
  onAddTrader,
}: FilterSectionProps) {
  const { isOpen, onOpen, onOpenChange } = useDisclosure();
  const [draftConditions, setDraftConditions] = useState<AdvancedFilterCondition[]>([]);

  // === Drawer ===
  const handleOpenDrawer = () => {
    setDraftConditions(
      filters.advancedFilters?.length
        ? filters.advancedFilters.map(c => ({ ...c }))
        : [{ field: '', op: '>', value: undefined }]
    );
    onOpen();
  };

  const handleApplyDrawerFilters = (conditions: AdvancedFilterCondition[]) => {
    const valid = conditions.filter(
      c => c.field && c.op && (c.op === 'exist' || c.value !== undefined)
    );
    onFiltersChange({ ...filters, advancedFilters: valid.length ? valid : undefined });
  };

  const handleRemoveCondition = (index: number) => {
    const next = [...(filters.advancedFilters || [])];
    next.splice(index, 1);
    onFiltersChange({ ...filters, advancedFilters: next.length ? next : undefined });
  };

  // === Period ===
  const handlePeriodChange = (key: string) => {
    const next = filters.period === key ? undefined : (key as FilterConfig['period']);
    onFiltersChange({ ...filters, period: next });
  };

  // === Tags ===
  const handleTagToggle = (filterKey: string, tagKey: string) => {
    const current = (filters as Record<string, unknown>)[filterKey];
    onFiltersChange({
      ...filters,
      [filterKey]: current === tagKey ? undefined : tagKey,
    });
  };

  // === Helpers ===
  const advancedCount = filters.advancedFilters?.length ?? 0;
  const hasActiveFilters = advancedCount > 0;
  const hasActiveTags =
    filters.tagAccountValue ||
    filters.tagTradingRhythm ||
    filters.tagProfitStatus ||
    filters.tagDirectionPreference ||
    filters.tagTradingStyle;
  const showChipsBar = hasActiveFilters || !!hasActiveTags || !!selectedRating;

  return (
    <div className="flex flex-col gap-3">
      {/* ====== Row 1: Top bar ====== */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        {/* Left: count + search */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-default-500 whitespace-nowrap">
            已收录{' '}
            <span className="text-primary font-semibold">{totalCount.toLocaleString()}</span>{' '}
            个地址
          </span>
          <Input
            className="w-[200px]"
            placeholder="搜索地址或昵称..."
            size="sm"
            startContent={<SearchIcon className="text-default-400" width={14} />}
            value={searchAddress}
            onValueChange={onSearchChange}
            isClearable
            onClear={() => onSearchChange('')}
          />
        </div>

        {/* Right: controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Sort field */}
          <Select
            className="w-[120px]"
            aria-label="排序"
            placeholder="排序"
            size="sm"
            variant="flat"
            startContent={<Icon icon="solar:sort-linear" width={14} className="text-default-400" />}
            selectedKeys={sortDescriptor.column ? [sortDescriptor.column as string] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              if (selected) {
                onSortChange({ column: selected, direction: sortDescriptor.direction });
              }
            }}
          >
            {columns.filter(c => c.sortable).map(col => (
              <SelectItem key={col.uid} textValue={col.name}>{col.name}</SelectItem>
            ))}
          </Select>

          {/* Asc / Desc */}
          <Button
            size="sm"
            variant="flat"
            className="min-w-0 px-2"
            onPress={() =>
              onSortChange({
                column: sortDescriptor.column,
                direction:
                  sortDescriptor.direction === 'descending' ? 'ascending' : 'descending',
              })
            }
          >
            <Icon
              icon={
                sortDescriptor.direction === 'descending'
                  ? 'solar:sort-from-top-to-bottom-linear'
                  : 'solar:sort-from-bottom-to-top-linear'
              }
              width={16}
            />
            <span className="text-xs ml-1">
              {sortDescriptor.direction === 'descending' ? '降序' : '升序'}
            </span>
          </Button>

          {/* Period */}
          <div className="flex items-center bg-default-100 rounded-lg p-0.5">
            <Icon icon="solar:clock-circle-linear" width={14} className="text-default-400 ml-1.5 mr-0.5" />
            {PERIOD_OPTIONS.map(p => (
              <Button
                key={p.key}
                size="sm"
                variant={filters.period === p.key ? 'solid' : 'light'}
                color={filters.period === p.key ? 'primary' : 'default'}
                className="min-w-0 px-2.5 h-7 text-xs"
                onPress={() => handlePeriodChange(p.key)}
              >
                {p.label}
              </Button>
            ))}
          </div>

          {/* Rating */}
          <Select
            className="w-[90px]"
            aria-label="评级"
            placeholder="评级"
            size="sm"
            variant="flat"
            selectedKeys={selectedRating ? [selectedRating] : []}
            onSelectionChange={(keys) => {
              const selected = Array.from(keys)[0] as string;
              onRatingChange(selected || '');
            }}
          >
            {RATING_OPTIONS.map(r => (
              <SelectItem key={r} textValue={r}>{r}</SelectItem>
            ))}
          </Select>

          {/* Advanced filter */}
          <Button
            size="sm"
            variant={hasActiveFilters ? 'flat' : 'light'}
            color={hasActiveFilters ? 'primary' : 'default'}
            startContent={<Icon icon="solar:filter-linear" width={16} />}
            onPress={handleOpenDrawer}
          >
            高级筛选{hasActiveFilters ? ` (${advancedCount})` : ''}
          </Button>

          {/* Add trader */}
          <Button
            size="sm"
            color="primary"
            startContent={<Icon icon="solar:add-circle-linear" width={16} />}
            onPress={onAddTrader}
          >
            新增
          </Button>
        </div>
      </div>

      {/* ====== Row 2: Tag filters ====== */}
      <div className="flex flex-col gap-1.5 px-1">
        {TAG_GROUPS.map(group => {
          const currentValue = (filters as Record<string, unknown>)[group.filterKey] as
            | string
            | undefined;
          return (
            <div key={group.key} className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-default-400 w-[72px] shrink-0 text-right">
                {group.label}
              </span>
              {group.options.map(tag => (
                <Button
                  key={tag.key}
                  size="sm"
                  variant={currentValue === tag.key ? 'flat' : 'light'}
                  color={currentValue === tag.key ? 'primary' : 'default'}
                  className="min-w-0 px-2 h-6 text-xs"
                  onPress={() => handleTagToggle(group.filterKey, tag.key)}
                >
                  {tag.label}
                </Button>
              ))}
            </div>
          );
        })}
      </div>

      {/* ====== Row 3: Active filter chips ====== */}
      {showChipsBar && (
        <div className="flex items-center gap-2 flex-wrap px-1">
          {/* Rating chip */}
          {selectedRating && (
            <Chip
              size="sm"
              variant="flat"
              color="secondary"
              onClose={() => onRatingChange('')}
            >
              评级 = {selectedRating}
            </Chip>
          )}

          {/* Period chip */}
          {filters.period && (
            <Chip
              size="sm"
              variant="flat"
              color="warning"
              onClose={() => onFiltersChange({ ...filters, period: undefined })}
            >
              周期: {PERIOD_OPTIONS.find(p => p.key === filters.period)?.label}
            </Chip>
          )}

          {/* Tag chips */}
          {TAG_GROUPS.map(group => {
            const val = (filters as Record<string, unknown>)[group.filterKey] as
              | string
              | undefined;
            if (!val) return null;
            const label = group.options.find(o => o.key === val)?.label ?? val;
            return (
              <Chip
                key={group.key}
                size="sm"
                variant="flat"
                color="default"
                onClose={() => onFiltersChange({ ...filters, [group.filterKey]: undefined })}
              >
                {group.label}: {label}
              </Chip>
            );
          })}

          {/* Advanced filter chips */}
          {filters.advancedFilters?.map((condition, index) => (
            <Chip
              key={`adv-${index}`}
              size="sm"
              variant="flat"
              color="primary"
              onClose={() => handleRemoveCondition(index)}
            >
              {FIELD_LABELS[condition.field] || condition.field}{' '}
              {condition.op === 'exist' ? '存在' : `${condition.op} ${condition.value}`}
            </Chip>
          ))}

          {/* Spacer + actions */}
          <div className="flex-1" />

          <Button
            size="sm"
            variant="light"
            color="danger"
            className="text-xs"
            startContent={<Icon icon="solar:trash-bin-trash-linear" width={14} />}
            onPress={onReset}
          >
            清除
          </Button>

          <Button
            size="sm"
            variant="flat"
            color="primary"
            className="text-xs"
            startContent={<Icon icon="solar:filter-bold" width={14} />}
            onPress={onSearch}
          >
            筛选
          </Button>
        </div>
      )}

      {/* ====== Advanced Filter Drawer ====== */}
      <AdvancedFilterDrawer
        isOpen={isOpen}
        onOpenChange={onOpenChange}
        conditions={draftConditions}
        onConditionsChange={setDraftConditions}
        onApply={handleApplyDrawerFilters}
      />
    </div>
  );
}
