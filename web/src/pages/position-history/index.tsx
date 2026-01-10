import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, Spinner } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import {
  positionHistoryApi,
  GlobalPositionHistoryRecord,
  GlobalPositionHistoryStats,
  PositionHistoryByCoin,
} from "@/services/api";

import { StatsCards, PositionFilters, PositionsTable, CoinSummary } from "./components";

export default function PositionHistoryPage() {
  // 数据状态
  const [positions, setPositions] = useState<GlobalPositionHistoryRecord[]>([]);
  const [stats, setStats] = useState<GlobalPositionHistoryStats | null>(null);
  const [byCoin, setByCoin] = useState<PositionHistoryByCoin[]>([]);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [directionFilter, setDirectionFilter] = useState<string>("all");
  const [coinFilter, setCoinFilter] = useState<string>("all");
  const [pnlFilter, setPnlFilter] = useState<string>("all");

  // 加载数据
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [positionsRes, byCoinRes] = await Promise.all([
        positionHistoryApi.getAll({
          status: statusFilter !== 'all' ? statusFilter as 'open' | 'closed' : undefined,
          direction: directionFilter !== 'all' ? directionFilter as 'long' | 'short' : undefined,
          coin: coinFilter !== 'all' ? coinFilter : undefined,
          limit: 1000,
        }),
        positionHistoryApi.getByCoin(),
      ]);

      if (positionsRes.success && positionsRes.data) {
        setPositions(positionsRes.data);
        if (positionsRes.stats) {
          setStats(positionsRes.stats);
        }
      }

      if (byCoinRes.success && byCoinRes.data) {
        setByCoin(byCoinRes.data);
      }
    } catch (error) {
      console.error("Failed to fetch position history:", error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, directionFilter, coinFilter]);

  // 重置所有筛选
  const handleReset = () => {
    setSearch("");
    setStatusFilter("all");
    setDirectionFilter("all");
    setCoinFilter("all");
    setPnlFilter("all");
  };

  // 应用本地筛选
  const filteredPositions = useMemo(() => {
    let filtered = positions;

    // 搜索筛选
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.address.toLowerCase().includes(searchLower) ||
          (p.trader_name && p.trader_name.toLowerCase().includes(searchLower))
      );
    }

    // 盈亏筛选
    if (pnlFilter === "profit") {
      filtered = filtered.filter((p) => (p.realized_pnl || 0) > 0);
    } else if (pnlFilter === "loss") {
      filtered = filtered.filter((p) => (p.realized_pnl || 0) < 0);
    }

    return filtered;
  }, [positions, search, pnlFilter]);

  // 根据筛选后的数据计算统计信息
  const filteredStats = useMemo((): GlobalPositionHistoryStats | null => {
    if (!stats) return null;
    if (filteredPositions.length === positions.length) return stats;

    // 重新计算统计
    const uniqueTraders = new Set(filteredPositions.map(p => p.address));
    const longPositions = filteredPositions.filter(p => p.direction === 'long');
    const shortPositions = filteredPositions.filter(p => p.direction === 'short');
    const closedPositions = filteredPositions.filter(p => p.status === 'closed');
    const openPositions = filteredPositions.filter(p => p.status === 'open');
    const winningPositions = closedPositions.filter(p => (p.realized_pnl || 0) > 0);
    const losingPositions = closedPositions.filter(p => (p.realized_pnl || 0) < 0);

    const totalPnl = filteredPositions.reduce((sum, p) => sum + (p.realized_pnl || 0), 0);
    const totalProfit = winningPositions.reduce((sum, p) => sum + (p.realized_pnl || 0), 0);
    const totalLoss = losingPositions.reduce((sum, p) => sum + (p.realized_pnl || 0), 0);
    const totalVolume = filteredPositions.reduce((sum, p) => sum + (p.total_volume || 0), 0);
    const totalFees = filteredPositions.reduce((sum, p) => sum + (p.total_fee || 0), 0);
    const avgHoldingHours = closedPositions.length > 0
      ? closedPositions.reduce((sum, p) => sum + (p.holding_hours || 0), 0) / closedPositions.length
      : 0;

    const uniqueCoins = new Set(filteredPositions.map(p => p.coin));

    return {
      ...stats,
      total_positions: filteredPositions.length,
      total_traders: uniqueTraders.size,
      closed_positions: closedPositions.length,
      open_positions: openPositions.length,
      long_count: longPositions.length,
      short_count: shortPositions.length,
      winning_positions: winningPositions.length,
      losing_positions: losingPositions.length,
      win_rate: closedPositions.length > 0 ? winningPositions.length / closedPositions.length : 0,
      total_pnl: totalPnl,
      total_profit: totalProfit,
      total_loss: totalLoss,
      total_volume: totalVolume,
      total_fees: totalFees,
      avg_holding_hours: avgHoldingHours,
      unique_coins: uniqueCoins.size,
    };
  }, [filteredPositions, positions, stats]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              仓位历史
            </h1>
            <p className="text-default-500">
              查看所有交易员的历史仓位记录和统计信息
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              color="primary"
              variant="flat"
              startContent={
                loading ? (
                  <Spinner size="sm" color="current" />
                ) : (
                  <Icon icon="solar:refresh-bold-duotone" width={18} />
                )
              }
              onPress={fetchData}
              isDisabled={loading}
            >
              {loading ? "加载中..." : "刷新数据"}
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <StatsCards stats={filteredStats} loading={loading && positions.length === 0} />

        {/* Coin Summary */}
        <CoinSummary byCoin={byCoin} />

        {/* Filters */}
        <PositionFilters
          search={search}
          onSearchChange={setSearch}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          directionFilter={directionFilter}
          onDirectionFilterChange={setDirectionFilter}
          coinFilter={coinFilter}
          onCoinFilterChange={setCoinFilter}
          pnlFilter={pnlFilter}
          onPnlFilterChange={setPnlFilter}
          byCoin={byCoin}
          onReset={handleReset}
        />

        {/* 显示筛选结果数量 */}
        {!loading && (
          <div className="mb-4 text-sm text-default-500">
            显示 {filteredPositions.length} / {positions.length} 条仓位历史记录
          </div>
        )}

        {/* Positions Table */}
        <PositionsTable positions={filteredPositions} loading={loading} />
      </div>
    </DefaultLayout>
  );
}
