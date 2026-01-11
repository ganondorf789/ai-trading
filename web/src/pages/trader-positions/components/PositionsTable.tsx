import { useState, useMemo, useEffect } from "react";
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
  Button,
  Pagination,
  Input,
  Select,
  SelectItem,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { TraderPosition } from "@/services/api";
import { getRatingColor } from "@/utils";

// 每页显示条数选项
const ROWS_PER_PAGE_OPTIONS = [10, 20, 50, 100];
const DEFAULT_ROWS_PER_PAGE = 20;

interface PositionsTableProps {
  positions: TraderPosition[];
  loading: boolean;
  onRefreshTrader?: (address: string) => Promise<void>;
  onToggleStar?: (address: string, isStarred: boolean) => Promise<void>;
  starLoadingAddresses?: Set<string>;
  onAIAnalyze?: (position: TraderPosition) => void;
}

export function PositionsTable({ positions, loading, onRefreshTrader, onToggleStar, starLoadingAddresses = new Set(), onAIAnalyze }: PositionsTableProps) {
  const [refreshingAddresses, setRefreshingAddresses] = useState<Set<string>>(new Set());
  
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
    setPage(1); // 重置到第一页
  };

  // 处理跳转页码
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      setPage(pageNum);
      setJumpPage('');
    }
  };

  const handleRefreshTrader = async (address: string) => {
    if (!onRefreshTrader || refreshingAddresses.has(address)) return;
    
    setRefreshingAddresses(prev => new Set(prev).add(address));
    try {
      await onRefreshTrader(address);
    } finally {
      setRefreshingAddresses(prev => {
        const next = new Set(prev);
        next.delete(address);
        return next;
      });
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

  const formatPercent = (num: number | null) => {
    if (num === null || num === undefined) return "-";
    const pct = num * 100;
    return `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
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
      aria-label="Trader positions table"
      classNames={{
        wrapper: "bg-content1/50 backdrop-blur-md",
        th: "bg-content2/50",
      }}
      bottomContent={bottomContent}
      bottomContentPlacement="outside"
    >
      <TableHeader>
        <TableColumn width={50}>收藏</TableColumn>
        <TableColumn>交易员</TableColumn>
        <TableColumn>评级</TableColumn>
        <TableColumn>币种</TableColumn>
        <TableColumn>方向</TableColumn>
        <TableColumn>数量</TableColumn>
        <TableColumn>开仓均价</TableColumn>
        <TableColumn>仓位价值</TableColumn>
        <TableColumn>未实现盈亏</TableColumn>
        <TableColumn>ROE</TableColumn>
        <TableColumn>杠杆</TableColumn>
        <TableColumn>更新时间</TableColumn>
        <TableColumn width={80}>操作</TableColumn>
      </TableHeader>
      <TableBody emptyContent="暂无持仓数据" isLoading={loading} loadingContent={<Spinner />}>
        {paginatedPositions.map((position) => {
          const isLong = position.szi > 0;
          const pnl = position.unrealized_pnl || 0;
          const roe = position.return_on_equity || 0;

          return (
            <TableRow key={`${position.address}-${position.coin}`}>
              <TableCell>
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  color={position.is_starred ? "warning" : "default"}
                  isLoading={starLoadingAddresses.has(position.address)}
                  onPress={() => onToggleStar?.(position.address, !position.is_starred)}
                  isDisabled={!onToggleStar}
                >
                  <Icon 
                    icon={position.is_starred ? "solar:star-bold" : "solar:star-line-duotone"} 
                    width={18} 
                    className={position.is_starred ? "text-warning" : "text-default-400"}
                  />
                </Button>
              </TableCell>
              <TableCell>
                  <a
                    href={`/traders/${position.address}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-sm text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {position.trader_name || formatAddress(position.address)}
                  </a>
              </TableCell>
              <TableCell>
                <span className={`font-bold text-lg ${getRatingColor(position.rating)}`}>
                  {position.rating || '-'}
                </span>
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
              <TableCell>
                <div className="flex gap-1">
                  {onAIAnalyze && (
                    <Tooltip content="AI 风险分析">
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                        color="secondary"
                        onPress={() => onAIAnalyze(position)}
                      >
                        <Icon icon="solar:magic-stick-2-bold-duotone" width={16} />
                      </Button>
                    </Tooltip>
                  )}
                  <Tooltip content="刷新持仓">
                    <Button
                      isIconOnly
                      size="sm"
                      variant="light"
                      color="primary"
                      isLoading={refreshingAddresses.has(position.address)}
                      onPress={() => handleRefreshTrader(position.address)}
                      isDisabled={!onRefreshTrader}
                    >
                      <Icon icon="solar:refresh-bold-duotone" width={16} />
                    </Button>
                  </Tooltip>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
