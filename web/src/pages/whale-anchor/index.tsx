import { useState, useEffect, useCallback, useMemo } from "react";
import type { SortDescriptor, Selection } from "@heroui/react";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Chip,
  Spinner,
  Input,
  Tooltip,
  Card,
  CardBody,
  Select,
  SelectItem,
  addToast,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { whaleAnchorApi, WhaleAnchorItem, tokenManager } from "@/services/api";
import { useLocalPagination, TablePagination } from "@/components/TablePagination";

// 格式化 USD 金额
function formatUsd(value: number): string {
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
  return `$${value.toFixed(2)}`;
}

// 格式化价格
function formatPrice(value: number): string {
  if (value >= 1000) return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  if (value >= 1) return `$${value.toFixed(4)}`;
  if (value >= 0.001) return `$${value.toFixed(6)}`;
  return `$${value.toPrecision(4)}`;
}

// 主导因子标签
const factorLabels: Record<string, string> = {
  volume: "Volume",
  oi: "OI",
  depth: "Depth",
  none: "-",
};

const factorColors: Record<string, "primary" | "secondary" | "warning" | "default"> = {
  volume: "primary",
  oi: "secondary",
  depth: "warning",
  none: "default",
};

// 表格列配置
type ColumnKey =
  | "rank"
  | "coin"
  | "mark_price"
  | "price_change_24h_pct"
  | "whale_threshold"
  | "components"
  | "dominant_factor"
  | "day_volume_usd"
  | "open_interest_usd"
  | "depth_1pct_usd"
  | "max_leverage";

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
  width?: number;
}

const columns: Column[] = [
  { uid: "rank", name: "#", width: 50 },
  { uid: "coin", name: "Coin", width: 100, sortable: true },
  { uid: "mark_price", name: "Price", sortable: true, width: 110 },
  { uid: "price_change_24h_pct", name: "24h Chg", sortable: true, width: 90 },
  { uid: "whale_threshold", name: "Whale Threshold", sortable: true, width: 130 },
  { uid: "components", name: "Components", width: 150 },
  { uid: "dominant_factor", name: "Dominant", width: 90 },
  { uid: "day_volume_usd", name: "24h Volume", sortable: true, width: 120 },
  { uid: "open_interest_usd", name: "Open Interest", sortable: true, width: 120 },
  { uid: "depth_1pct_usd", name: "1% Depth", sortable: true, width: 120 },
  { uid: "max_leverage", name: "Max Lev", sortable: true, width: 80 },
];

const INITIAL_VISIBLE_COLUMNS: ColumnKey[] = [
  "rank",
  "coin",
  "mark_price",
  "price_change_24h_pct",
  "whale_threshold",
  "components",
  "dominant_factor",
  "day_volume_usd",
  "open_interest_usd",
  "depth_1pct_usd",
  "max_leverage",
];

// 组件比例条
const ComponentBar = ({ item }: { item: WhaleAnchorItem }) => {
  const total = item.volume_component + item.oi_component + item.depth_component;
  if (total === 0) return <span className="text-default-400">-</span>;
  const vPct = (item.volume_component / total) * 100;
  const oiPct = (item.oi_component / total) * 100;
  const dPct = (item.depth_component / total) * 100;

  return (
    <Tooltip
      content={
        <div className="px-2 py-1 text-xs space-y-1">
          <div>Volume: {formatUsd(item.volume_component)} ({vPct.toFixed(1)}%)</div>
          <div>OI: {formatUsd(item.oi_component)} ({oiPct.toFixed(1)}%)</div>
          <div>Depth: {formatUsd(item.depth_component)} ({dPct.toFixed(1)}%)</div>
        </div>
      }
    >
      <div className="flex w-full h-2 rounded-full overflow-hidden bg-default-100 cursor-help" style={{ minWidth: 80 }}>
        {vPct > 0 && <div className="h-full bg-primary" style={{ width: `${vPct}%` }} />}
        {oiPct > 0 && <div className="h-full bg-secondary" style={{ width: `${oiPct}%` }} />}
        {dPct > 0 && <div className="h-full bg-warning" style={{ width: `${dPct}%` }} />}
      </div>
    </Tooltip>
  );
};

export default function WhaleAnchorPage() {
  const [data, setData] = useState<WhaleAnchorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: "whale_threshold",
    direction: "descending",
  });
  const [dominantFilter, setDominantFilter] = useState<string>("all");
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));

  // 获取当前用户角色
  const currentUser = tokenManager.getUser();
  const isAdmin = currentUser?.role === "admin";

  // 加载数据（从数据库）
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await whaleAnchorApi.getData();
      if (response.success && response.data) {
        setData(response.data);
        setUpdatedAt(response.updated_at || null);
      } else {
        setError(response.error || "Failed to load data");
      }
    } catch (e: any) {
      setError(e.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // 刷新数据（从 Hyperliquid API，仅管理员）
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await whaleAnchorApi.refresh();
      if (response.success) {
        addToast({
          title: "Refresh successful",
          description: response.message || `Updated ${response.total} coins`,
          color: "success",
        });
        // 重新加载数据
        await loadData();
      } else {
        addToast({
          title: "Refresh failed",
          description: response.error || "Unknown error",
          color: "danger",
        });
      }
    } catch (e: any) {
      addToast({
        title: "Refresh failed",
        description: e.message || "Request failed",
        color: "danger",
      });
    } finally {
      setRefreshing(false);
    }
  }, [loadData]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 可见列
  const headerColumns = useMemo(() => {
    if (visibleColumns === "all") return columns;
    return columns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  // 过滤和排序
  const filteredData = useMemo(() => {
    let result = [...data];

    // 搜索过滤
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toUpperCase();
      result = result.filter((item) => item.coin.toUpperCase().includes(q));
    }

    // 主导因子过滤
    if (dominantFilter !== "all") {
      result = result.filter((item) => item.dominant_factor === dominantFilter);
    }

    // 排序
    if (sortDescriptor.column) {
      const field = sortDescriptor.column as keyof WhaleAnchorItem;
      const direction = sortDescriptor.direction === "ascending" ? 1 : -1;
      result.sort((a, b) => {
        const aVal = a[field];
        const bVal = b[field];
        if (typeof aVal === "string" && typeof bVal === "string") {
          return direction * aVal.localeCompare(bVal);
        }
        return direction * ((aVal as number) - (bVal as number));
      });
    }

    return result;
  }, [data, searchQuery, sortDescriptor, dominantFilter]);

  // 分页
  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: filteredData.length, defaultRowsPerPage: 20 });

  const pageItems = useMemo(() => getPageItems(filteredData), [getPageItems, filteredData]);

  // 排序变更
  const handleSortChange = useCallback((descriptor: SortDescriptor) => {
    setSortDescriptor(descriptor);
  }, []);

  // 重置筛选
  const handleReset = useCallback(() => {
    setSearchQuery("");
    setDominantFilter("all");
    setSortDescriptor({ column: "whale_threshold", direction: "descending" });
  }, []);

  // 活跃筛选数量
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (searchQuery.trim()) count++;
    if (dominantFilter !== "all") count++;
    return count;
  }, [searchQuery, dominantFilter]);

  // 单元格渲染
  const renderCell = useCallback(
    (item: WhaleAnchorItem, columnKey: ColumnKey, idx: number) => {
      switch (columnKey) {
        case "rank":
          return <span className="text-default-400 text-xs">{(page - 1) * rowsPerPage + idx + 1}</span>;
        case "coin":
          return <span className="font-semibold">{item.coin}</span>;
        case "mark_price":
          return <span className="text-sm">{formatPrice(item.mark_price)}</span>;
        case "price_change_24h_pct":
          return (
            <span
              className={`text-sm font-medium ${
                item.price_change_24h_pct > 0
                  ? "text-success"
                  : item.price_change_24h_pct < 0
                    ? "text-danger"
                    : "text-default-500"
              }`}
            >
              {item.price_change_24h_pct > 0 ? "+" : ""}
              {item.price_change_24h_pct.toFixed(2)}%
            </span>
          );
        case "whale_threshold":
          return <span className="font-bold text-sm">{formatUsd(item.whale_threshold)}</span>;
        case "components":
          return <ComponentBar item={item} />;
        case "dominant_factor":
          return (
            <Chip size="sm" variant="flat" color={factorColors[item.dominant_factor]}>
              {factorLabels[item.dominant_factor]}
            </Chip>
          );
        case "day_volume_usd":
          return (
            <Tooltip content={`Component: ${formatUsd(item.volume_component)}`}>
              <span className="text-sm cursor-help">{formatUsd(item.day_volume_usd)}</span>
            </Tooltip>
          );
        case "open_interest_usd":
          return (
            <Tooltip content={`Component: ${formatUsd(item.oi_component)}`}>
              <span className="text-sm cursor-help">{formatUsd(item.open_interest_usd)}</span>
            </Tooltip>
          );
        case "depth_1pct_usd":
          return (
            <Tooltip content={`Component: ${formatUsd(item.depth_component)}`}>
              <span className="text-sm cursor-help">{formatUsd(item.depth_1pct_usd)}</span>
            </Tooltip>
          );
        case "max_leverage":
          return <span className="text-sm">{item.max_leverage}x</span>;
        default:
          return null;
      }
    },
    [page, rowsPerPage],
  );

  return (
    <DefaultLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Icon icon="lucide:anchor" width={28} />
              Whale Anchor
            </h1>
          </div>
          <div className="flex gap-2">
            {isAdmin && (
              <Tooltip content="Fetch latest data from Hyperliquid API and save to database">
                <Button
                  color="primary"
                  isLoading={refreshing}
                  onPress={handleRefresh}
                >
                  Refresh Data
                </Button>
              </Tooltip>
            )}
          </div>
        </div>

        {/* 无数据提示 */}
        {!loading && data.length === 0 && !error && (
          <Card className="bg-warning-50 border-warning-200">
            <CardBody className="py-4 px-4 text-warning-700 text-sm flex flex-row items-center gap-2">
              <Icon icon="solar:info-circle-line-duotone" width={20} />
              <span>No whale anchor data available. {isAdmin ? "Click \"Refresh Data\" to fetch from Hyperliquid API." : "Please contact an admin to refresh the data."}</span>
            </CardBody>
          </Card>
        )}

        {/* 工具栏 */}
        {data.length > 0 && (
          <div className="flex items-center justify-between gap-4 px-[6px] py-[4px]">
            {/* 左侧：筛选条件 */}
            <div className="flex items-center gap-4 overflow-auto">
              <Input
                className="w-full sm:w-64"
                placeholder="Search coin..."
                size="sm"
                startContent={<Icon icon="solar:magnifer-line-duotone" width={16} className="text-default-400" />}
                value={searchQuery}
                onValueChange={setSearchQuery}
                isClearable
                onClear={() => setSearchQuery("")}
              />

              {/* 主导因子筛选 */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm whitespace-nowrap">Dominant</span>
                <Select
                  className="min-w-[120px]"
                  size="sm"
                  selectedKeys={[dominantFilter]}
                  onSelectionChange={(keys) => {
                    const selected = Array.from(keys)[0] as string;
                    if (selected) setDominantFilter(selected);
                  }}
                >
                  <SelectItem key="all">All</SelectItem>
                  <SelectItem key="volume">Volume</SelectItem>
                  <SelectItem key="oi">OI</SelectItem>
                  <SelectItem key="depth">Depth</SelectItem>
                </Select>
              </div>

              {activeFiltersCount > 0 && (
                <Button
                  className="bg-default-100 text-default-800 shrink-0"
                  size="sm"
                  variant="flat"
                  onPress={handleReset}
                  startContent={
                    <Icon className="text-default-400" icon="solar:restart-linear" width={16} />
                  }
                >
                  Reset
                </Button>
              )}
            </div>

            {/* 右侧：排序和列 */}
            <div className="flex items-center gap-2 shrink-0">
              <div className="text-sm text-default-500 whitespace-nowrap">
                {filteredData.length} coins
              </div>

              {/* Sort 下拉 */}
              <Dropdown>
                <DropdownTrigger>
                  <Button
                    className="bg-default-100 text-default-800"
                    size="sm"
                    startContent={
                      <Icon className="text-default-400" icon="solar:sort-linear" width={16} />
                    }
                  >
                    Sort
                  </Button>
                </DropdownTrigger>
                <DropdownMenu
                  aria-label="Sort"
                  items={columns.filter((c) => c.sortable)}
                >
                  {(item) => (
                    <DropdownItem
                      key={item.uid}
                      onPress={() => {
                        handleSortChange({
                          column: item.uid,
                          direction:
                            sortDescriptor.column === item.uid && sortDescriptor.direction === "descending"
                              ? "ascending"
                              : "descending",
                        });
                      }}
                    >
                      {item.name}
                      {sortDescriptor.column === item.uid && (
                        <Icon
                          className="inline ml-1"
                          icon={
                            sortDescriptor.direction === "ascending"
                              ? "solar:sort-from-bottom-to-top-line-duotone"
                              : "solar:sort-from-top-to-bottom-line-duotone"
                          }
                          width={14}
                        />
                      )}
                    </DropdownItem>
                  )}
                </DropdownMenu>
              </Dropdown>

              {/* Columns 下拉 */}
              <Dropdown closeOnSelect={false}>
                <DropdownTrigger>
                  <Button
                    className="bg-default-100 text-default-800"
                    size="sm"
                    startContent={
                      <Icon className="text-default-400" icon="solar:sort-horizontal-linear" width={16} />
                    }
                  >
                    Columns
                  </Button>
                </DropdownTrigger>
                <DropdownMenu
                  disallowEmptySelection
                  aria-label="Columns"
                  items={columns}
                  selectedKeys={visibleColumns}
                  selectionMode="multiple"
                  onSelectionChange={setVisibleColumns}
                >
                  {(item) => <DropdownItem key={item.uid}>{item.name}</DropdownItem>}
                </DropdownMenu>
              </Dropdown>
            </div>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <Card className="bg-danger-50 border-danger-200">
            <CardBody className="py-3 px-4 text-danger text-sm">
              {error}
            </CardBody>
          </Card>
        )}

        {/* 数据表格 */}
        {(loading || data.length > 0) && (
          <Table
            aria-label="Whale anchor data"
            isStriped
            isHeaderSticky
            sortDescriptor={sortDescriptor}
            onSortChange={handleSortChange}
            classNames={{
              wrapper: "max-h-none overflow-visible",
            }}
          >
            <TableHeader columns={headerColumns}>
              {(column) => (
                <TableColumn
                  key={column.uid}
                  width={column.width}
                  allowsSorting={column.sortable}
                >
                  {column.name}
                </TableColumn>
              )}
            </TableHeader>
            <TableBody
              isLoading={loading}
              loadingContent={<Spinner label="Loading whale data..." />}
              emptyContent={error ? "Failed to load data" : "No data"}
            >
              {pageItems.map((item, idx) => (
                <TableRow key={item.coin}>
                  {(columnKey) => (
                    <TableCell>{renderCell(item, columnKey as ColumnKey, idx)}</TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {/* 分页 */}
        {data.length > 0 && (
          <TablePagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalCount={filteredData.length}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={setRowsPerPage}
          />
        )}
      </div>
    </DefaultLayout>
  );
}
