import { Card, CardBody, Spinner } from "@heroui/react";
import { CopyPositionStats } from "@/services/api";

interface StatsCardsProps {
  stats: CopyPositionStats | null;
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

  const longCount = stats.by_side?.long?.count || 0;
  const shortCount = stats.by_side?.short?.count || 0;
  const longNotional = stats.by_side?.long?.notional || 0;
  const shortNotional = stats.by_side?.short?.notional || 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold">{stats.total_positions}</div>
          <div className="text-sm text-default-500">Total Positions</div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold text-success">{longCount}</div>
          <div className="text-sm text-default-500">Long (${formatNumber(longNotional)})</div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold text-danger">{shortCount}</div>
          <div className="text-sm text-default-500">Short (${formatNumber(shortNotional)})</div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold text-primary">{stats.by_target?.length || 0}</div>
          <div className="text-sm text-default-500">Active Targets</div>
        </CardBody>
      </Card>
    </div>
  );
}
