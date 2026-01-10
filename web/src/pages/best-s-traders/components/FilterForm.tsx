import { Button } from '@heroui/button';
import { Input } from '@heroui/input';
import { Select, SelectItem } from '@heroui/select';
import { RangeFilter } from '@/components/filters/RangeFilter';
import type { BestSTraderParams } from '@/services/api';

interface FilterFormProps {
  params: BestSTraderParams;
  onChange: (params: BestSTraderParams) => void;
  onSearch: () => void;
  onReset: () => void;
  isLoading?: boolean;
}

const sortOptions = [
  { key: 'recent_pnl', label: '近期盈亏' },
  { key: 'position_win_rate', label: '仓位胜率' },
  { key: 'overall_score', label: '综合评分' },
  { key: 'sharpe_ratio', label: '夏普比率' },
  { key: 'position_profit_factor', label: '仓位盈亏比' },
  { key: 'total_pnl', label: '总盈亏' },
];

export function FilterForm({
  params,
  onChange,
  onSearch,
  onReset,
  isLoading,
}: FilterFormProps) {
  const handleChange = (key: keyof BestSTraderParams, value: any) => {
    onChange({ ...params, [key]: value });
  };

  return (
    <div className="flex flex-col gap-4">
      {/* 常用筛选 */}
      <div className="flex flex-wrap items-end gap-4">
        <Select
          selectedKeys={params.sort_by ? [params.sort_by] : ['recent_pnl']}
          onSelectionChange={(keys) => handleChange('sort_by', Array.from(keys)[0])}
          className="w-36"
        >
          {sortOptions.map((opt) => (
            <SelectItem key={opt.key}>{opt.label}</SelectItem>
          ))}
        </Select>

        <Input
          type="number"
          value={params.limit?.toString() || '20'}
          onChange={(e) => handleChange('limit', parseInt(e.target.value) || 20)}
          className="w-24"
        />

        <Select
          selectedKeys={[params.require_recent_profit !== false ? 'true' : 'false']}
          onSelectionChange={(keys) => handleChange('require_recent_profit', Array.from(keys)[0] === 'true')}
          className="w-36"
        >
          <SelectItem key="true">要求近期盈利</SelectItem>
          <SelectItem key="false">不限近期盈利</SelectItem>
        </Select>

        <Button color="primary" onPress={onSearch} isLoading={isLoading}>
          筛选
        </Button>
        <Button variant="flat" onPress={onReset}>
          重置
        </Button>
      </div>

      {/* 高级筛选 */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {/* 夏普比率 (只有最小值) */}
        <RangeFilter
          label="夏普比率"
          minValue={params.min_sharpe}
          onMinChange={(v) => handleChange('min_sharpe', v)}
          onMaxChange={() => {}}
          minPlaceholder="最小"
          maxPlaceholder="-"
        />

        {/* 回撤 (只有最大值) */}
        <RangeFilter
          label="回撤 (%)"
          maxValue={params.max_drawdown ? params.max_drawdown * 100 : undefined}
          onMinChange={() => {}}
          onMaxChange={(v) => handleChange('max_drawdown', v ? v / 100 : undefined)}
          minPlaceholder="-"
          maxPlaceholder="最大"
        />

        {/* 盈亏比 (只有最小值) */}
        <RangeFilter
          label="盈亏比"
          minValue={params.min_profit_factor}
          onMinChange={(v) => handleChange('min_profit_factor', v)}
          onMaxChange={() => {}}
          minPlaceholder="最小"
          maxPlaceholder="-"
        />

        {/* 仓位胜率 (只有最小值) */}
        <RangeFilter
          label="仓位胜率 (%)"
          minValue={params.min_position_win_rate ? params.min_position_win_rate * 100 : undefined}
          onMinChange={(v) => handleChange('min_position_win_rate', v ? v / 100 : undefined)}
          onMaxChange={() => {}}
          minPlaceholder="最小"
          maxPlaceholder="-"
          endContent={<span className="text-xs text-default-400">%</span>}
        />

        {/* 仓位盈亏比 (只有最小值) */}
        <RangeFilter
          label="仓位盈亏比"
          minValue={params.min_position_pf}
          onMinChange={(v) => handleChange('min_position_pf', v)}
          onMaxChange={() => {}}
          minPlaceholder="最小"
          maxPlaceholder="-"
        />

        {/* 已平仓位数 (只有最小值) */}
        <RangeFilter
          label="已平仓位数"
          minValue={params.min_positions}
          onMinChange={(v) => handleChange('min_positions', v)}
          onMaxChange={() => {}}
          minPlaceholder="最小"
          maxPlaceholder="-"
          isInteger
        />

        {/* 近期仓位数 (只有最小值) */}
        <RangeFilter
          label="近期仓位数"
          minValue={params.min_recent_positions}
          onMinChange={(v) => handleChange('min_recent_positions', v)}
          onMaxChange={() => {}}
          minPlaceholder="最小"
          maxPlaceholder="-"
          isInteger
        />

        {/* 持仓时长 (有最小和最大) */}
        <RangeFilter
          label="持仓时长 (h)"
          minValue={params.min_holding_hours}
          maxValue={params.max_holding_hours}
          onMinChange={(v) => handleChange('min_holding_hours', v)}
          onMaxChange={(v) => handleChange('max_holding_hours', v)}
        />

        {/* 近期天数 */}
        <div className="flex flex-col gap-1">
          <span className="text-xs text-default-600">近期天数</span>
          <Input
            type="number"
            size="sm"
            placeholder="默认14天"
            value={params.recent_days?.toString() || ''}
            onValueChange={(v) => handleChange('recent_days', v ? parseInt(v) : undefined)}
            endContent={<span className="text-xs text-default-400">天</span>}
          />
        </div>

        {/* 最大不活跃天数 */}
        <div className="flex flex-col gap-1">
          <span className="text-xs text-default-600">最大不活跃</span>
          <Input
            type="number"
            size="sm"
            placeholder="默认30天"
            value={params.max_inactive_days?.toString() || ''}
            onValueChange={(v) => handleChange('max_inactive_days', v ? parseInt(v) : undefined)}
            endContent={<span className="text-xs text-default-400">天</span>}
          />
        </div>
      </div>
    </div>
  );
}
