import { Card, CardBody } from '@heroui/card';
import type { BestSTrader } from '@/services/api';

interface StatsCardsProps {
  traders: BestSTrader[];
  presetName?: string;
  presetDescription?: string;
}

export function StatsCards({ traders, presetName, presetDescription }: StatsCardsProps) {
  // 计算统计数据
  const totalTraders = traders.length;
  const totalRecentPnl = traders.reduce((sum, t) => sum + Number(t.recent_pnl || 0), 0);
  const avgPositionWinRate = traders.length > 0
    ? traders.reduce((sum, t) => sum + Number(t.position_win_rate || 0), 0) / traders.length
    : 0;
  const avgSharpe = traders.length > 0
    ? traders.reduce((sum, t) => sum + Number(t.sharpe_ratio || 0), 0) / traders.length
    : 0;
  const starredCount = traders.filter(t => t.is_starred).length;

  const formatPnl = (value: number) => {
    const num = Number(value) || 0;
    if (num >= 0) {
      return `+$${num.toLocaleString()}`;
    }
    return `-$${Math.abs(num).toLocaleString()}`;
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <Card className="bg-gradient-to-br from-primary-50 to-primary-100 dark:from-primary-900/20 dark:to-primary-800/20">
        <CardBody className="p-4">
          <div className="flex flex-col">
            <span className="text-xs text-default-500">当前预设</span>
            <span className="text-lg font-bold text-primary">{presetName || '默认'}</span>
            <span className="text-xs text-default-400 truncate">{presetDescription}</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-4">
          <div className="flex flex-col">
            <span className="text-xs text-default-500">筛选结果</span>
            <span className="text-2xl font-bold">{totalTraders}</span>
            <span className="text-xs text-default-400">个交易员</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-4">
          <div className="flex flex-col">
            <span className="text-xs text-default-500">近期总PnL</span>
            <span className={`text-2xl font-bold ${totalRecentPnl >= 0 ? 'text-success' : 'text-danger'}`}>
              {formatPnl(totalRecentPnl)}
            </span>
            <span className="text-xs text-default-400">所有交易员</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-4">
          <div className="flex flex-col">
            <span className="text-xs text-default-500">平均仓位胜率</span>
            <span className={`text-2xl font-bold ${avgPositionWinRate >= 50 ? 'text-success' : 'text-warning'}`}>
              {avgPositionWinRate.toFixed(1)}%
            </span>
            <span className="text-xs text-default-400">仓位级别</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-4">
          <div className="flex flex-col">
            <span className="text-xs text-default-500">平均夏普比率</span>
            <span className={`text-2xl font-bold ${avgSharpe >= 1 ? 'text-success' : ''}`}>
              {avgSharpe.toFixed(2)}
            </span>
            <span className="text-xs text-default-400">风险调整收益</span>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-4">
          <div className="flex flex-col">
            <span className="text-xs text-default-500">已收藏</span>
            <span className="text-2xl font-bold text-warning">{starredCount}</span>
            <span className="text-xs text-default-400">个交易员</span>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
