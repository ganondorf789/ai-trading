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
          label="状态"
          size="sm"
          selectedKeys={[statusFilter]}
          onChange={(e) => onStatusFilterChange(e.target.value)}
        >
          <SelectItem key="all">全部</SelectItem>
          <SelectItem key="closed">已平仓</SelectItem>
          <SelectItem key="open">持仓中</SelectItem>
        </Select>

        {/* 方向筛选 */}
        <Select
          className="w-32"
          label="方向"
          size="sm"
          selectedKeys={[directionFilter]}
          onChange={(e) => onDirectionFilterChange(e.target.value)}
        >
          <SelectItem key="all">全部</SelectItem>
          <SelectItem key="long">多头</SelectItem>
          <SelectItem key="short">空头</SelectItem>
        </Select>

        {/* 币种筛选 */}
        <Select
          className="w-36"
          label="币种"
          size="sm"
          selectedKeys={[coinFilter]}
          onChange={(e) => onCoinFilterChange(e.target.value)}
        >
          {coinOptions.map((coin) => (
            <SelectItem key={coin}>
              {coin === 'all' ? '全部币种' : coin}
            </SelectItem>
          ))}
        </Select>

        {/* 盈亏筛选 */}
        <Select
          className="w-32"
          label="盈亏"
          size="sm"
          selectedKeys={[pnlFilter]}
          onChange={(e) => onPnlFilterChange(e.target.value)}
        >
          <SelectItem key="all">全部</SelectItem>
          <SelectItem key="profit">盈利</SelectItem>
          <SelectItem key="loss">亏损</SelectItem>
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
