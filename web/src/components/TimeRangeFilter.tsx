import { useMemo } from 'react';
import type { DateValue, RangeValue } from '@heroui/react';
import { Select, SelectItem } from '@heroui/select';
import { DateRangePicker } from '@heroui/react';

// 时间范围预设选项
const TIME_RANGE_OPTIONS = [
  { key: '', label: '全部时间' },
  { key: '1d', label: '最近1天' },
  { key: '7d', label: '最近7天' },
  { key: '30d', label: '最近30天' },
  { key: '90d', label: '最近90天' },
  { key: 'custom', label: '自定义' },
];

export interface TimeRange {
  startTime?: string;
  endTime?: string;
}

interface TimeRangeFilterProps {
  /** placeholder文本 */
  placeholder?: string;
  /** 当前选中的预设值 */
  value: string;
  /** 自定义日期范围 */
  dateRange: RangeValue<DateValue> | null;
  /** 预设值变化回调 */
  onValueChange: (value: string) => void;
  /** 日期范围变化回调 */
  onDateRangeChange: (range: RangeValue<DateValue> | null) => void;
  /** Select 的最小宽度 */
  selectClassName?: string;
}

/**
 * 时间范围筛选组件
 * 支持预设时间范围（全部、1天、7天、30天、90天）和自定义日期范围
 */
export function TimeRangeFilter({
  placeholder = '时间',
  value,
  dateRange,
  onValueChange,
  onDateRangeChange,
  selectClassName = 'min-w-[120px]',
}: TimeRangeFilterProps) {
  return (
    <>
      <Select
        className={selectClassName}
        aria-label="时间范围筛选"
        size="sm"
        placeholder={placeholder}
        selectedKeys={value ? [value] : []}
        onSelectionChange={(keys) => onValueChange(Array.from(keys)[0] as string || "")}
      >
        {TIME_RANGE_OPTIONS.map((opt) => (
          <SelectItem key={opt.key} textValue={opt.label}>
            {opt.label}
          </SelectItem>
        ))}
      </Select>

      {value === 'custom' && (
        <div className="flex items-center gap-2 shrink-0">
          <DateRangePicker
            className="w-auto"
            aria-label="自定义日期范围"
            size="sm"
            value={dateRange}
            onChange={onDateRangeChange}
            visibleMonths={2}
          />
        </div>
      )}
    </>
  );
}

/**
 * 格式化 DateValue 为 YYYY-MM-DD 字符串
 */
export function formatDateValue(d: DateValue): string {
  return `${d.year}-${String(d.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`;
}

/**
 * 根据时间范围筛选值和日期范围计算实际的时间范围
 * @param timeRangeFilter - 预设值 ('all', '1d', '7d', '30d', '90d', 'custom')
 * @param dateRange - 自定义日期范围（当 timeRangeFilter 为 'custom' 时使用）
 * @returns 包含 startTime 和 endTime 的对象
 */
export function useTimeRange(
  timeRangeFilter: string,
  dateRange: RangeValue<DateValue> | null
): TimeRange {
  return useMemo(() => {
    if (!timeRangeFilter) {
      return { startTime: undefined, endTime: undefined };
    }

    if (timeRangeFilter === 'custom') {
      if (!dateRange) {
        return { startTime: undefined, endTime: undefined };
      }
      return {
        startTime: dateRange.start ? formatDateValue(dateRange.start) : undefined,
        endTime: dateRange.end ? `${formatDateValue(dateRange.end)}T23:59:59` : undefined,
      };
    }

    // 预设时间范围
    const now = new Date();
    const days = parseInt(timeRangeFilter.replace('d', ''));
    const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    return {
      startTime: start.toISOString(),
      endTime: undefined,
    };
  }, [timeRangeFilter, dateRange]);
}

/**
 * 检查时间筛选是否有活跃的筛选条件
 */
export function isTimeFilterActive(
  timeRangeFilter: string,
  dateRange: RangeValue<DateValue> | null
): boolean {
  return !!timeRangeFilter || dateRange !== null;
}

export { TIME_RANGE_OPTIONS };
