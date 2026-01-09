import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, addToast, Spinner } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import {
  traderPositionsApi,
  copyTradingApi,
  traderApi,
  TraderPosition,
  TraderPositionsStats,
  CopyTradingGroup,
  CopyTradingAddress,
} from "@/services/api";
import { MetricFilterConfig, emptyMetricFilters } from "@/components/filters";

import { StatsCards, PositionFilters, PositionsTable, CoinSummary } from "./components";

// 扩展 TraderPosition 类型，包含交易员指标
interface TraderPositionWithMetrics extends TraderPosition {
  // 这些字段已经从后端返回，不需要前端合并
}

export default function TraderPositionsPage() {
  // 数据状态
  const [positions, setPositions] = useState<TraderPositionWithMetrics[]>([]);
  const [stats, setStats] = useState<TraderPositionsStats | null>(null);
  const [groups, setGroups] = useState<CopyTradingGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // 筛选状态
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<string>("all");
  const [traderFilter, setTraderFilter] = useState<string>("all");
  const [coinFilter, setCoinFilter] = useState<string>("all");
  const [groupFilter, setGroupFilter] = useState<string>("all");
  const [starFilter, setStarFilter] = useState<string>("all");
  const [metricFilters, setMetricFilters] = useState<MetricFilterConfig>(emptyMetricFilters);

  // 加载分组数据
  const fetchGroups = useCallback(async () => {
    try {
      const response = await copyTradingApi.getGroups();
      if (response.success && response.data) {
        setGroups(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch groups:", error);
    }
  }, []);

  // 加载持仓数据
  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {};

      if (groupFilter !== "all") {
        params.group_id = parseInt(groupFilter);
      }

      // 添加指标筛选参数
      if (metricFilters.minWinRate !== undefined) {
        params.min_win_rate = metricFilters.minWinRate;
      }
      if (metricFilters.maxWinRate !== undefined) {
        params.max_win_rate = metricFilters.maxWinRate;
      }
      if (metricFilters.minProfitFactor !== undefined) {
        params.min_profit_factor = metricFilters.minProfitFactor;
      }
      if (metricFilters.maxProfitFactor !== undefined) {
        params.max_profit_factor = metricFilters.maxProfitFactor;
      }
      if (metricFilters.minPnl !== undefined) {
        params.min_pnl = metricFilters.minPnl;
      }
      if (metricFilters.maxPnl !== undefined) {
        params.max_pnl = metricFilters.maxPnl;
      }
      if (metricFilters.minDrawdown !== undefined) {
        params.min_drawdown = metricFilters.minDrawdown;
      }
      if (metricFilters.maxDrawdown !== undefined) {
        params.max_drawdown = metricFilters.maxDrawdown;
      }
      if (metricFilters.minSharpe !== undefined) {
        params.min_sharpe = metricFilters.minSharpe;
      }
      if (metricFilters.maxSharpe !== undefined) {
        params.max_sharpe = metricFilters.maxSharpe;
      }
      if (metricFilters.minSortino !== undefined) {
        params.min_sortino = metricFilters.minSortino;
      }
      if (metricFilters.maxSortino !== undefined) {
        params.max_sortino = metricFilters.maxSortino;
      }
      if (metricFilters.minTrades !== undefined) {
        params.min_trades = metricFilters.minTrades;
      }
      if (metricFilters.maxTrades !== undefined) {
        params.max_trades = metricFilters.maxTrades;
      }
      if (metricFilters.minScore !== undefined) {
        params.min_score = metricFilters.minScore;
      }
      if (metricFilters.maxScore !== undefined) {
        params.max_score = metricFilters.maxScore;
      }

      const response = await traderPositionsApi.getPositions(params);

      if (response.success && response.data) {
        setPositions(response.data);
        if (response.stats) {
          setStats(response.stats);
        }
      }
    } catch (error) {
      console.error("Failed to fetch positions:", error);
      addToast({
        title: "加载失败",
        description: "无法获取持仓数据",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [groupFilter, metricFilters]);

  // 刷新持仓数据（从 Hyperliquid API）
  const handleRefresh = async () => {
    addToast({
      title: "提示",
      description: "批量刷新功能已禁用，请使用单个交易员刷新",
      color: "warning",
    });
  };

  // 刷新单个交易员的持仓数据
  const handleRefreshTrader = useCallback(async (address: string) => {
    try {
      const response = await traderApi.refreshTraderPositions(address);

      if (response.success) {
        addToast({
          title: "刷新成功",
          description: response.message || `已刷新交易员持仓`,
          color: "success",
        });
        // 重新加载数据
        await fetchPositions();
      }
    } catch (error) {
      console.error("Failed to refresh trader positions:", error);
      addToast({
        title: "刷新失败",
        description: "无法从 Hyperliquid 获取最新数据",
        color: "danger",
      });
    }
  }, [fetchPositions]);

  // 收藏状态
  const [starLoadingAddresses, setStarLoadingAddresses] = useState<Set<string>>(new Set());

  // 切换收藏状态
  const handleToggleStar = useCallback(async (address: string, isStarred: boolean) => {
    setStarLoadingAddresses(prev => new Set(prev).add(address));
    try {
      const response = await traderApi.toggleStar(address, isStarred);
      if (response.success) {
        // 更新本地状态
        setPositions(prev => prev.map(p => 
          p.address === address ? { ...p, is_starred: isStarred } : p
        ));
        addToast({
          title: isStarred ? "已收藏" : "已取消收藏",
          color: "success",
        });
      }
    } catch (error) {
      console.error("Toggle star failed:", error);
      addToast({
        title: "操作失败",
        color: "danger",
      });
    } finally {
      setStarLoadingAddresses(prev => {
        const next = new Set(prev);
        next.delete(address);
        return next;
      });
    }
  }, []);

  // 重置所有筛选
  const handleReset = () => {
    setSearch("");
    setSideFilter("all");
    setTraderFilter("all");
    setCoinFilter("all");
    setGroupFilter("all");
    setStarFilter("all");
    setMetricFilters(emptyMetricFilters);
  };

  // 应用本地筛选
  const filteredPositions = useMemo(() => {
    let filtered = positions;

    // 搜索筛选
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.coin.toLowerCase().includes(searchLower) ||
          p.address.toLowerCase().includes(searchLower) ||
          (p.trader_name && p.trader_name.toLowerCase().includes(searchLower))
      );
    }

    // 方向筛选
    if (sideFilter !== "all") {
      filtered = filtered.filter((p) =>
        sideFilter === "long" ? p.szi > 0 : p.szi < 0
      );
    }

    // 交易员筛选
    if (traderFilter !== "all") {
      filtered = filtered.filter((p) => p.address === traderFilter);
    }

    // 币种筛选
    if (coinFilter !== "all") {
      filtered = filtered.filter((p) => p.coin === coinFilter);
    }

    // 收藏筛选
    if (starFilter === "starred") {
      filtered = filtered.filter((p) => p.is_starred === true);
    } else if (starFilter === "unstarred") {
      filtered = filtered.filter((p) => !p.is_starred);
    }

    return filtered;
  }, [positions, search, sideFilter, traderFilter, coinFilter, starFilter]);

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              交易员持仓
            </h1>
            <p className="text-default-500">
              查看符合筛选条件的交易员的当前持仓情况
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              color="primary"
              variant="flat"
              startContent={
                refreshing ? (
                  <Spinner size="sm" color="current" />
                ) : (
                  <Icon icon="solar:refresh-bold-duotone" width={18} />
                )
              }
              onPress={handleRefresh}
              isDisabled={refreshing}
            >
              {refreshing ? "刷新中..." : "刷新数据"}
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <StatsCards stats={stats} loading={loading && positions.length === 0} />

        {/* Coin Summary */}
        <CoinSummary stats={stats} />

        {/* Filters */}
        <PositionFilters
          search={search}
          onSearchChange={setSearch}
          sideFilter={sideFilter}
          onSideFilterChange={setSideFilter}
          traderFilter={traderFilter}
          onTraderFilterChange={setTraderFilter}
          coinFilter={coinFilter}
          onCoinFilterChange={setCoinFilter}
          groupFilter={groupFilter}
          onGroupFilterChange={(value) => {
            setGroupFilter(value);
            // 重置其他筛选
            setTraderFilter("all");
          }}
          starFilter={starFilter}
          onStarFilterChange={setStarFilter}
          stats={stats}
          groups={groups}
          metricFilters={metricFilters}
          onMetricFiltersChange={setMetricFilters}
          onReset={handleReset}
        />

        {/* 显示筛选结果数量 */}
        {!loading && (
          <div className="mb-4 text-sm text-default-500">
            显示 {filteredPositions.length} / {positions.length} 条持仓记录
          </div>
        )}

        {/* Positions Table */}
        <PositionsTable 
          positions={filteredPositions} 
          loading={loading} 
          onRefreshTrader={handleRefreshTrader}
          onToggleStar={handleToggleStar}
          starLoadingAddresses={starLoadingAddresses}
        />
      </div>
    </DefaultLayout>
  );
}
