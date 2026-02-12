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

export interface LedgerItem {
  id?: number;
  delta_type: string;
  usdc: number | string;
  amount?: number | string;
  token?: string;
  fee?: number | string;
  nonce?: number;
  time: number;
  hash?: string;
}

// ==================== 列配置 ====================

type ColumnKey = 'time' | 'delta_type' | 'usdc' | 'amount' | 'token' | 'fee' | 'hash';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'time', name: 'Time', sortable: true },
  { uid: 'delta_type', name: 'Type', sortable: true },
  { uid: 'usdc', name: 'USDC', sortable: true },
  { uid: 'amount', name: 'Amount', sortable: true },
  { uid: 'token', name: 'Token', sortable: true },
  { uid: 'fee', name: 'Fee', sortable: true },
  { uid: 'hash', name: 'Tx Hash', sortable: false },
];

// ==================== 工具函数 ====================

function fmt(value: string | number | null | undefined, decimals = 2): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
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

const typeColorMap: Record<string, 'success' | 'danger' | 'warning' | 'primary' | 'default'> = {
  deposit: 'success',
  withdraw: 'danger',
  internalTransfer: 'primary',
  spotTransfer: 'primary',
  accountClassTransfer: 'warning',
  liquidation: 'danger',
};

// ==================== 组件 ====================

interface DepositsWithdrawalsProps {
  records: LedgerItem[];
}

export function DepositsWithdrawals({ records }: DepositsWithdrawalsProps) {
  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'time',
    direction: 'descending',
  });

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;
    return [...records].sort((a, b) => {
      let aVal: number, bVal: number;
      switch (col) {
        case 'delta_type':
          return dir === 'ascending' ? a.delta_type.localeCompare(b.delta_type) : b.delta_type.localeCompare(a.delta_type);
        case 'token':
          return dir === 'ascending'
            ? (a.token || '').localeCompare(b.token || '')
            : (b.token || '').localeCompare(a.token || '');
        case 'time': aVal = a.time; bVal = b.time; break;
        case 'usdc': aVal = numVal(a.usdc); bVal = numVal(b.usdc); break;
        case 'amount': aVal = numVal(a.amount); bVal = numVal(b.amount); break;
        case 'fee': aVal = numVal(a.fee); bVal = numVal(b.fee); break;
        default: return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [records, sortDescriptor]);

  const { page, setPage, rowsPerPage, setRowsPerPage, totalPages, getPageItems } =
    useLocalPagination({ totalItems: sortedItems.length });
  const pageItems = useMemo(() => getPageItems(sortedItems), [getPageItems, sortedItems]);

  const bottomContent = useMemo(() => (
    <TablePagination page={page} totalPages={totalPages} onPageChange={setPage}
      totalCount={sortedItems.length} rowsPerPage={rowsPerPage} onRowsPerPageChange={setRowsPerPage} />
  ), [page, totalPages, setPage, sortedItems.length, rowsPerPage, setRowsPerPage]);

  const renderCell = useCallback((item: LedgerItem, columnKey: ColumnKey) => {
    const usdc = numVal(item.usdc);
    switch (columnKey) {
      case 'time': return <span className="text-xs">{fmtTime(item.time)}</span>;
      case 'delta_type':
        return <Chip size="sm" color={typeColorMap[item.delta_type] || 'default'} variant="flat">{item.delta_type}</Chip>;
      case 'usdc':
        return <span className={usdc >= 0 ? 'text-green-500' : 'text-red-500'}>${fmt(usdc)}</span>;
      case 'amount': return <span>{fmt(item.amount, 4)}</span>;
      case 'token': return <span>{item.token || '-'}</span>;
      case 'fee': return <span className="text-orange-500">{item.fee ? '$' + fmt(item.fee, 4) : '-'}</span>;
      case 'hash':
        return item.hash ? (
          <a href={`https://arbiscan.io/tx/${item.hash}`} target="_blank" rel="noreferrer"
            className="text-primary text-xs hover:underline">{item.hash.slice(0, 8)}...</a>
        ) : <span>-</span>;
      default: return null;
    }
  }, []);

  return (
    <Table isHeaderSticky aria-label="Deposits & withdrawals table" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor} bottomContent={bottomContent} bottomContentPlacement="outside">
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={pageItems} emptyContent="No records">
        {(item) => (
          <TableRow key={`${item.delta_type}-${item.time}-${item.usdc}`}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
