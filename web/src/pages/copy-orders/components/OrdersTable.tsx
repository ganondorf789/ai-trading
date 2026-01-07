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
  Pagination,
} from "@heroui/react";
import { CopyTradingOrder, PaginationInfo } from "@/services/api";

interface OrdersTableProps {
  orders: CopyTradingOrder[];
  loading: boolean;
  pagination: PaginationInfo | null;
  onPageChange: (page: number) => void;
}

export function OrdersTable({
  orders,
  loading,
  pagination,
  onPageChange,
}: OrdersTableProps) {
  const navigate = useNavigate();

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "-";
    const date = new Date(timeStr);
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
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

  const formatPnl = (pnl: number | null) => {
    if (pnl === null || pnl === undefined || pnl === 0) return "-";
    const formatted = formatNumber(Math.abs(pnl), 2);
    return pnl >= 0 ? `+$${formatted}` : `-$${formatted}`;
  };

  const getSideColor = (side: string): "success" | "danger" => {
    return side.toLowerCase() === "long" || side.toLowerCase() === "buy" ? "success" : "danger";
  };

  const getActionColor = (action: string): "primary" | "secondary" => {
    return action.toLowerCase() === "open" ? "primary" : "secondary";
  };

  const getStatusColor = (status: string): "success" | "danger" | "warning" | "default" => {
    switch (status.toLowerCase()) {
      case "success":
        return "success";
      case "failed":
        return "danger";
      case "pending":
        return "warning";
      default:
        return "default";
    }
  };

  return (
    <div>
      <Table aria-label="Copy trading orders table">
        <TableHeader>
          <TableColumn>Time</TableColumn>
          <TableColumn>Trader</TableColumn>
          <TableColumn>Symbol</TableColumn>
          <TableColumn>Side</TableColumn>
          <TableColumn>Action</TableColumn>
          <TableColumn>Size</TableColumn>
          <TableColumn>Price</TableColumn>
          <TableColumn>Leverage</TableColumn>
          <TableColumn>Status</TableColumn>
          <TableColumn>PnL</TableColumn>
          <TableColumn>Mode</TableColumn>
        </TableHeader>
        <TableBody emptyContent="No orders found" isLoading={loading} loadingContent={<Spinner />}>
          {orders.map((order) => (
            <TableRow key={order.id}>
              <TableCell>
                <span className="text-sm text-default-500 whitespace-nowrap">
                  {formatTime(order.created_at)}
                </span>
              </TableCell>
              <TableCell>
                <Tooltip content={order.target_address}>
                  <span
                    className="font-mono text-sm cursor-pointer hover:text-primary"
                    onClick={() => navigate(`/traders/${order.target_address}`)}
                  >
                    {order.target_name || formatAddress(order.target_address)}
                  </span>
                </Tooltip>
              </TableCell>
              <TableCell>
                <span className="font-medium">{order.symbol}</span>
              </TableCell>
              <TableCell>
                <Chip color={getSideColor(order.side)} size="sm" variant="flat">
                  {order.side.toUpperCase()}
                </Chip>
              </TableCell>
              <TableCell>
                <Chip color={getActionColor(order.action)} size="sm" variant="dot">
                  {order.action.toUpperCase()}
                </Chip>
              </TableCell>
              <TableCell>
                <span className="font-mono">{formatNumber(order.size, 4)}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">
                  {order.price ? `$${formatNumber(order.price, 2)}` : "-"}
                </span>
              </TableCell>
              <TableCell>
                <span className="font-mono">{order.leverage}x</span>
              </TableCell>
              <TableCell>
                <Tooltip content={order.error_message || ""} isDisabled={!order.error_message}>
                  <Chip color={getStatusColor(order.status)} size="sm" variant="flat">
                    {order.status.toUpperCase()}
                  </Chip>
                </Tooltip>
              </TableCell>
              <TableCell>
                <span className={`font-mono ${order.pnl >= 0 ? "text-success" : "text-danger"}`}>
                  {formatPnl(order.pnl)}
                </span>
              </TableCell>
              <TableCell>
                <Chip 
                  color={order.is_dry_run ? "warning" : "success"} 
                  size="sm" 
                  variant="bordered"
                >
                  {order.is_dry_run ? "DRY" : "LIVE"}
                </Chip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Pagination */}
      {pagination && pagination.total_pages > 1 && (
        <div className="flex justify-center mt-4">
          <Pagination
            color="primary"
            page={pagination.page}
            total={pagination.total_pages}
            onChange={onPageChange}
          />
        </div>
      )}
    </div>
  );
}
