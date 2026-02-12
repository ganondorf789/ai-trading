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
  orig_sz: string;
  order_type: string;
  status: string;
  is_trigger: boolean;
  trigger_px: string;
  trigger_condition: string;
  is_position_tpsl: boolean;
  reduce_only: boolean;
  order_timestamp: number;
  status_timestamp: number;
  cloid?: string;
}

// ==================== 列配置 ====================

type ColumnKey = 'oid' | 'coin' | 'side' | 'order_type' | 'sz' | 'filled' | 'limit_px' | 'trigger_px' | 'status' | 'status_timestamp';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'oid', name: 'OID', sortable: true },
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'order_type', name: 'Type', sortable: true },
  { uid: 'sz', name: 'Size', sortable: true },
  { uid: 'filled', name: 'Filled', sortable: true },
  { uid: 'limit_px', name: 'Price', sortable: true },
  { uid: 'trigger_px', name: 'Trigger', sortable: true },
  { uid: 'status', name: 'Status', sortable: true },
  { uid: 'status_timestamp', name: 'Time', sortable: true },
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
    column: 'status_timestamp',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;
    return [...orders].sort((a, b) => {
      let aVal: number, bVal: number;
      switch (col) {
        case 'oid': aVal = a.oid; bVal = b.oid; break;
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'side':
          return dir === 'ascending' ? a.side.localeCompare(b.side) : b.side.localeCompare(a.side);
        case 'order_type':
          return dir === 'ascending' ? a.order_type.localeCompare(b.order_type) : b.order_type.localeCompare(a.order_type);
        case 'status':
          return dir === 'ascending' ? a.status.localeCompare(b.status) : b.status.localeCompare(a.status);
        case 'sz': aVal = numVal(a.sz); bVal = numVal(b.sz); break;
        case 'filled': aVal = numVal(a.orig_sz) - numVal(a.sz); bVal = numVal(b.orig_sz) - numVal(b.sz); break;
        case 'limit_px': aVal = numVal(a.limit_px); bVal = numVal(b.limit_px); break;
        case 'trigger_px': aVal = numVal(a.trigger_px); bVal = numVal(b.trigger_px); break;
        case 'status_timestamp': aVal = a.status_timestamp; bVal = b.status_timestamp; break;
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
      case 'oid': return <span className="text-xs font-mono">{order.oid}</span>;
      case 'coin': return <span className="font-bold">{order.coin}</span>;
      case 'side':
        return <Chip size="sm" color={order.side === 'B' ? 'success' : 'danger'} variant="flat">{order.side === 'B' ? 'BUY' : 'SELL'}</Chip>;
      case 'order_type':
        return <Chip size="sm" variant="bordered">{order.order_type || 'Limit'}</Chip>;
      case 'sz': return <span>{fmt(order.orig_sz, 4)}</span>;
      case 'filled': {
        const filled = numVal(order.orig_sz) - numVal(order.sz);
        return <span>{fmt(filled, 4)}</span>;
      }
      case 'limit_px': return <span>{fmtUsd(order.limit_px)}</span>;
      case 'trigger_px': return <span>{order.trigger_condition && order.trigger_condition !== 'N/A' ? `${order.trigger_condition} ${fmtUsd(order.trigger_px)}` : '-'}</span>;
      case 'status':
        return <Chip size="sm" color={statusColorMap[order.status] || 'default'} variant="flat">{order.status}</Chip>;
      case 'status_timestamp': return <span className="text-xs">{fmtTime(order.status_timestamp)}</span>;
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
