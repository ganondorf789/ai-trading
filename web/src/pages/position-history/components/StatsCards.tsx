import { Card, CardBody, Spinner } from "@heroui/react";
import { GlobalPositionHistoryStats } from "@/services/api";

interface StatsCardsProps {
  stats: GlobalPositionHistoryStats | null;
  loading: boolean;
}

export function StatsCards({ stats, loading }: StatsCardsProps) {
  const formatNumber = (num: number | null, decimals: number = 2) => {
    if (num === null || num === undefined) return "-";

    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number | null) => {
    if (num === null || num === undefined) return "-";
    return `${(num * 100).toFixed(1)}%`;
  };

  const formatHours = (hours: number | null) => {
    if (!hours) return "-";
    if (hours < 1) return `${Math.round(hours * 60)}分钟`;
    if (hours < 24) return `${hours.toFixed(1)}小时`;
    return `${(hours / 24).toFixed(1)}天`;
  };

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (!stats) return null;

  const totalPnl = stats.total_pnl || 0;
  const isPnlPositive = totalPnl >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <Card className="bg-gradient-to-br from-violet-500/10 to-purple-500/10 border border-violet-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-violet-400">{stats.total_positions}</div>
          <div className="text-sm text-default-500">总仓位数</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-blue-400">{stats.total_traders}</div>
          <div className="text-sm text-default-500">交易员数</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 border border-amber-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-amber-400">{formatPercent(stats.win_rate)}</div>
          <div className="text-sm text-default-500">仓位胜率</div>
        </CardBody>
      </Card>

      <Card className={`bg-gradient-to-br ${isPnlPositive ? 'from-emerald-500/10 to-green-500/10 border-emerald-500/20' : 'from-rose-500/10 to-red-500/10 border-rose-500/20'} border`}>
        <CardBody className="text-center py-4">
          <div className={`text-2xl font-bold ${isPnlPositive ? 'text-emerald-400' : 'text-rose-400'}`}>
            {isPnlPositive ? '+' : ''}${formatNumber(totalPnl, 0)}
          </div>
          <div className="text-sm text-default-500">总盈亏</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-emerald-500/10 to-green-500/10 border border-emerald-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-emerald-400">{stats.winning_positions || 0}</div>
          <div className="text-sm text-default-500">盈利 (+${formatNumber(stats.total_profit || 0, 0)})</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-rose-500/10 to-red-500/10 border border-rose-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-rose-400">{stats.losing_positions || 0}</div>
          <div className="text-sm text-default-500">亏损 (${formatNumber(stats.total_loss || 0, 0)})</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-teal-500/10 to-cyan-500/10 border border-teal-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-teal-400">{stats.long_count}</div>
          <div className="text-sm text-default-500">多头仓位</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-pink-500/10 to-fuchsia-500/10 border border-pink-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-pink-400">{stats.short_count}</div>
          <div className="text-sm text-default-500">空头仓位</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-indigo-500/10 to-blue-500/10 border border-indigo-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-indigo-400">{formatHours(stats.avg_holding_hours)}</div>
          <div className="text-sm text-default-500">平均持仓</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-cyan-500/10 to-teal-500/10 border border-cyan-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-cyan-400">${formatNumber(stats.total_volume, 0)}</div>
          <div className="text-sm text-default-500">总交易量</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-slate-500/10 to-gray-500/10 border border-slate-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-slate-400">{stats.unique_coins}</div>
          <div className="text-sm text-default-500">交易币种</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-orange-500/10 to-amber-500/10 border border-orange-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-orange-400">${formatNumber(stats.total_fees, 0)}</div>
          <div className="text-sm text-default-500">总手续费</div>
        </CardBody>
      </Card>
    </div>
  );
}
