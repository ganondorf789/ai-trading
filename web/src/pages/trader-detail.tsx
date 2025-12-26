import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Tabs, Tab } from '@heroui/tabs';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
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
  const [pnlFilter, setPnlFilter] = useState<'all' | 'profit' | 'loss'>('all');

  useEffect(() => {
    if (!address) return;

    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // 并行加载数据
        const [detailRes, fillsRes, historyRes] = await Promise.all([
          traderApi.getTraderDetail(address),
          traderApi.getTraderFills(address, { limit: 200 }),
          traderApi.getTraderHistory(address, { limit: 30 }),
        ]);

        if (detailRes.success && detailRes.data) {
          setTrader(detailRes.data.trader);
        }

        if (fillsRes.success && fillsRes.data) {
          setFills(fillsRes.data);
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

  // 获取所有币种
  const coins = ['all', ...Array.from(new Set(fills.map((f) => f.coin)))];

  // 过滤交易记录
  const filteredFills = fills.filter((fill) => {
    const coinMatch = selectedCoin === 'all' || fill.coin === selectedCoin;
    const pnlMatch =
      pnlFilter === 'all' ||
      (pnlFilter === 'profit' && fill.closed_pnl > 0) ||
      (pnlFilter === 'loss' && fill.closed_pnl < 0);
    return coinMatch && pnlMatch;
  });

  // 统计信息
  const fillsStats = {
    total: filteredFills.length,
    profitable: filteredFills.filter((f) => f.closed_pnl > 0).length,
    losing: filteredFills.filter((f) => f.closed_pnl < 0).length,
    totalPnl: filteredFills.reduce((sum, f) => sum + f.closed_pnl, 0),
    totalFees: filteredFills.reduce((sum, f) => sum + f.fee, 0),
    winRate:
      filteredFills.length > 0
        ? (filteredFills.filter((f) => f.closed_pnl > 0).length /
            filteredFills.length) *
          100
        : 0,
  };

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
      <section className="flex flex-col gap-4 py-8 md:py-10">
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
              <Tabs aria-label="Performance charts">
                <Tab key="roi" title="收益率 (ROI)">
                  <div className="py-4">
                    <ResponsiveContainer width="100%" height={400}>
                      <LineChart data={formatChartData(history?.roi || [])}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis
                          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                        />
                        <Tooltip
                          formatter={(value: number) => [`${formatPercent(value)}`, 'ROI']}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#8b5cf6"
                          strokeWidth={2}
                          name="ROI"
                          dot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Tab>
                <Tab key="pnl" title="收益额 (PnL)">
                  <div className="py-4">
                    <ResponsiveContainer width="100%" height={400}>
                      <LineChart data={formatChartData(history?.pnl || [])}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                        <Tooltip
                          formatter={(value: number) => [`$${formatNumber(value)}`, 'PnL']}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#10b981"
                          strokeWidth={2}
                          name="Total PnL"
                          dot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Tab>
                <Tab key="equity" title="资产 (Equity)">
                  <div className="py-4">
                    <ResponsiveContainer width="100%" height={400}>
                      <LineChart data={formatChartData(history?.equity || [])}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="date" />
                        <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                        <Tooltip
                          formatter={(value: number) => [
                            `$${formatNumber(value)}`,
                            'Equity',
                          ]}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#3b82f6"
                          strokeWidth={2}
                          name="Current Equity"
                          dot={{ r: 4 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
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
                <div className="flex gap-3 flex-wrap">
                  <div className="flex gap-2 items-center">
                    <span className="text-sm text-gray-500">币种:</span>
                    <select
                      className="px-3 py-1 border rounded-lg text-sm bg-white dark:bg-gray-800"
                      value={selectedCoin}
                      onChange={(e) => setSelectedCoin(e.target.value)}
                    >
                      {coins.map((coin) => (
                        <option key={coin} value={coin}>
                          {coin === 'all' ? '全部' : coin}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant={pnlFilter === 'all' ? 'solid' : 'bordered'}
                      color={pnlFilter === 'all' ? 'primary' : 'default'}
                      onPress={() => setPnlFilter('all')}
                    >
                      全部
                    </Button>
                    <Button
                      size="sm"
                      variant={pnlFilter === 'profit' ? 'solid' : 'bordered'}
                      color={pnlFilter === 'profit' ? 'success' : 'default'}
                      onPress={() => setPnlFilter('profit')}
                    >
                      盈利
                    </Button>
                    <Button
                      size="sm"
                      variant={pnlFilter === 'loss' ? 'solid' : 'bordered'}
                      color={pnlFilter === 'loss' ? 'danger' : 'default'}
                      onPress={() => setPnlFilter('loss')}
                    >
                      亏损
                    </Button>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardBody>
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
                  {filteredFills.map((fill) => (
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
            </CardBody>
          </Card>
        </div>
      </section>
    </DefaultLayout>
  );
}
