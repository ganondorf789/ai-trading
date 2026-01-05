import { useNavigate } from "react-router-dom";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Button,
  Chip,
  Spinner,
  Tooltip,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { CopyPositionState } from "@/services/api";

interface PositionsTableProps {
  positions: CopyPositionState[];
  loading: boolean;
  onDeletePosition: (address: string, symbol: string) => void;
  onClearTarget: (address: string) => void;
}

export function PositionsTable({
  positions,
  loading,
  onDeletePosition,
  onClearTarget,
}: PositionsTableProps) {
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

  return (
    <Table aria-label="Positions table">
      <TableHeader>
        <TableColumn>Target</TableColumn>
        <TableColumn>Symbol</TableColumn>
        <TableColumn>Side</TableColumn>
        <TableColumn>Size</TableColumn>
        <TableColumn>Entry Price</TableColumn>
        <TableColumn>Notional</TableColumn>
        <TableColumn>Leverage</TableColumn>
        <TableColumn>Updated</TableColumn>
        <TableColumn>Actions</TableColumn>
      </TableHeader>
      <TableBody emptyContent="No positions found" isLoading={loading} loadingContent={<Spinner />}>
        {positions.map((position) => (
          <TableRow key={`${position.target_address}-${position.symbol}`}>
            <TableCell>
              <Tooltip content={position.target_address}>
                <span
                  className="font-mono text-sm cursor-pointer hover:text-primary"
                  onClick={() => navigate(`/traders/${position.target_address}`)}
                >
                  {position.target_name || formatAddress(position.target_address)}
                </span>
              </Tooltip>
            </TableCell>
            <TableCell>
              <span className="font-medium">{position.symbol}</span>
            </TableCell>
            <TableCell>
              <Chip color={position.side === "long" ? "success" : "danger"} size="sm" variant="flat">
                {position.side.toUpperCase()}
              </Chip>
            </TableCell>
            <TableCell>
              <span className="font-mono">{formatNumber(Math.abs(position.size), 4)}</span>
            </TableCell>
            <TableCell>
              <span className="font-mono">${formatNumber(position.entry_price, 2)}</span>
            </TableCell>
            <TableCell>
              <span className="font-mono">${formatNumber(position.notional, 2)}</span>
            </TableCell>
            <TableCell>
              <span className="font-mono">{position.leverage}x</span>
            </TableCell>
            <TableCell>
              <span className="text-sm text-default-500">{formatTime(position.updated_at)}</span>
            </TableCell>
            <TableCell>
              <div className="flex gap-1">
                <Tooltip content="Delete this position state">
                  <Button
                    isIconOnly
                    color="danger"
                    size="sm"
                    variant="light"
                    onPress={() => onDeletePosition(position.target_address, position.symbol)}
                  >
                    <Icon icon="solar:trash-bin-trash-linear" width={16} />
                  </Button>
                </Tooltip>
                <Tooltip content="Clear all positions for this target">
                  <Button
                    isIconOnly
                    color="warning"
                    size="sm"
                    variant="light"
                    onPress={() => onClearTarget(position.target_address)}
                  >
                    <Icon icon="solar:eraser-linear" width={16} />
                  </Button>
                </Tooltip>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
