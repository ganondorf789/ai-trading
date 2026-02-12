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

export interface FundingHistoryItem {
  id?: number;
  coin: string;
  funding_rate: number | string;
  usdc: number | string;
  szi: number | string;
  time: number;
  hash?: string;
}

// ==================== 列配置 ====================

type ColumnKey = 'time' | 'coin' | 'side' | 'funding_rate' | 'usdc' | 'szi';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'time', name: 'Time', sortable: true },
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'side', name: 'Side', sortable: true },
  { uid: 'szi', name: 'Position Size', sortable: true },
  { uid: 'funding_rate', name: 'Funding Rate', sortable: true },
  { uid: 'usdc', name: 'Payment (USDC)', sortable: true },
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

// ==================== 组件 ====================

interface FundingHistoryProps {
  records: FundingHistoryItem[];
}

export function FundingHistory({ records }: FundingHistoryProps) {
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
        case 'coin':
          return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
        case 'side': {
          const aS = numVal(a.szi) >= 0 ? 'L' : 'S';
          const bS = numVal(b.szi) >= 0 ? 'L' : 'S';
          return dir === 'ascending' ? aS.localeCompare(bS) : bS.localeCompare(aS);
        }
        case 'time': aVal = a.time; bVal = b.time; break;
        case 'funding_rate': aVal = numVal(a.funding_rate); bVal = numVal(b.funding_rate); break;
        case 'usdc': aVal = numVal(a.usdc); bVal = numVal(b.usdc); break;
        case 'szi': aVal = Math.abs(numVal(a.szi)); bVal = Math.abs(numVal(b.szi)); break;
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

  const renderCell = useCallback((item: FundingHistoryItem, columnKey: ColumnKey) => {
    const szi = numVal(item.szi);
    const usdc = numVal(item.usdc);
    switch (columnKey) {
      case 'time': return <span className="text-xs">{fmtTime(item.time)}</span>;
      case 'coin': return <span className="font-bold">{item.coin}</span>;
      case 'side':
        return <Chip size="sm" color={szi >= 0 ? 'success' : 'danger'} variant="flat">{szi >= 0 ? 'LONG' : 'SHORT'}</Chip>;
      case 'szi': return <span>{fmt(Math.abs(szi), 4)}</span>;
      case 'funding_rate': return <span>{(numVal(item.funding_rate) * 100).toFixed(6)}%</span>;
      case 'usdc':
        return <span className={usdc >= 0 ? 'text-green-500' : 'text-red-500'}>${fmt(usdc, 4)}</span>;
      default: return null;
    }
  }, []);

  return (
    <Table isHeaderSticky aria-label="Funding history table" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor} bottomContent={bottomContent} bottomContentPlacement="outside">
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={pageItems} emptyContent="No funding records">
        {(item) => (
          <TableRow key={`${item.coin}-${item.time}`}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
