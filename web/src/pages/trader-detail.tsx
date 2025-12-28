import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import type { Selection, SortDescriptor } from '@heroui/react';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Tabs, Tab } from '@heroui/tabs';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { Pagination } from '@heroui/pagination';
import { Input } from '@heroui/input';
import { Chip } from '@heroui/chip';
import {
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from '@heroui/dropdown';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@heroui/popover';
import { RadioGroup, Radio } from '@heroui/radio';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { SearchIcon } from '@heroui/shared-icons';
import { Divider } from '@heroui/divider';
import { Icon } from '@iconify/react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import DefaultLayout from '@/layouts/default';
import { traderApi, Trader, TraderFill, TraderHistory, FillsStats, FillsSummary, AssetPosition } from '@/services/api';

// 表格列配置
type ColumnKey = 'trade_time' | 'coin' | 'side' | 'px' | 'sz' | 'value' | 'closed_pnl' | 'roi' | 'fee';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'trade_time', name: '时间', sortable: true },
  { uid: 'coin', name: '币种', sortable: true },
  { uid: 'side', name: '方向', sortable: true },
  { uid: 'px', name: '价格', sortable: true },
  { uid: 'sz', name: '数量', sortable: true },
  { uid: 'value', name: '价值', sortable: true },
  { uid: 'closed_pnl', name: '盈亏', sortable: true },
  { uid: 'roi', name: 'ROI', sortable: true },
  { uid: 'fee', name: '手续费', sortable: true },
];

const INITIAL_VISIBLE_COLUMNS: ColumnKey[] = ['trade_time', 'coin', 'side', 'px', 'sz', 'value', 'closed_pnl', 'roi', 'fee'];

export default function TraderDetailPage() {
  const { address } = useParams<{ address: string }>();
  const navigate = useNavigate();

  const [trader, setTrader] = useState<Trader | null>(null);
  const [fills, setFills] = useState<TraderFill[]>([]);
  const [history, setHistory] = useState<TraderHistory | null>(null);
  const [fillsSummary, setFillsSummary] = useState<FillsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCoin, setSelectedCoin] = useState<string>('all');
  const [allCoins, setAllCoins] = useState<string[]>([]); // 保存完整的币种列表
  const [pnlFilter, setPnlFilter] = useState<'all' | 'profit' | 'loss'>('all');
  const [timeRange, setTimeRange] = useState<number>(30); // 默认30天
  const [chartLoading, setChartLoading] = useState(false);
  const [page, setPage] = useState(1);
  const rowsPerPage = 20;
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [fillsLoading, setFillsLoading] = useState(false);
  const [fillsStats, setFillsStats] = useState<FillsStats | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // 高级表格状态
  const [searchValue, setSearchValue] = useState('');
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'trade_time',
    direction: 'descending',
  });

  // 当前持仓状态（使用 assetPositions）
  const [assetPositions, setAssetPositions] = useState<AssetPosition[]>([]);
  const [assetPositionsLoading, setAssetPositionsLoading] = useState(false);

  useEffect(() => {
    if (!address) return;

    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // 并行加载数据
        const [detailRes, fillsRes, historyRes, positionsRes, coinsRes] = await Promise.all([
          traderApi.getTraderDetail(address),
          traderApi.getTraderFills(address, {
            page: 1,
            limit: rowsPerPage,
            coin: selectedCoin !== 'all' ? selectedCoin : undefined,
            pnl_filter: pnlFilter,
            position_type: 'closed',
          }),
          traderApi.getTraderHistory(address, { days: timeRange }),
          // 获取当前持仓（来自 assetPositions）
          traderApi.getTraderPositions(address),
          // 获取币种列表（排除 @数字 格式的用户永续合约）
          traderApi.getCoins({ address, exclude_user_perps: true }),
        ]);

        if (detailRes.success && detailRes.data) {
          setTrader(detailRes.data.trader);
          if (detailRes.data.fills_summary) {
            setFillsSummary(detailRes.data.fills_summary);
          }
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

        // 使用 API 返回的币种列表（已过滤非标准币种）
        if (coinsRes.success && coinsRes.data) {
          setAllCoins(coinsRes.data as string[]);
        }

        if (historyRes.success && historyRes.data) {
          setHistory(historyRes.data);
        }

        // 设置当前持仓
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
        if (res.data.fills_summary) {
          setFillsSummary(res.data.fills_summary);
        }
        // 重新加载交易记录、图表数据、持仓和币种列表
        const [fillsRes, historyRes, positionsRes, coinsRes] = await Promise.all([
          traderApi.getTraderFills(address, {
            page: 1,
            limit: rowsPerPage,
            coin: selectedCoin !== 'all' ? selectedCoin : undefined,
            pnl_filter: pnlFilter,
            position_type: 'closed',
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
          sort_by: sortDescriptor.column as string,
          sort_order: sortDescriptor.direction === 'ascending' ? 'asc' : 'desc',
          position_type: 'closed',
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
  }, [address, page, selectedCoin, pnlFilter, sortDescriptor, loading]);

  // 筛选条件或排序改变时重置页码
  useEffect(() => {
    setPage(1);
  }, [selectedCoin, pnlFilter, sortDescriptor]);


  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getRatingColor = (rating: string) => {
    const colors: Record<string, string> = {
      S: 'text-purple-500',
      A: 'text-blue-500',
      B: 'text-green-500',
      C: 'text-yellow-500',
      D: 'text-orange-500',
      F: 'text-red-500',
    };
    return colors[rating] || 'text-gray-500';
  };

  // 格式化图表数据
  const formatChartData = (data: { timestamp: string; value: number }[]) => {
    return data.map((item) => ({
      ...item,
      date: new Date(item.timestamp).toLocaleDateString(),
    }));
  };

  // 计算收益率
  const calculateROI = (fill: TraderFill) => {
    const tradeValue = fill.px * fill.sz;
    if (tradeValue === 0) return 0;
    return (fill.closed_pnl / tradeValue) * 100;
  };

  // 使用初次加载保存的完整币种列表
  const coins = useMemo(() => {
    return ['all', ...allCoins];
  }, [allCoins]);

  // 可见列
  const headerColumns = useMemo(() => {
    if (visibleColumns === 'all') return columns;
    return columns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  // 本地搜索过滤（排序已由 API 完成）
  const filteredItems = useMemo(() => {
    if (!searchValue) {
      return fills;
    }
    return fills.filter((fill) =>
      fill.coin.toLowerCase().includes(searchValue.toLowerCase())
    );
  }, [fills, searchValue]);

  // 单元格渲染
  const renderCell = useCallback((fill: TraderFill, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'trade_time':
        return (
          <div className="flex flex-col">
            <span className="text-xs">{new Date(fill.trade_time).toLocaleDateString()}</span>
            <span className="text-xs text-gray-500">{new Date(fill.trade_time).toLocaleTimeString()}</span>
          </div>
        );
      case 'coin':
        return <span className="font-bold">{fill.coin}</span>;
      case 'side':
        return (
          <Chip
            size="sm"
            color={fill.side === 'B' ? 'success' : 'danger'}
            variant="flat"
          >
            {fill.side === 'B' ? 'BUY' : 'SELL'}
          </Chip>
        );
      case 'px':
        return <span>${formatNumber(fill.px, 4)}</span>;
      case 'sz':
        return <span>{formatNumber(fill.sz, 4)}</span>;
      case 'value':
        return <span>${formatNumber(fill.px * fill.sz, 2)}</span>;
      case 'closed_pnl':
        return (
          <span className={fill.closed_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
            ${formatNumber(fill.closed_pnl)}
          </span>
        );
      case 'roi':
        const roi = calculateROI(fill);
        return (
          <span className={`font-bold ${roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {roi.toFixed(2)}%
          </span>
        );
      case 'fee':
        return <span className="text-orange-500">${formatNumber(fill.fee, 4)}</span>;
      default:
        return null;
    }
  }, []);

  // 搜索变化处理
  const onSearchChange = useCallback((value?: string) => {
    setSearchValue(value || '');
    setPage(1);
  }, []);

  // 重置筛选
  const handleReset = useCallback(() => {
    setSelectedCoin('all');
    setPnlFilter('all');
    setSearchValue('');
    setPage(1);
  }, []);

  // 获取当前筛选状态文本
  const getActiveFiltersCount = useCallback(() => {
    let count = 0;
    if (selectedCoin !== 'all') count++;
    if (pnlFilter !== 'all') count++;
    if (searchValue) count++;
    return count;
  }, [selectedCoin, pnlFilter, searchValue]);

  // 表格顶部内容
  const topContent = useMemo(() => {
    const activeFilters = getActiveFiltersCount();

    return (
      <div className="flex flex-col gap-4">
        {/* 统计信息 */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 p-4 bg-default-100 rounded-lg">
          <div>
            <p className="text-xs text-default-500">总交易</p>
            <p className="text-lg font-bold text-default-800">{fillsStats?.total ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">盈利笔数</p>
            <p className="text-lg font-bold text-success">{fillsStats?.profitable ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">亏损笔数</p>
            <p className="text-lg font-bold text-danger">{fillsStats?.losing ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">胜率</p>
            <p className="text-lg font-bold text-default-800">{(fillsStats?.win_rate ?? 0).toFixed(2)}%</p>
          </div>
          <div>
            <p className="text-xs text-default-500">总盈亏</p>
            <p className={`text-lg font-bold ${(fillsStats?.total_pnl ?? 0) >= 0 ? 'text-success' : 'text-danger'}`}>
              ${formatNumber(fillsStats?.total_pnl ?? 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-default-500">总手续费</p>
            <p className="text-lg font-bold text-warning">${formatNumber(fillsStats?.total_fees ?? 0)}</p>
          </div>
        </div>

        {/* 筛选工具栏 */}
        <div className="flex items-center gap-4 overflow-auto px-[6px] py-[4px]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-4">
              <Input
                className="min-w-[200px]"
                endContent={<SearchIcon className="text-default-400" width={16} />}
                placeholder="搜索币种..."
                size="sm"
                value={searchValue}
                onValueChange={onSearchChange}
                isClearable
                onClear={() => setSearchValue('')}
              />

              {/* Filter 弹窗 */}
              <div>
                <Popover placement="bottom">
                  <PopoverTrigger>
                    <Button
                      className="bg-default-100 text-default-800"
                      size="sm"
                      startContent={
                        <Icon className="text-default-400" icon="solar:tuning-2-linear" width={16} />
                      }
                    >
                      筛选
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-80">
                    <div className="flex w-full flex-col gap-6 px-2 py-4">
                      <RadioGroup
                        label="币种"
                        value={selectedCoin}
                        onValueChange={setSelectedCoin}
                      >
                        {coins.map((coin) => (
                          <Radio key={coin} value={coin}>
                            {coin === 'all' ? '全部' : coin}
                          </Radio>
                        ))}
                      </RadioGroup>

                      <RadioGroup
                        label="盈亏"
                        value={pnlFilter}
                        onValueChange={(value) => setPnlFilter(value as 'all' | 'profit' | 'loss')}
                      >
                        <Radio value="all">全部</Radio>
                        <Radio value="profit">盈利</Radio>
                        <Radio value="loss">亏损</Radio>
                      </RadioGroup>
                    </div>
                  </PopoverContent>
                </Popover>
              </div>

              {/* Sort 下拉 */}
              <div>
                <Dropdown>
                  <DropdownTrigger>
                    <Button
                      className="bg-default-100 text-default-800"
                      size="sm"
                      startContent={
                        <Icon className="text-default-400" icon="solar:sort-linear" width={16} />
                      }
                    >
                      排序
                    </Button>
                  </DropdownTrigger>
                  <DropdownMenu
                    aria-label="Sort"
                    items={columns.filter((c) => c.sortable)}
                  >
                    {(item) => (
                      <DropdownItem
                        key={item.uid}
                        onPress={() => {
                          setSortDescriptor({
                            column: item.uid,
                            direction:
                              sortDescriptor.direction === 'ascending' ? 'descending' : 'ascending',
                          });
                        }}
                      >
                        {item.name}
                      </DropdownItem>
                    )}
                  </DropdownMenu>
                </Dropdown>
              </div>

              {/* Columns 下拉 */}
              <div>
                <Dropdown closeOnSelect={false}>
                  <DropdownTrigger>
                    <Button
                      className="bg-default-100 text-default-800"
                      size="sm"
                      startContent={
                        <Icon
                          className="text-default-400"
                          icon="solar:sort-horizontal-linear"
                          width={16}
                        />
                      }
                    >
                      列
                    </Button>
                  </DropdownTrigger>
                  <DropdownMenu
                    disallowEmptySelection
                    aria-label="Columns"
                    items={columns}
                    selectedKeys={visibleColumns}
                    selectionMode="multiple"
                    onSelectionChange={setVisibleColumns}
                  >
                    {(item) => <DropdownItem key={item.uid}>{item.name}</DropdownItem>}
                  </DropdownMenu>
                </Dropdown>
              </div>
            </div>

            {activeFilters > 0 && (
              <Button
                className="bg-default-100 text-default-800"
                size="sm"
                variant="flat"
                onPress={handleReset}
                startContent={
                  <Icon className="text-default-400" icon="solar:restart-linear" width={16} />
                }
              >
                重置
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }, [fillsStats, searchValue, selectedCoin, pnlFilter, coins, sortDescriptor, visibleColumns, onSearchChange, handleReset, getActiveFiltersCount]);

  // 历史交易页码跳转
  const [jumpPage, setJumpPage] = useState('');
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      setPage(pageNum);
      setJumpPage('');
    }
  };

  // 表格底部内容
  const bottomContent = useMemo(() => {
    return (
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2">
        <span className="text-sm text-gray-500">
          显示 {Math.min((page - 1) * rowsPerPage + 1, totalCount)} - {Math.min(page * rowsPerPage, totalCount)} 条，共 {totalCount} 条记录
        </span>
        <div className="flex items-center gap-3">
          <Pagination
            isCompact
            showControls
            showShadow
            color="primary"
            page={page}
            total={totalPages}
            onChange={setPage}
          />
          <div className="flex items-center gap-1">
            <span className="text-sm text-gray-500">跳转</span>
            <Input
              type="number"
              size="sm"
              className="w-16"
              min={1}
              max={totalPages}
              value={jumpPage}
              onValueChange={setJumpPage}
              onKeyDown={(e) => e.key === 'Enter' && handleJumpPage()}
            />
            <span className="text-sm text-gray-500">页</span>
          </div>
        </div>
      </div>
    );
  }, [page, totalPages, totalCount, rowsPerPage, jumpPage]);

  if (loading) {
    return (
      <DefaultLayout>
        <div className="flex justify-center items-center h-screen">
          <Spinner size="lg" />
        </div>
      </DefaultLayout>
    );
  }

  if (error || !trader) {
    return (
      <DefaultLayout>
        <div className="flex flex-col items-center justify-center h-screen gap-4">
          <p className="text-red-500 text-xl">{error || 'Trader not found'}</p>
          <Button color="primary" onPress={() => navigate('/traders')}>
            Back to Traders
          </Button>
        </div>
      </DefaultLayout>
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

          {/* 概览卡片 */}
          <Card className="mb-6">
            <CardHeader>
              <div className="flex justify-between items-center w-full">
                <div>
                  <h1 className="text-2xl font-bold">Trader Overview</h1>
                  <p className="text-sm text-gray-500 font-mono mt-1">{address}</p>
                </div>
                <div className="flex items-center gap-4">
                  <Button
                    size="sm"
                    color="primary"
                    variant="flat"
                    isLoading={refreshing}
                    onPress={handleRefresh}
                    startContent={!refreshing && <Icon icon="solar:refresh-linear" width={16} />}
                  >
                    {refreshing ? '分析中...' : '刷新分析'}
                  </Button>
                  <div className="text-right">
                    <p className="text-sm text-gray-500">Rating</p>
                    <p className={`text-4xl font-bold ${getRatingColor(trader.rating)}`}>
                      {trader.rating}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-500">Score</p>
                    <p className="text-2xl font-bold">{formatNumber(trader.overall_score)}</p>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardBody>
              {/* 基础统计 */}
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">基础统计</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">总交易数</p>
                    <p className="text-lg font-bold">{trader.total_trades}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">盈利笔数</p>
                    <p className="text-lg font-bold text-green-500">{trader.winning_trades || 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">亏损笔数</p>
                    <p className="text-lg font-bold text-red-500">{trader.losing_trades || 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">胜率</p>
                    <p className="text-lg font-bold">{formatPercent(trader.win_rate)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">活跃天数</p>
                    <p className="text-lg font-bold">{trader.active_days}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">交易品种数</p>
                    <p className="text-lg font-bold">{trader.unique_symbols || 0}</p>
                  </div>
                </div>
              </div>

              <Divider className="my-3" />

              {/* 盈亏指标 */}
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">盈亏指标</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">总盈亏</p>
                    <p className={`text-lg font-bold ${trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${formatNumber(trader.total_pnl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">已实现盈亏</p>
                    <p className={`text-lg font-bold ${(trader.realized_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${formatNumber(trader.realized_pnl || 0)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">未实现盈亏</p>
                    <p className={`text-lg font-bold ${(trader.unrealized_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${formatNumber(trader.unrealized_pnl || 0)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">ROI</p>
                    <p className={`text-lg font-bold ${trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {formatPercent(trader.roi)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">盈亏比</p>
                    <p className="text-lg font-bold">{formatNumber(trader.profit_factor)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">7天盈亏</p>
                    <p className={`text-lg font-bold ${(trader.recent_7d_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      ${formatNumber(trader.recent_7d_pnl || 0)}
                    </p>
                  </div>
                </div>
              </div>

              <Divider className="my-3" />

              {/* 风险指标 */}
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">风险指标</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">最大回撤</p>
                    <p className="text-lg font-bold text-red-500">{formatPercent(trader.max_drawdown)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Sharpe Ratio</p>
                    <p className="text-lg font-bold">{formatNumber(trader.sharpe_ratio)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Sortino Ratio</p>
                    <p className="text-lg font-bold">{formatNumber(trader.sortino_ratio || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">平均杠杆</p>
                    <p className="text-lg font-bold">{formatNumber(trader.avg_leverage || 1)}x</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">最大单笔盈利</p>
                    <p className="text-lg font-bold text-green-500">${formatNumber(trader.max_single_win || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">最大单笔亏损</p>
                    <p className="text-lg font-bold text-red-500">${formatNumber(trader.max_single_loss || 0)}</p>
                  </div>
                </div>
              </div>

              <Divider className="my-3" />

              {/* 交易特征 */}
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">交易特征</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">最大连赢</p>
                    <p className="text-lg font-bold text-green-500">{trader.max_consecutive_wins || 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">最大连亏</p>
                    <p className="text-lg font-bold text-red-500">{trader.max_consecutive_losses || 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">平均盈利金额</p>
                    <p className="text-lg font-bold text-green-500">${formatNumber(trader.avg_win_amount || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">平均亏损金额</p>
                    <p className="text-lg font-bold text-red-500">${formatNumber(trader.avg_loss_amount || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">多空比</p>
                    <p className="text-lg font-bold">{formatPercent(trader.long_short_ratio || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">常用品种</p>
                    <p className="text-lg font-bold">{trader.favorite_symbol || '-'}</p>
                  </div>
                </div>
              </div>

              <Divider className="my-3" />

              {/* 账户状态 */}
              <div className="mb-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-2">账户状态</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">当前权益</p>
                    <p className="text-lg font-bold">${formatNumber(trader.current_equity)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">当前持仓</p>
                    <p className="text-lg font-bold">{trader.current_positions || 0}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">7天胜率</p>
                    <p className="text-lg font-bold">{formatPercent(trader.recent_7d_win_rate || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">首次交易</p>
                    <p className="text-sm">{trader.first_trade_time ? formatDateTime(trader.first_trade_time) : '-'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">最后交易</p>
                    <p className="text-sm">{formatDateTime(trader.last_trade_time)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">分析时间</p>
                    <p className="text-sm">{trader.analyzed_at ? formatDateTime(trader.analyzed_at) : '-'}</p>
                  </div>
                </div>
              </div>

              <Divider className="my-3" />

              {/* 评分详情 */}
              <div>
                <h3 className="text-sm font-semibold text-gray-400 mb-2">评分详情</h3>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">综合评分</p>
                    <p className="text-lg font-bold">{formatNumber(trader.overall_score)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">盈利能力</p>
                    <p className="text-lg font-bold">{formatNumber(trader.profitability_score || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">风险控制</p>
                    <p className="text-lg font-bold">{formatNumber(trader.risk_score || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">一致性</p>
                    <p className="text-lg font-bold">{formatNumber(trader.consistency_score || 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">活跃度</p>
                    <p className="text-lg font-bold">{formatNumber(trader.activity_score || 0)}</p>
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Tabs: 收益率、收益额、资产 */}
          <Card>
            <CardBody>
              {/* 时间范围选择器 */}
              <div className="flex gap-2 mb-4 flex-wrap">
                <span className="text-sm text-gray-500 self-center">时间范围:</span>
                {[
                  { label: '7天', value: 7 },
                  { label: '30天', value: 30 },
                  { label: '90天', value: 90 },
                  { label: '180天', value: 180 },
                  { label: '1年', value: 365 },
                  { label: '全部', value: 0 },
                ].map((range) => (
                  <Button
                    key={range.value}
                    size="sm"
                    variant={timeRange === range.value ? 'solid' : 'bordered'}
                    color={timeRange === range.value ? 'primary' : 'default'}
                    onPress={() => setTimeRange(range.value)}
                    isDisabled={chartLoading}
                  >
                    {range.label}
                  </Button>
                ))}
              </div>

              <Tabs aria-label="Performance charts">
                <Tab key="roi" title="收益率 (ROI)">
                  <div className="py-4">
                    {chartLoading ? (
                      <div className="flex justify-center items-center h-[400px]">
                        <Spinner size="lg" />
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={400}>
                        <LineChart data={formatChartData(history?.roi || [])}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis
                            dataKey="date"
                            tick={{ fontSize: 12 }}
                            angle={-45}
                            textAnchor="end"
                            height={80}
                          />
                          <YAxis
                            tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                          />
                          <Tooltip
                            formatter={(value) => [`${formatPercent(value as number)}`, 'ROI']}
                            labelStyle={{ color: '#000' }}
                            contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                          />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#8b5cf6"
                            strokeWidth={2}
                            name="ROI"
                            dot={{ r: 3 }}
                            activeDot={{ r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </Tab>
                <Tab key="pnl" title="收益额 (PnL)">
                  <div className="py-4">
                    {chartLoading ? (
                      <div className="flex justify-center items-center h-[400px]">
                        <Spinner size="lg" />
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={400}>
                        <LineChart data={formatChartData(history?.pnl || [])}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis
                            dataKey="date"
                            tick={{ fontSize: 12 }}
                            angle={-45}
                            textAnchor="end"
                            height={80}
                          />
                          <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                          <Tooltip
                            formatter={(value) => [`$${formatNumber(value as number)}`, 'PnL']}
                            labelStyle={{ color: '#000' }}
                            contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                          />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#10b981"
                            strokeWidth={2}
                            name="Total PnL"
                            dot={{ r: 3 }}
                            activeDot={{ r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </Tab>
                <Tab key="equity" title="资产 (Equity)">
                  <div className="py-4">
                    {chartLoading ? (
                      <div className="flex justify-center items-center h-[400px]">
                        <Spinner size="lg" />
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height={400}>
                        <LineChart data={formatChartData(history?.equity || [])}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis
                            dataKey="date"
                            tick={{ fontSize: 12 }}
                            angle={-45}
                            textAnchor="end"
                            height={80}
                          />
                          <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                          <Tooltip
                            formatter={(value) => [
                              `$${formatNumber(value as number)}`,
                              'Equity',
                            ]}
                            labelStyle={{ color: '#000' }}
                            contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                          />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#3b82f6"
                            strokeWidth={2}
                            name="Current Equity"
                            dot={{ r: 3 }}
                            activeDot={{ r: 5 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </Tab>
              </Tabs>
            </CardBody>
          </Card>

          {/* 币种统计 */}
          <Card className="mt-6">
            <CardHeader>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold">币种统计</h2>
                <Chip size="sm" variant="flat" className="text-default-500">
                  {fillsSummary?.by_coin?.length || 0} 个币种
                </Chip>
              </div>
            </CardHeader>
            <CardBody>
              {fillsSummary?.by_coin && fillsSummary.by_coin.length > 0 ? (
                <Table
                  isHeaderSticky
                  aria-label="Coin statistics table"
                  classNames={{
                    wrapper: 'max-h-[400px]',
                  }}
                >
                  <TableHeader>
                    <TableColumn key="coin" allowsSorting>币种</TableColumn>
                    <TableColumn key="count" allowsSorting>交易次数</TableColumn>
                    <TableColumn key="total_pnl" allowsSorting>总盈亏</TableColumn>
                    <TableColumn key="avg_pnl">平均盈亏</TableColumn>
                    <TableColumn key="pnl_ratio">盈亏占比</TableColumn>
                  </TableHeader>
                  <TableBody items={fillsSummary.by_coin}>
                    {(item) => (
                      <TableRow key={item.coin}>
                        <TableCell>
                          <span className="font-bold">{item.coin}</span>
                        </TableCell>
                        <TableCell>{item.count}</TableCell>
                        <TableCell>
                          <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            ${formatNumber(item.total_pnl)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={(item.total_pnl / item.count) >= 0 ? 'text-green-500' : 'text-red-500'}>
                            ${formatNumber(item.total_pnl / item.count)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            {fillsSummary.total_pnl !== 0
                              ? formatPercent(Math.abs(item.total_pnl) / Math.abs(fillsSummary.total_pnl))
                              : '0%'}
                          </span>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center text-gray-500 py-8">暂无币种统计数据</div>
              )}
            </CardBody>
          </Card>

          {/* 当前持仓表格 */}
          <Card className="mt-6">
            <CardHeader>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold">当前持仓</h2>
                <Chip size="sm" variant="flat" color="warning">
                  {assetPositions.length}
                </Chip>
                {assetPositions.length > 0 && assetPositions[0]?.updated_at && (
                  <span className="text-xs text-gray-500">
                    更新于 {new Date(assetPositions[0].updated_at).toLocaleString()}
                  </span>
                )}
              </div>
            </CardHeader>
            <CardBody>
              {assetPositionsLoading ? (
                <div className="flex justify-center items-center h-64">
                  <Spinner size="lg" />
                </div>
              ) : assetPositions.length > 0 ? (
                <Table
                  isHeaderSticky
                  aria-label="Asset positions table"
                  classNames={{
                    wrapper: 'max-h-[400px]',
                  }}
                >
                  <TableHeader>
                    <TableColumn key="coin">币种</TableColumn>
                    <TableColumn key="side">方向</TableColumn>
                    <TableColumn key="szi">数量</TableColumn>
                    <TableColumn key="entry_px">开仓均价</TableColumn>
                    <TableColumn key="position_value">持仓价值</TableColumn>
                    <TableColumn key="unrealized_pnl">未实现盈亏</TableColumn>
                    <TableColumn key="roe">ROE</TableColumn>
                    <TableColumn key="leverage">杠杆</TableColumn>
                    <TableColumn key="liquidation_px">清算价格</TableColumn>
                  </TableHeader>
                  <TableBody items={assetPositions}>
                    {(item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <span className="font-bold">{item.coin}</span>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="sm"
                            color={item.szi > 0 ? 'success' : 'danger'}
                            variant="flat"
                          >
                            {item.szi > 0 ? 'LONG' : 'SHORT'}
                          </Chip>
                        </TableCell>
                        <TableCell>{formatNumber(Math.abs(item.szi), 4)}</TableCell>
                        <TableCell>${formatNumber(item.entry_px, 4)}</TableCell>
                        <TableCell>${formatNumber(Math.abs(item.position_value), 2)}</TableCell>
                        <TableCell>
                          <span className={item.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            ${formatNumber(item.unrealized_pnl, 2)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={item.return_on_equity >= 0 ? 'text-green-500' : 'text-red-500'}>
                            {formatPercent(item.return_on_equity)}
                          </span>
                        </TableCell>
                        <TableCell>{item.leverage_value}x</TableCell>
                        <TableCell>
                          {item.liquidation_px ? `$${formatNumber(item.liquidation_px, 2)}` : '-'}
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center text-gray-500 py-8">暂无当前持仓</div>
              )}
            </CardBody>
          </Card>

          {/* 历史交易表格 */}
          <Card className="mt-6">
            <CardHeader>
              <div className="flex items-center justify-between w-full">
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold">历史交易记录</h2>
                  <Chip size="sm" variant="flat" className="text-default-500">
                    {totalCount}
                  </Chip>
                </div>
              </div>
            </CardHeader>
            <CardBody>
              {fillsLoading ? (
                <div className="flex justify-center items-center h-64">
                  <Spinner size="lg" />
                </div>
              ) : (
                <Table
                  isHeaderSticky
                  aria-label="Trade history table"
                  topContent={topContent}
                  topContentPlacement="outside"
                  bottomContent={bottomContent}
                  bottomContentPlacement="outside"
                  sortDescriptor={sortDescriptor}
                  onSortChange={setSortDescriptor}
                  classNames={{
                    wrapper: 'max-h-[600px]',
                  }}
                >
                  <TableHeader columns={headerColumns}>
                    {(column) => (
                      <TableColumn
                        key={column.uid}
                        allowsSorting={column.sortable}
                      >
                        {column.name}
                      </TableColumn>
                    )}
                  </TableHeader>
                  <TableBody
                    items={filteredItems}
                    emptyContent="暂无交易记录"
                  >
                    {(item) => (
                      <TableRow key={item.id}>
                        {(columnKey) => (
                          <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>
                        )}
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
  );
}
