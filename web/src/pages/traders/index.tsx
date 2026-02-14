import { useState, useEffect, useCallback } from 'react';
import type { SortDescriptor } from '@heroui/react';
import { addToast } from "@heroui/react";
import { Spinner } from '@heroui/spinner';
import { useDisclosure } from '@heroui/modal';
import { Icon } from "@iconify/react";
import DefaultLayout from '@/layouts/default';
import { traderApi, Trader } from '@/services/api';
import { FilterSection } from './components/FilterSection';
import { TraderCard } from './components/TraderCard';
import { AddTraderModal } from './components/AddTraderModal';
import { ROWS_PER_PAGE } from './constants';
import { TablePagination } from '@/components/TablePagination';
import type { FilterConfig } from './types';

export default function TradersPage() {
  const [traders, setTraders] = useState<Trader[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchAddress, setSearchAddress] = useState('');
  const [selectedRating, setSelectedRating] = useState<string>('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [filters, setFilters] = useState<FilterConfig>({});
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

      const periodDays = filters.period === '1d' ? 1
        : filters.period === '7d' ? 7
        : filters.period === '30d' ? 30
        : undefined;

      const params = {
        page,
        limit: ROWS_PER_PAGE,
        search: searchAddress || undefined,
        rating: selectedRating || undefined,
        sort_by: sortDescriptor.column as string,
        sort_order: sortDescriptor.direction === 'ascending' ? 'asc' as const : 'desc' as const,
        has_recent_trade: periodDays,
        filters: filters.advancedFilters?.length
          ? JSON.stringify(filters.advancedFilters)
          : undefined,
        tag_account_value: filters.tagAccountValue,
        tag_trading_rhythm: filters.tagTradingRhythm,
        tag_profit_status: filters.tagProfitStatus,
        tag_direction_preference: filters.tagDirectionPreference,
        tag_trading_style: filters.tagTradingStyle,
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

        <FilterSection
          totalCount={totalCount}
          searchAddress={searchAddress}
          onSearchChange={onSearchChange}
          selectedRating={selectedRating}
          onRatingChange={setSelectedRating}
          sortDescriptor={sortDescriptor}
          onSortChange={setSortDescriptor}
          filters={filters}
          onFiltersChange={setFilters}
          onSearch={loadTraders}
          onReset={handleReset}
          onAddTrader={onOpen}
        />

        {/* Card list */}
        <div className="w-full">
          {error ? (
            <div className="text-center text-red-500 p-8">{error}</div>
          ) : loading ? (
            <div className="flex justify-center items-center min-h-[400px]">
              <Spinner size="lg" />
            </div>
          ) : traders.length === 0 ? (
            <div className="text-center text-default-500 p-8">暂无交易者数据</div>
          ) : (
            <div className="flex flex-col gap-3">
              {traders.map((trader) => (
                <TraderCard
                  key={trader.address}
                  trader={trader}
                  onToggleStar={handleToggleStar}
                  isStarLoading={starLoadingAddresses.has(trader.address)}
                />
              ))}
            </div>
          )}
        </div>

        {totalPages > 1 && (
          <TablePagination
            page={page}
            totalPages={totalPages}
            totalCount={totalCount}
            rowsPerPage={ROWS_PER_PAGE}
            onPageChange={setPage}
          />
        )}
      </section>

      <AddTraderModal
        isOpen={isOpen}
        onClose={onClose}
        onSuccess={loadTraders}
      />
    </DefaultLayout>
  );
}
