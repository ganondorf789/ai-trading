import { Card, CardBody, Spinner } from "@heroui/react";
import { Icon } from "@iconify/react";

interface OrderStats {
  total_orders: number;
  successful: number;
  failed: number;
  opens: number;
  closes: number;
  total_pnl: number;
  real_orders: number;
  by_symbol?: Array<{
    symbol: string;
    count: number;
    pnl: number;
  }>;
  by_target?: Array<{
    target_address: string;
    target_name: string | null;
    count: number;
    pnl: number;
  }>;
}

interface StatsCardsProps {
  stats: OrderStats | null;
  loading: boolean;
}

export function StatsCards({ stats, loading }: StatsCardsProps) {
  const formatNumber = (num: number | null | undefined, decimals: number = 2) => {
    if (num === null || num === undefined) return "-";
    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPnl = (pnl: number | null | undefined) => {
    if (pnl === null || pnl === undefined) return "-";
    const formatted = formatNumber(Math.abs(pnl), 2);
    return pnl >= 0 ? `+$${formatted}` : `-$${formatted}`;
  };

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    );
  }

  if (!stats) return null;

  const successRate = stats.total_orders > 0 
    ? ((stats.successful / stats.total_orders) * 100).toFixed(1) 
    : "0.0";

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold">{stats.total_orders || 0}</div>
          <div className="text-sm text-default-500">Total Orders</div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold text-success">{stats.successful || 0}</div>
          <div className="text-sm text-default-500">Success ({successRate}%)</div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="text-center">
          <div className="text-2xl font-bold text-danger">{stats.failed || 0}</div>
          <div className="text-sm text-default-500">Failed</div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="text-center">
          <div className="flex items-center justify-center gap-2 mb-1">
            <Icon icon="solar:arrow-up-linear" className="text-success" width={20} />
            <span className="text-success font-medium">{stats.opens || 0}</span>
            <span className="text-default-400">/</span>
            <Icon icon="solar:arrow-down-linear" className="text-danger" width={20} />
            <span className="text-danger font-medium">{stats.closes || 0}</span>
          </div>
          <div className="text-sm text-default-500">Open / Close</div>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="text-center">
          <div className={`text-2xl font-bold ${(stats.total_pnl || 0) >= 0 ? "text-success" : "text-danger"}`}>
            {formatPnl(stats.total_pnl)}
          </div>
          <div className="text-sm text-default-500">Total PnL</div>
        </CardBody>
      </Card>
    </div>
  );
}
