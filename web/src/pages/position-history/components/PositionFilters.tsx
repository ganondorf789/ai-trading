import { Input, Select, SelectItem, Button, Autocomplete, AutocompleteItem } from "@heroui/react";
import { Icon } from "@iconify/react";
import { PositionHistoryByCoin } from "@/services/api";

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
  byCoin: PositionHistoryByCoin[];
  onReset: () => void;
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
  byCoin,
  onReset,
}: PositionFiltersProps) {
  // 获取所有币种选项
  const coinOptions = ['all', ...byCoin.map(c => c.coin)];

  return (
    <div className="bg-content1/50 backdrop-blur-md rounded-xl p-4 mb-6">
      <div className="flex flex-wrap items-center gap-4">
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
            size="sm"
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
            size="sm"
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
            size="sm"
            aria-label="币种筛选"
            selectedKey={coinFilter}
            onSelectionChange={(key) => onCoinFilterChange((key as string) || 'all')}
            allowsCustomValue={false}
          >
            {coinOptions.map((coin) => (
              <AutocompleteItem key={coin} textValue={coin === 'all' ? '全部' : coin}>
                {coin === 'all' ? '全部' : coin}
              </AutocompleteItem>
            ))}
          </Autocomplete>
        </div>

        {/* 盈亏筛选 */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm whitespace-nowrap">盈亏</span>
          <Select
            className="min-w-[100px]"
            size="sm"
            aria-label="盈亏筛选"
            selectedKeys={[pnlFilter]}
            onSelectionChange={(keys) => onPnlFilterChange(Array.from(keys)[0] as string)}
          >
            <SelectItem key="all" textValue="全部">全部</SelectItem>
            <SelectItem key="profit" textValue="盈利">盈利</SelectItem>
            <SelectItem key="loss" textValue="亏损">亏损</SelectItem>
          </Select>
        </div>

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
    </div>
  );
}
