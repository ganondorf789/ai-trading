import { useState } from 'react';
import { Button } from '@heroui/button';
import { Input } from '@heroui/input';
import { Select, SelectItem } from '@heroui/select';
import { Switch } from '@heroui/switch';
import { Accordion, AccordionItem } from '@heroui/accordion';
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
          label="排序方式"
          selectedKeys={params.sort_by ? [params.sort_by] : ['recent_pnl']}
          onSelectionChange={(keys) => handleChange('sort_by', Array.from(keys)[0])}
          className="w-36"
          size="sm"
        >
          {sortOptions.map((opt) => (
            <SelectItem key={opt.key}>{opt.label}</SelectItem>
          ))}
        </Select>

        <Input
          type="number"
          label="返回数量"
          value={params.limit?.toString() || '20'}
          onChange={(e) => handleChange('limit', parseInt(e.target.value) || 20)}
          className="w-24"
          size="sm"
        />

        <div className="flex items-center gap-2">
          <Switch
            isSelected={params.require_recent_profit !== false}
            onValueChange={(checked) => handleChange('require_recent_profit', checked)}
            size="sm"
          />
          <span className="text-sm">要求近期盈利</span>
        </div>

        <Button color="primary" onPress={onSearch} isLoading={isLoading} size="sm">
          筛选
        </Button>
        <Button variant="flat" onPress={onReset} size="sm">
          重置
        </Button>
      </div>

      {/* 高级筛选 */}
      <Accordion variant="bordered" className="px-0">
        <AccordionItem key="advanced" title="高级筛选" className="text-sm">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 pb-4">
            {/* 基础指标 */}
            <Input
              type="number"
              label="最小夏普比率"
              value={params.min_sharpe?.toString() || ''}
              onChange={(e) => handleChange('min_sharpe', parseFloat(e.target.value) || undefined)}
              size="sm"
              step="0.1"
            />
            <Input
              type="number"
              label="最大回撤 (%)"
              value={params.max_drawdown ? (params.max_drawdown * 100).toString() : ''}
              onChange={(e) => handleChange('max_drawdown', (parseFloat(e.target.value) || 0) / 100)}
              size="sm"
              step="1"
            />
            <Input
              type="number"
              label="最小盈亏比"
              value={params.min_profit_factor?.toString() || ''}
              onChange={(e) => handleChange('min_profit_factor', parseFloat(e.target.value) || undefined)}
              size="sm"
              step="0.1"
            />

            {/* 仓位指标 */}
            <Input
              type="number"
              label="最小已平仓位数"
              value={params.min_positions?.toString() || ''}
              onChange={(e) => handleChange('min_positions', parseInt(e.target.value) || undefined)}
              size="sm"
            />
            <Input
              type="number"
              label="仓位胜率 (%)"
              value={params.min_position_win_rate ? (params.min_position_win_rate * 100).toString() : ''}
              onChange={(e) => handleChange('min_position_win_rate', (parseFloat(e.target.value) || 0) / 100)}
              size="sm"
              step="1"
            />
            <Input
              type="number"
              label="仓位盈亏比"
              value={params.min_position_pf?.toString() || ''}
              onChange={(e) => handleChange('min_position_pf', parseFloat(e.target.value) || undefined)}
              size="sm"
              step="0.1"
            />

            {/* 近期表现 */}
            <Input
              type="number"
              label="近期天数"
              value={params.recent_days?.toString() || ''}
              onChange={(e) => handleChange('recent_days', parseInt(e.target.value) || undefined)}
              size="sm"
            />
            <Input
              type="number"
              label="近期最小仓位数"
              value={params.min_recent_positions?.toString() || ''}
              onChange={(e) => handleChange('min_recent_positions', parseInt(e.target.value) || undefined)}
              size="sm"
            />
            <Input
              type="number"
              label="最大不活跃天数"
              value={params.max_inactive_days?.toString() || ''}
              onChange={(e) => handleChange('max_inactive_days', parseInt(e.target.value) || undefined)}
              size="sm"
            />

            {/* 持仓风格 */}
            <Input
              type="number"
              label="最小持仓时长(h)"
              value={params.min_holding_hours?.toString() || ''}
              onChange={(e) => handleChange('min_holding_hours', parseFloat(e.target.value) || undefined)}
              size="sm"
            />
            <Input
              type="number"
              label="最大持仓时长(h)"
              value={params.max_holding_hours?.toString() || ''}
              onChange={(e) => handleChange('max_holding_hours', parseFloat(e.target.value) || undefined)}
              size="sm"
            />
          </div>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
