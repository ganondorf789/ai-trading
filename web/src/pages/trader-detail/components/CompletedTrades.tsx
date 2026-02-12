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

export interface CompletedTradeItem {
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
  open_trades: number;
  close_trades: number;
  holding_hours: number | null;
  status: 'open' | 'closed';
}

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'direction' | 'status' | 'open_time' | 'close_time' | 'max_size' | 'avg_entry_price' | 'avg_close_price' | 'position_value' | 'realized_pnl' | 'total_fee' | 'holding_hours';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'direction', name: 'Direction', sortable: true },
  { uid: 'status', name: 'Status', sortable: true },
  { uid: 'open_time', name: 'Open Time', sortable: true },
  { uid: 'close_time', name: 'Close Time', sortable: true },
  { uid: 'max_size', name: 'Max Size', sortable: true },
  { uid: 'avg_entry_price', name: 'Entry Price', sortable: true },
  { uid: 'avg_close_price', name: 'Close Price', sortable: true },
  { uid: 'position_value', name: 'Value', sortable: true },
  { uid: 'realized_pnl', name: 'Realized PnL', sortable: true },
  { uid: 'total_fee', name: 'Fee', sortable: true },
  { uid: 'holding_hours', name: 'Holding (h)', sortable: true },
];

// ==================== 工具函数 ====================

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null || isNaN(value)) return '-';
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtTime(time: string | null): string {
  if (!time) return '-';
  return new Date(time).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

function numVal(v: number | string | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return isNaN(n) ? 0 : n;
}

// ==================== 组件 ====================

interface CompletedTradesProps {
  trades: CompletedTradeItem[];
}

export function CompletedTrades({ trades }: CompletedTradesProps) {
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'close_time',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;
    return [...trades].sort((a, b) => {
      let aVal: number, bVal: number;
      switch (col) {
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'direction':
          return dir === 'ascending' ? a.direction.localeCompare(b.direction) : b.direction.localeCompare(a.direction);
        case 'status':
          return dir === 'ascending' ? a.status.localeCompare(b.status) : b.status.localeCompare(a.status);
        case 'open_time':
          aVal = new Date(a.open_time).getTime(); bVal = new Date(b.open_time).getTime(); break;
        case 'close_time':
          aVal = a.close_time ? new Date(a.close_time).getTime() : 0;
          bVal = b.close_time ? new Date(b.close_time).getTime() : 0; break;
        case 'max_size': aVal = a.max_size; bVal = b.max_size; break;
        case 'avg_entry_price': aVal = a.avg_entry_price; bVal = b.avg_entry_price; break;
        case 'avg_close_price': aVal = numVal(a.avg_close_price); bVal = numVal(b.avg_close_price); break;
        case 'position_value': aVal = a.position_value; bVal = b.position_value; break;
        case 'realized_pnl': aVal = a.realized_pnl; bVal = b.realized_pnl; break;
        case 'total_fee': aVal = a.total_fee; bVal = b.total_fee; break;
        case 'holding_hours': aVal = numVal(a.holding_hours); bVal = numVal(b.holding_hours); break;
        default: return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [trades, sortDescriptor]);

  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: sortedItems.length });
  const pageItems = useMemo(() => getPageItems(sortedItems), [getPageItems, sortedItems]);

  const bottomContent = useMemo(() => (
    <TablePagination page={page} totalPages={totalPages} onPageChange={setPage}
      totalCount={sortedItems.length} rowsPerPage={rowsPerPage} onRowsPerPageChange={setRowsPerPage} />
  ), [page, totalPages, setPage, sortedItems.length, rowsPerPage, setRowsPerPage]);

  const renderCell = useCallback((item: CompletedTradeItem, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin': return <span className="font-bold">{item.coin}</span>;
      case 'direction':
        return <Chip size="sm" color={item.direction === 'long' ? 'success' : 'danger'} variant="flat">{item.direction.toUpperCase()}</Chip>;
      case 'status':
        return <Chip size="sm" color={item.status === 'open' ? 'primary' : 'default'} variant="flat">{item.status}</Chip>;
      case 'open_time': return <span className="text-xs">{fmtTime(item.open_time)}</span>;
      case 'close_time': return <span className="text-xs">{fmtTime(item.close_time)}</span>;
      case 'max_size': return <span>{fmt(item.max_size, 4)}</span>;
      case 'avg_entry_price': return <span>${fmt(item.avg_entry_price, 4)}</span>;
      case 'avg_close_price': return <span>{item.avg_close_price != null ? '$' + fmt(item.avg_close_price, 4) : '-'}</span>;
      case 'position_value': return <span>${fmt(item.position_value)}</span>;
      case 'realized_pnl':
        return <span className={item.realized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>${fmt(item.realized_pnl)}</span>;
      case 'total_fee': return <span className="text-orange-500">${fmt(item.total_fee, 4)}</span>;
      case 'holding_hours': return <span>{item.holding_hours != null ? fmt(item.holding_hours, 1) : '-'}</span>;
      default: return null;
    }
  }, []);

  return (
    <Table isHeaderSticky aria-label="Completed trades table" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor} bottomContent={bottomContent} bottomContentPlacement="outside">
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={pageItems} emptyContent="No completed trades">
        {(item) => (
          <TableRow key={item.id}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
