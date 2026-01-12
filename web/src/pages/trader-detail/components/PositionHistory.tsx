import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Button } from '@heroui/button';
import { Spinner } from '@heroui/spinner';
import { Select, SelectItem } from '@heroui/select';
import { Pagination } from '@heroui/pagination';
import { Input } from '@heroui/input';
import { Tabs, Tab } from '@heroui/tabs';
import { addToast, Autocomplete, AutocompleteItem } from '@heroui/react';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Icon } from '@iconify/react';
import { traderApi, PositionHistoryRecord, PositionHistoryStats, PositionHistoryByCoin } from '@/services/api';

interface PositionHistoryProps {
  address: string;
}

// 时间范围预设选项
const TIME_RANGE_OPTIONS = [
  { key: 'all', label: '全部时间' },
  { key: '1d', label: '最近1天' },
  { key: '7d', label: '最近7天' },
  { key: '30d', label: '最近30天' },
  { key: '90d', label: '最近90天' },
  { key: 'custom', label: '自定义' },
];

export function PositionHistory({ address }: PositionHistoryProps) {
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [positions, setPositions] = useState<PositionHistoryRecord[]>([]);
  const [stats, setStats] = useState<PositionHistoryStats | null>(null);
  const [byCoin, setByCoin] = useState<PositionHistoryByCoin[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedTab, setSelectedTab] = useState<string>('list');
  const [jumpPage, setJumpPage] = useState('');
  const rowsPerPage = 20;

  // 筛选状态
  const [coinFilter, setCoinFilter] = useState<string>('all');
  const [directionFilter, setDirectionFilter] = useState<'all' | 'long' | 'short'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [pnlFilter, setPnlFilter] = useState<'all' | 'profit' | 'loss'>('all');
  const [timeRangeFilter, setTimeRangeFilter] = useState<string>('all');
  const [customStartDate, setCustomStartDate] = useState<string>('');
  const [customEndDate, setCustomEndDate] = useState<string>('');

  // 计算实际的时间范围
  const { startTime, endTime } = useMemo(() => {
    if (timeRangeFilter === 'all') {
      return { startTime: undefined, endTime: undefined };
    }
    if (timeRangeFilter === 'custom') {
      return {
        startTime: customStartDate || undefined,
        endTime: customEndDate ? `${customEndDate}T23:59:59` : undefined,
      };
    }
    // 预设时间范围
    const now = new Date();
    const days = parseInt(timeRangeFilter.replace('d', ''));
    const start = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
    return {
      startTime: start.toISOString(),
      endTime: undefined,
    };
  }, [timeRangeFilter, customStartDate, customEndDate]);

  // 获取币种选项
  const coinOptions = useMemo(() => {
    return ['all', ...byCoin.map(c => c.coin)];
  }, [byCoin]);

  // 重置筛选
  const handleResetFilters = () => {
    setCoinFilter('all');
    setDirectionFilter('all');
    setStatusFilter('all');
    setPnlFilter('all');
    setTimeRangeFilter('all');
    setCustomStartDate('');
    setCustomEndDate('');
    setPage(1);
  };

  // 检查是否有活跃的筛选
  const hasActiveFilters = coinFilter !== 'all' || directionFilter !== 'all' || statusFilter !== 'all' || pnlFilter !== 'all' || timeRangeFilter !== 'all';

  // 页码跳转
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      setPage(pageNum);
      setJumpPage('');
    }
  };

  const formatNumber = (num: number, decimals = 2) => {
    return num?.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }) || '0';
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const formatHours = (hours: number | null) => {
    if (!hours) return '-';
    if (hours < 1) return `${Math.round(hours * 60)}分钟`;
    if (hours < 24) return `${hours.toFixed(1)}小时`;
    return `${(hours / 24).toFixed(1)}天`;
  };

  const formatTime = (time: string | null) => {
    if (!time) return '-';
    return new Date(time).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 加载仓位历史列表
  const loadPositions = useCallback(async () => {
    try {
      setLoading(true);
      const res = await traderApi.getPositionHistory(address, {
        coin: coinFilter !== 'all' ? coinFilter : undefined,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        direction: directionFilter !== 'all' ? directionFilter : undefined,
        start_time: startTime,
        end_time: endTime,
        pnl_filter: pnlFilter !== 'all' ? pnlFilter : undefined,
        page,
        limit: rowsPerPage,
      });

      if (res.success && res.data) {
        setPositions(res.data);
        if (res.pagination) {
          setTotalPages(res.pagination.total_pages);
          setTotalCount(res.pagination.total_count);
        }
      }
    } catch (err) {
      console.error('Failed to load position history:', err);
    } finally {
      setLoading(false);
    }
  }, [address, coinFilter, statusFilter, directionFilter, startTime, endTime, pnlFilter, page]);

  // 加载统计信息
  const loadStats = useCallback(async () => {
    try {
      const [statsRes, byCoinRes] = await Promise.all([
        traderApi.getPositionHistoryStats(address),
        traderApi.getPositionHistoryByCoin(address),
      ]);

      if (statsRes.success && statsRes.data) {
        setStats(statsRes.data);
      }
      if (byCoinRes.success && byCoinRes.data) {
        setByCoin(byCoinRes.data);
      }
    } catch (err) {
      console.error('Failed to load position history stats:', err);
    }
  }, [address]);

  // 重建仓位历史
  const handleRebuild = async () => {
    if (rebuilding) return;

    try {
      setRebuilding(true);
      const res = await traderApi.rebuildPositionHistory(address);

      if (res.success) {
        addToast({
          title: `已重建 ${res.data?.count || 0} 条仓位历史`,
          color: 'success',
        });
        // 重新加载数据
        loadPositions();
        loadStats();
      } else {
        addToast({
          title: '重建失败: ' + (res.error || '未知错误'),
          color: 'danger',
        });
      }
    } catch (err: any) {
      addToast({
        title: '重建失败: ' + (err.message || '请求失败'),
        color: 'danger',
      });
    } finally {
      setRebuilding(false);
    }
  };

  useEffect(() => {
    loadPositions();
  }, [loadPositions]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // 筛选改变时重置页码
  useEffect(() => {
    setPage(1);
  }, [coinFilter, statusFilter, directionFilter, pnlFilter, startTime, endTime]);

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold">仓位历史</h2>
            <Chip size="sm" variant="flat" color="secondary">
              {totalCount}
            </Chip>
          </div>
          <Button
            size="sm"
            color="primary"
            variant="flat"
            isLoading={rebuilding}
            onPress={handleRebuild}
            startContent={!rebuilding && <Icon icon="solar:refresh-bold" width={16} />}
          >
            {rebuilding ? '重建中...' : '重建历史'}
          </Button>
        </div>
      </CardHeader>
      <CardBody>
        {/* 统计卡片 */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-4">
            <div className="bg-default-100 rounded-lg p-3">
              <div className="text-xs text-gray-500">总仓位数</div>
              <div className="text-lg font-bold">{stats.total_positions}</div>
            </div>
            <div className="bg-default-100 rounded-lg p-3">
              <div className="text-xs text-gray-500">已平仓</div>
              <div className="text-lg font-bold">{stats.closed_positions}</div>
            </div>
            <div className="bg-default-100 rounded-lg p-3">
              <div className="text-xs text-gray-500">仓位胜率</div>
              <div className="text-lg font-bold">{formatPercent(stats.win_rate)}</div>
            </div>
            <div className="bg-default-100 rounded-lg p-3">
              <div className="text-xs text-gray-500">总盈亏</div>
              <div className={`text-lg font-bold ${stats.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${formatNumber(stats.total_pnl)}
              </div>
            </div>
            <div className="bg-default-100 rounded-lg p-3">
              <div className="text-xs text-gray-500">平均持仓</div>
              <div className="text-lg font-bold">{formatHours(stats.avg_holding_hours)}</div>
            </div>
            <div className="bg-default-100 rounded-lg p-3">
              <div className="text-xs text-gray-500">交易币种</div>
              <div className="text-lg font-bold">{stats.unique_coins}</div>
            </div>
          </div>
        )}

        {/* 选项卡 */}
        <Tabs
          selectedKey={selectedTab}
          onSelectionChange={(key) => setSelectedTab(key as string)}
          className="mb-4"
        >
          <Tab key="list" title="仓位列表" />
          <Tab key="by-coin" title="按币种统计" />
        </Tabs>

        {selectedTab === 'list' && (
          <>
            {/* 筛选条件 */}
            <div className="flex flex-wrap gap-3 items-center mb-4">
              {/* 币种筛选 */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm whitespace-nowrap text-gray-500">币种</span>
                <Autocomplete
                  className="min-w-[140px]"
                  aria-label="币种筛选"
                  size="sm"
                  selectedKey={coinFilter}
                  onSelectionChange={(key) => setCoinFilter((key as string) || 'all')}
                  allowsCustomValue={false}
                  defaultItems={coinOptions.map((coin) => ({
                    key: coin,
                    label: coin === 'all' ? '全部' : coin,
                  }))}
                >
                  {(item) => (
                    <AutocompleteItem key={item.key} textValue={item.label}>
                      {item.label}
                    </AutocompleteItem>
                  )}
                </Autocomplete>
              </div>

              {/* 方向筛选 */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm whitespace-nowrap text-gray-500">方向</span>
                <Select
                  className="min-w-[100px]"
                  aria-label="方向筛选"
                  size="sm"
                  selectedKeys={[directionFilter]}
                  onSelectionChange={(keys) => setDirectionFilter(Array.from(keys)[0] as 'all' | 'long' | 'short')}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="long" textValue="多头">多头</SelectItem>
                  <SelectItem key="short" textValue="空头">空头</SelectItem>
                </Select>
              </div>

              {/* 状态筛选 */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm whitespace-nowrap text-gray-500">状态</span>
                <Select
                  className="min-w-[100px]"
                  aria-label="状态筛选"
                  size="sm"
                  selectedKeys={[statusFilter]}
                  onSelectionChange={(keys) => setStatusFilter(Array.from(keys)[0] as 'all' | 'open' | 'closed')}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="closed" textValue="已平仓">已平仓</SelectItem>
                  <SelectItem key="open" textValue="持仓中">持仓中</SelectItem>
                </Select>
              </div>

              {/* 盈亏筛选 */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm whitespace-nowrap text-gray-500">盈亏</span>
                <Select
                  className="min-w-[100px]"
                  aria-label="盈亏筛选"
                  size="sm"
                  selectedKeys={[pnlFilter]}
                  onSelectionChange={(keys) => setPnlFilter(Array.from(keys)[0] as 'all' | 'profit' | 'loss')}
                >
                  <SelectItem key="all" textValue="全部">全部</SelectItem>
                  <SelectItem key="profit" textValue="盈利">盈利</SelectItem>
                  <SelectItem key="loss" textValue="亏损">亏损</SelectItem>
                </Select>
              </div>

              {/* 时间范围筛选 */}
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-sm whitespace-nowrap text-gray-500">时间</span>
                <Select
                  className="min-w-[120px]"
                  aria-label="时间范围筛选"
                  size="sm"
                  selectedKeys={[timeRangeFilter]}
                  onSelectionChange={(keys) => setTimeRangeFilter(Array.from(keys)[0] as string)}
                >
                  {TIME_RANGE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.key} textValue={opt.label}>{opt.label}</SelectItem>
                  ))}
                </Select>
              </div>

              {/* 自定义时间范围 */}
              {timeRangeFilter === 'custom' && (
                <div className="flex items-center gap-2 shrink-0">
                  <Input
                    type="date"
                    size="sm"
                    className="w-36"
                    aria-label="开始日期"
                    value={customStartDate}
                    onValueChange={setCustomStartDate}
                  />
                  <span className="text-gray-400">-</span>
                  <Input
                    type="date"
                    size="sm"
                    className="w-36"
                    aria-label="结束日期"
                    value={customEndDate}
                    onValueChange={setCustomEndDate}
                  />
                </div>
              )}

              {/* 重置按钮 */}
              {hasActiveFilters && (
                <Button
                  variant="flat"
                  color="warning"
                  size="sm"
                  startContent={<Icon icon="solar:restart-linear" width={16} />}
                  onPress={handleResetFilters}
                >
                  重置
                </Button>
              )}
            </div>

            {/* 仓位列表表格 */}
            {loading ? (
              <div className="flex justify-center items-center h-64">
                <Spinner size="lg" />
              </div>
            ) : positions.length > 0 ? (
              <>
                <Table
                  isHeaderSticky
                  aria-label="Position history table"
                  classNames={{
                    wrapper: 'max-h-[500px]',
                  }}
                >
                  <TableHeader>
                    <TableColumn key="coin">币种</TableColumn>
                    <TableColumn key="direction">方向</TableColumn>
                    <TableColumn key="open_time">开仓时间</TableColumn>
                    <TableColumn key="close_time">平仓时间</TableColumn>
                    <TableColumn key="max_size">最大仓位</TableColumn>
                    <TableColumn key="entry_price">开仓均价</TableColumn>
                    <TableColumn key="close_price">平仓均价</TableColumn>
                    <TableColumn key="holding">持仓时长</TableColumn>
                    <TableColumn key="pnl">盈亏</TableColumn>
                    <TableColumn key="status">状态</TableColumn>
                  </TableHeader>
                  <TableBody items={positions}>
                    {(item) => (
                      <TableRow key={item.id}>
                        <TableCell>
                          <span className="font-bold">{item.coin}</span>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="sm"
                            color={item.direction === 'long' ? 'success' : 'danger'}
                            variant="flat"
                          >
                            {item.direction === 'long' ? 'LONG' : 'SHORT'}
                          </Chip>
                        </TableCell>
                        <TableCell>{formatTime(item.open_time)}</TableCell>
                        <TableCell>{formatTime(item.close_time)}</TableCell>
                        <TableCell>{formatNumber(item.max_size, 4)}</TableCell>
                        <TableCell>${formatNumber(item.avg_entry_price, 4)}</TableCell>
                        <TableCell>
                          {item.avg_close_price ? `$${formatNumber(item.avg_close_price, 4)}` : '-'}
                        </TableCell>
                        <TableCell>{formatHours(item.holding_hours)}</TableCell>
                        <TableCell>
                          <span className={item.realized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            ${formatNumber(item.realized_pnl)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="sm"
                            color={item.status === 'open' ? 'warning' : 'default'}
                            variant="flat"
                          >
                            {item.status === 'open' ? '持仓中' : '已平仓'}
                          </Chip>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>

                {/* 分页 */}
                <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2 mt-4">
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
              </>
            ) : (
              <div className="text-center text-gray-500 py-8">
                暂无仓位历史，点击"重建历史"从交易记录中生成
              </div>
            )}
          </>
        )}

        {selectedTab === 'by-coin' && (
          <>
            {byCoin.length > 0 ? (
              <Table
                isHeaderSticky
                aria-label="Position history by coin"
                classNames={{
                  wrapper: 'max-h-[500px]',
                }}
              >
                <TableHeader>
                  <TableColumn key="coin">币种</TableColumn>
                  <TableColumn key="total">总仓位数</TableColumn>
                  <TableColumn key="closed">已平仓</TableColumn>
                  <TableColumn key="win_rate">胜率</TableColumn>
                  <TableColumn key="pnl">总盈亏</TableColumn>
                  <TableColumn key="avg_pnl">平均盈亏</TableColumn>
                  <TableColumn key="pnl_ratio">盈亏占比</TableColumn>
                  <TableColumn key="volume">总交易量</TableColumn>
                  <TableColumn key="holding">平均持仓</TableColumn>
                </TableHeader>
                <TableBody items={byCoin}>
                  {(item) => {
                    const avgPnl = item.closed_positions > 0 ? item.total_pnl / item.closed_positions : 0;
                    const pnlRatio = stats?.total_pnl && stats.total_pnl !== 0
                      ? (item.total_pnl / stats.total_pnl) * 100
                      : 0;
                    return (
                      <TableRow key={item.coin}>
                        <TableCell>
                          <span className="font-bold">{item.coin}</span>
                        </TableCell>
                        <TableCell>{item.total_positions}</TableCell>
                        <TableCell>{item.closed_positions}</TableCell>
                        <TableCell>{formatPercent(item.win_rate)}</TableCell>
                        <TableCell>
                          <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            ${formatNumber(item.total_pnl)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={avgPnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            ${formatNumber(avgPnl)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                            {pnlRatio.toFixed(2)}%
                          </span>
                        </TableCell>
                        <TableCell>${formatNumber(item.total_volume)}</TableCell>
                        <TableCell>{formatHours(item.avg_holding_hours)}</TableCell>
                      </TableRow>
                    );
                  }}
                </TableBody>
              </Table>
            ) : (
              <div className="text-center text-gray-500 py-8">
                暂无币种统计数据
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}
