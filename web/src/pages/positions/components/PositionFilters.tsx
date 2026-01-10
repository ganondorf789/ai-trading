import { Input, Select, SelectItem, Button } from "@heroui/react";
import { Icon } from "@iconify/react";
import { CopyPositionStats } from "@/services/api";

interface PositionFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  sideFilter: string;
  onSideFilterChange: (value: string) => void;
  targetFilter: string;
  onTargetFilterChange: (value: string) => void;
  stats: CopyPositionStats | null;
  onReset: () => void;
}

export function PositionFilters({
  search,
  onSearchChange,
  sideFilter,
  onSideFilterChange,
  targetFilter,
  onTargetFilterChange,
  stats,
  onReset,
}: PositionFiltersProps) {
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 检查是否有任何筛选条件
  const hasAnyFilter = search || sideFilter !== "all" || targetFilter !== "all";

  return (
    <div className="flex flex-col gap-4 mb-4">
      <div className="flex flex-wrap items-center gap-4">
        <Input
          className="w-64"
          placeholder="搜索币种或地址..."
          startContent={<Icon icon="solar:magnifer-linear" width={18} className="text-default-400" />}
          value={search}
          onValueChange={onSearchChange}
          isClearable
          onClear={() => onSearchChange("")}
        />

        <div className="flex items-center gap-2">
          <span className="text-sm text-default-500 whitespace-nowrap">方向:</span>
          <Select
            className="w-28"
            aria-label="Side"
            selectedKeys={[sideFilter]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string;
              onSideFilterChange(value);
            }}
          >
            <SelectItem key="all">全部</SelectItem>
            <SelectItem key="long">多头</SelectItem>
            <SelectItem key="short">空头</SelectItem>
          </Select>
        </div>

        {stats && stats.by_target && stats.by_target.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-500 whitespace-nowrap">目标:</span>
            <Select
              className="w-40"
              aria-label="Target"
              selectedKeys={[targetFilter]}
              size="sm"
              items={[
                { key: "all", label: "全部目标" },
                ...stats.by_target.map((t) => ({
                  key: t.target_address,
                  label: `${t.target_name || formatAddress(t.target_address)} (${t.position_count})`,
                })),
              ]}
              onSelectionChange={(keys) => {
                const value = Array.from(keys)[0] as string;
                onTargetFilterChange(value);
              }}
            >
              {(item) => <SelectItem key={item.key}>{item.label}</SelectItem>}
            </Select>
          </div>
        )}

        {hasAnyFilter && (
          <Button
            variant="flat"
            size="sm"
            color="warning"
            startContent={<Icon icon="solar:restart-linear" width={16} />}
            onPress={onReset}
          >
            重置
          </Button>
        )}
      </div>
    </div>
  );
}
