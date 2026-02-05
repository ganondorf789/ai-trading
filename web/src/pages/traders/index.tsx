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
import { addToast } from "@heroui/react";
import { Spinner } from '@heroui/spinner';
import { Card, CardBody } from '@heroui/card';
import { useDisclosure } from '@heroui/modal';
import { Icon } from "@iconify/react";
import DefaultLayout from '@/layouts/default';
import { traderApi, Trader } from '@/services/api';
import { FilterSection } from './components/FilterSection';
import { TraderTableCell } from './components/TraderTableCell';
import { AddTraderModal } from './components/AddTraderModal';
import { columns, INITIAL_VISIBLE_COLUMNS, ROWS_PER_PAGE } from './constants';
import { TablePagination } from '@/components/TablePagination';
import type { FilterConfig, ColumnKey } from './types';

export default function TradersPage() {
  const navigate = useNavigate();
  const [traders, setTraders] = useState<Trader[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchAddress, setSearchAddress] = useState('');
  const [selectedRating, setSelectedRating] = useState<string>('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [filters, setFilters] = useState<FilterConfig>({});
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'overall_score',
    direction: 'descending',
  });

  const { isOpen, onOpen, onClose } = useDisclosure();
  const [starLoadingAddresses, setStarLoadingAddresses] = useState<Set<string>>(new Set());

  const handleToggleStar = useCallback(async (address: string, isStarred: boolean) => {
    setStarLoadingAddresses(prev => new Set(prev).add(address));
    try {
      const response = await traderApi.toggleStar(address, isStarred);
      if (response.success) {
        // 更新本地状态
        setTraders(prev => prev.map(t => 
          t.address === address ? { ...t, is_starred: isStarred } : t
        ));
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
      setStarLoadingAddresses(prev => {
        const next = new Set(prev);
        next.delete(address);
        return next;
      });
    }
  }, []);

  const loadTraders = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        page,
        limit: ROWS_PER_PAGE,
        search: searchAddress || undefined,
        rating: selectedRating || undefined,
        sort_by: sortDescriptor.column as string,
        sort_order: sortDescriptor.direction === 'ascending' ? 'asc' as const : 'desc' as const,
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
        min_sortino: filters.minSortino,
        max_sortino: filters.maxSortino,
        min_calmar: filters.minCalmar,
        max_calmar: filters.maxCalmar,
        min_trades: filters.minTrades,
        max_trades: filters.maxTrades,
        min_active_days: filters.minActiveDays,
        max_active_days: filters.maxActiveDays,
        has_recent_trade: filters.hasRecentTrade,
        // 标签筛选
        tag_capital_scale: filters.tagCapitalScale,
        tag_trading_direction: filters.tagTradingDirection,
        tag_trading_cycle: filters.tagTradingCycle,
        tag_frequency_style: filters.tagFrequencyStyle,
        tag_return_risk: filters.tagReturnRisk,
        tag_strategy_capability: filters.tagStrategyCapability,
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

  useEffect(() => {
    setPage(1);
  }, [searchAddress, selectedRating, sortDescriptor, filters]);

  const handleRowClick = (address: string) => {
    navigate(`/traders/${address}`);
  };

  const headerColumns = useMemo(() => {
    if (visibleColumns === 'all') return columns;
    return columns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  const onSearchChange = useCallback((value?: string) => {
    setSearchAddress(value || '');
    setPage(1);
  }, []);

  const handleReset = useCallback(() => {
    setSelectedRating('');
    setSearchAddress('');
    setFilters({});
    setSortDescriptor({ column: 'overall_score', direction: 'descending' });
    setPage(1);
  }, []);

  return (
    <DefaultLayout>
      <section className="flex flex-col gap-4">
        {/* 标题 */}
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Icon icon="lucide:trending-up" width={28} />
            交易者列表
          </h1>
        </div>

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
                  topContent={
                    <FilterSection
                      searchAddress={searchAddress}
                      onSearchChange={onSearchChange}
                      selectedRating={selectedRating}
                      onRatingChange={setSelectedRating}
                      sortDescriptor={sortDescriptor}
                      onSortChange={setSortDescriptor}
                      visibleColumns={visibleColumns}
                      onVisibleColumnsChange={setVisibleColumns}
                      filters={filters}
                      onFiltersChange={setFilters}
                      onSearch={loadTraders}
                      onReset={handleReset}
                      onAddTrader={onOpen}
                    />
                  }
                  topContentPlacement="outside"
                  bottomContent={
                    totalPages > 1 ? (
                      <TablePagination
                        page={page}
                        totalPages={totalPages}
                        totalCount={totalCount}
                        rowsPerPage={ROWS_PER_PAGE}
                        onPageChange={setPage}
                      />
                    ) : null
                  }
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
                          <TableCell>
                            <TraderTableCell 
                              trader={item} 
                              columnKey={columnKey as ColumnKey}
                              onToggleStar={handleToggleStar}
                              isStarLoading={starLoadingAddresses.has(item.address)}
                            />
                          </TableCell>
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

      <AddTraderModal
        isOpen={isOpen}
        onClose={onClose}
        onSuccess={loadTraders}
      />
    </DefaultLayout>
  );
}
