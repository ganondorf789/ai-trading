import { useState, useEffect, useCallback } from "react";
import { addToast } from "@heroui/react";

import DefaultLayout from "@/layouts/default";
import { copyTradingOrdersApi, copyTradingApi, CopyTradingOrder, PaginationInfo } from "@/services/api";

import { StatsCards, OrderFilters, OrdersTable } from "./components";

interface OrderStats {
  total_orders: number;
  successful: number;
  failed: number;
  opens: number;
  closes: number;
  total_pnl: number;
  real_orders: number;
  by_symbol?: Array<{ symbol: string; count: number; pnl: number }>;
  by_target?: Array<{ target_address: string; target_name: string | null; count: number; pnl: number }>;
}

export default function CopyOrdersPage() {
  // 数据状态
  const [orders, setOrders] = useState<CopyTradingOrder[]>([]);
  const [stats, setStats] = useState<OrderStats | null>(null);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [targets, setTargets] = useState<Array<{ address: string; name: string | null }>>([]);

  // 筛选状态
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [daysFilter, setDaysFilter] = useState(7);
  const [page, setPage] = useState(1);
  const limit = 20;

  // 加载跟单地址列表（用于筛选器）
  const fetchTargets = useCallback(async () => {
    try {
      const response = await copyTradingApi.getAddresses({ limit: 1000 });
      if (response.success && response.data) {
        setTargets(
          response.data.map((addr) => ({
            address: addr.address,
            name: addr.name || null,
          }))
        );
      }
    } catch (error) {
      console.error("Failed to fetch targets:", error);
    }
  }, []);

  // 加载订单列表
  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit,
        days: daysFilter,
        sort_by: "created_at",
        sort_order: "desc",
      };

      if (targetFilter) {
        params.target_address = targetFilter;
      }
      if (statusFilter) {
        params.status = statusFilter;
      }
      if (actionFilter) {
        params.action = actionFilter;
      }

      const response = await copyTradingOrdersApi.getOrders(params);

      if (response.success && response.data) {
        let filtered = response.data;

        // 本地筛选：搜索和方向
        if (search) {
          const searchLower = search.toLowerCase();
          filtered = filtered.filter(
            (o) =>
              o.symbol.toLowerCase().includes(searchLower) ||
              o.target_address.toLowerCase().includes(searchLower) ||
              (o.target_name && o.target_name.toLowerCase().includes(searchLower))
          );
        }

        if (sideFilter) {
          filtered = filtered.filter(
            (o) => o.side.toLowerCase() === sideFilter.toLowerCase()
          );
        }

        setOrders(filtered);
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
  }, [page, daysFilter, targetFilter, statusFilter, actionFilter, search, sideFilter]);

  // 加载统计数据
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const params: Record<string, any> = {
        days: daysFilter,
      };

      if (targetFilter) {
        params.target_address = targetFilter;
      }

      const response = await copyTradingOrdersApi.getStats(params);

      if (response.success && response.data) {
        setStats(response.data as unknown as OrderStats);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setStatsLoading(false);
    }
  }, [daysFilter, targetFilter]);

  // 刷新所有数据
  const handleRefresh = useCallback(() => {
    fetchOrders();
    fetchStats();
  }, [fetchOrders, fetchStats]);

  // 页码变化
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  // 筛选变化时重置页码
  useEffect(() => {
    setPage(1);
  }, [search, sideFilter, actionFilter, statusFilter, targetFilter, daysFilter]);

  // 初始加载
  useEffect(() => {
    fetchTargets();
  }, [fetchTargets]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold">Copy Trading Orders</h1>
          <p className="text-default-500">
            View all copy trading open/close orders (long/short positions)
          </p>
        </div>

        {/* Stats Cards */}
        <StatsCards stats={stats} loading={statsLoading} />

        {/* Filters */}
        <OrderFilters
          search={search}
          onSearchChange={setSearch}
          sideFilter={sideFilter}
          onSideFilterChange={setSideFilter}
          actionFilter={actionFilter}
          onActionFilterChange={setActionFilter}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          targetFilter={targetFilter}
          onTargetFilterChange={setTargetFilter}
          daysFilter={daysFilter}
          onDaysFilterChange={setDaysFilter}
          targets={targets}
          onRefresh={handleRefresh}
          loading={loading}
        />

        {/* Orders Table */}
        <OrdersTable
          orders={orders}
          loading={loading}
          pagination={pagination}
          onPageChange={handlePageChange}
        />
      </div>
    </DefaultLayout>
  );
}
