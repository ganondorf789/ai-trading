import { Card, CardBody } from "@heroui/react";
import { Icon } from "@iconify/react";
import type { PositionTrackingStats } from "@/services/api";

interface StatsCardsProps {
  stats: PositionTrackingStats;
}

export default function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      title: "总记录",
      value: stats.total_count,
      icon: "solar:document-bold-duotone",
      color: "text-primary",
    },
    {
      title: "跟单中",
      value: stats.active_count,
      icon: "solar:play-bold-duotone",
      color: "text-success",
    },
    {
      title: "等待开仓",
      value: stats.pending_count,
      icon: "solar:clock-circle-bold-duotone",
      color: "text-warning",
    },
    {
      title: "已平仓",
      value: stats.closed_count,
      icon: "solar:check-circle-bold-duotone",
      color: "text-primary",
    },
    {
      title: "已停止",
      value: stats.stopped_count,
      icon: "solar:stop-bold-duotone",
      color: "text-danger",
    },
    {
      title: "累计盈亏",
      value: `$${stats.total_closed_pnl?.toFixed(2) || "0.00"}`,
      icon: "solar:wallet-money-bold-duotone",
      color: (stats.total_closed_pnl || 0) >= 0 ? "text-success" : "text-danger",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
      {cards.map((card) => (
        <Card key={card.title} className="bg-content1/50">
          <CardBody className="flex flex-row items-center gap-3 py-3">
            <div className={`p-2 rounded-lg bg-default-100 ${card.color}`}>
              <Icon icon={card.icon} width={24} />
            </div>
            <div>
              <p className="text-xs text-default-500">{card.title}</p>
              <p className={`text-lg font-semibold ${card.color}`}>{card.value}</p>
            </div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
