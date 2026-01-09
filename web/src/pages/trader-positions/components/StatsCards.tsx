import { Card, CardBody, Spinner } from "@heroui/react";
import { Icon } from "@iconify/react";
import { TraderPositionsStats } from "@/services/api";

interface StatsCardsProps {
  stats: TraderPositionsStats | null;
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

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
      <Card className="bg-gradient-to-br from-violet-500/10 to-purple-500/10 border border-violet-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-violet-400">{stats.total_positions}</div>
          <div className="text-sm text-default-500">总持仓数</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-blue-400">{stats.total_traders}</div>
          <div className="text-sm text-default-500">活跃交易员</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-amber-500/10 to-orange-500/10 border border-amber-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-amber-400">${formatNumber(stats.total_notional, 0)}</div>
          <div className="text-sm text-default-500">总仓位价值</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-emerald-500/10 to-green-500/10 border border-emerald-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-emerald-400">{stats.long_count}</div>
          <div className="text-sm text-default-500">多头 (${formatNumber(stats.long_notional, 0)})</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-rose-500/10 to-red-500/10 border border-rose-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-rose-400">{stats.short_count}</div>
          <div className="text-sm text-default-500">空头 (${formatNumber(stats.short_notional, 0)})</div>
        </CardBody>
      </Card>

      <Card className="bg-gradient-to-br from-slate-500/10 to-gray-500/10 border border-slate-500/20">
        <CardBody className="text-center py-4">
          <div className="text-2xl font-bold text-slate-300">{stats.by_coin?.length || 0}</div>
          <div className="text-sm text-default-500">不同币种</div>
        </CardBody>
      </Card>
    </div>
  );
}
