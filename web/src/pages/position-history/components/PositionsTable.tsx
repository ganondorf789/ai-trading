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
} from "@heroui/react";
import type { Selection, SortDescriptor } from "@heroui/react";
import { Icon } from "@iconify/react";
import { GlobalPositionHistoryRecord } from "@/services/api";
import { getRatingColor } from "@/utils";
import { positionHistoryColumns, PositionHistoryColumnKey } from "./PositionFilters";
import { TablePagination } from "@/components/TablePagination";

// 每页显示条数选项
const ROWS_PER_PAGE_OPTIONS = [10, 20, 50, 100];
const DEFAULT_ROWS_PER_PAGE = 20;

interface PositionsTableProps {
  positions: GlobalPositionHistoryRecord[];
  loading: boolean;
  visibleColumns: Selection;
  sortDescriptor: SortDescriptor;
  onSortChange: (descriptor: SortDescriptor) => void;
}

export function PositionsTable({ positions, loading, visibleColumns, sortDescriptor, onSortChange }: PositionsTableProps) {
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
    if (visibleColumns === 'all') return positionHistoryColumns;
    return positionHistoryColumns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  // 排序后的数据
  const sortedPositions = useMemo(() => {
    if (!sortDescriptor.column) return positions;

    return [...positions].sort((a, b) => {
      const column = sortDescriptor.column as PositionHistoryColumnKey;
      let first: any;
      let second: any;

      switch (column) {
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
          first = a.direction;
          second = b.direction;
          break;
        case 'open_time':
          first = a.open_time ? new Date(a.open_time).getTime() : 0;
          second = b.open_time ? new Date(b.open_time).getTime() : 0;
          break;
        case 'close_time':
          first = a.close_time ? new Date(a.close_time).getTime() : 0;
          second = b.close_time ? new Date(b.close_time).getTime() : 0;
          break;
        case 'max_size':
          first = a.max_size || 0;
          second = b.max_size || 0;
          break;
        case 'avg_entry_price':
          first = a.avg_entry_price || 0;
          second = b.avg_entry_price || 0;
          break;
        case 'avg_close_price':
          first = a.avg_close_price || 0;
          second = b.avg_close_price || 0;
          break;
        case 'position_value':
          first = a.position_value || 0;
          second = b.position_value || 0;
          break;
        case 'holding_hours':
          first = a.holding_hours || 0;
          second = b.holding_hours || 0;
          break;
        case 'realized_pnl':
          first = a.realized_pnl || 0;
          second = b.realized_pnl || 0;
          break;
        case 'status':
          first = a.status;
          second = b.status;
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
    setPage(1);
  }, []);

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

  // 单元格渲染
  const renderCell = useCallback((position: GlobalPositionHistoryRecord, columnKey: PositionHistoryColumnKey) => {
    const isLong = position.direction === 'long';
    const pnl = position.realized_pnl || 0;

    switch (columnKey) {
      case 'trader':
        return (
          <div className="flex items-center gap-2">
            {position.is_starred && (
              <Icon icon="solar:star-bold" className="text-warning" width={14} />
            )}
            <a
              href={`/traders/${position.address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {position.trader_name || formatAddress(position.address)}
            </a>
          </div>
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
      case 'open_time':
        return <span className="text-sm">{formatTime(position.open_time)}</span>;
      case 'close_time':
        return <span className="text-sm">{formatTime(position.close_time)}</span>;
      case 'max_size':
        return <span className="font-mono">{formatNumber(position.max_size, 4)}</span>;
      case 'avg_entry_price':
        return <span className="font-mono">${formatNumber(position.avg_entry_price, 4)}</span>;
      case 'avg_close_price':
        return (
          <span className="font-mono">
            {position.avg_close_price ? `$${formatNumber(position.avg_close_price, 4)}` : '-'}
          </span>
        );
      case 'position_value':
        return <span className="font-mono font-medium">${formatNumber(position.position_value, 2)}</span>;
      case 'holding_hours':
        return <span className="text-sm">{formatHours(position.holding_hours)}</span>;
      case 'realized_pnl':
        return (
          <span className={`font-mono font-medium ${pnl >= 0 ? "text-success" : "text-danger"}`}>
            {pnl >= 0 ? "+" : ""}${formatNumber(pnl, 2)}
          </span>
        );
      case 'status':
        return (
          <Chip
            size="sm"
            color={position.status === 'open' ? 'warning' : 'default'}
            variant="flat"
          >
            {position.status === 'open' ? '持仓中' : '已平仓'}
          </Chip>
        );
      default:
        return null;
    }
  }, []);

  // 底部分页内容
  const bottomContent = useMemo(() => {
    if (totalCount === 0) return null;
    
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
      aria-label="Position history table"
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
          <TableColumn key={column.uid} allowsSorting={column.sortable}>
            {column.name}
          </TableColumn>
        )}
      </TableHeader>
      <TableBody emptyContent="暂无仓位历史数据" isLoading={loading} loadingContent={<Spinner />}>
        {paginatedPositions.map((position) => (
          <TableRow key={position.id}>
            {(columnKey) => (
              <TableCell>{renderCell(position, columnKey as PositionHistoryColumnKey)}</TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
