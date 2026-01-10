import { Input, Select, SelectItem, Button } from "@heroui/react";
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
        <Select
          className="w-32"
          placeholder="状态"
          aria-label="状态筛选"
          selectedKeys={[statusFilter]}
          onSelectionChange={(keys) => onStatusFilterChange(Array.from(keys)[0] as string)}
        >
          <SelectItem key="all" textValue="全部状态">全部状态</SelectItem>
          <SelectItem key="closed" textValue="已平仓">已平仓</SelectItem>
          <SelectItem key="open" textValue="持仓中">持仓中</SelectItem>
        </Select>

        {/* 方向筛选 */}
        <Select
          className="w-32"
          placeholder="方向"
          aria-label="方向筛选"
          selectedKeys={[directionFilter]}
          onSelectionChange={(keys) => onDirectionFilterChange(Array.from(keys)[0] as string)}
        >
          <SelectItem key="all" textValue="全部方向">全部方向</SelectItem>
          <SelectItem key="long" textValue="多头">多头</SelectItem>
          <SelectItem key="short" textValue="空头">空头</SelectItem>
        </Select>

        {/* 币种筛选 */}
        <Select
          className="w-36"
          placeholder="币种"
          aria-label="币种筛选"
          selectedKeys={[coinFilter]}
          onSelectionChange={(keys) => onCoinFilterChange(Array.from(keys)[0] as string)}
        >
          {coinOptions.map((coin) => (
            <SelectItem key={coin} textValue={coin === 'all' ? '全部币种' : coin}>
              {coin === 'all' ? '全部币种' : coin}
            </SelectItem>
          ))}
        </Select>

        {/* 盈亏筛选 */}
        <Select
          className="w-32"
          placeholder="盈亏"
          aria-label="盈亏筛选"
          selectedKeys={[pnlFilter]}
          onSelectionChange={(keys) => onPnlFilterChange(Array.from(keys)[0] as string)}
        >
          <SelectItem key="all" textValue="全部盈亏">全部盈亏</SelectItem>
          <SelectItem key="profit" textValue="盈利">盈利</SelectItem>
          <SelectItem key="loss" textValue="亏损">亏损</SelectItem>
        </Select>

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
