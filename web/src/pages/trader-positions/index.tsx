import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, addToast, Spinner } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import {
  traderPositionsApi,
  copyTradingApi,
  TraderPosition,
  TraderPositionsStats,
  CopyTradingGroup,
} from "@/services/api";

import { StatsCards, PositionFilters, PositionsTable, CoinSummary } from "./components";

export default function TraderPositionsPage() {
  // 数据状态
  const [positions, setPositions] = useState<TraderPosition[]>([]);
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
      const params: Record<string, any> = {
        enabled_only: true,
      };

      if (groupFilter !== "all") {
        params.group_id = parseInt(groupFilter);
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
  }, [groupFilter]);

  // 刷新持仓数据（从 Hyperliquid API）
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await traderPositionsApi.refresh(true);

      if (response.success) {
        addToast({
          title: "刷新成功",
          description: response.message || `已刷新 ${response.data?.refreshed_count} 个交易员的持仓`,
          color: "success",
        });
        // 重新加载数据
        await fetchPositions();
      }
    } catch (error) {
      console.error("Failed to refresh positions:", error);
      addToast({
        title: "刷新失败",
        description: "无法从 Hyperliquid 获取最新数据",
        color: "danger",
      });
    } finally {
      setRefreshing(false);
    }
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

    return filtered;
  }, [positions, search, sideFilter, traderFilter, coinFilter]);

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
              查看所有跟单交易员的当前持仓情况
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
            <Button
              color="default"
              variant="flat"
              startContent={<Icon icon="solar:refresh-linear" width={18} />}
              onPress={() => fetchPositions()}
              isDisabled={loading}
            >
              重新加载
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
          stats={stats}
          groups={groups}
        />

        {/* 显示筛选结果数量 */}
        {!loading && (
          <div className="mb-4 text-sm text-default-500">
            显示 {filteredPositions.length} / {positions.length} 条持仓记录
          </div>
        )}

        {/* Positions Table */}
        <PositionsTable positions={filteredPositions} loading={loading} />
      </div>
    </DefaultLayout>
  );
}
