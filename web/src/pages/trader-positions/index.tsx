import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, addToast, Spinner, Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import {
  traderPositionsApi,
  copyTradingApi,
  traderApi,
  TraderPosition,
  TraderPositionsStats,
  CopyTradingGroup,
  PositionsAIAnalysis,
} from "@/services/api";
import { MetricFilterConfig, emptyMetricFilters } from "@/components/filters";

import { StatsCards, PositionFilters, PositionsTable, CoinSummary, PositionsAIAnalysisModal } from "./components";

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
  const [pnlFilter, setPnlFilter] = useState<string>("all");
  const [scoreFilter, setScoreFilter] = useState<string>("all");
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
    setPnlFilter("all");
    setScoreFilter("all");
    setMetricFilters(emptyMetricFilters);
  };

  // ==================== AI 分析状态 ====================
  const [aiAnalysisOpen, setAiAnalysisOpen] = useState(false);
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [aiAnalysisData, setAiAnalysisData] = useState<PositionsAIAnalysis | null>(null);
  const [aiAnalysisType, setAiAnalysisType] = useState<'overall' | 'coin' | 'single'>('overall');
  const [aiAnalysisCoin, setAiAnalysisCoin] = useState<string>('');
  const [aiAnalysisCached, setAiAnalysisCached] = useState(false);  // 是否是缓存的结果
  const [aiAnalysisTime, setAiAnalysisTime] = useState<string | undefined>();  // 分析时间

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

    return filtered;
  }, [positions, search, sideFilter, traderFilter, coinFilter, starFilter, pnlFilter, scoreFilter]);

  // 根据筛选后的数据计算统计信息
  const filteredStats = useMemo((): TraderPositionsStats | null => {
    if (filteredPositions.length === 0) {
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
    const uniqueTraders = new Set(filteredPositions.map(p => p.address));
    const longPositions = filteredPositions.filter(p => p.szi > 0);
    const shortPositions = filteredPositions.filter(p => p.szi < 0);

    // 计算盈亏统计
    const profitPositions = filteredPositions.filter(p => (p.unrealized_pnl || 0) > 0);
    const lossPositions = filteredPositions.filter(p => (p.unrealized_pnl || 0) < 0);
    const totalUnrealizedPnl = filteredPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const profitPnl = profitPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
    const lossPnl = lossPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);

    // 按币种分组统计
    const coinMap = new Map<string, { count: number; notional: number; long: number; short: number }>();
    filteredPositions.forEach(p => {
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
    filteredPositions.forEach(p => {
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
      total_positions: filteredPositions.length,
      total_traders: uniqueTraders.size,
      total_notional: filteredPositions.reduce((sum, p) => sum + (p.position_value || 0), 0),
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
  }, [filteredPositions]);

  // ==================== AI 分析函数 ====================

  // 整体持仓 AI 分析
  const handleAIAnalyzeAll = useCallback(async (forceRefresh: boolean = false) => {
    if (filteredPositions.length === 0) {
      addToast({
        title: "无法分析",
        description: "当前没有持仓数据",
        color: "warning",
      });
      return;
    }

    setAiAnalysisType('overall');
    setAiAnalysisData(null);
    setAiAnalysisCached(false);
    setAiAnalysisTime(undefined);
    setAiAnalysisOpen(true);
    setAiAnalyzing(true);

    try {
      const response = await traderPositionsApi.aiAnalyzeAll({
        positions: filteredPositions,
        stats: filteredStats || undefined,
        force_refresh: forceRefresh,
      });

      if (response.success && response.data) {
        setAiAnalysisData(response.data);
        setAiAnalysisCached(response.cached || false);
        setAiAnalysisTime(response.analyzed_at);
        addToast({
          title: response.cached ? "加载完成" : "分析完成",
          description: response.message || (response.cached ? "已加载历史分析结果" : "AI 分析已完成"),
          color: "success",
        });
      } else {
        addToast({
          title: "分析失败",
          description: response.error || "未知错误",
          color: "danger",
        });
      }
    } catch (error: any) {
      console.error("AI analysis failed:", error);
      addToast({
        title: "分析失败",
        description: error.message || "AI 分析请求失败",
        color: "danger",
      });
    } finally {
      setAiAnalyzing(false);
    }
  }, [filteredPositions, filteredStats]);

  // 币种持仓 AI 分析
  const handleAIAnalyzeCoin = useCallback(async (coin: string, forceRefresh: boolean = false) => {
    const coinPositions = filteredPositions.filter(p => p.coin === coin);
    if (coinPositions.length === 0) {
      addToast({
        title: "无法分析",
        description: `没有 ${coin} 的持仓数据`,
        color: "warning",
      });
      return;
    }

    setAiAnalysisType('coin');
    setAiAnalysisCoin(coin);
    setAiAnalysisData(null);
    setAiAnalysisCached(false);
    setAiAnalysisTime(undefined);
    setAiAnalysisOpen(true);
    setAiAnalyzing(true);

    try {
      const response = await traderPositionsApi.aiAnalyzeCoin({
        coin,
        positions: coinPositions,
        force_refresh: forceRefresh,
      });

      if (response.success && response.data) {
        setAiAnalysisData(response.data);
        setAiAnalysisCached(response.cached || false);
        setAiAnalysisTime(response.analyzed_at);
        addToast({
          title: response.cached ? "加载完成" : "分析完成",
          description: response.message || (response.cached ? `已加载 ${coin} 历史分析结果` : `${coin} AI 分析已完成`),
          color: "success",
        });
      } else {
        addToast({
          title: "分析失败",
          description: response.error || "未知错误",
          color: "danger",
        });
      }
    } catch (error: any) {
      console.error("AI analysis failed:", error);
      addToast({
        title: "分析失败",
        description: error.message || "AI 分析请求失败",
        color: "danger",
      });
    } finally {
      setAiAnalyzing(false);
    }
  }, [filteredPositions]);

  // 单仓位 AI 分析
  const handleAIAnalyzeSingle = useCallback(async (position: TraderPosition, forceRefresh: boolean = false) => {
    setAiAnalysisType('single');
    setAiAnalysisCoin(position.coin);
    setAiAnalysisData(null);
    setAiAnalysisCached(false);
    setAiAnalysisTime(undefined);
    setAiAnalysisOpen(true);
    setAiAnalyzing(true);

    try {
      const response = await traderPositionsApi.aiAnalyzeSingle({
        position,
        force_refresh: forceRefresh,
      });

      if (response.success && response.data) {
        setAiAnalysisData(response.data);
        setAiAnalysisCached(response.cached || false);
        setAiAnalysisTime(response.analyzed_at);
        addToast({
          title: response.cached ? "加载完成" : "分析完成",
          description: response.message || (response.cached ? "已加载历史分析结果" : "仓位风险分析已完成"),
          color: "success",
        });
      } else {
        addToast({
          title: "分析失败",
          description: response.error || "未知错误",
          color: "danger",
        });
      }
    } catch (error: any) {
      console.error("AI analysis failed:", error);
      addToast({
        title: "分析失败",
        description: error.message || "AI 分析请求失败",
        color: "danger",
      });
    } finally {
      setAiAnalyzing(false);
    }
  }, []);

  // 当前分析的单仓位（用于重新分析）
  const [currentSinglePosition, setCurrentSinglePosition] = useState<TraderPosition | null>(null);

  // 包装单仓位分析以保存当前位置
  const handleAIAnalyzeSingleWrapper = useCallback(async (position: TraderPosition, forceRefresh: boolean = false) => {
    setCurrentSinglePosition(position);
    await handleAIAnalyzeSingle(position, forceRefresh);
  }, [handleAIAnalyzeSingle]);

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
            <Dropdown>
              <DropdownTrigger>
                <Button
                  color="secondary"
                  variant="flat"
                  startContent={<Icon icon="solar:magic-stick-2-bold-duotone" width={18} />}
                  isDisabled={loading || filteredPositions.length === 0}
                >
                  AI 分析
                </Button>
              </DropdownTrigger>
              <DropdownMenu aria-label="AI分析选项">
                <DropdownItem
                  key="overall"
                  startContent={<Icon icon="solar:chart-2-bold-duotone" width={18} />}
                  description={`分析当前 ${filteredPositions.length} 个持仓的整体情况`}
                  onPress={() => handleAIAnalyzeAll(false)}
                >
                  整体持仓分析
                </DropdownItem>
                <DropdownItem
                  key="coin"
                  startContent={<Icon icon="solar:dollar-bold-duotone" width={18} />}
                  description="选择一个币种进行深度分析"
                  onPress={() => {
                    // 获取当前筛选后的币种列表
                    const coins = [...new Set(filteredPositions.map(p => p.coin))];
                    if (coins.length === 0) {
                      addToast({ title: "无法分析", description: "当前没有持仓数据", color: "warning" });
                      return;
                    }
                    // 默认分析持仓最多的币种
                    const coinCounts = coins.map(c => ({
                      coin: c,
                      count: filteredPositions.filter(p => p.coin === c).length
                    })).sort((a, b) => b.count - a.count);
                    handleAIAnalyzeCoin(coinCounts[0].coin);
                  }}
                >
                  币种深度分析
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
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
        <StatsCards stats={filteredStats} loading={loading && positions.length === 0} />

        {/* Coin Summary */}
        <CoinSummary stats={filteredStats} onAIAnalyzeCoin={handleAIAnalyzeCoin} />

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
          pnlFilter={pnlFilter}
          onPnlFilterChange={setPnlFilter}
          scoreFilter={scoreFilter}
          onScoreFilterChange={setScoreFilter}
          stats={stats}
          groups={groups}
          metricFilters={metricFilters}
          onMetricFiltersChange={setMetricFilters}
          onReset={handleReset}
        />

        {/* Positions Table */}
        <PositionsTable 
          positions={filteredPositions} 
          loading={loading} 
          onRefreshTrader={handleRefreshTrader}
          onToggleStar={handleToggleStar}
          starLoadingAddresses={starLoadingAddresses}
          onAIAnalyze={handleAIAnalyzeSingleWrapper}
        />
      </div>

      {/* AI 分析弹窗 */}
      <PositionsAIAnalysisModal
        isOpen={aiAnalysisOpen}
        analysisData={aiAnalysisData}
        analyzing={aiAnalyzing}
        analysisType={aiAnalysisType}
        coinName={aiAnalysisCoin}
        onClose={() => {
          setAiAnalysisOpen(false);
          setCurrentSinglePosition(null);
        }}
        onReanalyze={
          aiAnalysisType === 'overall' 
            ? () => handleAIAnalyzeAll(true) 
            : aiAnalysisType === 'coin' 
              ? () => handleAIAnalyzeCoin(aiAnalysisCoin, true)
              : currentSinglePosition 
                ? () => handleAIAnalyzeSingleWrapper(currentSinglePosition, true)
                : undefined
        }
        cached={aiAnalysisCached}
        analyzedAt={aiAnalysisTime}
      />
    </DefaultLayout>
  );
}
