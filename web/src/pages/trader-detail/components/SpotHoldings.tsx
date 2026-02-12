import { useState, useEffect, useMemo, useCallback } from 'react';
import type { SortDescriptor } from '@heroui/react';
import { addToast } from '@heroui/react';
import { Spinner } from '@heroui/spinner';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { tradingApi } from '@/services/api';

// ==================== 类型 ====================

interface SpotBalance {
  coin: string;
  token: number;
  hold: string;
  total: string;
  entryNtl: string;
  price: number;
  value: number;
}

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'total' | 'hold' | 'available' | 'price' | 'value' | 'share';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'price', name: 'Price', sortable: true },
  { uid: 'total', name: 'Total', sortable: true },
  { uid: 'hold', name: 'In Orders', sortable: true },
  { uid: 'available', name: 'Available', sortable: true },
  { uid: 'value', name: 'Value (USD)', sortable: true },
  { uid: 'share', name: 'Asset Share', sortable: true },
];

// ==================== 工具函数 ====================

function fmt(value: number, decimals = 4): string {
  if (isNaN(value)) return '-';
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtUsd(value: number): string {
  if (isNaN(value)) return '-';
  return '$' + value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function numVal(value: string | number | null | undefined): number {
  if (value == null || value === '') return 0;
  const n = typeof value === 'string' ? parseFloat(value) : value;
  return isNaN(n) ? 0 : n;
}

// ==================== 组件 ====================

interface SpotHoldingsProps {
  address: string;
}

export function SpotHoldings({ address }: SpotHoldingsProps) {
  const [balances, setBalances] = useState<SpotBalance[]>([]);
  const [totalValue, setTotalValue] = useState(0);
  const [loading, setLoading] = useState(false);

  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'value',
    direction: 'descending',
  });

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    tradingApi.getSpotHoldings(address)
      .then((res: any) => {
        if (res.success) {
          setBalances(res.data || []);
          setTotalValue(res.total_value || 0);
        }
      })
      .catch((err: any) => {
        addToast({ title: '获取现货持仓失败', description: err.message, color: 'danger' });
      })
      .finally(() => setLoading(false));
  }, [address]);

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;
    return [...balances].sort((a, b) => {
      if (col === 'coin') {
        return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
      }
      let aVal: number, bVal: number;
      switch (col) {
        case 'total': aVal = numVal(a.total); bVal = numVal(b.total); break;
        case 'hold': aVal = numVal(a.hold); bVal = numVal(b.hold); break;
        case 'available': aVal = numVal(a.total) - numVal(a.hold); bVal = numVal(b.total) - numVal(b.hold); break;
        case 'price': aVal = a.price; bVal = b.price; break;
        case 'value': aVal = a.value; bVal = b.value; break;
        case 'share': aVal = a.value; bVal = b.value; break;
        default: return 0;
      }
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [balances, sortDescriptor]);

  const renderCell = useCallback((item: SpotBalance, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin':
        return <span className="font-bold">{item.coin}</span>;
      case 'price':
        return <span>{fmtUsd(item.price)}</span>;
      case 'total':
        return <span>{fmt(numVal(item.total))}</span>;
      case 'hold':
        return <span>{numVal(item.hold) > 0 ? fmt(numVal(item.hold)) : '-'}</span>;
      case 'available': {
        const available = numVal(item.total) - numVal(item.hold);
        return <span>{fmt(available)}</span>;
      }
      case 'value':
        return <span>{fmtUsd(item.value)}</span>;
      case 'share': {
        const pct = totalValue > 0 ? (item.value / totalValue * 100) : 0;
        return (
          <div className="flex flex-col gap-1 w-[100px]">
            <span className="text-sm text-right">{fmt(pct, 2)} %</span>
            <div className="w-full h-1.5 rounded-full bg-default-200">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
          </div>
        );
      }
      default: return null;
    }
  }, [totalValue]);

  if (loading) {
    return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  }

  return (
    <Table isHeaderSticky aria-label="Spot holdings" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor}>
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={sortedItems} emptyContent="No spot holdings">
        {(item) => (
          <TableRow key={item.coin}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
