import { useState, useMemo, useCallback } from "react";
import { Pagination, Input, Select, SelectItem } from "@heroui/react";

// 每页显示条数选项
const DEFAULT_ROWS_PER_PAGE_OPTIONS = [10, 20, 50, 100];

export interface TablePaginationProps {
  /** 当前页码 */
  page: number;
  /** 总页数 */
  totalPages: number;
  /** 页码变化回调 */
  onPageChange: (page: number) => void;
  /** 总记录数（用于显示记录数信息） */
  totalCount?: number;
  /** 每页显示条数 */
  rowsPerPage?: number;
  /** 每页显示条数选项 */
  rowsPerPageOptions?: number[];
  /** 每页条数变化回调（如果提供则显示每页条数选择器） */
  onRowsPerPageChange?: (rowsPerPage: number) => void;
  /** 是否显示跳转输入框，默认 true */
  showJumpInput?: boolean;
  /** 自定义类名 */
  className?: string;
}

export function TablePagination({
  page,
  totalPages,
  onPageChange,
  totalCount,
  rowsPerPage,
  rowsPerPageOptions = DEFAULT_ROWS_PER_PAGE_OPTIONS,
  onRowsPerPageChange,
  showJumpInput = true,
  className = "",
}: TablePaginationProps) {
  const [jumpPage, setJumpPage] = useState("");

  // 处理跳转页码
  const handleJumpPage = useCallback(() => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      onPageChange(pageNum);
      setJumpPage("");
    }
  }, [jumpPage, totalPages, onPageChange]);

  // 处理每页条数变化
  const handleRowsPerPageChange = useCallback(
    (value: string) => {
      if (onRowsPerPageChange) {
        onRowsPerPageChange(Number(value));
      }
    },
    [onRowsPerPageChange]
  );

  // 计算显示范围
  const displayRange = useMemo(() => {
    if (totalCount === undefined || rowsPerPage === undefined) return null;
    const start = Math.min((page - 1) * rowsPerPage + 1, totalCount);
    const end = Math.min(page * rowsPerPage, totalCount);
    return { start, end };
  }, [page, rowsPerPage, totalCount]);

  // 如果没有数据或只有一页且不需要显示记录数，则不渲染
  if (totalPages <= 0) return null;
  if (totalPages === 1 && !totalCount) return null;

  return (
    <div className={`flex flex-col sm:flex-row items-center justify-between gap-3 py-3 px-2 ${className}`}>
      {/* 左侧：记录数显示和每页条数选择 */}
      <div className="flex items-center gap-3">
        {displayRange && totalCount !== undefined && (
          <span className="text-sm text-default-500">
            显示 {displayRange.start} - {displayRange.end} 条，共 {totalCount} 条记录
          </span>
        )}
        {onRowsPerPageChange && rowsPerPage !== undefined && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-500">每页</span>
            <Select
              size="sm"
              className="w-20"
              selectedKeys={[String(rowsPerPage)]}
              onChange={(e) => handleRowsPerPageChange(e.target.value)}
              aria-label="每页显示条数"
            >
              {rowsPerPageOptions.map((option) => (
                <SelectItem key={String(option)} textValue={String(option)}>
                  {option}
                </SelectItem>
              ))}
            </Select>
            <span className="text-sm text-default-500">条</span>
          </div>
        )}
      </div>

      {/* 右侧：分页控件和跳转 */}
      {totalPages > 1 && (
        <div className="flex items-center gap-3">
          <Pagination
            isCompact
            showControls
            showShadow
            color="primary"
            page={page}
            total={totalPages}
            onChange={onPageChange}
          />
          {showJumpInput && (
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
                onKeyDown={(e) => e.key === "Enter" && handleJumpPage()}
              />
              <span className="text-sm text-default-500">页</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Hook for managing pagination state with local data
export interface UseLocalPaginationOptions {
  /** 默认每页条数 */
  defaultRowsPerPage?: number;
  /** 总数据条数（用于计算总页数） */
  totalItems: number;
}

export interface UseLocalPaginationReturn {
  page: number;
  setPage: (page: number) => void;
  rowsPerPage: number;
  setRowsPerPage: (rowsPerPage: number) => void;
  totalPages: number;
  /** 获取分页后的数据切片 */
  getPageItems: <T>(items: T[]) => T[];
  /** 当数据条数变化时重置页码（如果当前页超出范围） */
  resetPageIfNeeded: () => void;
}

export function useLocalPagination({
  defaultRowsPerPage = 20,
  totalItems,
}: UseLocalPaginationOptions): UseLocalPaginationReturn {
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPageState] = useState(defaultRowsPerPage);

  const totalPages = Math.ceil(totalItems / rowsPerPage);

  const setRowsPerPage = useCallback((value: number) => {
    setRowsPerPageState(value);
    setPage(1); // 重置到第一页
  }, []);

  const getPageItems = useCallback(
    <T,>(items: T[]): T[] => {
      const start = (page - 1) * rowsPerPage;
      const end = start + rowsPerPage;
      return items.slice(start, end);
    },
    [page, rowsPerPage]
  );

  const resetPageIfNeeded = useCallback(() => {
    if (page > totalPages && totalPages > 0) {
      setPage(1);
    }
  }, [page, totalPages]);

  return {
    page,
    setPage,
    rowsPerPage,
    setRowsPerPage,
    totalPages,
    getPageItems,
    resetPageIfNeeded,
  };
}

export default TablePagination;
