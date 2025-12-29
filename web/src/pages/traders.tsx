import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Selection, SortDescriptor } from '@heroui/react';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Spinner } from '@heroui/spinner';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Input } from '@heroui/input';
import { Button } from '@heroui/button';
import { Pagination } from '@heroui/pagination';
import { Chip } from '@heroui/chip';
import { Select, SelectItem } from '@heroui/select';
import { Form } from '@heroui/form';
import { SearchIcon } from '@heroui/shared-icons';
import { Icon } from '@iconify/react';
import DefaultLayout from '@/layouts/default';
import { traderApi, Trader } from '@/services/api';

// 表格列配置
type ColumnKey =
  | 'rating' | 'address' | 'overall_score' | 'total_trades' | 'win_rate'
  | 'total_pnl' | 'roi' | 'profit_factor' | 'max_drawdown' | 'sharpe_ratio'
  | 'sortino_ratio' | 'current_equity' | 'active_days' | 'avg_leverage'
  | 'current_positions' | 'recent_7d_pnl' | 'recent_7d_win_rate'
  | 'max_consecutive_wins' | 'max_consecutive_losses' | 'unique_symbols'
  | 'favorite_symbol' | 'long_short_ratio' | 'last_trade_time';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
  group?: string;
}

const columns: Column[] = [
  // 基础
  { uid: 'rating', name: '评级', sortable: true, group: '基础' },
  { uid: 'address', name: '地址', sortable: false, group: '基础' },
  { uid: 'overall_score', name: '评分', sortable: true, group: '基础' },
  // 交易统计
  { uid: 'total_trades', name: '交易数', sortable: true, group: '统计' },
  { uid: 'win_rate', name: '胜率', sortable: true, group: '统计' },
  { uid: 'total_pnl', name: '总盈亏', sortable: true, group: '盈亏' },
  { uid: 'roi', name: 'ROI', sortable: true, group: '盈亏' },
  { uid: 'profit_factor', name: '盈亏比', sortable: true, group: '盈亏' },
  // 风险
  { uid: 'max_drawdown', name: '回撤', sortable: true, group: '风险' },
  { uid: 'sharpe_ratio', name: 'Sharpe', sortable: true, group: '风险' },
  { uid: 'sortino_ratio', name: 'Sortino', sortable: true, group: '风险' },
  // 活跃度
  { uid: 'active_days', name: '活跃天', sortable: true, group: '活跃' },
  { uid: 'current_equity', name: '权益', sortable: true, group: '活跃' },
  { uid: 'avg_leverage', name: '杠杆', sortable: true, group: '活跃' },
  { uid: 'current_positions', name: '持仓', sortable: true, group: '活跃' },
  { uid: 'last_trade_time', name: '最后交易', sortable: true, group: '活跃' },
  // 近期表现
  { uid: 'recent_7d_pnl', name: '7天PnL', sortable: true, group: '近期' },
  { uid: 'recent_7d_win_rate', name: '7天胜率', sortable: true, group: '近期' },
  // 交易特征
  { uid: 'max_consecutive_wins', name: '连赢', sortable: true, group: '特征' },
  { uid: 'max_consecutive_losses', name: '连亏', sortable: true, group: '特征' },
  { uid: 'unique_symbols', name: '品种数', sortable: true, group: '特征' },
  { uid: 'favorite_symbol', name: '常用品种', sortable: false, group: '特征' },
  { uid: 'long_short_ratio', name: '多空比', sortable: true, group: '特征' },
];

const INITIAL_VISIBLE_COLUMNS: ColumnKey[] = [
  'rating', 'address', 'overall_score', 'total_trades', 'win_rate',
  'total_pnl', 'roi', 'profit_factor', 'max_drawdown', 'sharpe_ratio',
  'sortino_ratio', 'current_equity', 'active_days', 'avg_leverage',
  'current_positions', 'recent_7d_pnl', 'recent_7d_win_rate',
  'max_consecutive_wins', 'max_consecutive_losses', 'unique_symbols',
  'favorite_symbol', 'long_short_ratio', 'last_trade_time'
];

// 高级筛选器配置
interface FilterConfig {
  minWinRate?: number;
  maxWinRate?: number;
  minProfitFactor?: number;
  maxProfitFactor?: number;
  minPnl?: number;
  maxPnl?: number;
  minDrawdown?: number;
  maxDrawdown?: number;
  minSharpe?: number;
  maxSharpe?: number;
  minTrades?: number;
  maxTrades?: number;
  minActiveDays?: number;
  maxActiveDays?: number;
  hasRecentTrade?: number;
}

export default function TradersPage() {
  const navigate = useNavigate();
  const [traders, setTraders] = useState<Trader[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchAddress, setSearchAddress] = useState('');
  const [selectedRating, setSelectedRating] = useState<string>('');
  const [page, setPage] = useState(1);
  const rowsPerPage = 20;
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  // 筛选状态
  const [filters, setFilters] = useState<FilterConfig>({});

  // 高级表格状态
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'overall_score',
    direction: 'descending',
  });

  const loadTraders = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        page,
        limit: rowsPerPage,
        search: searchAddress || undefined,
        rating: selectedRating || undefined,
        sort_by: sortDescriptor.column as string,
        sort_order: sortDescriptor.direction === 'ascending' ? 'asc' as const : 'desc' as const,
        // 高级筛选 - 区间查询（百分比字段需要除以100转换为小数）
        min_win_rate: filters.minWinRate !== undefined ? filters.minWinRate / 100 : undefined,
        max_win_rate: filters.maxWinRate !== undefined ? filters.maxWinRate / 100 : undefined,
        min_profit_factor: filters.minProfitFactor,
        max_profit_factor: filters.maxProfitFactor,
        min_pnl: filters.minPnl,
        max_pnl: filters.maxPnl,
        min_drawdown: filters.minDrawdown !== undefined ? filters.minDrawdown / 100 : undefined,
        max_drawdown: filters.maxDrawdown !== undefined ? filters.maxDrawdown / 100 : undefined,
        min_sharpe: filters.minSharpe,
        max_sharpe: filters.maxSharpe,
        min_trades: filters.minTrades,
        max_trades: filters.maxTrades,
        min_active_days: filters.minActiveDays,
        max_active_days: filters.maxActiveDays,
        has_recent_trade: filters.hasRecentTrade,
      };

      const response = await traderApi.getTraders(params);

      if (response.success && response.data) {
        setTraders(response.data);
        if (response.pagination) {
          setTotalPages(response.pagination.total_pages);
          setTotalCount(response.pagination.total_count);
        }
      } else {
        setError(response.error || 'Failed to load traders');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, [page, searchAddress, selectedRating, sortDescriptor, filters]);

  useEffect(() => {
    loadTraders();
  }, [loadTraders]);

  // 筛选条件或排序改变时重置页码
  useEffect(() => {
    setPage(1);
  }, [searchAddress, selectedRating, sortDescriptor, filters]);

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

  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const handleRowClick = (address: string) => {
    navigate(`/traders/${address}`);
  };


  // 可见列
  const headerColumns = useMemo(() => {
    if (visibleColumns === 'all') return columns;
    return columns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  // 搜索变化处理
  const onSearchChange = useCallback((value?: string) => {
    setSearchAddress(value || '');
    setPage(1);
  }, []);

  // 重置筛选
  const handleReset = useCallback(() => {
    setSelectedRating('');
    setSearchAddress('');
    setFilters({});
    setSortDescriptor({ column: 'overall_score', direction: 'descending' });
    setPage(1);
  }, []);

  // 格式化日期
  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return '-';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
    } catch {
      return '-';
    }
  };

  // 单元格渲染
  const renderCell = useCallback((trader: Trader, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'rating':
        return (
          <span className={`font-bold text-lg ${getRatingColor(trader.rating)}`}>
            {trader.rating}
          </span>
        );
      case 'address':
        return (
          <a
            href={`/traders/${trader.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-sm text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {trader.address.slice(0, 6)}...{trader.address.slice(-4)}
          </a>
        );
      case 'overall_score':
        return <span className="font-bold">{formatNumber(trader.overall_score)}</span>;
      case 'total_trades':
        return <span>{trader.total_trades}</span>;
      case 'win_rate':
        return <span>{formatPercent(trader.win_rate)}</span>;
      case 'total_pnl':
        return (
          <span className={trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
            ${formatNumber(trader.total_pnl, 0)}
          </span>
        );
      case 'roi':
        return (
          <span className={trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}>
            {formatPercent(trader.roi)}
          </span>
        );
      case 'profit_factor':
        return <span>{formatNumber(trader.profit_factor)}</span>;
      case 'max_drawdown':
        return <span className="text-red-500">{formatPercent(trader.max_drawdown)}</span>;
      case 'sharpe_ratio':
        return <span>{formatNumber(trader.sharpe_ratio)}</span>;
      case 'sortino_ratio':
        return <span>{formatNumber(trader.sortino_ratio || 0)}</span>;
      case 'current_equity':
        return <span>${formatNumber(trader.current_equity, 0)}</span>;
      case 'active_days':
        return <span>{trader.active_days}</span>;
      case 'avg_leverage':
        return <span>{trader.avg_leverage || 1}x</span>;
      case 'current_positions':
        return <span>{trader.current_positions || 0}</span>;
      case 'last_trade_time':
        return <span className="text-sm">{formatDate(trader.last_trade_time)}</span>;
      case 'recent_7d_pnl':
        const pnl7d = trader.recent_7d_pnl || 0;
        return (
          <span className={pnl7d >= 0 ? 'text-green-500' : 'text-red-500'}>
            ${formatNumber(pnl7d, 0)}
          </span>
        );
      case 'recent_7d_win_rate':
        return <span>{formatPercent(trader.recent_7d_win_rate || 0)}</span>;
      case 'max_consecutive_wins':
        return <span className="text-green-500">{trader.max_consecutive_wins || 0}</span>;
      case 'max_consecutive_losses':
        return <span className="text-red-500">{trader.max_consecutive_losses || 0}</span>;
      case 'unique_symbols':
        return <span>{trader.unique_symbols || 0}</span>;
      case 'favorite_symbol':
        return <span className="text-sm">{trader.favorite_symbol || '-'}</span>;
      case 'long_short_ratio':
        return <span>{formatPercent(trader.long_short_ratio || 0)}</span>;
      default:
        return null;
    }
  }, []);

  // 表格顶部内容
  const topContent = useMemo(() => {
    return (
      <div className="flex flex-col gap-4">
        <Form className="flex flex-col gap-4">
          {/* 第一行：地址搜索 + 评级 + 排序 + 列选择 */}
          <div className="flex flex-wrap items-end gap-3">
            <Input
              className="w-[220px]"
              endContent={<SearchIcon className="text-default-400" width={16} />}
              label="地址"
              labelPlacement="outside"
              placeholder="搜索地址..."
              size="sm"
              value={searchAddress}
              onValueChange={onSearchChange}
              isClearable
              onClear={() => setSearchAddress('')}
            />

            <Select
              className="w-[120px]"
              label="评级"
              labelPlacement="outside"
              placeholder="全部"
              size="sm"
              selectedKeys={selectedRating ? [selectedRating] : []}
              onSelectionChange={(keys) => {
                const selected = Array.from(keys)[0] as string;
                setSelectedRating(selected || '');
              }}
            >
              <SelectItem key="S">S</SelectItem>
              <SelectItem key="A">A</SelectItem>
              <SelectItem key="B">B</SelectItem>
              <SelectItem key="C">C</SelectItem>
              <SelectItem key="D">D</SelectItem>
              <SelectItem key="F">F</SelectItem>
            </Select>

            <Select
              className="w-[140px]"
              label="排序"
              labelPlacement="outside"
              placeholder="选择排序"
              size="sm"
              selectedKeys={sortDescriptor.column ? [sortDescriptor.column as string] : []}
              onSelectionChange={(keys) => {
                const selected = Array.from(keys)[0] as string;
                if (selected) {
                  setSortDescriptor({
                    column: selected,
                    direction: sortDescriptor.column === selected && sortDescriptor.direction === 'descending'
                      ? 'ascending'
                      : 'descending',
                  });
                }
              }}
            >
              {columns.filter((c) => c.sortable).map((col) => (
                <SelectItem key={col.uid}>{col.name}</SelectItem>
              ))}
            </Select>

            <Select
              className="w-[160px]"
              label="显示列"
              labelPlacement="outside"
              placeholder="选择列"
              size="sm"
              selectionMode="multiple"
              selectedKeys={visibleColumns}
              onSelectionChange={setVisibleColumns}
            >
              {columns.map((col) => (
                <SelectItem key={col.uid}>{col.name}</SelectItem>
              ))}
            </Select>
          </div>

          {/* 第二行：数值筛选条件（区间查询） */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 胜率区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">胜率</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minWinRate?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minWinRate: v ? parseFloat(v) : undefined })}
                  endContent={<span className="text-xs text-default-400">%</span>}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxWinRate?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxWinRate: v ? parseFloat(v) : undefined })}
                  endContent={<span className="text-xs text-default-400">%</span>}
                />
              </div>
            </div>

            {/* 盈亏比区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">盈亏比</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minProfitFactor?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minProfitFactor: v ? parseFloat(v) : undefined })}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxProfitFactor?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxProfitFactor: v ? parseFloat(v) : undefined })}
                />
              </div>
            </div>

            {/* PnL区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">总盈亏 ($)</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minPnl?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minPnl: v ? parseFloat(v) : undefined })}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxPnl?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxPnl: v ? parseFloat(v) : undefined })}
                />
              </div>
            </div>

            {/* 回撤区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">回撤</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minDrawdown?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minDrawdown: v ? parseFloat(v) : undefined })}
                  endContent={<span className="text-xs text-default-400">%</span>}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxDrawdown?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxDrawdown: v ? parseFloat(v) : undefined })}
                  endContent={<span className="text-xs text-default-400">%</span>}
                />
              </div>
            </div>

            {/* Sharpe区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">Sharpe</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minSharpe?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minSharpe: v ? parseFloat(v) : undefined })}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxSharpe?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxSharpe: v ? parseFloat(v) : undefined })}
                />
              </div>
            </div>

            {/* 交易数区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">交易数</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minTrades?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minTrades: v ? parseInt(v) : undefined })}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxTrades?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxTrades: v ? parseInt(v) : undefined })}
                />
              </div>
            </div>

            {/* 活跃天区间 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">活跃天数</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="最小"
                  value={filters.minActiveDays?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, minActiveDays: v ? parseInt(v) : undefined })}
                />
                <span className="text-default-400">-</span>
                <Input
                  type="number"
                  size="sm"
                  placeholder="最大"
                  value={filters.maxActiveDays?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, maxActiveDays: v ? parseInt(v) : undefined })}
                />
              </div>
            </div>

            {/* 最近活跃 */}
            <div className="flex flex-col gap-1">
              <span className="text-xs text-default-600">最近活跃</span>
              <div className="flex items-center gap-1">
                <Input
                  type="number"
                  size="sm"
                  placeholder="N天内"
                  value={filters.hasRecentTrade?.toString() || ''}
                  onValueChange={(v) => setFilters({ ...filters, hasRecentTrade: v ? parseInt(v) : undefined })}
                  endContent={<span className="text-xs text-default-400">天</span>}
                />
              </div>
            </div>
          </div>

          {/* 第三行：搜索和重置按钮 */}
          <div className="flex gap-2">
            <Button
              color="primary"
              size="sm"
              startContent={<SearchIcon width={16} />}
              onPress={loadTraders}
            >
              搜索
            </Button>
            <Button
              variant="flat"
              size="sm"
              startContent={<Icon icon="solar:restart-linear" width={16} />}
              onPress={handleReset}
            >
              重置
            </Button>
          </div>
        </Form>
      </div>
    );
  }, [searchAddress, selectedRating, sortDescriptor, visibleColumns, filters, onSearchChange, handleReset, loadTraders]);

  // 页码跳转
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
  }, [page, totalPages, totalCount, jumpPage]);

  return (
    <DefaultLayout>
      <section className="flex flex-col gap-4 py-4">
        <div className="w-full">
          <Card>
            <CardBody>
              {error ? (
                <div className="text-center text-red-500 p-8">{error}</div>
              ) : (
                <Table
                  isHeaderSticky
                  aria-label="Traders table"
                  selectionMode="single"
                  onRowAction={(key) => handleRowClick(key.toString())}
                  topContent={topContent}
                  topContentPlacement="outside"
                  bottomContent={bottomContent}
                  bottomContentPlacement="outside"
                  sortDescriptor={sortDescriptor}
                  onSortChange={setSortDescriptor}
                  classNames={{
                    wrapper: 'min-h-[400px] max-h-[600px]',
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
                    items={traders}
                    isLoading={loading}
                    loadingContent={<Spinner size="lg" />}
                    emptyContent="暂无交易者数据"
                  >
                    {(item) => (
                      <TableRow
                        key={item.address}
                        className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
                      >
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
      </section>
    </DefaultLayout>
  );
}
