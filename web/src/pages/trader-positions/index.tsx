import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Button, addToast } from "@heroui/react";
import type { Selection, SortDescriptor, DateValue, RangeValue } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import {
  traderPositionsApi,
  traderApi,
  TraderPosition,
} from "@/services/api";
import type { TraderPositionsStats } from "@/types/api";
import { useTimeRange } from "@/components/TimeRangeFilter";

import { StatsCards, PositionFilters, PositionsTable, CoinSummary } from "./components";
import { INITIAL_VISIBLE_COLUMNS } from "./components/PositionFilters";

// 扩展 TraderPosition 类型，包含交易员指标
interface TraderPositionWithMetrics extends TraderPosition {
  // 这些字段已经从后端返回，不需要前端合并
}

export default function TraderPositionsPage() {
  // 数据状态
  const [positions, setPositions] = useState<TraderPositionWithMetrics[]>([]);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<string>("all");
  const [coinFilter, setCoinFilter] = useState<string>("all");
  const [starFilter, setStarFilter] = useState<string>("all");
  const [pnlFilter, setPnlFilter] = useState<string>("all");
  const [scoreFilter, setScoreFilter] = useState<string>("all");
  // 开仓时间筛选状态
  const [openTimeFilter, setOpenTimeFilter] = useState<string>("");
  const [openTimeDateRange, setOpenTimeDateRange] = useState<RangeValue<DateValue> | null>(null);
  const openTimeRange = useTimeRange(openTimeFilter, openTimeDateRange);

  // 排序和列可见性状态
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'unrealized_pnl',
    direction: 'descending',
  });
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));

  // 加载持仓数据（获取最近10分钟内更新的数据）
  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await traderPositionsApi.getPositions({ minutes: 10 });

      if (response.success && response.data) {
        setPositions(response.data);
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
  }, []);

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
    setCoinFilter("all");
    setStarFilter("all");
    setPnlFilter("all");
    setScoreFilter("all");
    setOpenTimeFilter("all");
    setOpenTimeDateRange(null);
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

    // 盈亏筛选（基于未实现盈亏）
    if (pnlFilter === "profit") {
      filtered = filtered.filter((p) => (p.unrealized_pnl || 0) > 0);
    } else if (pnlFilter === "loss") {
      filtered = filtered.filter((p) => (p.unrealized_pnl || 0) < 0);
    }

    // 评级筛选（基于交易员评级）
    if (scoreFilter !== "all" && scoreFilter) {
      filtered = filtered.filter((p) => p.rating === scoreFilter);
    }

    // 开仓时间筛选
    if (openTimeRange.startTime || openTimeRange.endTime) {
      filtered = filtered.filter((p) => {
        if (!p.open_time) return false;
        const openTime = new Date(p.open_time).getTime();
        if (openTimeRange.startTime && openTime < new Date(openTimeRange.startTime).getTime()) {
          return false;
        }
        if (openTimeRange.endTime && openTime > new Date(openTimeRange.endTime).getTime()) {
          return false;
        }
        return true;
      });
    }

    return filtered;
  }, [positions, search, sideFilter, coinFilter, starFilter, pnlFilter, scoreFilter, openTimeRange]);

  // 计算统计信息的通用函数
  const computeStats = useCallback((positionList: TraderPositionWithMetrics[]): TraderPositionsStats => {
    if (positionList.length === 0) {
      return {
        total_positions: 0,
        total_traders: 0,
        total_notional: 0,
        long_count: 0,
        short_count: 0,
        long_notional: 0,
        short_notional: 0,
        total_unrealized_pnl: 0,
        profit_count: 0,
        loss_count: 0,
        profit_pnl: 0,
        loss_pnl: 0,
        by_coin: [],
        by_trader: [],
      };
    }

    // 计算基础统计
    const uniqueTraders = new Set(positionList.map(p => p.address));
    const longPositions = positionList.filter(p => p.szi > 0);
    const shortPositions = positionList.filter(p => p.szi < 0);

    // 计算盈亏统计
    const profitPositions = positionList.filter(p => (p.unrealized_pnl || 0) > 0);
    const lossPositions = positionList.filter(p => (p.unrealized_pnl || 0) < 0);
    const totalUnrealizedPnl = positionList.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const profitPnl = profitPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const lossPnl = lossPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);

    // 按币种分组统计
    const coinMap = new Map<string, { count: number; notional: number; long: number; short: number }>();
    positionList.forEach(p => {
      const existing = coinMap.get(p.coin) || { count: 0, notional: 0, long: 0, short: 0 };
      existing.count += 1;
      existing.notional += p.position_value || 0;
      if (p.szi > 0) {
        existing.long += 1;
      } else {
        existing.short += 1;
      }
      coinMap.set(p.coin, existing);
    });

    // 按交易员分组统计
    const traderMap = new Map<string, { name: string | null; count: number; notional: number }>();
    positionList.forEach(p => {
      const existing = traderMap.get(p.address) || { name: p.trader_name, count: 0, notional: 0 };
      existing.count += 1;
      existing.notional += p.position_value || 0;
      traderMap.set(p.address, existing);
    });

    // 转换为数组并排序
    const byCoin = Array.from(coinMap.entries())
      .map(([coin, data]) => ({ coin, ...data }))
      .sort((a, b) => b.notional - a.notional);

    const byTrader = Array.from(traderMap.entries())
      .map(([address, data]) => ({ address, ...data }))
      .sort((a, b) => b.notional - a.notional);

    return {
      total_positions: positionList.length,
      total_traders: uniqueTraders.size,
      total_notional: positionList.reduce((sum, p) => sum + (p.position_value || 0), 0),
      long_count: longPositions.length,
      short_count: shortPositions.length,
      long_notional: longPositions.reduce((sum, p) => sum + (p.position_value || 0), 0),
      short_notional: shortPositions.reduce((sum, p) => sum + (p.position_value || 0), 0),
      total_unrealized_pnl: totalUnrealizedPnl,
      profit_count: profitPositions.length,
      loss_count: lossPositions.length,
      profit_pnl: profitPnl,
      loss_pnl: lossPnl,
      by_coin: byCoin,
      by_trader: byTrader,
    };
  }, []);

  // 全部数据的统计信息（用于筛选选项）
  const allStats = useMemo(() => computeStats(positions), [positions, computeStats]);

  // 根据筛选后的数据计算统计信息
  const filteredStats = useMemo(() => computeStats(filteredPositions), [filteredPositions, computeStats]);

  // 防止 React StrictMode 下重复请求
  const hasFetched = useRef(false);
  useEffect(() => {
    if (hasFetched.current) return;
    hasFetched.current = true;
    fetchPositions();
  }, [fetchPositions]);

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-4">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Icon icon="lucide:wallet" width={28} />
              交易员持仓
            </h1>
          </div>
          <div className="flex gap-2">
            <Button
              color="primary"
              variant="flat"
              startContent={<Icon icon="solar:refresh-bold-duotone" width={18} />}
              onPress={handleRefresh}
            >
              刷新数据
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <StatsCards stats={filteredStats} loading={loading && positions.length === 0} />

        {/* Coin Summary */}
        <CoinSummary stats={filteredStats} />

        {/* Filters */}
        <PositionFilters
          search={search}
          onSearchChange={setSearch}
          sideFilter={sideFilter}
          onSideFilterChange={setSideFilter}
          coinFilter={coinFilter}
          onCoinFilterChange={setCoinFilter}
          starFilter={starFilter}
          onStarFilterChange={setStarFilter}
          pnlFilter={pnlFilter}
          onPnlFilterChange={setPnlFilter}
          scoreFilter={scoreFilter}
          onScoreFilterChange={setScoreFilter}
          openTimeFilter={openTimeFilter}
          onOpenTimeFilterChange={setOpenTimeFilter}
          openTimeDateRange={openTimeDateRange}
          onOpenTimeDateRangeChange={setOpenTimeDateRange}
          stats={allStats}
          onReset={handleReset}
          sortDescriptor={sortDescriptor}
          onSortChange={setSortDescriptor}
          visibleColumns={visibleColumns}
          onVisibleColumnsChange={setVisibleColumns}
        />

        {/* Positions Table */}
        <PositionsTable 
          positions={filteredPositions} 
          loading={loading} 
          onRefreshTrader={handleRefreshTrader}
          onToggleStar={handleToggleStar}
          starLoadingAddresses={starLoadingAddresses}
          visibleColumns={visibleColumns}
          sortDescriptor={sortDescriptor}
          onSortChange={setSortDescriptor}
        />
      </div>
    </DefaultLayout>
  );
}
