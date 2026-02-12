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

export interface OpenOrderItem {
  coin: string;
  limitPx: string;
  oid: number;
  side: string;
  sz: string;
  timestamp: number;
  orderType: string;
  tif: string;
  origSz: string;
  isTrigger: boolean;
  triggerPx: string;
  triggerCondition: string;
  isPositionTpsl: boolean;
  children: any[];
  reduceOnly?: boolean;
  cloid?: string | null;
}

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'side' | 'orderType' | 'sz' | 'limitPx' | 'trigger' | 'tif' | 'reduceOnly' | 'tpsl' | 'timestamp';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'orderType', name: 'Type', sortable: true },
  { uid: 'sz', name: 'Size', sortable: true },
  { uid: 'limitPx', name: 'Price', sortable: true },
  { uid: 'trigger', name: 'Trigger', sortable: false },
  { uid: 'tif', name: 'TIF', sortable: true },
  { uid: 'reduceOnly', name: 'Reduce Only', sortable: true },
  { uid: 'tpsl', name: 'TP/SL', sortable: true },
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
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function numVal(value: string | number | null | undefined): number {
  if (value == null || value === '') return 0;
  const n = typeof value === 'string' ? parseFloat(value) : value;
  return isNaN(n) ? 0 : n;
}

// ==================== 组件 ====================

interface OpenOrdersProps {
  orders: OpenOrderItem[];
}

export function OpenOrders({ orders }: OpenOrdersProps) {
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
        case 'orderType':
          return dir === 'ascending'
            ? (a.orderType || '').localeCompare(b.orderType || '')
            : (b.orderType || '').localeCompare(a.orderType || '');
        case 'sz':
          aVal = numVal(a.sz); bVal = numVal(b.sz); break;
        case 'limitPx':
          aVal = numVal(a.limitPx); bVal = numVal(b.limitPx); break;
        case 'tif':
          return dir === 'ascending'
            ? (a.tif || '').localeCompare(b.tif || '')
            : (b.tif || '').localeCompare(a.tif || '');
        case 'reduceOnly':
          aVal = a.reduceOnly ? 1 : 0; bVal = b.reduceOnly ? 1 : 0; break;
        case 'tpsl':
          aVal = a.isPositionTpsl ? 1 : 0; bVal = b.isPositionTpsl ? 1 : 0; break;
        case 'timestamp':
          aVal = a.timestamp; bVal = b.timestamp; break;
        default:
          return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [orders, sortDescriptor]);

  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: sortedItems.length });

  const pageItems = useMemo(() => getPageItems(sortedItems), [getPageItems, sortedItems]);

  const bottomContent = useMemo(() => (
    <TablePagination
      page={page}
      totalPages={totalPages}
      onPageChange={setPage}
      totalCount={sortedItems.length}
      rowsPerPage={rowsPerPage}
      onRowsPerPageChange={setRowsPerPage}
    />
  ), [page, totalPages, setPage, sortedItems.length, rowsPerPage, setRowsPerPage]);

  const renderCell = useCallback((order: OpenOrderItem, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin':
        return <span className="font-bold">{order.coin}</span>;
      case 'side':
        return (
          <Chip size="sm" color={order.side === 'B' ? 'success' : 'danger'} variant="flat">
            {order.side === 'B' ? 'BUY' : 'SELL'}
          </Chip>
        );
      case 'orderType':
        return (
          <Chip size="sm" variant="bordered">
            {order.orderType || 'Limit'}
          </Chip>
        );
      case 'sz':
        return <span>{fmt(order.sz, 4)}</span>;
      case 'limitPx':
        return <span>{fmtUsd(order.limitPx)}</span>;
      case 'trigger':
        return order.isTrigger ? (
          <span className="text-xs">
            {order.triggerCondition} {fmtUsd(order.triggerPx)}
          </span>
        ) : <span>-</span>;
      case 'tif':
        return <span>{order.tif || '-'}</span>;
      case 'reduceOnly':
        return <span>{order.reduceOnly ? 'Yes' : 'No'}</span>;
      case 'tpsl':
        return <span>{order.isPositionTpsl ? 'Yes' : '-'}</span>;
      case 'timestamp':
        return <span className="text-xs">{fmtTime(order.timestamp)}</span>;
      default:
        return null;
    }
  }, []);

  return (
    <Table
      isHeaderSticky
      aria-label="Open orders table"
      sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor}
      bottomContent={bottomContent}
      bottomContentPlacement="outside"
      classNames={{ wrapper: '' }}
    >
      <TableHeader columns={columns}>
        {(column) => (
          <TableColumn key={column.uid} allowsSorting={column.sortable}>
            {column.name}
          </TableColumn>
        )}
      </TableHeader>
      <TableBody items={pageItems} emptyContent="No open orders">
        {(item) => (
          <TableRow key={item.oid}>
            {(columnKey) => (
              <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>
            )}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
