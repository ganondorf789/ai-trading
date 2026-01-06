import { useNavigate } from "react-router-dom";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Chip,
  Spinner,
  Tooltip,
  Progress,
} from "@heroui/react";
import { TraderPosition } from "@/services/api";

interface PositionsTableProps {
  positions: TraderPosition[];
  loading: boolean;
}

export function PositionsTable({ positions, loading }: PositionsTableProps) {
  const navigate = useNavigate();

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "-";
    const date = new Date(timeStr);

    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  const formatNumber = (num: number | null, decimals: number = 2) => {
    if (num === null || num === undefined) return "-";

    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number | null) => {
    if (num === null || num === undefined) return "-";
    const pct = num * 100;
    return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
  };

  return (
    <Table
      aria-label="Trader positions table"
      classNames={{
        wrapper: "bg-content1/50 backdrop-blur-md",
        th: "bg-content2/50",
      }}
    >
      <TableHeader>
        <TableColumn>交易员</TableColumn>
        <TableColumn>分组</TableColumn>
        <TableColumn>币种</TableColumn>
        <TableColumn>方向</TableColumn>
        <TableColumn>数量</TableColumn>
        <TableColumn>开仓均价</TableColumn>
        <TableColumn>仓位价值</TableColumn>
        <TableColumn>未实现盈亏</TableColumn>
        <TableColumn>ROE</TableColumn>
        <TableColumn>杠杆</TableColumn>
        <TableColumn>更新时间</TableColumn>
      </TableHeader>
      <TableBody emptyContent="暂无持仓数据" isLoading={loading} loadingContent={<Spinner />}>
        {positions.map((position) => {
          const isLong = position.szi > 0;
          const pnl = position.unrealized_pnl || 0;
          const roe = position.return_on_equity || 0;

          return (
            <TableRow key={`${position.address}-${position.coin}`}>
              <TableCell>
                <Tooltip content={position.address}>
                  <span
                    className="font-mono text-sm cursor-pointer hover:text-primary transition-colors"
                    onClick={() => navigate(`/traders/${position.address}`)}
                  >
                    {position.trader_name || formatAddress(position.address)}
                  </span>
                </Tooltip>
              </TableCell>
              <TableCell>
                {position.group_name ? (
                  <Chip
                    size="sm"
                    variant="flat"
                    style={{
                      backgroundColor: `${position.group_color}20`,
                      color: position.group_color || undefined,
                      borderColor: position.group_color || undefined,
                    }}
                    className="border"
                  >
                    {position.group_name}
                  </Chip>
                ) : (
                  <span className="text-default-400">-</span>
                )}
              </TableCell>
              <TableCell>
                <span className="font-semibold">{position.coin}</span>
              </TableCell>
              <TableCell>
                <Chip
                  color={isLong ? "success" : "danger"}
                  size="sm"
                  variant="flat"
                  startContent={
                    isLong ? (
                      <span className="text-xs">▲</span>
                    ) : (
                      <span className="text-xs">▼</span>
                    )
                  }
                >
                  {isLong ? "LONG" : "SHORT"}
                </Chip>
              </TableCell>
              <TableCell>
                <span className="font-mono">{formatNumber(Math.abs(position.szi), 4)}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">${formatNumber(position.entry_px, 2)}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono font-medium">${formatNumber(position.position_value, 2)}</span>
              </TableCell>
              <TableCell>
                <span className={`font-mono font-medium ${pnl >= 0 ? "text-success" : "text-danger"}`}>
                  {pnl >= 0 ? "+" : ""}${formatNumber(pnl, 2)}
                </span>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  <span className={`font-mono text-sm ${roe >= 0 ? "text-success" : "text-danger"}`}>
                    {formatPercent(roe)}
                  </span>
                  <Progress
                    size="sm"
                    value={Math.min(Math.abs(roe * 100), 100)}
                    color={roe >= 0 ? "success" : "danger"}
                    className="w-12"
                  />
                </div>
              </TableCell>
              <TableCell>
                <Chip size="sm" variant="bordered" className="font-mono">
                  {position.leverage_value}x
                </Chip>
              </TableCell>
              <TableCell>
                <span className="text-sm text-default-500">{formatTime(position.updated_at)}</span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
