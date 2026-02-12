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

export interface TwapSliceFill {
  coin: string;
  px: string;
  sz: string;
  side: string;
  time: number;
  fee: string;
  oid: number;
  twapId: number;
  closedPnl?: string;
}

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'side' | 'px' | 'sz' | 'fee' | 'closedPnl' | 'twapId' | 'oid' | 'time';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'px', name: 'Price', sortable: true },
  { uid: 'sz', name: 'Size', sortable: true },
  { uid: 'fee', name: 'Fee', sortable: true },
  { uid: 'closedPnl', name: 'Closed PnL', sortable: true },
  { uid: 'twapId', name: 'TWAP ID', sortable: true },
  { uid: 'oid', name: 'Order ID', sortable: true },
  { uid: 'time', name: 'Time', sortable: true },
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

function pnlColor(value: string | number | null | undefined): string {
  if (value == null || value === '') return '';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '';
  return n >= 0 ? 'text-green-500' : 'text-red-500';
}

function numVal(value: string | number | null | undefined): number {
  if (value == null || value === '') return 0;
  const n = typeof value === 'string' ? parseFloat(value) : value;
  return isNaN(n) ? 0 : n;
}

// ==================== 组件 ====================

interface TwapSliceFillsProps {
  fills: TwapSliceFill[];
}

export function TwapSliceFills({ fills }: TwapSliceFillsProps) {
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'time',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;

    return [...fills].sort((a, b) => {
      let aVal: number, bVal: number;

      switch (col) {
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'side':
          return dir === 'ascending' ? a.side.localeCompare(b.side) : b.side.localeCompare(a.side);
        case 'px':
          aVal = numVal(a.px); bVal = numVal(b.px); break;
        case 'sz':
          aVal = numVal(a.sz); bVal = numVal(b.sz); break;
        case 'fee':
          aVal = numVal(a.fee); bVal = numVal(b.fee); break;
        case 'closedPnl':
          aVal = numVal(a.closedPnl); bVal = numVal(b.closedPnl); break;
        case 'twapId':
          aVal = a.twapId; bVal = b.twapId; break;
        case 'oid':
          aVal = a.oid; bVal = b.oid; break;
        case 'time':
          aVal = a.time; bVal = b.time; break;
        default:
          return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [fills, sortDescriptor]);

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

  const renderCell = useCallback((fill: TwapSliceFill, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin':
        return <span className="font-bold">{fill.coin}</span>;
      case 'side':
        return (
          <Chip size="sm" color={fill.side === 'B' ? 'success' : 'danger'} variant="flat">
            {fill.side === 'B' ? 'BUY' : 'SELL'}
          </Chip>
        );
      case 'px':
        return <span>{fmtUsd(fill.px)}</span>;
      case 'sz':
        return <span>{fmt(fill.sz, 4)}</span>;
      case 'fee':
        return <span className="text-orange-500">{fmtUsd(fill.fee)}</span>;
      case 'closedPnl':
        return <span className={pnlColor(fill.closedPnl)}>{fmtUsd(fill.closedPnl)}</span>;
      case 'twapId':
        return <span>{fill.twapId}</span>;
      case 'oid':
        return <span>{fill.oid}</span>;
      case 'time':
        return <span className="text-xs">{fmtTime(fill.time)}</span>;
      default:
        return null;
    }
  }, []);

  return (
    <Table
      isHeaderSticky
      aria-label="TWAP slice fills table"
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
      <TableBody items={pageItems} emptyContent="No TWAP records">
        {(item) => (
          <TableRow key={`${item.oid}-${item.time}`}>
            {(columnKey) => (
              <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>
            )}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
