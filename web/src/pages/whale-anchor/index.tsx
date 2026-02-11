import { useState, useEffect, useCallback, useMemo } from "react";
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

// 排序选项
type SortField = "whale_threshold" | "day_volume_usd" | "open_interest_usd" | "depth_1pct_usd" | "mark_price" | "price_change_24h_pct";

const sortOptions: { key: SortField; label: string }[] = [
  { key: "whale_threshold", label: "Whale Threshold" },
  { key: "day_volume_usd", label: "24h Volume" },
  { key: "open_interest_usd", label: "Open Interest" },
  { key: "depth_1pct_usd", label: "1% Depth" },
  { key: "mark_price", label: "Price" },
  { key: "price_change_24h_pct", label: "24h Change" },
];

export default function WhaleAnchorPage() {
  const [data, setData] = useState<WhaleAnchorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<SortField>("whale_threshold");
  const [sortAsc, setSortAsc] = useState(false);
  const [dominantFilter, setDominantFilter] = useState<string>("all");

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
    result.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      return sortAsc ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });

    return result;
  }, [data, searchQuery, sortField, sortAsc, dominantFilter]);

  // 分页
  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: filteredData.length, defaultRowsPerPage: 50 });

  const pageItems = useMemo(() => getPageItems(filteredData), [getPageItems, filteredData]);

  // 统计卡片数据
  const stats = useMemo(() => {
    if (data.length === 0) return null;
    const totalCoins = data.length;
    const avgThreshold = data.reduce((s, d) => s + d.whale_threshold, 0) / totalCoins;
    const maxThreshold = Math.max(...data.map((d) => d.whale_threshold));
    const minThreshold = Math.min(...data.filter((d) => d.whale_threshold > 0).map((d) => d.whale_threshold));
    const volumeDominant = data.filter((d) => d.dominant_factor === "volume").length;
    const oiDominant = data.filter((d) => d.dominant_factor === "oi").length;
    const depthDominant = data.filter((d) => d.dominant_factor === "depth").length;
    return { totalCoins, avgThreshold, maxThreshold, minThreshold, volumeDominant, oiDominant, depthDominant };
  }, [data]);

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

  return (
    <DefaultLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Whale Anchor</h1>
            <p className="text-default-500 text-sm mt-1">
              Whale position threshold for each coin. Formula: max(0.4% x 24h Vol, 1% x OI, 30% x 1% Depth)
            </p>
            {updatedAt && (
              <p className="text-default-400 text-xs mt-1">
                Last updated: {updatedAt}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            {isAdmin && (
              <Tooltip content="Fetch latest data from Hyperliquid API and save to database">
                <Button
                  color="primary"
                  startContent={<Icon icon="solar:refresh-line-duotone" width={18} />}
                  isLoading={refreshing}
                  onPress={handleRefresh}
                >
                  Refresh Data
                </Button>
              </Tooltip>
            )}
          </div>
        </div>

        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardBody className="py-3 px-4">
                <p className="text-xs text-default-500">Total Coins</p>
                <p className="text-xl font-bold">{stats.totalCoins}</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-3 px-4">
                <p className="text-xs text-default-500">Avg Threshold</p>
                <p className="text-xl font-bold">{formatUsd(stats.avgThreshold)}</p>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-3 px-4">
                <p className="text-xs text-default-500">Dominant Factor</p>
                <div className="flex gap-2 mt-1">
                  <Chip size="sm" color="primary" variant="flat">Vol: {stats.volumeDominant}</Chip>
                  <Chip size="sm" color="secondary" variant="flat">OI: {stats.oiDominant}</Chip>
                  <Chip size="sm" color="warning" variant="flat">Dep: {stats.depthDominant}</Chip>
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardBody className="py-3 px-4">
                <p className="text-xs text-default-500">Threshold Range</p>
                <p className="text-sm font-semibold">{formatUsd(stats.minThreshold)} ~ {formatUsd(stats.maxThreshold)}</p>
              </CardBody>
            </Card>
          </div>
        )}

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
          <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
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
            <Select
              className="w-full sm:w-48"
              size="sm"
              label="Sort By"
              selectedKeys={[sortField]}
              onChange={(e) => {
                if (e.target.value) setSortField(e.target.value as SortField);
              }}
            >
              {sortOptions.map((opt) => (
                <SelectItem key={opt.key}>{opt.label}</SelectItem>
              ))}
            </Select>
            <Button
              size="sm"
              variant="flat"
              isIconOnly
              onPress={() => setSortAsc(!sortAsc)}
            >
              <Icon
                icon={sortAsc ? "solar:sort-from-bottom-to-top-line-duotone" : "solar:sort-from-top-to-bottom-line-duotone"}
                width={18}
              />
            </Button>
            <Select
              className="w-full sm:w-48"
              size="sm"
              label="Dominant Factor"
              selectedKeys={[dominantFilter]}
              onChange={(e) => {
                if (e.target.value) setDominantFilter(e.target.value);
              }}
            >
              <SelectItem key="all">All</SelectItem>
              <SelectItem key="volume">Volume</SelectItem>
              <SelectItem key="oi">OI</SelectItem>
              <SelectItem key="depth">Depth</SelectItem>
            </Select>
            <div className="text-sm text-default-500 whitespace-nowrap">
              {filteredData.length} coins
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
            classNames={{
              wrapper: "max-h-[calc(100vh-400px)]",
            }}
          >
            <TableHeader>
              <TableColumn key="rank" width={50}>#</TableColumn>
              <TableColumn key="coin" width={100}>Coin</TableColumn>
              <TableColumn key="mark_price" width={110}>Price</TableColumn>
              <TableColumn key="price_change" width={90}>24h Chg</TableColumn>
              <TableColumn key="whale_threshold" width={130}>Whale Threshold</TableColumn>
              <TableColumn key="components" width={150}>Components</TableColumn>
              <TableColumn key="dominant" width={90}>Dominant</TableColumn>
              <TableColumn key="volume" width={120}>24h Volume</TableColumn>
              <TableColumn key="oi" width={120}>Open Interest</TableColumn>
              <TableColumn key="depth" width={120}>1% Depth</TableColumn>
              <TableColumn key="leverage" width={80}>Max Lev</TableColumn>
            </TableHeader>
            <TableBody
              isLoading={loading}
              loadingContent={<Spinner label="Loading whale data..." />}
              emptyContent={error ? "Failed to load data" : "No data"}
            >
              {pageItems.map((item, idx) => (
                <TableRow key={item.coin}>
                  <TableCell>
                    <span className="text-default-400 text-xs">{(page - 1) * rowsPerPage + idx + 1}</span>
                  </TableCell>
                  <TableCell>
                    <span className="font-semibold">{item.coin}</span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">{formatPrice(item.mark_price)}</span>
                  </TableCell>
                  <TableCell>
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
                  </TableCell>
                  <TableCell>
                    <span className="font-bold text-sm">{formatUsd(item.whale_threshold)}</span>
                  </TableCell>
                  <TableCell>
                    <ComponentBar item={item} />
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="sm"
                      variant="flat"
                      color={factorColors[item.dominant_factor]}
                    >
                      {factorLabels[item.dominant_factor]}
                    </Chip>
                  </TableCell>
                  <TableCell>
                    <Tooltip content={`Component: ${formatUsd(item.volume_component)}`}>
                      <span className="text-sm cursor-help">{formatUsd(item.day_volume_usd)}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Tooltip content={`Component: ${formatUsd(item.oi_component)}`}>
                      <span className="text-sm cursor-help">{formatUsd(item.open_interest_usd)}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Tooltip content={`Component: ${formatUsd(item.depth_component)}`}>
                      <span className="text-sm cursor-help">{formatUsd(item.depth_1pct_usd)}</span>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm">{item.max_leverage}x</span>
                  </TableCell>
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

        {/* 公式说明 */}
        <Card>
          <CardBody className="py-3 px-4">
            <h3 className="text-sm font-semibold mb-2">Calculation Formula</h3>
            <div className="text-xs text-default-500 space-y-1">
              <p>
                <strong>Whale Threshold</strong> = max(
                <Chip size="sm" color="primary" variant="flat" className="mx-1">0.4% x 24h Volume</Chip>,
                <Chip size="sm" color="secondary" variant="flat" className="mx-1">1% x OI</Chip>,
                <Chip size="sm" color="warning" variant="flat" className="mx-1">30% x 1% Depth</Chip>
                )
              </p>
              <p>
                <strong>24h Volume</strong>: Notional trading volume in the last 24 hours (USD).
              </p>
              <p>
                <strong>OI (Open Interest)</strong>: Total outstanding contracts value (USD).
              </p>
              <p>
                <strong>1% Depth</strong>: Total orderbook liquidity within 1% of mid price on both sides (USD).
              </p>
            </div>
          </CardBody>
        </Card>
      </div>
    </DefaultLayout>
  );
}
