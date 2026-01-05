import { Input, Select, SelectItem } from "@heroui/react";
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
}

export function PositionFilters({
  search,
  onSearchChange,
  sideFilter,
  onSideFilterChange,
  targetFilter,
  onTargetFilterChange,
  stats,
}: PositionFiltersProps) {
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  return (
    <div className="flex flex-wrap items-center gap-4 mb-4">
      <Input
        className="w-64"
        placeholder="Search symbol or address..."
        startContent={<Icon icon="solar:magnifer-linear" width={18} />}
        value={search}
        onValueChange={onSearchChange}
      />
      <div className="flex items-center gap-2">
        <span className="text-sm text-default-500 whitespace-nowrap">Side:</span>
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
          <SelectItem key="all">All</SelectItem>
          <SelectItem key="long">Long</SelectItem>
          <SelectItem key="short">Short</SelectItem>
        </Select>
      </div>
      {stats && stats.by_target && stats.by_target.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-default-500 whitespace-nowrap">Target:</span>
          <Select
            className="w-40"
            aria-label="Target"
            selectedKeys={[targetFilter]}
            size="sm"
            items={[
              { key: "all", label: "All Targets" },
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
    </div>
  );
}
