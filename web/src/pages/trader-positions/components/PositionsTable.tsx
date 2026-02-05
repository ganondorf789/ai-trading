import { useState, useMemo, useEffect, useCallback } from "react";
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
  Button,
} from "@heroui/react";
import type { Selection, SortDescriptor } from "@heroui/react";
import { Icon } from "@iconify/react";
import { TraderPosition } from "@/services/api";
import { getRatingColor } from "@/utils";
import { traderPositionColumns, TraderPositionColumnKey } from "./PositionFilters";
import { TablePagination } from "@/components/TablePagination";

// 每页显示条数选项
const ROWS_PER_PAGE_OPTIONS = [10, 20, 50, 100];
const DEFAULT_ROWS_PER_PAGE = 20;

interface PositionsTableProps {
  positions: TraderPosition[];
  loading: boolean;
  onRefreshTrader?: (address: string) => Promise<void>;
  onToggleStar?: (address: string, isStarred: boolean) => Promise<void>;
  starLoadingAddresses?: Set<string>;
  visibleColumns: Selection;
  sortDescriptor: SortDescriptor;
  onSortChange: (descriptor: SortDescriptor) => void;
}

export function PositionsTable({ positions, loading, onRefreshTrader, onToggleStar, starLoadingAddresses = new Set(), visibleColumns, sortDescriptor, onSortChange }: PositionsTableProps) {
  const [refreshingAddresses, setRefreshingAddresses] = useState<Set<string>>(new Set());
  
  // 分页状态
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(DEFAULT_ROWS_PER_PAGE);

  // 计算分页数据
  const totalCount = positions.length;
  const totalPages = Math.ceil(totalCount / rowsPerPage);
  
  // 当数据变化时重置页码
  useEffect(() => {
    if (page > totalPages && totalPages > 0) {
      setPage(1);
    }
  }, [positions.length, rowsPerPage, page, totalPages]);

  // 可见列
  const headerColumns = useMemo(() => {
    if (visibleColumns === 'all') return traderPositionColumns;
    return traderPositionColumns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  // 排序后的数据
  const sortedPositions = useMemo(() => {
    if (!sortDescriptor.column) return positions;

    return [...positions].sort((a, b) => {
      const column = sortDescriptor.column as TraderPositionColumnKey;
      let first: any;
      let second: any;

      switch (column) {
        case 'star':
          first = a.is_starred ? 1 : 0;
          second = b.is_starred ? 1 : 0;
          break;
        case 'trader':
          first = a.trader_name || a.address;
          second = b.trader_name || b.address;
          break;
        case 'rating':
          first = a.rating || '';
          second = b.rating || '';
          break;
        case 'coin':
          first = a.coin;
          second = b.coin;
          break;
        case 'direction':
          first = a.szi > 0 ? 1 : 0;
          second = b.szi > 0 ? 1 : 0;
          break;
        case 'size':
          first = Math.abs(a.szi);
          second = Math.abs(b.szi);
          break;
        case 'entry_px':
          first = a.entry_px || 0;
          second = b.entry_px || 0;
          break;
        case 'position_value':
          first = a.position_value || 0;
          second = b.position_value || 0;
          break;
        case 'unrealized_pnl':
          first = a.unrealized_pnl || 0;
          second = b.unrealized_pnl || 0;
          break;
        case 'roe':
          first = a.return_on_equity || 0;
          second = b.return_on_equity || 0;
          break;
        case 'leverage':
          first = a.leverage_value || 0;
          second = b.leverage_value || 0;
          break;
        case 'open_time':
          first = a.open_time ? new Date(a.open_time).getTime() : 0;
          second = b.open_time ? new Date(b.open_time).getTime() : 0;
          break;
        case 'updated_at':
          first = a.updated_at ? new Date(a.updated_at).getTime() : 0;
          second = b.updated_at ? new Date(b.updated_at).getTime() : 0;
          break;
        default:
          return 0;
      }

      const cmp = first < second ? -1 : first > second ? 1 : 0;
      return sortDescriptor.direction === 'descending' ? -cmp : cmp;
    });
  }, [positions, sortDescriptor]);

  // 获取当前页的数据
  const paginatedPositions = useMemo(() => {
    const start = (page - 1) * rowsPerPage;
    const end = start + rowsPerPage;
    return sortedPositions.slice(start, end);
  }, [sortedPositions, page, rowsPerPage]);

  // 处理每页条数变化
  const handleRowsPerPageChange = useCallback((value: number) => {
    setRowsPerPage(value);
    setPage(1); // 重置到第一页
  }, []);

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

  // 单元格渲染
  const renderCell = useCallback((position: TraderPosition, columnKey: TraderPositionColumnKey) => {
    const isLong = position.szi > 0;
    const pnl = position.unrealized_pnl || 0;
    const roe = position.return_on_equity || 0;

    switch (columnKey) {
      case 'star':
        return (
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
        );
      case 'trader':
        return (
          <a
            href={`/traders/${position.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-sm text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {position.trader_name || formatAddress(position.address)}
          </a>
        );
      case 'rating':
        return (
          <span className={`font-bold text-lg ${getRatingColor(position.rating)}`}>
            {position.rating || '-'}
          </span>
        );
      case 'coin':
        return <span className="font-semibold">{position.coin}</span>;
      case 'direction':
        return (
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
        );
      case 'size':
        return <span className="font-mono">{formatNumber(Math.abs(position.szi), 4)}</span>;
      case 'entry_px':
        return <span className="font-mono">${formatNumber(position.entry_px, 2)}</span>;
      case 'position_value':
        return <span className="font-mono font-medium">${formatNumber(position.position_value, 2)}</span>;
      case 'unrealized_pnl':
        return (
          <span className={`font-mono font-medium ${pnl >= 0 ? "text-success" : "text-danger"}`}>
            {pnl >= 0 ? "+" : ""}${formatNumber(pnl, 2)}
          </span>
        );
      case 'roe':
        return (
          <span className={`font-mono text-sm ${roe >= 0 ? "text-success" : "text-danger"}`}>
            {formatPercent(roe)}
          </span>
        );
      case 'leverage':
        return (
          <Chip size="sm" variant="bordered" className="font-mono">
            {position.leverage_value}x
          </Chip>
        );
      case 'open_time':
        return <span className="text-sm text-default-500">{formatTime(position.open_time)}</span>;
      case 'updated_at':
        return <span className="text-sm text-default-500">{formatTime(position.updated_at)}</span>;
      case 'actions':
        return (
          <div className="flex gap-1">
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
        );
      default:
        return null;
    }
  }, [starLoadingAddresses, onToggleStar, refreshingAddresses, onRefreshTrader, handleRefreshTrader]);

  // 底部分页内容
  const bottomContent = useMemo(() => {
    if (totalPages <= 1) return null;
    
    return (
      <TablePagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalCount={totalCount}
        rowsPerPage={rowsPerPage}
        rowsPerPageOptions={ROWS_PER_PAGE_OPTIONS}
        onRowsPerPageChange={handleRowsPerPageChange}
      />
    );
  }, [page, totalPages, totalCount, rowsPerPage, handleRowsPerPageChange]);

  return (
    <Table
      aria-label="Trader positions table"
      classNames={{
        wrapper: "bg-content1/50 backdrop-blur-md",
        th: "bg-content2/50",
      }}
      bottomContent={bottomContent}
      bottomContentPlacement="outside"
      sortDescriptor={sortDescriptor}
      onSortChange={onSortChange}
    >
      <TableHeader columns={headerColumns}>
        {(column) => (
          <TableColumn
            key={column.uid}
            allowsSorting={column.sortable}
            width={column.uid === 'star' ? 50 : column.uid === 'actions' ? 120 : undefined}
          >
            {column.name}
          </TableColumn>
        )}
      </TableHeader>
      <TableBody emptyContent="暂无持仓数据" isLoading={loading} loadingContent={<Spinner />}>
        {paginatedPositions.map((position) => (
          <TableRow key={`${position.address}-${position.coin}`}>
            {(columnKey) => (
              <TableCell>{renderCell(position, columnKey as TraderPositionColumnKey)}</TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
