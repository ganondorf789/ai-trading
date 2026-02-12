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

export interface PerpPosition {
  coin: string;
  size: number;
  side: 'long' | 'short';
  entryPx: string;
  positionValue: string;
  unrealizedPnl: string;
  returnOnEquity: string;
  leverage: { type: string; value: number };
  liquidationPx: string | null;
  marginUsed: string;
  maxLeverage: number;
}

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'side' | 'size' | 'entryPx' | 'positionValue' | 'unrealizedPnl' | 'roe' | 'leverage' | 'liquidationPx' | 'marginUsed';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'size', name: 'Size', sortable: true },
  { uid: 'entryPx', name: 'Entry Price', sortable: true },
  { uid: 'positionValue', name: 'Position Value', sortable: true },
  { uid: 'unrealizedPnl', name: 'Unrealized PnL', sortable: true },
  { uid: 'roe', name: 'ROE', sortable: true },
  { uid: 'leverage', name: 'Leverage', sortable: true },
  { uid: 'liquidationPx', name: 'Liq. Price', sortable: true },
  { uid: 'marginUsed', name: 'Margin Used', sortable: true },
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

function fmtPct(value: string | number | null | undefined): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return (n * 100).toFixed(2) + '%';
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

interface PerpPositionsProps {
  positions: PerpPosition[];
}

export function PerpPositions({ positions }: PerpPositionsProps) {
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'positionValue',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;

    return [...positions].sort((a, b) => {
      let aVal: number, bVal: number;

      switch (col) {
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'side':
          return dir === 'ascending' ? a.side.localeCompare(b.side) : b.side.localeCompare(a.side);
        case 'size':
          aVal = Math.abs(a.size); bVal = Math.abs(b.size); break;
        case 'entryPx':
          aVal = numVal(a.entryPx); bVal = numVal(b.entryPx); break;
        case 'positionValue':
          aVal = numVal(a.positionValue); bVal = numVal(b.positionValue); break;
        case 'unrealizedPnl':
          aVal = numVal(a.unrealizedPnl); bVal = numVal(b.unrealizedPnl); break;
        case 'roe':
          aVal = numVal(a.returnOnEquity); bVal = numVal(b.returnOnEquity); break;
        case 'leverage':
          aVal = a.leverage?.value ?? 0; bVal = b.leverage?.value ?? 0; break;
        case 'liquidationPx':
          aVal = numVal(a.liquidationPx); bVal = numVal(b.liquidationPx); break;
        case 'marginUsed':
          aVal = numVal(a.marginUsed); bVal = numVal(b.marginUsed); break;
        default:
          return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [positions, sortDescriptor]);

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

  const renderCell = useCallback((pos: PerpPosition, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin':
        return <span className="font-bold">{pos.coin}</span>;
      case 'side':
        return (
          <Chip size="sm" color={pos.side === 'long' ? 'success' : 'danger'} variant="flat">
            {pos.side.toUpperCase()}
          </Chip>
        );
      case 'size':
        return <span>{fmt(Math.abs(pos.size), 4)}</span>;
      case 'entryPx':
        return <span>{fmtUsd(pos.entryPx)}</span>;
      case 'positionValue':
        return <span>{fmtUsd(pos.positionValue)}</span>;
      case 'unrealizedPnl':
        return <span className={pnlColor(pos.unrealizedPnl)}>{fmtUsd(pos.unrealizedPnl)}</span>;
      case 'roe':
        return <span className={pnlColor(pos.returnOnEquity)}>{fmtPct(pos.returnOnEquity)}</span>;
      case 'leverage':
        return (
          <span>
            {pos.leverage?.value ?? '-'}x
            <span className="text-xs text-default-400 ml-1">
              ({pos.leverage?.type === 'cross' ? 'Cross' : 'Isolated'})
            </span>
          </span>
        );
      case 'liquidationPx':
        return <span>{pos.liquidationPx ? fmtUsd(pos.liquidationPx) : '-'}</span>;
      case 'marginUsed':
        return <span>{fmtUsd(pos.marginUsed)}</span>;
      default:
        return null;
    }
  }, []);

  return (
    <Table
      isHeaderSticky
      aria-label="Perp positions table"
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
      <TableBody items={pageItems} emptyContent="No positions">
        {(item) => (
          <TableRow key={item.coin}>
            {(columnKey) => (
              <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>
            )}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
