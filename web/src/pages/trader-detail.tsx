import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Tabs, Tab } from '@heroui/tabs';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { Pagination } from '@heroui/pagination';
import { Select, SelectItem } from '@heroui/select';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
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

  // 筛选条件或分页改变时加载交易记录
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
  }, [address, page, selectedCoin, pnlFilter, loading]);

  // 筛选条件改变时重置页码
  useEffect(() => {
    setPage(1);
  }, [selectedCoin, pnlFilter]);

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
              <div className="flex flex-col gap-4 w-full">
                <h2 className="text-xl font-bold">历史交易记录</h2>

                {/* 统计信息 */}
                <div className="grid grid-cols-2 md:grid-cols-6 gap-3 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div>
                    <p className="text-xs text-gray-500">总交易</p>
                    <p className="text-lg font-bold">{fillsStats.total}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">盈利笔数</p>
                    <p className="text-lg font-bold text-green-500">
                      {fillsStats.profitable}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">亏损笔数</p>
                    <p className="text-lg font-bold text-red-500">{fillsStats.losing}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">胜率</p>
                    <p className="text-lg font-bold">{fillsStats.winRate.toFixed(2)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">总盈亏</p>
                    <p
                      className={`text-lg font-bold ${fillsStats.totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}
                    >
                      ${formatNumber(fillsStats.totalPnl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">总手续费</p>
                    <p className="text-lg font-bold text-orange-500">
                      ${formatNumber(fillsStats.totalFees)}
                    </p>
                  </div>
                </div>

                {/* 筛选器 */}
                <div className="flex gap-3 flex-wrap items-end">
                  <Select
                    label="币种"
                    size="sm"
                    selectedKeys={[selectedCoin]}
                    onSelectionChange={(keys) => {
                      const selected = Array.from(keys)[0] as string;
                      if (selected) setSelectedCoin(selected);
                    }}
                    className="w-40"
                  >
                    {coins.map((coin) => (
                      <SelectItem key={coin}>
                        {coin === 'all' ? '全部' : coin}
                      </SelectItem>
                    ))}
                  </Select>
                  <Select
                    label="盈亏"
                    size="sm"
                    selectedKeys={[pnlFilter]}
                    onSelectionChange={(keys) => {
                      const selected = Array.from(keys)[0] as 'all' | 'profit' | 'loss';
                      if (selected) setPnlFilter(selected);
                    }}
                    className="w-32"
                  >
                    <SelectItem key="all">全部</SelectItem>
                    <SelectItem key="profit">盈利</SelectItem>
                    <SelectItem key="loss">亏损</SelectItem>
                  </Select>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      color="primary"
                      onPress={() => {
                        setPage(1);
                      }}
                      isLoading={fillsLoading}
                    >
                      查询
                    </Button>
                    <Button
                      size="sm"
                      variant="bordered"
                      onPress={() => {
                        setSelectedCoin('all');
                        setPnlFilter('all');
                        setPage(1);
                      }}
                    >
                      重置
                    </Button>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardBody>
              <div className="flex flex-col gap-4">
                {fillsLoading ? (
                  <div className="flex justify-center items-center h-64">
                    <Spinner size="lg" />
                  </div>
                ) : (
                  <>
                    <Table aria-label="Trade history table">
                      <TableHeader>
                        <TableColumn>Time</TableColumn>
                        <TableColumn>Coin</TableColumn>
                        <TableColumn>Side</TableColumn>
                        <TableColumn>Price</TableColumn>
                        <TableColumn>Size</TableColumn>
                        <TableColumn>Value</TableColumn>
                        <TableColumn>PnL</TableColumn>
                        <TableColumn>ROI</TableColumn>
                        <TableColumn>Fee</TableColumn>
                      </TableHeader>
                      <TableBody>
                        {fills.map((fill) => (
                      <TableRow key={fill.id}>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="text-xs">
                              {new Date(fill.trade_time).toLocaleDateString()}
                            </span>
                            <span className="text-xs text-gray-500">
                              {new Date(fill.trade_time).toLocaleTimeString()}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="font-bold">{fill.coin}</span>
                        </TableCell>
                        <TableCell>
                          <span
                            className={
                              fill.side === 'B'
                                ? 'text-green-500 font-bold'
                                : 'text-red-500 font-bold'
                            }
                          >
                            {fill.side === 'B' ? 'BUY' : 'SELL'}
                          </span>
                        </TableCell>
                        <TableCell>${formatNumber(fill.px, 4)}</TableCell>
                        <TableCell>{formatNumber(fill.sz, 4)}</TableCell>
                        <TableCell>${formatNumber(fill.px * fill.sz, 2)}</TableCell>
                        <TableCell>
                          <div className="flex flex-col">
                            <span
                              className={
                                fill.closed_pnl >= 0 ? 'text-green-500' : 'text-red-500'
                              }
                            >
                              ${formatNumber(fill.closed_pnl)}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span
                            className={
                              fill.closed_pnl >= 0
                                ? 'text-green-500 font-bold'
                                : 'text-red-500 font-bold'
                            }
                          >
                            {calculateROI(fill).toFixed(2)}%
                          </span>
                        </TableCell>
                        <TableCell className="text-orange-500">
                          ${formatNumber(fill.fee, 4)}
                        </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>

                    {/* 分页控件 */}
                    {totalPages > 1 && (
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-gray-500">
                          显示 {Math.min((page - 1) * rowsPerPage + 1, totalCount)} -{' '}
                          {Math.min(page * rowsPerPage, totalCount)} 条，共 {totalCount} 条记录
                        </span>
                        <Pagination
                          total={totalPages}
                          page={page}
                          onChange={setPage}
                          showControls
                          color="primary"
                          size="sm"
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
    </DefaultLayout>
  );
}
