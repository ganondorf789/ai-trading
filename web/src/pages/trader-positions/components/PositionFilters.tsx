import { Input, Select, SelectItem } from "@heroui/react";
import { Icon } from "@iconify/react";
import { TraderPositionsStats, CopyTradingGroup } from "@/services/api";

interface PositionFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  sideFilter: string;
  onSideFilterChange: (value: string) => void;
  traderFilter: string;
  onTraderFilterChange: (value: string) => void;
  coinFilter: string;
  onCoinFilterChange: (value: string) => void;
  groupFilter: string;
  onGroupFilterChange: (value: string) => void;
  stats: TraderPositionsStats | null;
  groups: CopyTradingGroup[];
}

export function PositionFilters({
  search,
  onSearchChange,
  sideFilter,
  onSideFilterChange,
  traderFilter,
  onTraderFilterChange,
  coinFilter,
  onCoinFilterChange,
  groupFilter,
  onGroupFilterChange,
  stats,
  groups,
}: PositionFiltersProps) {
  // 构建交易员选项
  const traderOptions = stats?.by_trader || [];
  const coinOptions = stats?.by_coin || [];

  return (
    <div className="flex flex-wrap gap-3 items-center mb-6">
      <Input
        className="w-64"
        placeholder="搜索币种或交易员..."
        value={search}
        onValueChange={onSearchChange}
        startContent={<Icon icon="solar:magnifer-linear" width={18} className="text-default-400" />}
        isClearable
        onClear={() => onSearchChange("")}
      />

      <Select
        className="w-36"
        placeholder="方向"
        selectedKeys={[sideFilter]}
        onSelectionChange={(keys) => onSideFilterChange(Array.from(keys)[0] as string)}
      >
        <SelectItem key="all">全部方向</SelectItem>
        <SelectItem key="long">多头</SelectItem>
        <SelectItem key="short">空头</SelectItem>
      </Select>

      <Select
        className="w-40"
        placeholder="分组"
        selectedKeys={[groupFilter]}
        onSelectionChange={(keys) => onGroupFilterChange(Array.from(keys)[0] as string)}
      >
        <SelectItem key="all">全部分组</SelectItem>
        {groups.map((group) => (
          <SelectItem key={group.id.toString()}>{group.name}</SelectItem>
        ))}
      </Select>

      <Select
        className="w-48"
        placeholder="交易员"
        selectedKeys={[traderFilter]}
        onSelectionChange={(keys) => onTraderFilterChange(Array.from(keys)[0] as string)}
      >
        <SelectItem key="all">全部交易员</SelectItem>
        {traderOptions.map((trader) => (
          <SelectItem key={trader.address}>
            {trader.name || `${trader.address.slice(0, 6)}...${trader.address.slice(-4)}`} ({trader.count})
          </SelectItem>
        ))}
      </Select>

      <Select
        className="w-36"
        placeholder="币种"
        selectedKeys={[coinFilter]}
        onSelectionChange={(keys) => onCoinFilterChange(Array.from(keys)[0] as string)}
      >
        <SelectItem key="all">全部币种</SelectItem>
        {coinOptions.map((coin) => (
          <SelectItem key={coin.coin}>
            {coin.coin} ({coin.count})
          </SelectItem>
        ))}
      </Select>
    </div>
  );
}
