import { Input, Select, SelectItem, Button } from "@heroui/react";
import { Icon } from "@iconify/react";

interface OrderFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  sideFilter: string;
  onSideFilterChange: (value: string) => void;
  actionFilter: string;
  onActionFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  targetFilter: string;
  onTargetFilterChange: (value: string) => void;
  daysFilter: number;
  onDaysFilterChange: (value: number) => void;
  targets: Array<{ address: string; name: string | null }>;
  onRefresh: () => void;
  loading: boolean;
}

export function OrderFilters({
  search,
  onSearchChange,
  sideFilter,
  onSideFilterChange,
  actionFilter,
  onActionFilterChange,
  statusFilter,
  onStatusFilterChange,
  targetFilter,
  onTargetFilterChange,
  daysFilter,
  onDaysFilterChange,
  targets,
  onRefresh,
  loading,
}: OrderFiltersProps) {
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  return (
    <div className="mb-6">
      <div className="flex flex-wrap gap-4">
        {/* Search */}
        <Input
          className="w-64"
          placeholder="Search symbol..."
          startContent={<Icon icon="solar:magnifer-linear" className="text-default-400" width={18} />}
          value={search}
          onValueChange={onSearchChange}
        />

        {/* Target Address Filter */}
        <Select
          className="w-48"
          label="Trader"
          placeholder="All Traders"
          selectedKeys={targetFilter ? [targetFilter] : []}
          size="sm"
          onChange={(e) => onTargetFilterChange(e.target.value)}
        >
          {[
            <SelectItem key="" textValue="All Traders">
              All Traders
            </SelectItem>,
            ...targets.map((t) => (
              <SelectItem key={t.address} textValue={t.name || formatAddress(t.address)}>
                {t.name || formatAddress(t.address)}
              </SelectItem>
            )),
          ]}
        </Select>

        {/* Side Filter */}
        <Select
          className="w-32"
          label="Side"
          placeholder="All"
          selectedKeys={sideFilter ? [sideFilter] : []}
          size="sm"
          onChange={(e) => onSideFilterChange(e.target.value)}
        >
          <SelectItem key="" textValue="All">All</SelectItem>
          <SelectItem key="long" textValue="Long">
            <span className="text-success">Long</span>
          </SelectItem>
          <SelectItem key="short" textValue="Short">
            <span className="text-danger">Short</span>
          </SelectItem>
        </Select>

        {/* Action Filter */}
        <Select
          className="w-32"
          label="Action"
          placeholder="All"
          selectedKeys={actionFilter ? [actionFilter] : []}
          size="sm"
          onChange={(e) => onActionFilterChange(e.target.value)}
        >
          <SelectItem key="" textValue="All">All</SelectItem>
          <SelectItem key="open" textValue="Open">Open</SelectItem>
          <SelectItem key="close" textValue="Close">Close</SelectItem>
        </Select>

        {/* Status Filter */}
        <Select
          className="w-32"
          label="Status"
          placeholder="All"
          selectedKeys={statusFilter ? [statusFilter] : []}
          size="sm"
          onChange={(e) => onStatusFilterChange(e.target.value)}
        >
          <SelectItem key="" textValue="All">All</SelectItem>
          <SelectItem key="success" textValue="Success">
            <span className="text-success">Success</span>
          </SelectItem>
          <SelectItem key="failed" textValue="Failed">
            <span className="text-danger">Failed</span>
          </SelectItem>
          <SelectItem key="pending" textValue="Pending">
            <span className="text-warning">Pending</span>
          </SelectItem>
        </Select>

        {/* Days Filter */}
        <Select
          className="w-32"
          label="Period"
          placeholder="7 Days"
          selectedKeys={[String(daysFilter)]}
          size="sm"
          onChange={(e) => onDaysFilterChange(Number(e.target.value))}
        >
          <SelectItem key="1" textValue="1 Day">1 Day</SelectItem>
          <SelectItem key="3" textValue="3 Days">3 Days</SelectItem>
          <SelectItem key="7" textValue="7 Days">7 Days</SelectItem>
          <SelectItem key="14" textValue="14 Days">14 Days</SelectItem>
          <SelectItem key="30" textValue="30 Days">30 Days</SelectItem>
        </Select>

        {/* Refresh Button */}
        <Button
          color="primary"
          isLoading={loading}
          startContent={!loading && <Icon icon="solar:refresh-linear" width={18} />}
          variant="flat"
          onPress={onRefresh}
        >
          Refresh
        </Button>
      </div>
    </div>
  );
}
