import { useState, useEffect, useMemo, useCallback } from 'react';
import type { SortDescriptor } from '@heroui/react';
import { Chip, addToast } from '@heroui/react';
import { Spinner } from '@heroui/spinner';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { traderApi } from '@/services/api';
import type { PositionHistoryByCoin } from '@/types/api';

// ==================== 列配置 ====================

type ColumnKey = 'coin' | 'total_positions' | 'winning_positions' | 'losing_positions' | 'win_rate' | 'total_pnl' | 'total_volume' | 'avg_holding_hours';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'coin', name: 'Coin', sortable: true },
  { uid: 'total_positions', name: 'Trades', sortable: true },
  { uid: 'winning_positions', name: 'Wins', sortable: true },
  { uid: 'losing_positions', name: 'Losses', sortable: true },
  { uid: 'win_rate', name: 'Win Rate', sortable: true },
  { uid: 'total_pnl', name: 'Total PnL', sortable: true },
  { uid: 'total_volume', name: 'Volume', sortable: true },
  { uid: 'avg_holding_hours', name: 'Avg Hold Time', sortable: true },
];

// ==================== 工具函数 ====================

function fmt(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '-';
  if (isNaN(value)) return '-';
  return value.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtHoldingTime(hours: number): string {
  if (!hours || hours <= 0) return '-';
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${fmt(hours, 1)}h`;
  const days = hours / 24;
  return `${fmt(days, 1)}d`;
}

// ==================== 组件 ====================

interface PerformanceByAssetProps {
  address: string;
}

export function PerformanceByAsset({ address }: PerformanceByAssetProps) {
  const [data, setData] = useState<PositionHistoryByCoin[]>([]);
  const [loading, setLoading] = useState(false);

  const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor>({
    column: 'total_positions',
    direction: 'descending',
  });

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    traderApi.getPositionHistoryByCoin(address)
      .then(res => {
        if (res.success) setData(res.data || []);
      })
      .catch((err: any) => {
        addToast({ title: '获取币种统计失败', description: err.message, color: 'danger' });
      })
      .finally(() => setLoading(false));
  }, [address]);

  const sortedItems = useMemo(() => {
    const col = sortDescriptor.column as ColumnKey;
    const dir = sortDescriptor.direction;
    return [...data].sort((a, b) => {
      if (col === 'coin') {
        return dir === 'ascending' ? a.coin.localeCompare(b.coin) : b.coin.localeCompare(a.coin);
      }
      const aVal = (a as any)[col] ?? 0;
      const bVal = (b as any)[col] ?? 0;
      return dir === 'ascending' ? aVal - bVal : bVal - aVal;
    });
  }, [data, sortDescriptor]);

  const renderCell = useCallback((item: PositionHistoryByCoin, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'coin':
        return <span className="font-bold">{item.coin}</span>;
      case 'total_positions':
        return <span>{item.total_positions}</span>;
      case 'winning_positions':
        return <span className="text-green-500">{item.winning_positions}</span>;
      case 'losing_positions':
        return <span className="text-red-500">{item.losing_positions}</span>;
      case 'win_rate': {
        const pct = (item.win_rate * 100);
        const color = pct >= 50 ? 'success' : 'danger';
        return <Chip size="sm" color={color} variant="flat">{fmt(pct, 1)}%</Chip>;
      }
      case 'total_pnl':
        return <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>${fmt(item.total_pnl)}</span>;
      case 'total_volume':
        return <span>${fmt(item.total_volume)}</span>;
      case 'avg_holding_hours':
        return <span>{fmtHoldingTime(item.avg_holding_hours)}</span>;
      default: return null;
    }
  }, []);

  if (loading) {
    return <div className="flex justify-center py-12"><Spinner size="lg" /></div>;
  }

  return (
    <Table isHeaderSticky aria-label="Performance by asset" sortDescriptor={sortDescriptor}
      onSortChange={setSortDescriptor}>
      <TableHeader columns={columns}>
        {(column) => <TableColumn key={column.uid} allowsSorting={column.sortable}>{column.name}</TableColumn>}
      </TableHeader>
      <TableBody items={sortedItems} emptyContent="No data">
        {(item) => (
          <TableRow key={item.coin}>
            {(columnKey) => <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
