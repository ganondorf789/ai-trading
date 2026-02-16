import { useState, useEffect, useCallback, useMemo } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody } from '@heroui/modal';
import { Spinner } from '@heroui/spinner';
import { Chip } from '@heroui/chip';
import { Dropdown, DropdownTrigger, DropdownMenu, DropdownItem } from '@heroui/dropdown';
import { Button } from '@heroui/button';
import { Tabs, Tab } from '@heroui/tabs';
import { addToast } from '@heroui/react';
import { Icon } from '@iconify/react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { traderApi } from '@/services/api';
import type { PositionHistoryByCoin } from '@/types/api';

// ==================== Types ====================

interface ClosedPositionsSummary {
  win_rate: {
    rate: number;
    closing_pnl: number;
    fees_deducted: number;
  };
  closed_positions: {
    total: number;
    profit: number;
    loss: number;
  };
  net_pnl: {
    total: number;
    long: number;
    short: number;
  };
  holding_time: {
    total: string;
    range_min: string;
    range_max: string;
    average: string;
  };
}

interface BestTrade {
  coin: string;
  direction: 'long' | 'short';
  open_time: string;
  close_time: string;
  realized_pnl: number;
  holding_hours: number;
  max_size: number;
  avg_entry_price: number;
  avg_close_price: number;
  total_fee: number;
  total_volume: number;
}

interface PositionItem {
  id: number;
  coin: string;
  direction: 'long' | 'short';
  open_time: string;
  close_time: string | null;
  max_size: number;
  avg_entry_price: number;
  avg_close_price: number | null;
  position_value: number;
  total_volume: number;
  realized_pnl: number;
  total_fee: number;
  holding_hours: number | null;
  status: 'open' | 'closed';
}

type TimeRange = '1w' | '1m' | 'all';
type TabKey = 'overview' | 'by-asset' | 'by-position';

interface TradingStatisticsModalProps {
  isOpen: boolean;
  onClose: () => void;
  address: string;
}

// ==================== Helpers ====================

function shortenAddress(addr: string): string {
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).then(() => {
    addToast({ title: 'Copied', color: 'success' });
  });
}

function formatPnl(n: number): string {
  const prefix = n >= 0 ? '+' : '';
  return `${prefix}${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null || isNaN(value)) return '-';
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function formatHoldingTime(hours: number): string {
  if (hours <= 0) return '0m';
  const totalMinutes = Math.round(hours * 60);
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (h > 0 && m > 0) return `${h}h ${m}m`;
  if (h > 0) return `${h}h`;
  return `${m}m`;
}

function fmtHoldingTime(hours: number): string {
  if (!hours || hours <= 0) return '-';
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${fmt(hours, 1)}h`;
  const days = hours / 24;
  return `${fmt(days, 1)}d`;
}


function timeAgo(dateStr: string): string {
  const now = Date.now();
  const date = new Date(dateStr).getTime();
  const diffMs = now - date;
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) return `${diffDays} days ago`;
  if (diffHours > 0) return `${diffHours} hours ago`;
  return 'just now';
}

const TIME_RANGE_LABELS: Record<TimeRange, string> = {
  '1w': '1W',
  '1m': '1M',
  'all': 'All',
};

function getDateRange(range: TimeRange): { start_date?: string; end_date?: string } {
  if (range === 'all') return {};
  const now = new Date();
  const end_date = now.toISOString().split('T')[0];
  const start = new Date(now);
  if (range === '1w') start.setDate(start.getDate() - 7);
  else if (range === '1m') start.setMonth(start.getMonth() - 1);
  return { start_date: start.toISOString().split('T')[0], end_date };
}

function getTimeRange(range: TimeRange): { start_time?: string; end_time?: string } {
  if (range === 'all') return {};
  const now = new Date();
  const end_time = now.toISOString();
  const start = new Date(now);
  if (range === '1w') start.setDate(start.getDate() - 7);
  else if (range === '1m') start.setMonth(start.getMonth() - 1);
  return { start_time: start.toISOString(), end_time };
}

// ==================== Donut Chart ====================

const DONUT_COLORS = ['#3b82f6', '#4b5563'];

function ClosedPositionsDonut({ profit, loss }: { profit: number; loss: number }) {
  const data = [
    { name: 'Profit', value: profit },
    { name: 'Loss', value: loss },
  ];

  return (
    <ResponsiveContainer width={100} height={100}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={28}
          outerRadius={42}
          dataKey="value"
          strokeWidth={0}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={DONUT_COLORS[i]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}

// ==================== Performance by Asset Tab ====================

function PerformanceByAssetTab({ address, timeRange }: { address: string; timeRange: TimeRange }) {
  const [data, setData] = useState<PositionHistoryByCoin[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    const timeParams = getTimeRange(timeRange);
    traderApi.getPositionHistoryByCoin(address, {
      start_time: timeParams.start_time,
      end_time: timeParams.end_time,
    })
      .then(res => {
        if (res.success) setData(res.data || []);
      })
      .catch((err: any) => {
        addToast({ title: 'Failed to load asset performance', description: err.message, color: 'danger' });
      })
      .finally(() => setLoading(false));
  }, [address, timeRange]);

  const sorted = useMemo(() => [...data].sort((a, b) => b.total_pnl - a.total_pnl), [data]);

  if (loading) {
    return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  }

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-default-400">
        <Icon icon="solar:chart-2-broken" width={48} />
        <p className="mt-2">No asset data for this period</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {sorted.map((item) => {
        const winRate = item.win_rate * 100;
        return (
          <div key={item.coin} className="bg-default-50 rounded-xl p-4">
            {/* Header: Coin + Trades */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-sm">{item.coin}</span>
              </div>
              <span className="text-xs text-default-400">{item.total_positions} Trades</span>
            </div>

            {/* PnL */}
            <p className="text-xs text-default-400">PnL</p>
            <p className={`text-lg font-bold ${item.total_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
              $ {formatPnl(item.total_pnl)}
            </p>

            {/* Details */}
            <div className="mt-2 space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-default-400">Win Rate</span>
                <span className={`font-semibold ${winRate >= 50 ? 'text-success' : 'text-danger'}`}>{fmt(winRate, 1)}%</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-default-400">Volume</span>
                <span className="font-semibold">$ {fmt(item.total_volume)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ==================== Performance by Position Tab ====================

function PerformanceByPositionTab({ address, timeRange }: { address: string; timeRange: TimeRange }) {
  const [data, setData] = useState<PositionItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    const timeParams = getTimeRange(timeRange);
    traderApi.getPositionHistory(address, {
      limit: 10000,
      sort_order: 'desc',
      start_time: timeParams.start_time,
      end_time: timeParams.end_time,
    })
      .then(res => {
        if (res.success) setData(res.data || []);
      })
      .catch((err: any) => {
        addToast({ title: 'Failed to load position history', description: err.message, color: 'danger' });
      })
      .finally(() => setLoading(false));
  }, [address, timeRange]);

  if (loading) {
    return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  }

  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-default-400">
        <Icon icon="solar:chart-2-broken" width={48} />
        <p className="mt-2">No positions for this period</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-1">
      {data.map((item) => (
        <div key={item.id} className="bg-default-50 rounded-xl p-4">
          {/* Header: Coin + Direction + Time */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">{item.coin}</span>
              <Chip
                size="sm"
                color={item.direction === 'short' ? 'danger' : 'success'}
                variant="flat"
                classNames={{ content: 'text-xs font-semibold px-1' }}
              >
                {item.direction === 'short' ? 'Short' : 'Long'}
              </Chip>
            </div>
            <span className="text-xs text-default-400">
              {item.close_time ? timeAgo(item.close_time) : item.status === 'open' ? 'Open' : ''}
            </span>
          </div>

          {/* Details */}
          <div className="mt-2 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-default-400">Size</span>
              <span className="font-semibold">$ {fmt(item.position_value)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-default-400">Fees</span>
              <span className="font-semibold text-orange-500">$ {fmt(item.total_fee, 4)}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ==================== Main Component ====================

export function TradingStatisticsModal({ isOpen, onClose, address }: TradingStatisticsModalProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>('1w');
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [summary, setSummary] = useState<ClosedPositionsSummary | null>(null);
  const [bestTrades, setBestTrades] = useState<BestTrade[]>([]);
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const dateParams = getDateRange(timeRange);
      const [summaryRes, tradesRes] = await Promise.all([
        traderApi.getClosedPositionsSummary(address, dateParams),
        traderApi.getBestTrades(address, { ...dateParams, limit: 10 }),
      ]);

      if (summaryRes.success && summaryRes.data) {
        setSummary(summaryRes.data);
      } else {
        setSummary(null);
      }

      if (tradesRes.success && tradesRes.data) {
        setBestTrades(tradesRes.data);
      } else {
        setBestTrades([]);
      }
    } catch (err: any) {
      addToast({ title: 'Failed to load statistics', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address, timeRange]);

  useEffect(() => {
    if (isOpen && activeTab === 'overview') loadData();
  }, [isOpen, loadData, activeTab]);

  const noData = !loading && !summary;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="5xl" scrollBehavior="inside">
      <ModalContent className="bg-content1">
        {() => (
          <>
            <ModalHeader className="flex items-center justify-between pr-12">
              <span className="text-lg font-bold">Trading Statistics</span>
            </ModalHeader>
            <ModalBody className="pb-6">
              {/* Address + Time Range */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-default-100 flex items-center justify-center">
                    <Icon icon="solar:user-bold" width={16} className="text-default-400" />
                  </div>
                  <span className="font-mono text-sm text-default-500">{shortenAddress(address)}</span>
                  <button
                    onClick={() => copyToClipboard(address)}
                    className="text-default-400 hover:text-default-600 transition-colors"
                  >
                    <Icon icon="solar:copy-linear" width={14} />
                  </button>
                </div>

                <Dropdown>
                  <DropdownTrigger>
                    <Button
                      size="sm"
                      variant="bordered"
                      startContent={<Icon icon="solar:clock-circle-linear" width={16} />}
                      endContent={<Icon icon="solar:alt-arrow-down-linear" width={14} />}
                    >
                      {TIME_RANGE_LABELS[timeRange]}
                    </Button>
                  </DropdownTrigger>
                  <DropdownMenu
                    selectionMode="single"
                    selectedKeys={new Set([timeRange])}
                    onSelectionChange={(keys) => {
                      const key = Array.from(keys)[0] as TimeRange;
                      if (key) setTimeRange(key);
                    }}
                  >
                    <DropdownItem key="1w">1W</DropdownItem>
                    <DropdownItem key="1m">1M</DropdownItem>
                    <DropdownItem key="all">All</DropdownItem>
                  </DropdownMenu>
                </Dropdown>
              </div>

              {/* Tabs */}
              <Tabs
                selectedKey={activeTab}
                onSelectionChange={(key) => setActiveTab(key as TabKey)}
                aria-label="Statistics tabs"
                color="primary"
                variant="underlined"
                classNames={{ tabList: 'gap-4' }}
              >
                <Tab key="overview" title="Overview" />
                <Tab key="by-asset" title="Performance by Asset" />
                <Tab key="by-position" title="Performance by Position" />
              </Tabs>

              {/* Overview Tab */}
              {activeTab === 'overview' && (
                <>
                  {loading && (
                    <div className="flex justify-center py-12">
                      <Spinner size="lg" />
                    </div>
                  )}

                  {noData && (
                    <div className="flex flex-col items-center justify-center py-12 text-default-400">
                      <Icon icon="solar:chart-2-broken" width={48} />
                      <p className="mt-2">No closed positions found for this period</p>
                    </div>
                  )}

                  {!loading && summary && (
                    <>
                      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                        {/* Win Rate Card */}
                        <div className="bg-default-50 rounded-xl p-4">
                          <p className="text-xs text-default-400 mb-1">Win Rate</p>
                          <p className="text-2xl font-bold">{summary.win_rate.rate}%</p>
                          <div className="mt-2 space-y-1">
                            <div className="flex justify-between text-xs">
                              <span className="text-default-400">Closing PnL (before fees)</span>
                              <span className="text-success">${formatPnl(summary.win_rate.closing_pnl)}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-default-400">Fees deducted</span>
                              <span className="text-success">${formatPnl(summary.win_rate.fees_deducted)}</span>
                            </div>
                          </div>
                        </div>

                        {/* Closed Positions Card */}
                        <div className="bg-default-50 rounded-xl p-4">
                          <p className="text-xs text-default-400 mb-1">Closed Positions</p>
                          <div className="flex items-center gap-3">
                            <div className="flex-1">
                              <p className="text-2xl font-bold">{summary.closed_positions.total}</p>
                              <div className="mt-2 space-y-1">
                                <div className="flex items-center gap-2 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-primary" />
                                  <span className="text-default-400">Profit</span>
                                  <span className="font-semibold ml-auto">{summary.closed_positions.profit}</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                  <span className="w-2 h-2 rounded-full bg-default-400" />
                                  <span className="text-default-400">Loss</span>
                                  <span className="font-semibold ml-auto">{summary.closed_positions.loss}</span>
                                </div>
                              </div>
                            </div>
                            <ClosedPositionsDonut
                              profit={summary.closed_positions.profit}
                              loss={summary.closed_positions.loss}
                            />
                          </div>
                        </div>

                        {/* Net PnL Card */}
                        <div className="bg-default-50 rounded-xl p-4">
                          <p className="text-xs text-default-400 mb-1">Net PnL</p>
                          <p className={`text-2xl font-bold ${summary.net_pnl.total >= 0 ? 'text-success' : 'text-danger'}`}>
                            $ {formatPnl(summary.net_pnl.total)}
                          </p>
                          <div className="mt-2 space-y-1">
                            <div className="flex justify-between text-xs">
                              <span className="text-default-400">Long</span>
                              <span className={summary.net_pnl.long >= 0 ? 'text-success' : 'text-danger'}>
                                $ {formatPnl(summary.net_pnl.long)}
                              </span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-default-400">Short</span>
                              <span className={summary.net_pnl.short >= 0 ? 'text-success' : 'text-danger'}>
                                $ {formatPnl(summary.net_pnl.short)}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Total Holding Time Card */}
                        <div className="bg-default-50 rounded-xl p-4">
                          <p className="text-xs text-default-400 mb-1">Total Holding Time</p>
                          <p className="text-2xl font-bold">{summary.holding_time.total}</p>
                          <div className="mt-2 space-y-1">
                            <div className="flex justify-between text-xs">
                              <span className="text-default-400">Holding Range</span>
                              <span className="font-semibold">{summary.holding_time.range_min} ~ {summary.holding_time.range_max}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                              <span className="text-default-400">Average Holding Time</span>
                              <span className="font-semibold">{summary.holding_time.average}</span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Best Trades Section */}
                      {bestTrades.length > 0 && (
                        <div className="mt-4">
                          <p className="text-base font-bold mb-3">Top {bestTrades.length} Best Trades</p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                            {bestTrades.map((trade, idx) => (
                              <div key={idx} className="bg-default-50 rounded-xl p-4">
                                {/* Header: Coin + Direction + Time */}
                                <div className="flex items-center justify-between mb-2">
                                  <div className="flex items-center gap-2">
                                    <span className="font-semibold text-sm">{trade.coin}</span>
                                    <Chip
                                      size="sm"
                                      color={trade.direction === 'short' ? 'danger' : 'success'}
                                      variant="flat"
                                      classNames={{ content: 'text-xs font-semibold px-1' }}
                                    >
                                      {trade.direction === 'short' ? 'Short' : 'Long'}
                                    </Chip>
                                  </div>
                                  <span className="text-xs text-default-400">
                                    {trade.close_time ? timeAgo(trade.close_time) : ''}
                                  </span>
                                </div>

                                {/* PnL */}
                                <p className="text-xs text-default-400">PnL</p>
                                <p className={`text-lg font-bold ${trade.realized_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                                  $ {formatPnl(trade.realized_pnl)}
                                </p>

                                {/* Duration */}
                                <div className="flex justify-between mt-2 text-xs">
                                  <span className="text-default-400">Duration</span>
                                  <span className="font-semibold">{formatHoldingTime(trade.holding_hours)}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}

              {/* Performance by Asset Tab */}
              {activeTab === 'by-asset' && (
                <PerformanceByAssetTab address={address} timeRange={timeRange} />
              )}

              {/* Performance by Position Tab */}
              {activeTab === 'by-position' && (
                <PerformanceByPositionTab address={address} timeRange={timeRange} />
              )}
            </ModalBody>
          </>
        )}
      </ModalContent>
    </Modal>
  );
}
