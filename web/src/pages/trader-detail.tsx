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
import { traderApi, Trader, TraderFill, TraderHistory } from '@/services/api';

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

const INITIAL_VISIBLE_COLUMNS: ColumnKey[] = ['trade_time', 'coin', 'side', 'px', 'sz', 'closed_pnl', 'roi', 'fee'];

export default function TraderDetailPage() {
  const { address } = useParams<{ address: string }>();
  const navigate = useNavigate();

  const [trader, setTrader] = useState<Trader | null>(null);
  const [fills, setFills] = useState<TraderFill[]>([]);
  const [history, setHistory] = useState<TraderHistory | null>(null);
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

  // 高级表格状态
  const [searchValue, setSearchValue] = useState('');
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'trade_time',
    direction: 'descending',
  });

  useEffect(() => {
    if (!address) return;

    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // 并行加载数据
        const [detailRes, fillsRes, historyRes] = await Promise.all([
          traderApi.getTraderDetail(address),
          traderApi.getTraderFills(address, {
            page: 1,
            limit: rowsPerPage,
            coin: selectedCoin !== 'all' ? selectedCoin : undefined,
            pnl_filter: pnlFilter,
          }),
          traderApi.getTraderHistory(address, { days: timeRange }),
        ]);

        if (detailRes.success && detailRes.data) {
          setTrader(detailRes.data.trader);
        }

        if (fillsRes.success && fillsRes.data) {
          setFills(fillsRes.data);
          // 初次加载时保存完整的币种列表
          const coinSet = new Set(fillsRes.data.map((f: TraderFill) => f.coin));
          setAllCoins(Array.from(coinSet).sort());
          if (fillsRes.pagination) {
            setTotalPages(fillsRes.pagination.total_pages);
            setTotalCount(fillsRes.pagination.total_count);
          }
        }

        if (historyRes.success && historyRes.data) {
          setHistory(historyRes.data);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load trader data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [address]);

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
        });

        if (fillsRes.success && fillsRes.data) {
          const fillsData = fillsRes.data;
          setFills(fillsData);
          // 累积收集新发现的币种
          setAllCoins((prev) => {
            const newCoins = fillsData.map((f: TraderFill) => f.coin);
            const combined = new Set([...prev, ...newCoins]);
            return Array.from(combined).sort();
          });
          if (fillsRes.pagination) {
            setTotalPages(fillsRes.pagination.total_pages);
            setTotalCount(fillsRes.pagination.total_count);
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

  // 统计信息（基于当前筛选条件的全部数据）
  const fillsStats = useMemo(() => ({
    total: totalCount,
    profitable: fills.filter((f) => f.closed_pnl > 0).length, // 当前页
    losing: fills.filter((f) => f.closed_pnl < 0).length, // 当前页
    totalPnl: fills.reduce((sum, f) => sum + f.closed_pnl, 0), // 当前页
    totalFees: fills.reduce((sum, f) => sum + f.fee, 0), // 当前页
    winRate: totalCount > 0 ? (fills.filter((f) => f.closed_pnl > 0).length / fills.length) * 100 : 0,
  }), [fills, totalCount]);

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
            <p className="text-lg font-bold text-default-800">{fillsStats.total}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">盈利笔数</p>
            <p className="text-lg font-bold text-success">{fillsStats.profitable}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">亏损笔数</p>
            <p className="text-lg font-bold text-danger">{fillsStats.losing}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">胜率</p>
            <p className="text-lg font-bold text-default-800">{fillsStats.winRate.toFixed(2)}%</p>
          </div>
          <div>
            <p className="text-xs text-default-500">总盈亏</p>
            <p className={`text-lg font-bold ${fillsStats.totalPnl >= 0 ? 'text-success' : 'text-danger'}`}>
              ${formatNumber(fillsStats.totalPnl)}
            </p>
          </div>
          <div>
            <p className="text-xs text-default-500">总手续费</p>
            <p className="text-lg font-bold text-warning">${formatNumber(fillsStats.totalFees)}</p>
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

  // 表格底部内容
  const bottomContent = useMemo(() => {
    return (
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2">
        <span className="text-sm text-gray-500">
          显示 {Math.min((page - 1) * rowsPerPage + 1, totalCount)} - {Math.min(page * rowsPerPage, totalCount)} 条，共 {totalCount} 条记录
        </span>
        <Pagination
          isCompact
          showControls
          showShadow
          color="primary"
          page={page}
          total={totalPages}
          onChange={setPage}
        />
      </div>
    );
  }, [page, totalPages, totalCount, rowsPerPage]);

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
    <DefaultLayout>
      <div className="flex flex-col gap-4 py-8 md:py-10">
        <div className="max-w-7xl w-full mx-auto">
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
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Total Trades</p>
                  <p className="text-xl font-bold">{trader.total_trades}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Win Rate</p>
                  <p className="text-xl font-bold">{formatPercent(trader.win_rate)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Total PnL</p>
                  <p
                    className={`text-xl font-bold ${trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}
                  >
                    ${formatNumber(trader.total_pnl)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Current Equity</p>
                  <p className="text-xl font-bold">${formatNumber(trader.current_equity)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">ROI</p>
                  <p
                    className={`text-xl font-bold ${trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}`}
                  >
                    {formatPercent(trader.roi)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Profit Factor</p>
                  <p className="text-xl font-bold">{formatNumber(trader.profit_factor)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Max Drawdown</p>
                  <p className="text-xl font-bold text-red-500">
                    {formatPercent(trader.max_drawdown)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Sharpe Ratio</p>
                  <p className="text-xl font-bold">{formatNumber(trader.sharpe_ratio)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Active Days</p>
                  <p className="text-xl font-bold">{trader.active_days}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Last Trade</p>
                  <p className="text-sm">{formatDateTime(trader.last_trade_time)}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Avg Leverage</p>
                  <p className="text-xl font-bold">{formatNumber(trader.avg_leverage || 1)}x</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Current Positions</p>
                  <p className="text-xl font-bold">{trader.current_positions || 0}</p>
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
    </DefaultLayout>
  );
}
