import { useState, useMemo, useCallback } from 'react';
import type { SortDescriptor } from '@heroui/react';
import { Chip } from '@heroui/chip';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { TablePagination, useLocalPagination } from '@/components/TablePagination';

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
  { uid: 'value', name: 'Value', sortable: true },
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

const tradeTypeMap: Record<string, { label: string; color: 'success' | 'danger' | 'warning' }> = {
  'open_long': { label: '开多', color: 'success' },
  'add_long': { label: '加多', color: 'success' },
  'close_long': { label: '平多', color: 'warning' },
  'open_short': { label: '开空', color: 'danger' },
  'add_short': { label: '加空', color: 'danger' },
  'close_short': { label: '平空', color: 'warning' },
};

// ==================== 组件 ====================

interface RecentFillsProps {
  fills: RecentFillItem[];
}

export function RecentFills({ fills }: RecentFillsProps) {
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'trade_time',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;

    return [...fills].sort((a, b) => {
      let aVal: number, bVal: number;
      switch (col) {
        case 'trade_time':
          return dir === 'ascending'
            ? new Date(a.trade_time).getTime() - new Date(b.trade_time).getTime()
            : new Date(b.trade_time).getTime() - new Date(a.trade_time).getTime();
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'side':
          return dir === 'ascending' ? a.side.localeCompare(b.side) : b.side.localeCompare(a.side);
        case 'trade_type':
          return dir === 'ascending'
            ? (a.trade_type || '').localeCompare(b.trade_type || '')
            : (b.trade_type || '').localeCompare(a.trade_type || '');
        case 'px': aVal = a.px; bVal = b.px; break;
        case 'sz': aVal = a.sz; bVal = b.sz; break;
        case 'start_position': aVal = a.start_position ?? 0; bVal = b.start_position ?? 0; break;
        case 'value': aVal = a.px * a.sz; bVal = b.px * b.sz; break;
        case 'closed_pnl': aVal = a.closed_pnl; bVal = b.closed_pnl; break;
        case 'fee': aVal = a.fee; bVal = b.fee; break;
        default: return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [fills, sortDescriptor]);

  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: sortedItems.length });
  const pageItems = useMemo(() => getPageItems(sortedItems), [getPageItems, sortedItems]);

  const bottomContent = useMemo(() => (
    <TablePagination page={page} totalPages={totalPages} onPageChange={setPage}
      totalCount={sortedItems.length} rowsPerPage={rowsPerPage} onRowsPerPageChange={setRowsPerPage} />
  ), [page, totalPages, setPage, sortedItems.length, rowsPerPage, setRowsPerPage]);

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

  return (
    <Table isHeaderSticky aria-label="Recent fills table" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor} bottomContent={bottomContent} bottomContentPlacement="outside">
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={pageItems} emptyContent="No fills">
        {(item) => (
          <TableRow key={item.id}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
