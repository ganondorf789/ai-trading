import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Pagination,
  Input,
  Button,
  Chip,
  Spinner,
  Select,
  SelectItem,
  Card,
  CardBody,
  Tooltip,
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { copyTradingOrdersApi, CopyTradingOrder, CopyOrderStats, PaginationInfo } from "@/services/api";

// 状态颜色映射
const statusColors: Record<string, "success" | "warning" | "danger" | "default"> = {
  success: "success",
  pending: "warning",
  failed: "danger",
};

// 操作颜色映射
const actionColors: Record<string, "primary" | "secondary"> = {
  open: "primary",
  close: "secondary",
};

export default function OrdersPage() {
  const navigate = useNavigate();

  // 数据状态
  const [orders, setOrders] = useState<CopyTradingOrder[]>([]);
  const [stats, setStats] = useState<CopyOrderStats | null>(null);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);

  // 筛选状态
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [modeFilter, setModeFilter] = useState<string>("all");
  const [daysFilter, setDaysFilter] = useState<number>(7);
  const sortBy = "created_at";
  const sortOrder: "asc" | "desc" = "desc";
  const rowsPerPage = 20;

  // 页码跳转
  const [jumpPage, setJumpPage] = useState("");

  // 加载订单列表
  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit: 20,
        days: daysFilter,
        sort_by: sortBy,
        sort_order: sortOrder,
      };

      if (search) {
        params.target_address = search;
        params.symbol = search;
      }
      if (statusFilter !== "all") {
        params.status = statusFilter;
      }
      if (actionFilter !== "all") {
        params.action = actionFilter;
      }
      if (modeFilter !== "all") {
        params.is_dry_run = modeFilter === "dry_run";
      }

      const response = await copyTradingOrdersApi.getOrders(params);

      if (response.success && response.data) {
        setOrders(response.data);
        setPagination(response.pagination || null);
      }
    } catch (error) {
      console.error("Failed to fetch orders:", error);
      addToast({
        title: "Error",
        description: "Failed to load orders",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, actionFilter, modeFilter, daysFilter, sortBy, sortOrder]);

  // 加载统计数据
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await copyTradingOrdersApi.getStats({ days: daysFilter });

      if (response.success && response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setStatsLoading(false);
    }
  }, [daysFilter]);

  // 清理旧订单
  const handleCleanup = async () => {
    try {
      const response = await copyTradingOrdersApi.cleanup(30);

      if (response.success) {
        addToast({
          title: "Success",
          description: response.message || "Old orders cleaned up",
          color: "success",
        });
        fetchOrders();
        fetchStats();
      }
    } catch (error) {
      console.error("Failed to cleanup orders:", error);
      addToast({
        title: "Error",
        description: "Failed to cleanup orders",
        color: "danger",
      });
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // 格式化时间
  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "-";
    const date = new Date(timeStr);

    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  // 格式化地址
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 格式化数字
  const formatNumber = (num: number | null, decimals: number = 2) => {
    if (num === null || num === undefined) return "-";

    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  // 格式化 PnL
  const formatPnl = (pnl: number) => {
    const formatted = formatNumber(pnl);
    const prefix = pnl >= 0 ? "+" : "";

    return `${prefix}$${formatted}`;
  };

  // 页码跳转
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pagination && pageNum >= 1 && pageNum <= pagination.total_pages) {
      setPage(pageNum);
      setJumpPage("");
    }
  };

  // 渲染统计卡片
  const renderStatsCards = () => {
    if (statsLoading) {
      return (
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      );
    }

    if (!stats) return null;

    const successRate = stats.total_orders > 0
      ? ((stats.successful_orders / stats.total_orders) * 100).toFixed(1)
      : "0.0";

    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold">{stats.total_orders}</div>
            <div className="text-sm text-default-500">Total Orders</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold text-success">{stats.successful_orders}</div>
            <div className="text-sm text-default-500">Successful ({successRate}%)</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold text-danger">{stats.failed_orders}</div>
            <div className="text-sm text-default-500">Failed</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className={`text-2xl font-bold ${stats.total_pnl >= 0 ? "text-success" : "text-danger"}`}>
              {formatPnl(stats.total_pnl)}
            </div>
            <div className="text-sm text-default-500">Total PnL</div>
          </CardBody>
        </Card>
      </div>
    );
  };

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold">Order Management</h1>
            <p className="text-default-500">View and manage copy trading orders</p>
          </div>
          <div className="flex gap-2">
            <Button
              color="default"
              startContent={<Icon icon="solar:trash-bin-trash-linear" width={18} />}
              variant="flat"
              onPress={handleCleanup}
            >
              Cleanup Old Orders
            </Button>
            <Button
              color="primary"
              startContent={<Icon icon="solar:refresh-linear" width={18} />}
              variant="flat"
              onPress={() => {
                fetchOrders();
                fetchStats();
              }}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        {renderStatsCards()}

        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-4">
          <Input
            className="w-64"
            placeholder="Search address or symbol..."
            startContent={<Icon icon="solar:magnifer-linear" width={18} />}
            value={search}
            onValueChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
          />
          <Select
            className="w-32"
            label="Status"
            selectedKeys={[statusFilter]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string;

              setStatusFilter(value);
              setPage(1);
            }}
          >
            <SelectItem key="all">All</SelectItem>
            <SelectItem key="success">Success</SelectItem>
            <SelectItem key="pending">Pending</SelectItem>
            <SelectItem key="failed">Failed</SelectItem>
          </Select>
          <Select
            className="w-32"
            label="Action"
            selectedKeys={[actionFilter]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string;

              setActionFilter(value);
              setPage(1);
            }}
          >
            <SelectItem key="all">All</SelectItem>
            <SelectItem key="open">Open</SelectItem>
            <SelectItem key="close">Close</SelectItem>
          </Select>
          <Select
            className="w-32"
            label="Mode"
            selectedKeys={[modeFilter]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string;

              setModeFilter(value);
              setPage(1);
            }}
          >
            <SelectItem key="all">All</SelectItem>
            <SelectItem key="dry_run">Dry Run</SelectItem>
            <SelectItem key="live">Live</SelectItem>
          </Select>
          <Select
            className="w-32"
            label="Time Range"
            selectedKeys={[String(daysFilter)]}
            size="sm"
            onSelectionChange={(keys) => {
              const value = Number(Array.from(keys)[0]);

              setDaysFilter(value);
              setPage(1);
            }}
          >
            <SelectItem key="1">Last 1 Day</SelectItem>
            <SelectItem key="7">Last 7 Days</SelectItem>
            <SelectItem key="30">Last 30 Days</SelectItem>
            <SelectItem key="90">Last 90 Days</SelectItem>
          </Select>
        </div>

        {/* Orders Table */}
        <Table
          aria-label="Orders table"
          bottomContent={
            pagination && pagination.total_pages > 1 ? (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2">
                <span className="text-sm text-default-500">
                  显示 {Math.min((page - 1) * rowsPerPage + 1, pagination.total_count)} - {Math.min(page * rowsPerPage, pagination.total_count)} 条，共 {pagination.total_count} 条记录
                </span>
                <div className="flex items-center gap-3">
                  <Pagination
                    isCompact
                    showControls
                    showShadow
                    color="primary"
                    page={page}
                    total={pagination.total_pages}
                    onChange={setPage}
                  />
                  <div className="flex items-center gap-1">
                    <span className="text-sm text-default-500">跳转</span>
                    <Input
                      type="number"
                      size="sm"
                      className="w-16"
                      min={1}
                      max={pagination.total_pages}
                      value={jumpPage}
                      onValueChange={setJumpPage}
                      onKeyDown={(e) => e.key === "Enter" && handleJumpPage()}
                    />
                    <span className="text-sm text-default-500">页</span>
                  </div>
                </div>
              </div>
            ) : null
          }
        >
          <TableHeader>
            <TableColumn>Time</TableColumn>
            <TableColumn>Target</TableColumn>
            <TableColumn>Symbol</TableColumn>
            <TableColumn>Action</TableColumn>
            <TableColumn>Side</TableColumn>
            <TableColumn>Size</TableColumn>
            <TableColumn>Price</TableColumn>
            <TableColumn>Leverage</TableColumn>
            <TableColumn>PnL</TableColumn>
            <TableColumn>Status</TableColumn>
            <TableColumn>Mode</TableColumn>
          </TableHeader>
          <TableBody
            emptyContent="No orders found"
            isLoading={loading}
            loadingContent={<Spinner />}
          >
            {orders.map((order) => (
              <TableRow key={order.id}>
                <TableCell>
                  <div className="text-sm">
                    {formatTime(order.created_at)}
                  </div>
                </TableCell>
                <TableCell>
                  <Tooltip content={order.target_address}>
                    <span
                      className="font-mono text-sm cursor-pointer hover:text-primary"
                      onClick={() => navigate(`/traders/${order.target_address}`)}
                    >
                      {order.target_name || formatAddress(order.target_address)}
                    </span>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <span className="font-medium">{order.symbol}</span>
                </TableCell>
                <TableCell>
                  <Chip
                    color={actionColors[order.action] || "default"}
                    size="sm"
                    variant="flat"
                  >
                    {order.action.toUpperCase()}
                  </Chip>
                </TableCell>
                <TableCell>
                  <Chip
                    color={order.side === "long" ? "success" : "danger"}
                    size="sm"
                    variant="flat"
                  >
                    {order.side.toUpperCase()}
                  </Chip>
                </TableCell>
                <TableCell>
                  <span className="font-mono">{formatNumber(order.size, 4)}</span>
                </TableCell>
                <TableCell>
                  <span className="font-mono">${formatNumber(order.price, 2)}</span>
                </TableCell>
                <TableCell>
                  <span className="font-mono">{order.leverage}x</span>
                </TableCell>
                <TableCell>
                  {order.action === "close" && order.pnl !== 0 ? (
                    <span className={`font-mono ${order.pnl >= 0 ? "text-success" : "text-danger"}`}>
                      {formatPnl(order.pnl)}
                    </span>
                  ) : (
                    <span className="text-default-400">-</span>
                  )}
                </TableCell>
                <TableCell>
                  <Tooltip content={order.error_message || undefined} isDisabled={!order.error_message}>
                    <Chip
                      color={statusColors[order.status] || "default"}
                      size="sm"
                      variant="flat"
                    >
                      {order.status.toUpperCase()}
                    </Chip>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <Chip
                    color={order.is_dry_run ? "warning" : "success"}
                    size="sm"
                    variant="dot"
                  >
                    {order.is_dry_run ? "Dry Run" : "Live"}
                  </Chip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </DefaultLayout>
  );
}
