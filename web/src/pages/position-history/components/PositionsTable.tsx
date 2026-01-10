import { useState, useMemo, useEffect } from "react";
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
  Input,
  Select,
  SelectItem,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { GlobalPositionHistoryRecord } from "@/services/api";

// 每页显示条数选项
const ROWS_PER_PAGE_OPTIONS = [10, 20, 50, 100];
const DEFAULT_ROWS_PER_PAGE = 20;

interface PositionsTableProps {
  positions: GlobalPositionHistoryRecord[];
  loading: boolean;
}

export function PositionsTable({ positions, loading }: PositionsTableProps) {
  const navigate = useNavigate();
  
  // 分页状态
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(DEFAULT_ROWS_PER_PAGE);
  const [jumpPage, setJumpPage] = useState('');

  // 计算分页数据
  const totalCount = positions.length;
  const totalPages = Math.ceil(totalCount / rowsPerPage);
  
  // 当数据变化时重置页码
  useEffect(() => {
    if (page > totalPages && totalPages > 0) {
      setPage(1);
    }
  }, [positions.length, rowsPerPage, page, totalPages]);

  // 获取当前页的数据
  const paginatedPositions = useMemo(() => {
    const start = (page - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    return positions.slice(start, end);
  }, [positions, page, rowsPerPage]);

  // 处理每页条数变化
  const handleRowsPerPageChange = (value: string) => {
    setRowsPerPage(Number(value));
    setPage(1);
  };

  // 处理跳转页码
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      setPage(pageNum);
      setJumpPage('');
    }
  };

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

  const formatHours = (hours: number | null) => {
    if (!hours) return "-";
    if (hours < 1) return `${Math.round(hours * 60)}分`;
    if (hours < 24) return `${hours.toFixed(1)}时`;
    return `${(hours / 24).toFixed(1)}天`;
  };

  // 底部分页内容
  const bottomContent = useMemo(() => {
    if (totalCount === 0) return null;
    
    return (
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 py-3 px-2">
        <div className="flex items-center gap-3">
          <span className="text-sm text-default-500">
            显示 {Math.min((page - 1) * rowsPerPage + 1, totalCount)} - {Math.min(page * rowsPerPage, totalCount)} 条，共 {totalCount} 条记录
          </span>
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-500">每页</span>
            <Select
              size="sm"
              className="w-20"
              selectedKeys={[String(rowsPerPage)]}
              onChange={(e) => handleRowsPerPageChange(e.target.value)}
              aria-label="每页显示条数"
            >
              {ROWS_PER_PAGE_OPTIONS.map((option) => (
                <SelectItem key={String(option)} textValue={String(option)}>
                  {option}
                </SelectItem>
              ))}
            </Select>
            <span className="text-sm text-default-500">条</span>
          </div>
        </div>
        
        {totalPages > 1 && (
          <div className="flex items-center gap-3">
            <Pagination
              isCompact
              showControls
              showShadow
              color="primary"
              page={page}
              total={totalPages}
              onChange={setPage}
            />
            <div className="flex items-center gap-1">
              <span className="text-sm text-default-500">跳转</span>
              <Input
                type="number"
                size="sm"
                className="w-16"
                min={1}
                max={totalPages}
                value={jumpPage}
                onValueChange={setJumpPage}
                onKeyDown={(e) => e.key === 'Enter' && handleJumpPage()}
              />
              <span className="text-sm text-default-500">页</span>
            </div>
          </div>
        )}
      </div>
    );
  }, [page, totalPages, totalCount, rowsPerPage, jumpPage]);

  return (
    <Table
      aria-label="Position history table"
      classNames={{
        wrapper: "bg-content1/50 backdrop-blur-md",
        th: "bg-content2/50",
      }}
      bottomContent={bottomContent}
      bottomContentPlacement="outside"
    >
      <TableHeader>
        <TableColumn>交易员</TableColumn>
        <TableColumn>分组</TableColumn>
        <TableColumn>币种</TableColumn>
        <TableColumn>方向</TableColumn>
        <TableColumn>开仓时间</TableColumn>
        <TableColumn>平仓时间</TableColumn>
        <TableColumn>最大仓位</TableColumn>
        <TableColumn>开仓均价</TableColumn>
        <TableColumn>平仓均价</TableColumn>
        <TableColumn>持仓时长</TableColumn>
        <TableColumn>盈亏</TableColumn>
        <TableColumn>状态</TableColumn>
      </TableHeader>
      <TableBody emptyContent="暂无仓位历史数据" isLoading={loading} loadingContent={<Spinner />}>
        {paginatedPositions.map((position) => {
          const isLong = position.direction === 'long';
          const pnl = position.realized_pnl || 0;

          return (
            <TableRow key={position.id}>
              <TableCell>
                <div className="flex items-center gap-2">
                  {position.is_starred && (
                    <Icon icon="solar:star-bold" className="text-warning" width={14} />
                  )}
                  <Tooltip content={position.address}>
                    <span
                      className="font-mono text-sm cursor-pointer hover:text-primary transition-colors"
                      onClick={() => navigate(`/traders/${position.address}`)}
                    >
                      {position.trader_name || formatAddress(position.address)}
                    </span>
                  </Tooltip>
                </div>
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
                <span className="text-sm">{formatTime(position.open_time)}</span>
              </TableCell>
              <TableCell>
                <span className="text-sm">{formatTime(position.close_time)}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">{formatNumber(position.max_size, 4)}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">${formatNumber(position.avg_entry_price, 4)}</span>
              </TableCell>
              <TableCell>
                <span className="font-mono">
                  {position.avg_close_price ? `$${formatNumber(position.avg_close_price, 4)}` : '-'}
                </span>
              </TableCell>
              <TableCell>
                <span className="text-sm">{formatHours(position.holding_hours)}</span>
              </TableCell>
              <TableCell>
                <span className={`font-mono font-medium ${pnl >= 0 ? "text-success" : "text-danger"}`}>
                  {pnl >= 0 ? "+" : ""}${formatNumber(pnl, 2)}
                </span>
              </TableCell>
              <TableCell>
                <Chip
                  size="sm"
                  color={position.status === 'open' ? 'warning' : 'default'}
                  variant="flat"
                >
                  {position.status === 'open' ? '持仓中' : '已平仓'}
                </Chip>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
