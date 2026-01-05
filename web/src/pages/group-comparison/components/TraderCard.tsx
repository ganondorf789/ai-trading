import { Card, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Icon } from '@iconify/react';
import { formatNumber, formatUSD, formatPercent } from '../utils';

interface TraderCardProps {
  trader: any;
  rank?: number;
  isFinalist?: boolean;
  showEliminatedRound?: boolean;
  onClick?: () => void;
}

export const TraderCard = ({
  trader,
  rank,
  isFinalist,
  showEliminatedRound,
  onClick,
}: TraderCardProps) => {
  const address = trader.address || '';
  const shortAddr = `${address.slice(0, 6)}...${address.slice(-4)}`;

  return (
    <Card
      isPressable={!!onClick}
      onPress={onClick}
      className={`bg-content2/50 ${isFinalist ? 'border-2 border-success/50' : ''} ${
        trader.eliminated_round ? 'opacity-75' : ''
      }`}
    >
      <CardBody className="p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {rank && (
              <span className={`text-lg font-bold ${rank <= 3 ? 'text-warning' : 'text-default-500'}`}>
                #{rank}
              </span>
            )}
            {isFinalist && (
              <Icon icon="solar:medal-ribbon-bold" className="text-success text-lg" />
            )}
            <a
              href={`/traders/${address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm hover:text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {shortAddr}
            </a>
          </div>
          <div className="flex items-center gap-1">
            {showEliminatedRound && trader.eliminated_round && (
              <Chip size="sm" variant="flat" color="danger">
                第{trader.eliminated_round}轮淘汰
              </Chip>
            )}
            <Chip size="sm" variant="flat" color="primary">
              {formatNumber(trader.overall_score, 1)}分
            </Chip>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-default-500">总盈亏</span>
            <span className={trader.total_pnl >= 0 ? 'text-success' : 'text-danger'}>
              {formatUSD(trader.total_pnl)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-default-500">胜率</span>
            <span>{formatPercent(trader.win_rate)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-default-500">Sharpe</span>
            <span>{formatNumber(trader.sharpe_ratio)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-default-500">回撤</span>
            <span className="text-danger">{formatPercent(trader.max_drawdown)}</span>
          </div>
        </div>

        {trader.elimination_reason && (
          <div className="mt-2 text-xs text-danger">
            <Icon icon="solar:danger-triangle-linear" className="inline mr-1" />
            {trader.elimination_reason}
          </div>
        )}
      </CardBody>
    </Card>
  );
};
