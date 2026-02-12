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

export interface HistoricalOrderItem {
  oid: number;
  coin: string;
  side: string;
  limit_px: string;
  sz: string;
  filled_sz?: string;
  order_status: string;
  order_type: string;
  tif?: string;
  trigger_px?: string;
  trigger_condition?: string;
  reduce_only?: boolean;
  timestamp: number;
  cloid?: string;
}

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'side' | 'order_type' | 'sz' | 'filled_sz' | 'limit_px' | 'trigger_px' | 'order_status' | 'tif' | 'timestamp';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'order_type', name: 'Type', sortable: true },
  { uid: 'sz', name: 'Size', sortable: true },
  { uid: 'filled_sz', name: 'Filled', sortable: true },
  { uid: 'limit_px', name: 'Price', sortable: true },
  { uid: 'trigger_px', name: 'Trigger', sortable: true },
  { uid: 'order_status', name: 'Status', sortable: true },
  { uid: 'tif', name: 'TIF', sortable: true },
  { uid: 'timestamp', name: 'Time', sortable: true },
];

// ==================== 工具函数 ====================

function fmt(value: string | number | null | undefined, decimals = 2): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtUsd(value: string | number | null | undefined): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return '$' + fmt(n);
}

function fmtTime(ts: number): string {
  if (!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}

function numVal(value: string | number | null | undefined): number {
  if (value == null || value === '') return 0;
  const n = typeof value === 'string' ? parseFloat(value) : value;
  return isNaN(n) ? 0 : n;
}

const statusColorMap: Record<string, 'success' | 'danger' | 'warning' | 'default' | 'primary'> = {
  filled: 'success',
  canceled: 'default',
  open: 'primary',
  triggered: 'warning',
  rejected: 'danger',
  marginCanceled: 'danger',
};

// ==================== 组件 ====================

interface HistoricalOrdersProps {
  orders: HistoricalOrderItem[];
}

export function HistoricalOrders({ orders }: HistoricalOrdersProps) {
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'timestamp',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;
    return [...orders].sort((a, b) => {
      let aVal: number, bVal: number;
      switch (col) {
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'side':
          return dir === 'ascending' ? a.side.localeCompare(b.side) : b.side.localeCompare(a.side);
        case 'order_type':
          return dir === 'ascending' ? a.order_type.localeCompare(b.order_type) : b.order_type.localeCompare(a.order_type);
        case 'order_status':
          return dir === 'ascending' ? a.order_status.localeCompare(b.order_status) : b.order_status.localeCompare(a.order_status);
        case 'tif':
          return dir === 'ascending' ? (a.tif || '').localeCompare(b.tif || '') : (b.tif || '').localeCompare(a.tif || '');
        case 'sz': aVal = numVal(a.sz); bVal = numVal(b.sz); break;
        case 'filled_sz': aVal = numVal(a.filled_sz); bVal = numVal(b.filled_sz); break;
        case 'limit_px': aVal = numVal(a.limit_px); bVal = numVal(b.limit_px); break;
        case 'trigger_px': aVal = numVal(a.trigger_px); bVal = numVal(b.trigger_px); break;
        case 'timestamp': aVal = a.timestamp; bVal = b.timestamp; break;
        default: return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [orders, sortDescriptor]);

  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: sortedItems.length });
  const pageItems = useMemo(() => getPageItems(sortedItems), [getPageItems, sortedItems]);

  const bottomContent = useMemo(() => (
    <TablePagination page={page} totalPages={totalPages} onPageChange={setPage}
      totalCount={sortedItems.length} rowsPerPage={rowsPerPage} onRowsPerPageChange={setRowsPerPage} />
  ), [page, totalPages, setPage, sortedItems.length, rowsPerPage, setRowsPerPage]);

  const renderCell = useCallback((order: HistoricalOrderItem, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin': return <span className="font-bold">{order.coin}</span>;
      case 'side':
        return <Chip size="sm" color={order.side === 'B' ? 'success' : 'danger'} variant="flat">{order.side === 'B' ? 'BUY' : 'SELL'}</Chip>;
      case 'order_type':
        return <Chip size="sm" variant="bordered">{order.order_type || 'Limit'}</Chip>;
      case 'sz': return <span>{fmt(order.sz, 4)}</span>;
      case 'filled_sz': return <span>{fmt(order.filled_sz, 4)}</span>;
      case 'limit_px': return <span>{fmtUsd(order.limit_px)}</span>;
      case 'trigger_px': return <span>{order.trigger_px ? fmtUsd(order.trigger_px) : '-'}</span>;
      case 'order_status':
        return <Chip size="sm" color={statusColorMap[order.order_status] || 'default'} variant="flat">{order.order_status}</Chip>;
      case 'tif': return <span>{order.tif || '-'}</span>;
      case 'timestamp': return <span className="text-xs">{fmtTime(order.timestamp)}</span>;
      default: return null;
    }
  }, []);

  return (
    <Table isHeaderSticky aria-label="Historical orders table" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor} bottomContent={bottomContent} bottomContentPlacement="outside">
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={pageItems} emptyContent="No historical orders">
        {(item) => (
          <TableRow key={item.oid}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
