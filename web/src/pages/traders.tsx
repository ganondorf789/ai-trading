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
import {
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from '@heroui/dropdown';
import { Divider } from '@heroui/divider';
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
  'total_pnl', 'profit_factor', 'max_drawdown', 'sharpe_ratio',
  'active_days', 'recent_7d_pnl', 'last_trade_time'
];

// 高级筛选器配置
interface FilterConfig {
  minWinRate?: number;
  minProfitFactor?: number;
  minPnl?: number;
  maxDrawdown?: number;
  minSharpe?: number;
  minTrades?: number;
  minActiveDays?: number;
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

  // 高级筛选状态
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
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
        min_rating: selectedRating || undefined,
        sort_by: sortDescriptor.column as string,
        sort_order: sortDescriptor.direction === 'ascending' ? 'asc' as const : 'desc' as const,
        // 高级筛选
        min_win_rate: filters.minWinRate,
        min_profit_factor: filters.minProfitFactor,
        min_pnl: filters.minPnl,
        max_drawdown: filters.maxDrawdown,
        min_sharpe: filters.minSharpe,
        min_trades: filters.minTrades,
        min_active_days: filters.minActiveDays,
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

  // 获取当前筛选状态数量
  const getActiveFiltersCount = useCallback(() => {
    let count = 0;
    if (selectedRating) count++;
    if (searchAddress) count++;
    if (filters.minWinRate !== undefined) count++;
    if (filters.minProfitFactor !== undefined) count++;
    if (filters.minPnl !== undefined) count++;
    if (filters.maxDrawdown !== undefined) count++;
    if (filters.minSharpe !== undefined) count++;
    if (filters.minTrades !== undefined) count++;
    if (filters.minActiveDays !== undefined) count++;
    if (filters.hasRecentTrade !== undefined) count++;
    return count;
  }, [selectedRating, searchAddress, filters]);

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
          <span className="font-mono text-sm">
            {trader.address.slice(0, 6)}...{trader.address.slice(-4)}
          </span>
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
    const activeFilters = getActiveFiltersCount();

    return (
      <div className="flex flex-col gap-4">
        {/* 筛选工具栏 */}
        <div className="flex items-center gap-4 overflow-auto px-[6px] py-[4px]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-4">
              <Input
                className="min-w-[200px]"
                endContent={<SearchIcon className="text-default-400" width={16} />}
                placeholder="搜索地址..."
                size="sm"
                value={searchAddress}
                onValueChange={onSearchChange}
                isClearable
                onClear={() => setSearchAddress('')}
              />

              {/* Rating 筛选 */}
              <div className="flex gap-1">
                {['S', 'A', 'B', 'C', 'D', 'F'].map((rating) => (
                  <Button
                    key={rating}
                    size="sm"
                    variant={selectedRating === rating ? 'solid' : 'bordered'}
                    color={selectedRating === rating ? 'primary' : 'default'}
                    className="min-w-8 px-2"
                    onPress={() =>
                      setSelectedRating(selectedRating === rating ? '' : rating)
                    }
                  >
                    {rating}
                  </Button>
                ))}
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
                              sortDescriptor.column === item.uid && sortDescriptor.direction === 'descending'
                                ? 'ascending'
                                : 'descending',
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

              {/* 高级筛选按钮 */}
              <Button
                className={showAdvancedFilters ? 'bg-primary-100 text-primary-800' : 'bg-default-100 text-default-800'}
                size="sm"
                startContent={
                  <Icon className="text-default-400" icon="solar:filter-linear" width={16} />
                }
                onPress={() => setShowAdvancedFilters(!showAdvancedFilters)}
              >
                高级筛选
                {activeFilters > 0 && (
                  <Chip size="sm" color="primary" variant="flat" className="ml-1">
                    {activeFilters}
                  </Chip>
                )}
              </Button>
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

        {/* 高级筛选面板 */}
        {showAdvancedFilters && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 p-4 bg-default-50 rounded-lg">
            <Input
              type="number"
              size="sm"
              label="最小胜率"
              placeholder="0.5"
              value={filters.minWinRate?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, minWinRate: v ? parseFloat(v) : undefined })}
              endContent={<span className="text-xs text-default-400">%</span>}
            />
            <Input
              type="number"
              size="sm"
              label="最小盈亏比"
              placeholder="1.5"
              value={filters.minProfitFactor?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, minProfitFactor: v ? parseFloat(v) : undefined })}
            />
            <Input
              type="number"
              size="sm"
              label="最小PnL"
              placeholder="1000"
              value={filters.minPnl?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, minPnl: v ? parseFloat(v) : undefined })}
              startContent={<span className="text-xs text-default-400">$</span>}
            />
            <Input
              type="number"
              size="sm"
              label="最大回撤"
              placeholder="0.3"
              value={filters.maxDrawdown?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, maxDrawdown: v ? parseFloat(v) : undefined })}
              endContent={<span className="text-xs text-default-400">%</span>}
            />
            <Input
              type="number"
              size="sm"
              label="最小Sharpe"
              placeholder="1.0"
              value={filters.minSharpe?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, minSharpe: v ? parseFloat(v) : undefined })}
            />
            <Input
              type="number"
              size="sm"
              label="最小交易数"
              placeholder="50"
              value={filters.minTrades?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, minTrades: v ? parseInt(v) : undefined })}
            />
            <Input
              type="number"
              size="sm"
              label="最小活跃天"
              placeholder="7"
              value={filters.minActiveDays?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, minActiveDays: v ? parseInt(v) : undefined })}
            />
            <Input
              type="number"
              size="sm"
              label="最近N天活跃"
              placeholder="7"
              value={filters.hasRecentTrade?.toString() || ''}
              onValueChange={(v) => setFilters({ ...filters, hasRecentTrade: v ? parseInt(v) : undefined })}
              endContent={<span className="text-xs text-default-400">天</span>}
            />
          </div>
        )}
      </div>
    );
  }, [searchAddress, selectedRating, sortDescriptor, visibleColumns, showAdvancedFilters, filters, onSearchChange, handleReset, getActiveFiltersCount]);

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
  }, [page, totalPages, totalCount]);

  return (
    <DefaultLayout>
      <section className="flex flex-col gap-4 py-8 md:py-10">
        <div className="max-w-7xl w-full mx-auto">
          <Card>
            <CardHeader className="flex flex-col gap-3">
              <div className="flex justify-between items-center w-full">
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold">Trader Analytics</h1>
                  <Chip size="sm" variant="flat" className="text-default-500">
                    {totalCount}
                  </Chip>
                </div>
              </div>
            </CardHeader>
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
