import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Chip } from '@heroui/chip';
import { Button } from '@heroui/button';
import { Spinner } from '@heroui/spinner';
import { Tooltip } from '@heroui/tooltip';
import type { BestSTrader } from '@/services/api';

interface TradersTableProps {
  traders: BestSTrader[];
  isLoading: boolean;
  onToggleStar?: (address: string, isStarred: boolean) => void;
  starLoadingAddresses?: Set<string>;
}

const formatPnl = (value: number | string | null) => {
  const num = Number(value) || 0;
  if (num >= 0) {
    return <span className="text-success">${num.toLocaleString()}</span>;
  }
  return <span className="text-danger">-${Math.abs(num).toLocaleString()}</span>;
};

const formatPercent = (value: number | string | null, decimals = 1) => {
  if (value === null || value === undefined) return 'N/A';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return 'N/A';
  return `${num.toFixed(decimals)}%`;
};

const getHoldingStyle = (hours: number) => {
  if (!hours || hours === 0) return { label: '未知', color: 'default' as const };
  if (hours < 4) return { label: '超短线', color: 'danger' as const };
  if (hours < 24) return { label: '短线', color: 'warning' as const };
  if (hours < 168) return { label: '中线', color: 'primary' as const };
  return { label: '长线', color: 'success' as const };
};

const columns = [
  { key: 'rank', label: '#', width: 50 },
  { key: 'address', label: '地址', width: 150 },
  { key: 'score', label: '评分', width: 80 },
  { key: 'position_win_rate', label: '仓位胜率', width: 100 },
  { key: 'position_pf', label: '仓位盈亏比', width: 100 },
  { key: 'recent_pnl', label: '近期PnL', width: 120 },
  { key: 'recent_win_rate', label: '近期胜率', width: 100 },
  { key: 'total_pnl', label: '总PnL', width: 120 },
  { key: 'sharpe', label: '夏普', width: 80 },
  { key: 'drawdown', label: '回撤', width: 80 },
  { key: 'style', label: '风格', width: 80 },
  { key: 'positions', label: '仓位数', width: 80 },
  { key: 'actions', label: '', width: 60 },
];

export function TradersTable({
  traders,
  isLoading,
  onToggleStar,
  starLoadingAddresses = new Set(),
}: TradersTableProps) {
  const navigate = useNavigate();

  const handleRowClick = useCallback((address: string) => {
    navigate(`/traders/${address}`);
  }, [navigate]);

  const renderCell = useCallback((trader: BestSTrader, columnKey: string, index: number) => {
    switch (columnKey) {
      case 'rank':
        return <span className="font-medium">{index + 1}</span>;
      
      case 'address':
        return (
          <div className="flex flex-col">
            <Tooltip content={trader.address}>
              <a
                href={`/traders/${trader.address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-sm text-primary hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                {trader.address.slice(0, 8)}...{trader.address.slice(-4)}
              </a>
            </Tooltip>
            {trader.trader_name && (
              <span className="text-xs text-default-400">{trader.trader_name}</span>
            )}
          </div>
        );
      
      case 'score':
        return (
          <div className="flex items-center gap-1">
            <Chip size="sm" color="warning" variant="flat">S</Chip>
            <span className="font-medium">{Number(trader.overall_score || 0).toFixed(1)}</span>
          </div>
        );
      
      case 'position_win_rate':
        return (
          <span className={trader.position_win_rate && trader.position_win_rate >= 50 ? 'text-success' : 'text-danger'}>
            {formatPercent(trader.position_win_rate)}
          </span>
        );
      
      case 'position_pf':
        const pf = Number(trader.position_profit_factor);
        return !isNaN(pf) && pf > 0
          ? <span className={pf >= 1.5 ? 'text-success' : ''}>{pf.toFixed(2)}</span>
          : 'N/A';
      
      case 'recent_pnl':
        return formatPnl(trader.recent_pnl || 0);
      
      case 'recent_win_rate':
        return (
          <span className={trader.recent_position_win_rate && trader.recent_position_win_rate >= 50 ? 'text-success' : 'text-danger'}>
            {formatPercent(trader.recent_position_win_rate)}
          </span>
        );
      
      case 'total_pnl':
        return formatPnl(trader.total_pnl);
      
      case 'sharpe':
        const sharpe = Number(trader.sharpe_ratio || 0);
        return (
          <span className={sharpe >= 1 ? 'text-success' : ''}>
            {sharpe.toFixed(2)}
          </span>
        );
      
      case 'drawdown':
        const drawdown = Number(trader.max_drawdown || 0);
        return (
          <span className={drawdown <= 0.2 ? 'text-success' : 'text-warning'}>
            {(drawdown * 100).toFixed(1)}%
          </span>
        );
      
      case 'style':
        const style = getHoldingStyle(trader.avg_holding_hours);
        return <Chip size="sm" color={style.color} variant="flat">{style.label}</Chip>;
      
      case 'positions':
        return trader.closed_positions;
      
      case 'actions':
        return (
          <Button
            isIconOnly
            size="sm"
            variant="light"
            onPress={() => onToggleStar?.(trader.address, !trader.is_starred)}
            isLoading={starLoadingAddresses.has(trader.address)}
          >
            {trader.is_starred ? '⭐' : '☆'}
          </Button>
        );
      
      default:
        return null;
    }
  }, [onToggleStar, starLoadingAddresses]);

  return (
    <Table
      isHeaderSticky
      aria-label="S级优选交易员表格"
      selectionMode="single"
      onRowAction={(key) => handleRowClick(key.toString())}
      classNames={{
        wrapper: 'min-h-[400px] max-h-[600px]',
      }}
    >
      <TableHeader columns={columns}>
        {(column) => (
          <TableColumn key={column.key} width={column.width}>
            {column.label}
          </TableColumn>
        )}
      </TableHeader>
      <TableBody
        items={traders}
        isLoading={isLoading}
        loadingContent={<Spinner size="lg" />}
        emptyContent="暂无符合条件的交易员"
      >
        {(item) => (
          <TableRow
            key={item.address}
            className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            {(columnKey) => (
              <TableCell>
                {renderCell(item, columnKey.toString(), traders.indexOf(item))}
              </TableCell>
            )}
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
