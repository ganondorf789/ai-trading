import { Card, CardHeader, CardBody } from '@heroui/card';
import { Icon } from '@iconify/react';
import { TraderCard } from './TraderCard';

interface FinalistsListProps {
  finalists: any[];
  onTraderClick: (address: string) => void;
}

export const FinalistsList = ({ finalists, onTraderClick }: FinalistsListProps) => {
  if (!finalists || finalists.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold flex items-center gap-2">
          <Icon icon="solar:cup-star-bold" className="text-warning" />
          决赛晋级者 ({finalists.length})
        </h3>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {finalists.map((trader, index) => (
            <TraderCard
              key={trader.address}
              trader={trader}
              rank={trader.final_rank || index + 1}
              isFinalist
              onClick={() => onTraderClick(trader.address)}
            />
          ))}
        </div>
      </CardBody>
    </Card>
  );
};
