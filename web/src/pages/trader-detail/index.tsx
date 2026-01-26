import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { SortDescriptor, DateValue, RangeValue } from '@heroui/react';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { addToast } from "@heroui/react";
import { traderApi, Trader, TraderFill, TraderHistory, FillsStats, AssetPosition } from '@/services/api';
import { useTimeRange } from '@/components/TimeRangeFilter';
import { TraderOverviewCard } from './components/TraderOverviewCard';
import { PerformanceCharts } from './components/PerformanceCharts';
import { CurrentPositions } from './components/CurrentPositions';
import { PositionHistory } from './components/PositionHistory';
import { TradeHistory } from './components/TradeHistory';
import { AIAnalysisModal } from './components/AIAnalysisModal';

export default function TraderDetailPage() {
  const { address } = useParams<{ address: string }>();
  const navigate = useNavigate();

  const [trader, setTrader] = useState<Trader | null>(null);
  const [fills, setFills] = useState<TraderFill[]>([]);
  const [history, setHistory] = useState<TraderHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCoin, setSelectedCoin] = useState<string>('all');
  const [allCoins, setAllCoins] = useState<string[]>([]);
  const [pnlFilter, setPnlFilter] = useState<'all' | 'profit' | 'loss'>('all');
  const [tradeTypeFilter, setTradeTypeFilter] = useState<string>('all');
  const [timeRangeFilter, setTimeRangeFilter] = useState<string>('all');
  const [dateRange, setDateRange] = useState<RangeValue<DateValue> | null>(null);
  const [timeRange, setTimeRange] = useState<number>(30);
  const [chartLoading, setChartLoading] = useState(false);
  const [page, setPage] = useState(1);
  const rowsPerPage = 20;
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [fillsLoading, setFillsLoading] = useState(false);
  const [fillsStats, setFillsStats] = useState<FillsStats | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [aiAnalyzing, setAiAnalyzing] = useState(false);
  const [aiAnalysisData, setAiAnalysisData] = useState<any>(null);
  const [showAiAnalysis, setShowAiAnalysis] = useState(false);

  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'trade_time',
    direction: 'descending',
  });

  const [assetPositions, setAssetPositions] = useState<AssetPosition[]>([]);
  const [assetPositionsLoading, setAssetPositionsLoading] = useState(false);
  const [positionsRefreshing, setPositionsRefreshing] = useState(false);
  const [isStarLoading, setIsStarLoading] = useState(false);

  // 计算交易记录的时间范围
  const { startTime: fillsStartTime, endTime: fillsEndTime } = useTimeRange(timeRangeFilter, dateRange);

  // 切换收藏状态
  const handleToggleStar = useCallback(async (address: string, isStarred: boolean) => {
    setIsStarLoading(true);
    try {
      const response = await traderApi.toggleStar(address, isStarred);
      if (response.success) {
        // 更新本地状态
        setTrader(prev => prev ? { ...prev, is_starred: isStarred } : null);
        addToast({
          title: isStarred ? '已收藏' : '已取消收藏',
          color: 'success',
        });
      }
    } catch (error) {
      console.error('Toggle star failed:', error);
      addToast({
        title: '操作失败',
        color: 'danger',
      });
    } finally {
      setIsStarLoading(false);
    }
  }, []);

  // 刷新持仓数据
  const handleRefreshPositions = async () => {
    if (!address || positionsRefreshing) return;

    try {
      setPositionsRefreshing(true);
      const res = await traderApi.refreshTraderPositions(address);

      if (res.success && res.data) {
        setAssetPositions(res.data);
      } else {
        console.error('刷新持仓失败:', res.error);
      }
    } catch (err: any) {
      console.error('Failed to refresh positions:', err);
    } finally {
      setPositionsRefreshing(false);
    }
  };

  useEffect(() => {
    if (!address) return;

    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [detailRes, fillsRes, historyRes, positionsRes, coinsRes] = await Promise.all([
          traderApi.getTraderDetail(address),
          traderApi.getTraderFills(address, {
            page: 1,
            limit: rowsPerPage,
            coin: selectedCoin !== 'all' ? selectedCoin : undefined,
            pnl_filter: pnlFilter,
          }),
          traderApi.getTraderHistory(address, { days: timeRange }),
          traderApi.getTraderPositions(address),
          traderApi.getCoins({ address, exclude_user_perps: true }),
        ]);

        if (detailRes.success && detailRes.data) {
          setTrader(detailRes.data.trader);
        }

        if (fillsRes.success && fillsRes.data) {
          setFills(fillsRes.data);
          if (fillsRes.pagination) {
            setTotalPages(fillsRes.pagination.total_pages);
            setTotalCount(fillsRes.pagination.total_count);
          }
          if (fillsRes.stats) {
            setFillsStats(fillsRes.stats);
          }
        }

        if (coinsRes.success && coinsRes.data) {
          setAllCoins(coinsRes.data as string[]);
        }

        if (historyRes.success && historyRes.data) {
          setHistory(historyRes.data);
        }

        if (positionsRes.success && positionsRes.data) {
          setAssetPositions(positionsRes.data);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load trader data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [address]);

  // 自动加载已有的AI分析
  useEffect(() => {
    if (!address) return;

    const loadExistingAnalysis = async () => {
      try {
        const res = await traderApi.getTraderAIAnalysis(address);
        if (res.success && res.data) {
          setAiAnalysisData(res.data);
        }
      } catch (err: any) {
        console.log('No existing AI analysis found');
      }
    };

    loadExistingAnalysis();
  }, [address]);

  // AI分析交易者（支持强制重新分析）
  const handleAiAnalysis = async (forceReanalyze: boolean = false) => {
    if (!address || aiAnalyzing) return;

    if (aiAnalysisData && !forceReanalyze) {
      setShowAiAnalysis(true);
      return;
    }

    try {
      setAiAnalyzing(true);
      const res = await traderApi.aiAnalyzeTrader(address);

      if (res.success && res.data) {
        setAiAnalysisData(res.data);
        setShowAiAnalysis(true);
      } else {
        console.error('AI分析失败:', res.error);
        alert('AI分析失败: ' + (res.error || '未知错误'));
      }
    } catch (err: any) {
      console.error('AI analysis failed:', err);
      alert('AI分析失败: ' + (err.message || '请求失败'));
    } finally {
      setAiAnalyzing(false);
    }
  };

  // 刷新交易者数据
  const handleRefresh = async () => {
    if (!address || refreshing) return;

    try {
      setRefreshing(true);
      const res = await traderApi.refreshTrader(address, {
        lookback_days: 30,
        max_fills: 0,
      });

      if (res.success && res.data) {
        setTrader(res.data.trader);
        const [fillsRes, historyRes, positionsRes, coinsRes] = await Promise.all([
          traderApi.getTraderFills(address, {
            page: 1,
            limit: rowsPerPage,
            coin: selectedCoin !== 'all' ? selectedCoin : undefined,
            pnl_filter: pnlFilter,
          }),
          traderApi.getTraderHistory(address, { days: timeRange }),
          traderApi.getTraderPositions(address),
          traderApi.getCoins({ address, exclude_user_perps: true }),
        ]);

        if (fillsRes.success && fillsRes.data) {
          setFills(fillsRes.data);
          if (fillsRes.pagination) {
            setTotalPages(fillsRes.pagination.total_pages);
            setTotalCount(fillsRes.pagination.total_count);
          }
          if (fillsRes.stats) {
            setFillsStats(fillsRes.stats);
          }
        }

        if (coinsRes.success && coinsRes.data) {
          setAllCoins(coinsRes.data as string[]);
        }

        if (historyRes.success && historyRes.data) {
          setHistory(historyRes.data);
        }

        if (positionsRes.success && positionsRes.data) {
          setAssetPositions(positionsRes.data);
        }

        setPage(1);
      } else {
        setError(res.error || '刷新失败');
      }
    } catch (err: any) {
      console.error('Failed to refresh trader:', err);
      setError(err.message || '刷新失败');
    } finally {
      setRefreshing(false);
    }
  };

  // 时间范围改变时重新加载图表数据
  useEffect(() => {
    if (!address || loading) return;

    const loadChartData = async () => {
      try {
        setChartLoading(true);
        const historyRes = await traderApi.getTraderHistory(address, { days: timeRange });

        if (historyRes.success && historyRes.data) {
          setHistory(historyRes.data);
        }
      } catch (err: any) {
        console.error('Failed to load chart data:', err);
      } finally {
        setChartLoading(false);
      }
    };

    loadChartData();
  }, [timeRange, address, loading]);

  // 筛选条件、分页或排序改变时加载交易记录
  useEffect(() => {
    if (!address || loading) return;

    const loadFills = async () => {
      try {
        setFillsLoading(true);

        const fillsRes = await traderApi.getTraderFills(address, {
          page,
          limit: rowsPerPage,
          coin: selectedCoin !== 'all' ? selectedCoin : undefined,
          pnl_filter: pnlFilter,
          trade_type: tradeTypeFilter !== 'all' ? tradeTypeFilter : undefined,
          sort_by: sortDescriptor.column as string,
          sort_order: sortDescriptor.direction === 'ascending' ? 'asc' : 'desc',
          start_date: fillsStartTime,
          end_date: fillsEndTime,
        });

        if (fillsRes.success && fillsRes.data) {
          setFills(fillsRes.data);
          if (fillsRes.pagination) {
            setTotalPages(fillsRes.pagination.total_pages);
            setTotalCount(fillsRes.pagination.total_count);
          }
          if (fillsRes.stats) {
            setFillsStats(fillsRes.stats);
          }
        }
      } catch (err: any) {
        console.error('Failed to load fills:', err);
      } finally {
        setFillsLoading(false);
      }
    };

    loadFills();
  }, [address, page, selectedCoin, pnlFilter, tradeTypeFilter, sortDescriptor, loading, fillsStartTime, fillsEndTime]);

  // 筛选条件或排序改变时重置页码
  useEffect(() => {
    setPage(1);
  }, [selectedCoin, pnlFilter, tradeTypeFilter, sortDescriptor, timeRangeFilter, dateRange]);

  // 重置筛选
  const handleReset = () => {
    setSelectedCoin('all');
    setPnlFilter('all');
    setTradeTypeFilter('all');
    setTimeRangeFilter('all');
    setDateRange(null);
    setPage(1);
  };

  const coins = useMemo(() => {
    return ['all', ...allCoins];
  }, [allCoins]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !trader) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <p className="text-red-500 text-xl">{error || 'Trader not found'}</p>
        <Button color="primary" onPress={() => navigate('/traders')}>
          Back to Traders
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 py-4 px-6 max-w-[1800px] mx-auto w-full">
      <div className="w-full">
        <Button
          size="sm"
          variant="light"
          onPress={() => navigate('/traders')}
          className="mb-4"
        >
          ← Back to Traders
        </Button>

        <TraderOverviewCard
          trader={trader}
          address={address || ''}
          aiAnalyzing={aiAnalyzing}
          aiAnalysisData={aiAnalysisData}
          refreshing={refreshing}
          onAiAnalysis={() => handleAiAnalysis(false)}
          onRefresh={handleRefresh}
          isStarLoading={isStarLoading}
          onToggleStar={handleToggleStar}
        />

        <PerformanceCharts
          history={history}
          timeRange={timeRange}
          chartLoading={chartLoading}
          onTimeRangeChange={setTimeRange}
        />

        <CurrentPositions
          assetPositions={assetPositions}
          assetPositionsLoading={assetPositionsLoading}
          positionsRefreshing={positionsRefreshing}
          onRefresh={handleRefreshPositions}
        />

        <PositionHistory address={address || ''} />

        <TradeHistory
          fills={fills}
          fillsStats={fillsStats}
          fillsLoading={fillsLoading}
          totalCount={totalCount}
          totalPages={totalPages}
          page={page}
          rowsPerPage={rowsPerPage}
          coins={coins}
          selectedCoin={selectedCoin}
          pnlFilter={pnlFilter}
          tradeTypeFilter={tradeTypeFilter}
          timeRangeFilter={timeRangeFilter}
          dateRange={dateRange}
          sortDescriptor={sortDescriptor}
          onPageChange={setPage}
          onCoinChange={setSelectedCoin}
          onPnlFilterChange={setPnlFilter}
          onTradeTypeFilterChange={setTradeTypeFilter}
          onTimeRangeFilterChange={setTimeRangeFilter}
          onDateRangeChange={setDateRange}
          onSortChange={setSortDescriptor}
          onReset={handleReset}
        />

        <AIAnalysisModal
          isOpen={showAiAnalysis}
          aiAnalysisData={aiAnalysisData}
          aiAnalyzing={aiAnalyzing}
          onClose={() => setShowAiAnalysis(false)}
          onReanalyze={() => handleAiAnalysis(true)}
        />
      </div>
    </div>
  );
}
