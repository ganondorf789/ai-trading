import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, addToast, useDisclosure } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { 
  copyPositionStatesApi, 
  copyTradingApi,
  CopyPositionState, 
  CopyPositionStats,
  CopyTradingAddress 
} from "@/services/api";
import { MetricFilterConfig, emptyMetricFilters } from "@/components/filters";

import { StatsCards } from "./components/StatsCards";
import { PositionFilters } from "./components/PositionFilters";
import { PositionsTable } from "./components/PositionsTable";
import { DeleteConfirmModal } from "./components/DeleteConfirmModal";
import { ClearAllModal } from "./components/ClearAllModal";

// 扩展仓位类型，包含交易员指标
interface CopyPositionStateWithMetrics extends CopyPositionState {
  win_rate?: number;
  trader_pnl?: number;
  overall_score?: number;
  total_trades?: number;
  profit_factor?: number;
  max_drawdown?: number;
  sharpe_ratio?: number;
  is_starred?: boolean;
}

export default function PositionsPage() {
  // 数据状态
  const [positions, setPositions] = useState<CopyPositionStateWithMetrics[]>([]);
  const [stats, setStats] = useState<CopyPositionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [addressMetrics, setAddressMetrics] = useState<Map<string, CopyTradingAddress>>(new Map());

  // 筛选状态
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<string>("all");
  const [targetFilter, setTargetFilter] = useState<string>("all");
  const [starFilter, setStarFilter] = useState<string>("all");
  const [metricFilters, setMetricFilters] = useState<MetricFilterConfig>(emptyMetricFilters);

  // 删除确认弹窗
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<{ address: string; symbol?: string } | null>(null);
  const [clearAllOpen, setClearAllOpen] = useState(false);

  // 加载跟单地址及其指标
  const fetchAddressMetrics = useCallback(async () => {
    try {
      const response = await copyTradingApi.getAddresses({ limit: 1000 });
      if (response.success && response.data) {
        const metricsMap = new Map<string, CopyTradingAddress>();
        response.data.forEach(addr => {
          metricsMap.set(addr.address, addr);
        });
        setAddressMetrics(metricsMap);
      }
    } catch (error) {
      console.error("Failed to fetch address metrics:", error);
    }
  }, []);

  // 加载仓位列表
  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {};

      if (targetFilter !== "all") {
        params.target_address = targetFilter;
      }

      const response = await copyPositionStatesApi.getPositions(params);

      if (response.success && response.data) {
        // 合并交易员指标到仓位数据
        const positionsWithMetrics = response.data.map(pos => {
          const addrMetrics = addressMetrics.get(pos.target_address);
          return {
            ...pos,
            win_rate: addrMetrics?.win_rate,
            trader_pnl: addrMetrics?.trader_pnl,
            overall_score: addrMetrics?.overall_score,
            total_trades: addrMetrics?.total_trades,
            profit_factor: addrMetrics?.profit_factor,
            max_drawdown: addrMetrics?.max_drawdown,
            sharpe_ratio: addrMetrics?.sharpe_ratio,
            is_starred: addrMetrics?.is_starred,
          };
        });

        setPositions(positionsWithMetrics);
      }
    } catch (error) {
      console.error("Failed to fetch positions:", error);
      addToast({
        title: "Error",
        description: "Failed to load positions",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [targetFilter, addressMetrics]);

  // 应用本地筛选（包括指标筛选）
  const filteredPositions = useMemo(() => {
    let filtered = positions;

    // 搜索筛选
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.symbol.toLowerCase().includes(searchLower) ||
          p.target_address.toLowerCase().includes(searchLower) ||
          (p.target_name && p.target_name.toLowerCase().includes(searchLower))
      );
    }

    // 方向筛选
    if (sideFilter !== "all") {
      filtered = filtered.filter((p) => p.side === sideFilter);
    }

    // 收藏筛选
    if (starFilter === "starred") {
      filtered = filtered.filter((p) => p.is_starred === true);
    } else if (starFilter === "unstarred") {
      filtered = filtered.filter((p) => !p.is_starred);
    }

    // 指标筛选
    if (metricFilters.minWinRate !== undefined) {
      filtered = filtered.filter((p) => (p.win_rate ?? 0) >= metricFilters.minWinRate!);
    }
    if (metricFilters.maxWinRate !== undefined) {
      filtered = filtered.filter((p) => (p.win_rate ?? 100) <= metricFilters.maxWinRate!);
    }
    if (metricFilters.minProfitFactor !== undefined) {
      filtered = filtered.filter((p) => (p.profit_factor ?? 0) >= metricFilters.minProfitFactor!);
    }
    if (metricFilters.maxProfitFactor !== undefined) {
      filtered = filtered.filter((p) => (p.profit_factor ?? 999) <= metricFilters.maxProfitFactor!);
    }
    if (metricFilters.minPnl !== undefined) {
      filtered = filtered.filter((p) => (p.trader_pnl ?? 0) >= metricFilters.minPnl!);
    }
    if (metricFilters.maxPnl !== undefined) {
      filtered = filtered.filter((p) => (p.trader_pnl ?? 0) <= metricFilters.maxPnl!);
    }
    if (metricFilters.minDrawdown !== undefined) {
      filtered = filtered.filter((p) => (p.max_drawdown ?? 0) >= metricFilters.minDrawdown!);
    }
    if (metricFilters.maxDrawdown !== undefined) {
      filtered = filtered.filter((p) => (p.max_drawdown ?? 100) <= metricFilters.maxDrawdown!);
    }
    if (metricFilters.minSharpe !== undefined) {
      filtered = filtered.filter((p) => (p.sharpe_ratio ?? -999) >= metricFilters.minSharpe!);
    }
    if (metricFilters.maxSharpe !== undefined) {
      filtered = filtered.filter((p) => (p.sharpe_ratio ?? 999) <= metricFilters.maxSharpe!);
    }
    if (metricFilters.minTrades !== undefined) {
      filtered = filtered.filter((p) => (p.total_trades ?? 0) >= metricFilters.minTrades!);
    }
    if (metricFilters.maxTrades !== undefined) {
      filtered = filtered.filter((p) => (p.total_trades ?? 0) <= metricFilters.maxTrades!);
    }
    if (metricFilters.minScore !== undefined) {
      filtered = filtered.filter((p) => (p.overall_score ?? 0) >= metricFilters.minScore!);
    }
    if (metricFilters.maxScore !== undefined) {
      filtered = filtered.filter((p) => (p.overall_score ?? 100) <= metricFilters.maxScore!);
    }

    return filtered;
  }, [positions, search, sideFilter, starFilter, metricFilters]);

  // 加载统计数据
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await copyPositionStatesApi.getStats();

      if (response.success && response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // 重置所有筛选
  const handleReset = () => {
    setSearch("");
    setSideFilter("all");
    setTargetFilter("all");
    setStarFilter("all");
    setMetricFilters(emptyMetricFilters);
  };

  // 删除单个仓位
  const handleDeletePosition = async () => {
    if (!deleteTarget) return;

    try {
      if (deleteTarget.symbol) {
        // 删除单个仓位
        const response = await copyPositionStatesApi.deletePosition(
          deleteTarget.address,
          deleteTarget.symbol
        );

        if (response.success) {
          addToast({
            title: "Success",
            description: response.message || "Position deleted",
            color: "success",
          });
          fetchPositions();
          fetchStats();
        }
      } else {
        // 清空目标所有仓位
        const response = await copyPositionStatesApi.clearTargetPositions(deleteTarget.address);

        if (response.success) {
          addToast({
            title: "Success",
            description: response.message || "All positions cleared",
            color: "success",
          });
          fetchPositions();
          fetchStats();
        }
      }
    } catch (error) {
      console.error("Failed to delete position:", error);
      addToast({
        title: "Error",
        description: "Failed to delete position",
        color: "danger",
      });
    } finally {
      onClose();
      setDeleteTarget(null);
    }
  };

  // 清空所有仓位
  const handleClearAll = async () => {
    try {
      const response = await copyPositionStatesApi.clearAll();

      if (response.success) {
        addToast({
          title: "Success",
          description: response.message || "All positions cleared",
          color: "success",
        });
        fetchPositions();
        fetchStats();
      }
    } catch (error) {
      console.error("Failed to clear all positions:", error);
      addToast({
        title: "Error",
        description: "Failed to clear all positions",
        color: "danger",
      });
    } finally {
      setClearAllOpen(false);
    }
  };

  // 处理删除单个仓位按钮点击
  const handleDeleteClick = (address: string, symbol: string) => {
    setDeleteTarget({ address, symbol });
    onOpen();
  };

  // 处理清空目标所有仓位按钮点击
  const handleClearTargetClick = (address: string) => {
    setDeleteTarget({ address });
    onOpen();
  };

  useEffect(() => {
    fetchAddressMetrics();
  }, [fetchAddressMetrics]);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              仓位管理
            </h1>
            <p className="text-default-500">
              管理跟单仓位状态（用于重启后恢复）
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              color="danger"
              startContent={<Icon icon="solar:trash-bin-trash-linear" width={18} />}
              variant="flat"
              onPress={() => setClearAllOpen(true)}
            >
              清空全部
            </Button>
            <Button
              color="primary"
              startContent={<Icon icon="solar:refresh-linear" width={18} />}
              variant="flat"
              onPress={() => {
                fetchPositions();
                fetchStats();
              }}
            >
              刷新
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <StatsCards stats={stats} loading={statsLoading} />

        {/* Filters */}
        <PositionFilters
          search={search}
          onSearchChange={setSearch}
          sideFilter={sideFilter}
          onSideFilterChange={setSideFilter}
          targetFilter={targetFilter}
          onTargetFilterChange={setTargetFilter}
          starFilter={starFilter}
          onStarFilterChange={setStarFilter}
          stats={stats}
          metricFilters={metricFilters}
          onMetricFiltersChange={setMetricFilters}
          onReset={handleReset}
        />

        {/* 显示筛选结果数量 */}
        {!loading && (
          <div className="mb-4 text-sm text-default-500">
            显示 {filteredPositions.length} / {positions.length} 条仓位记录
          </div>
        )}

        {/* Positions Table */}
        <PositionsTable
          positions={filteredPositions}
          loading={loading}
          onDeletePosition={handleDeleteClick}
          onClearTarget={handleClearTargetClick}
        />

        {/* Delete Confirmation Modal */}
        <DeleteConfirmModal
          isOpen={isOpen}
          onClose={onClose}
          onConfirm={handleDeletePosition}
          deleteTarget={deleteTarget}
        />

        {/* Clear All Confirmation Modal */}
        <ClearAllModal
          isOpen={clearAllOpen}
          onClose={() => setClearAllOpen(false)}
          onConfirm={handleClearAll}
        />
      </div>
    </DefaultLayout>
  );
}
