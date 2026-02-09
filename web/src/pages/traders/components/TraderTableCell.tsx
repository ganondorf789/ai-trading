import { Button, Tooltip } from '@heroui/react';
import { Icon } from '@iconify/react';
import type { Trader } from '@/services/api';
import type { ColumnKey } from '../types';
import { getRatingColor, formatNumber, formatPercent, formatDate } from '@/utils';

interface TraderTableCellProps {
  trader: Trader;
  columnKey: ColumnKey;
  onToggleStar?: (address: string, isStarred: boolean) => void;
  isStarLoading?: boolean;
}

export function TraderTableCell({ trader, columnKey, onToggleStar, isStarLoading }: TraderTableCellProps) {
  switch (columnKey) {
    case 'star':
      return (
        <Button
          isIconOnly
          size="sm"
          variant="light"
          color={trader.is_starred ? "warning" : "default"}
          isLoading={isStarLoading}
          onPress={(e) => {
            e.continuePropagation?.();
            onToggleStar?.(trader.address, !trader.is_starred);
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <Icon 
            icon={trader.is_starred ? "solar:star-bold" : "solar:star-line-duotone"} 
            width={18} 
            className={trader.is_starred ? "text-warning" : "text-default-400"}
          />
        </Button>
      );
    case 'rating':
      return (
        <span className={`font-bold text-lg ${getRatingColor(trader.rating)}`}>
          {trader.rating}
        </span>
      );
    case 'address': {
      const shortAddr = `${trader.address.slice(0, 6)}...${trader.address.slice(-4)}`;
      const hasDisplayName = !!trader.display_name;
      return (
        <Tooltip content={trader.address} placement="top" delay={300}>
          <a
            href={`/traders/${trader.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {hasDisplayName ? (
              <span className="flex items-center gap-1">
                <span className="font-medium">{trader.display_name}</span>
                <span className="text-xs text-default-400 font-mono">({shortAddr})</span>
              </span>
            ) : (
              <span className="font-mono">{shortAddr}</span>
            )}
          </a>
        </Tooltip>
      );
    }
    case 'overall_score':
      return <span className="font-bold">{formatNumber(trader.overall_score)}</span>;
    case 'total_trades':
      return <span>{trader.total_trades}</span>;
    case 'win_rate':
      return <span>{formatPercent(trader.win_rate)}</span>;
    case 'total_pnl':
      return (
        <span className={trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
          ${formatNumber(trader.total_pnl, 0)}
        </span>
      );
    case 'roi':
      return (
        <span className={trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}>
          {formatPercent(trader.roi)}
        </span>
      );
    case 'profit_factor':
      return <span>{formatNumber(trader.profit_factor)}</span>;
    case 'max_drawdown':
      return <span className="text-red-500">{formatPercent(trader.max_drawdown)}</span>;
    case 'sharpe_ratio':
      return <span>{formatNumber(trader.sharpe_ratio)}</span>;
    case 'sortino_ratio':
      return <span>{formatNumber(trader.sortino_ratio || 0)}</span>;
    case 'calmar_ratio':
      return <span>{formatNumber(trader.calmar_ratio || 0)}</span>;
    case 'current_equity':
      return <span>${formatNumber(trader.current_equity, 0)}</span>;
    case 'active_days':
      return <span>{trader.active_days}</span>;
    case 'avg_leverage':
      return <span>{trader.avg_leverage || 1}x</span>;
    case 'current_positions':
      return <span>{trader.current_positions || 0}</span>;
    case 'last_trade_time':
      return <span className="text-sm">{formatDate(trader.last_trade_time)}</span>;
    case 'recent_7d_pnl': {
      const pnl7d = trader.recent_7d_pnl || 0;
      return (
        <span className={pnl7d >= 0 ? 'text-green-500' : 'text-red-500'}>
          ${formatNumber(pnl7d, 0)}
        </span>
      );
    }
    case 'recent_7d_win_rate':
      return <span>{formatPercent(trader.recent_7d_win_rate || 0)}</span>;
    case 'max_consecutive_wins':
      return <span className="text-green-500">{trader.max_consecutive_wins || 0}</span>;
    case 'max_consecutive_losses':
      return <span className="text-red-500">{trader.max_consecutive_losses || 0}</span>;
    case 'unique_symbols':
      return <span>{trader.unique_symbols || 0}</span>;
    case 'favorite_symbol':
      return <span className="text-sm">{trader.favorite_symbol || '-'}</span>;
    case 'long_short_ratio':
      return <span>{formatPercent(trader.long_short_ratio || 0)}</span>;
    default:
      return null;
  }
}
