import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { GroupComparisonSession } from '@/services/api';
import { formatPercent } from '../utils';
import { StatusBadge } from './StatusBadge';

interface SessionOverviewProps {
  session: GroupComparisonSession;
}

export const SessionOverview = ({ session }: SessionOverviewProps) => {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <h3 className="font-semibold">分析概览</h3>
          <StatusBadge status={session.status} />
        </div>
      </CardHeader>
      <CardBody>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-3 bg-content2/50 rounded-lg">
            <div className="text-2xl font-bold text-primary">
              {session.total_traders}
            </div>
            <div className="text-xs text-default-500">参与交易员</div>
          </div>
          <div className="text-center p-3 bg-content2/50 rounded-lg">
            <div className="text-2xl font-bold text-secondary">
              {session.total_rounds || 1}
            </div>
            <div className="text-xs text-default-500">淘汰轮次</div>
          </div>
          <div className="text-center p-3 bg-content2/50 rounded-lg">
            <div className="text-2xl font-bold text-warning">
              {session.num_groups}
            </div>
            <div className="text-xs text-default-500">总分组数</div>
          </div>
          <div className="text-center p-3 bg-content2/50 rounded-lg">
            <div className="text-2xl font-bold text-success">
              {session.finalists_count}
            </div>
            <div className="text-xs text-default-500">晋级决赛</div>
          </div>
          <div className="text-center p-3 bg-content2/50 rounded-lg">
            <div className="text-2xl font-bold">
              {session.group_size} → {session.top_per_group}
            </div>
            <div className="text-xs text-default-500">每组/晋级</div>
          </div>
        </div>

        {/* 筛选条件 */}
        {(session.min_sharpe || session.max_drawdown) && (
          <div className="mt-4 pt-4 border-t border-divider">
            <div className="text-xs text-default-500 mb-2">预筛选条件</div>
            <div className="flex flex-wrap gap-2">
              {session.min_sharpe && (
                <Chip size="sm" variant="flat">
                  Sharpe ≥ {session.min_sharpe}
                </Chip>
              )}
              {session.min_sortino && (
                <Chip size="sm" variant="flat">
                  Sortino ≥ {session.min_sortino}
                </Chip>
              )}
              {session.max_drawdown && (
                <Chip size="sm" variant="flat">
                  回撤 ≤ {formatPercent(session.max_drawdown)}
                </Chip>
              )}
              {session.min_win_rate && (
                <Chip size="sm" variant="flat">
                  胜率 ≥ {formatPercent(session.min_win_rate)}
                </Chip>
              )}
              {session.max_win_rate && (
                <Chip size="sm" variant="flat">
                  胜率 ≤ {formatPercent(session.max_win_rate)}
                </Chip>
              )}
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
};
