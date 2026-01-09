import { useState, useEffect, useCallback, useMemo } from "react";
import { addToast } from "@heroui/react";

import DefaultLayout from "@/layouts/default";
import { 
  copyTradingOrdersApi, 
  copyTradingApi, 
  CopyTradingOrder, 
  PaginationInfo,
  CopyTradingAddress 
} from "@/services/api";
import { MetricFilterConfig, emptyMetricFilters } from "@/components/filters";

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

// 扩展订单类型，包含交易员指标
interface CopyTradingOrderWithMetrics extends CopyTradingOrder {
  win_rate?: number;
  trader_pnl?: number;
  overall_score?: number;
  total_trades?: number;
  profit_factor?: number;
  max_drawdown?: number;
  sharpe_ratio?: number;
}

export default function CopyOrdersPage() {
  // 数据状态
  const [orders, setOrders] = useState<CopyTradingOrderWithMetrics[]>([]);
  const [stats, setStats] = useState<OrderStats | null>(null);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [targets, setTargets] = useState<Array<{ address: string; name: string | null }>>([]);
  const [addressMetrics, setAddressMetrics] = useState<Map<string, CopyTradingAddress>>(new Map());

  // 筛选状态
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [targetFilter, setTargetFilter] = useState("");
  const [daysFilter, setDaysFilter] = useState(7);
  const [metricFilters, setMetricFilters] = useState<MetricFilterConfig>(emptyMetricFilters);
  const [page, setPage] = useState(1);
  const limit = 20;

  // 加载跟单地址列表（用于筛选器和指标数据）
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
        // 保存完整的地址指标数据
        const metricsMap = new Map<string, CopyTradingAddress>();
        response.data.forEach(addr => {
          metricsMap.set(addr.address, addr);
        });
        setAddressMetrics(metricsMap);
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
        // 合并交易员指标到订单数据
        const ordersWithMetrics = response.data.map(order => ({
          ...order,
          win_rate: addressMetrics.get(order.target_address)?.win_rate,
          trader_pnl: addressMetrics.get(order.target_address)?.trader_pnl,
          overall_score: addressMetrics.get(order.target_address)?.overall_score,
          total_trades: addressMetrics.get(order.target_address)?.total_trades,
          profit_factor: addressMetrics.get(order.target_address)?.profit_factor,
          max_drawdown: addressMetrics.get(order.target_address)?.max_drawdown,
          sharpe_ratio: addressMetrics.get(order.target_address)?.sharpe_ratio,
        }));

        setOrders(ordersWithMetrics);
        setPagination(response.pagination || null);
      }
    } catch (error) {
      console.error("Failed to fetch orders:", error);
      addToast({
        title: "错误",
        description: "加载订单失败",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [page, daysFilter, targetFilter, statusFilter, actionFilter, addressMetrics]);

  // 应用本地筛选（包括指标筛选）
  const filteredOrders = useMemo(() => {
    let filtered = orders;

    // 搜索筛选
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(
        (o) =>
          o.symbol.toLowerCase().includes(searchLower) ||
          o.target_address.toLowerCase().includes(searchLower) ||
          (o.target_name && o.target_name.toLowerCase().includes(searchLower))
      );
    }

    // 方向筛选
    if (sideFilter) {
      filtered = filtered.filter(
        (o) => o.side.toLowerCase() === sideFilter.toLowerCase()
      );
    }

    // 指标筛选
    if (metricFilters.minWinRate !== undefined) {
      filtered = filtered.filter((o) => (o.win_rate ?? 0) >= metricFilters.minWinRate!);
    }
    if (metricFilters.maxWinRate !== undefined) {
      filtered = filtered.filter((o) => (o.win_rate ?? 100) <= metricFilters.maxWinRate!);
    }
    if (metricFilters.minProfitFactor !== undefined) {
      filtered = filtered.filter((o) => (o.profit_factor ?? 0) >= metricFilters.minProfitFactor!);
    }
    if (metricFilters.maxProfitFactor !== undefined) {
      filtered = filtered.filter((o) => (o.profit_factor ?? 999) <= metricFilters.maxProfitFactor!);
    }
    if (metricFilters.minPnl !== undefined) {
      filtered = filtered.filter((o) => (o.trader_pnl ?? 0) >= metricFilters.minPnl!);
    }
    if (metricFilters.maxPnl !== undefined) {
      filtered = filtered.filter((o) => (o.trader_pnl ?? 0) <= metricFilters.maxPnl!);
    }
    if (metricFilters.minDrawdown !== undefined) {
      filtered = filtered.filter((o) => (o.max_drawdown ?? 0) >= metricFilters.minDrawdown!);
    }
    if (metricFilters.maxDrawdown !== undefined) {
      filtered = filtered.filter((o) => (o.max_drawdown ?? 100) <= metricFilters.maxDrawdown!);
    }
    if (metricFilters.minSharpe !== undefined) {
      filtered = filtered.filter((o) => (o.sharpe_ratio ?? -999) >= metricFilters.minSharpe!);
    }
    if (metricFilters.maxSharpe !== undefined) {
      filtered = filtered.filter((o) => (o.sharpe_ratio ?? 999) <= metricFilters.maxSharpe!);
    }
    if (metricFilters.minTrades !== undefined) {
      filtered = filtered.filter((o) => (o.total_trades ?? 0) >= metricFilters.minTrades!);
    }
    if (metricFilters.maxTrades !== undefined) {
      filtered = filtered.filter((o) => (o.total_trades ?? 0) <= metricFilters.maxTrades!);
    }
    if (metricFilters.minScore !== undefined) {
      filtered = filtered.filter((o) => (o.overall_score ?? 0) >= metricFilters.minScore!);
    }
    if (metricFilters.maxScore !== undefined) {
      filtered = filtered.filter((o) => (o.overall_score ?? 100) <= metricFilters.maxScore!);
    }

    return filtered;
  }, [orders, search, sideFilter, metricFilters]);

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

  // 重置所有筛选
  const handleReset = () => {
    setSearch("");
    setSideFilter("");
    setActionFilter("");
    setStatusFilter("");
    setTargetFilter("");
    setDaysFilter(7);
    setMetricFilters(emptyMetricFilters);
    setPage(1);
  };

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
          <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
            跟单订单
          </h1>
          <p className="text-default-500">
            查看所有跟单交易的开仓/平仓订单记录
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
          metricFilters={metricFilters}
          onMetricFiltersChange={setMetricFilters}
          onReset={handleReset}
        />

        {/* 显示筛选结果数量 */}
        {!loading && (
          <div className="mb-4 text-sm text-default-500">
            显示 {filteredOrders.length} / {orders.length} 条订单记录
          </div>
        )}

        {/* Orders Table */}
        <OrdersTable
          orders={filteredOrders}
          loading={loading}
          pagination={pagination}
          onPageChange={handlePageChange}
        />
      </div>
    </DefaultLayout>
  );
}
