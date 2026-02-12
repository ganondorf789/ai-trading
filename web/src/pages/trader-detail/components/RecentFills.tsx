import { useState, useEffect, useMemo, useCallback } from 'react';
import type { SortDescriptor } from '@heroui/react';
import { Chip, addToast } from '@heroui/react';
import { Spinner } from '@heroui/spinner';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { TablePagination } from '@/components/TablePagination';
import { traderApi } from '@/services/api';
import type { PaginationInfo, FillsStats } from '@/types';

// ==================== 类型 ====================

export interface RecentFillItem {
  id: number;
  coin: string;
  side: string;
  px: number;
  sz: number;
  trade_time: string;
  closed_pnl: number;
  fee: number;
  start_position?: number;
  trade_type?: string;
}

// ==================== 列配置 ====================

type ColumnKey = 'trade_time' | 'coin' | 'side' | 'trade_type' | 'px' | 'sz' | 'start_position' | 'value' | 'closed_pnl' | 'fee';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'trade_time', name: 'Time', sortable: true },
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'trade_type', name: 'Type', sortable: true },
  { uid: 'px', name: 'Price', sortable: true },
  { uid: 'sz', name: 'Size', sortable: true },
  { uid: 'start_position', name: 'Start Pos', sortable: true },
  { uid: 'value', name: 'Value', sortable: false },
  { uid: 'closed_pnl', name: 'Closed PnL', sortable: true },
  { uid: 'fee', name: 'Fee', sortable: true },
];

// ==================== 工具函数 ====================

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  if (isNaN(value)) return '-';
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtTime(time: string): string {
  if (!time) return '-';
  return new Date(time).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

const tradeTypeMap: Record<string, { label: string; color: 'success' | 'danger' | 'warning' | 'default' }> = {
  '1': { label: '开多', color: 'success' },
  '2': { label: '加多', color: 'success' },
  '3': { label: '平多', color: 'warning' },
  '4': { label: '开空', color: 'danger' },
  '5': { label: '加空', color: 'danger' },
  '6': { label: '平空', color: 'warning' },
};

// sort descriptor direction -> API sort_order
function toSortOrder(direction: 'ascending' | 'descending' | undefined): 'asc' | 'desc' {
  return direction === 'ascending' ? 'asc' : 'desc';
}

// ==================== 组件 ====================

interface RecentFillsProps {
  address: string;
  onTotalCountChange?: (count: number) => void;
}

export function RecentFills({ address, onTotalCountChange }: RecentFillsProps) {
  const [fills, setFills] = useState<RecentFillItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(20);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [_stats, setStats] = useState<FillsStats | null>(null);

  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'trade_time',
    direction: 'descending',
  });

  const fetchFills = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await traderApi.getTraderFills(address, {
        page,
        limit: rowsPerPage,
        sort_by: sortDescriptor.column as string,
        sort_order: toSortOrder(sortDescriptor.direction),
      });
      if (res.success) {
        setFills(res.data || []);
        if (res.pagination) setPagination(res.pagination);
        if (res.stats) setStats(res.stats);
        onTotalCountChange?.(res.pagination?.total_count ?? 0);
      }
    } catch (err: any) {
      addToast({ title: '获取成交失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address, page, rowsPerPage, sortDescriptor, onTotalCountChange]);

  useEffect(() => { fetchFills(); }, [fetchFills]);

  const handleSortChange = useCallback((descriptor: SortDescriptor) => {
    setSortDescriptor(descriptor);
    setPage(1);
  }, []);

  const handleRowsPerPageChange = useCallback((value: number) => {
    setRowsPerPage(value);
    setPage(1);
  }, []);

  const totalPages = pagination?.total_pages ?? 1;
  const totalCount = pagination?.total_count ?? 0;

  const bottomContent = useMemo(() => (
    <TablePagination page={page} totalPages={totalPages} onPageChange={setPage}
      totalCount={totalCount} rowsPerPage={rowsPerPage} onRowsPerPageChange={handleRowsPerPageChange} />
  ), [page, totalPages, setPage, totalCount, rowsPerPage, handleRowsPerPageChange]);

  const renderCell = useCallback((fill: RecentFillItem, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'trade_time':
        return <span className="text-xs">{fmtTime(fill.trade_time)}</span>;
      case 'coin':
        return <span className="font-bold">{fill.coin}</span>;
      case 'side':
        return (
          <Chip size="sm" color={fill.side === 'B' ? 'success' : 'danger'} variant="flat">
            {fill.side === 'B' ? 'BUY' : 'SELL'}
          </Chip>
        );
      case 'trade_type': {
        const info = fill.trade_type ? tradeTypeMap[fill.trade_type] : null;
        return <Chip size="sm" color={info?.color || 'default'} variant="flat">{info?.label || '-'}</Chip>;
      }
      case 'px':
        return <span>${fmt(fill.px, 4)}</span>;
      case 'sz':
        return <span>{fmt(fill.sz, 4)}</span>;
      case 'start_position':
        return <span>{fill.start_position != null ? fmt(fill.start_position, 4) : '-'}</span>;
      case 'value':
        return <span>${fmt(fill.px * fill.sz)}</span>;
      case 'closed_pnl':
        return <span className={fill.closed_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>${fmt(fill.closed_pnl)}</span>;
      case 'fee':
        return <span className="text-orange-500">${fmt(fill.fee, 4)}</span>;
      default: return null;
    }
  }, []);

  if (loading && fills.length === 0) {
    return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  }

  return (
    <Table isHeaderSticky aria-label="Recent fills table" sortDescriptor={sortDescriptor}
      onSortChange={handleSortChange} bottomContent={bottomContent} bottomContentPlacement="outside">
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={fills} emptyContent="No fills" isLoading={loading} loadingContent={<Spinner />}>
        {(item) => (
          <TableRow key={item.id}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
