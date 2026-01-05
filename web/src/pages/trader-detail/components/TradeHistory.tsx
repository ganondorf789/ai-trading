import { useState, useMemo, useCallback } from 'react';
import type { Selection, SortDescriptor, DateValue, RangeValue } from '@heroui/react';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Button } from '@heroui/button';
import { Spinner } from '@heroui/spinner';
import { Pagination } from '@heroui/pagination';
import { Input } from '@heroui/input';
import { DateRangePicker } from '@heroui/react';
import {
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
} from '@heroui/dropdown';
import { Select, SelectItem } from '@heroui/select';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Icon } from '@iconify/react';
import { TraderFill, FillsStats } from '@/services/api';

// 表格列配置
type ColumnKey = 'trade_time' | 'coin' | 'side' | 'trade_type' | 'px' | 'sz' | 'start_position' | 'value' | 'closed_pnl' | 'roi' | 'fee';

interface Column {
  uid: ColumnKey;
  name: string;
  sortable?: boolean;
}

const columns: Column[] = [
  { uid: 'trade_time', name: '时间', sortable: true },
  { uid: 'coin', name: '币种', sortable: true },
  { uid: 'side', name: '方向', sortable: true },
  { uid: 'trade_type', name: '类型', sortable: true },
  { uid: 'px', name: '价格', sortable: true },
  { uid: 'sz', name: '数量', sortable: true },
  { uid: 'start_position', name: '开始仓位', sortable: true },
  { uid: 'value', name: '价值', sortable: true },
  { uid: 'closed_pnl', name: '盈亏', sortable: true },
  { uid: 'roi', name: 'ROI', sortable: true },
  { uid: 'fee', name: '手续费', sortable: true },
];

const INITIAL_VISIBLE_COLUMNS: ColumnKey[] = ['trade_time', 'coin', 'side', 'trade_type', 'px', 'sz', 'start_position', 'value', 'closed_pnl', 'roi', 'fee'];

interface TradeHistoryProps {
  fills: TraderFill[];
  fillsStats: FillsStats | null;
  fillsLoading: boolean;
  totalCount: number;
  totalPages: number;
  page: number;
  rowsPerPage: number;
  coins: string[];
  selectedCoin: string;
  pnlFilter: 'all' | 'profit' | 'loss';
  tradeTypeFilter: string;
  dateRange: RangeValue<DateValue> | null;
  sortDescriptor: SortDescriptor;
  onPageChange: (page: number) => void;
  onCoinChange: (coin: string) => void;
  onPnlFilterChange: (filter: 'all' | 'profit' | 'loss') => void;
  onTradeTypeFilterChange: (type: string) => void;
  onDateRangeChange: (range: RangeValue<DateValue> | null) => void;
  onSortChange: (descriptor: SortDescriptor) => void;
  onReset: () => void;
}

export function TradeHistory({
  fills,
  fillsStats,
  fillsLoading,
  totalCount,
  totalPages,
  page,
  rowsPerPage,
  coins,
  selectedCoin,
  pnlFilter,
  tradeTypeFilter,
  dateRange,
  sortDescriptor,
  onPageChange,
  onCoinChange,
  onPnlFilterChange,
  onTradeTypeFilterChange,
  onDateRangeChange,
  onSortChange,
  onReset,
}: TradeHistoryProps) {
  const [searchValue, setSearchValue] = useState('');
  const [visibleColumns, setVisibleColumns] = useState<Selection>(new Set(INITIAL_VISIBLE_COLUMNS));
  const [jumpPage, setJumpPage] = useState('');

  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const calculateROI = (fill: TraderFill) => {
    const tradeValue = fill.px * fill.sz;
    if (tradeValue === 0) return 0;
    return (fill.closed_pnl / tradeValue) * 100;
  };

  // 可见列
  const headerColumns = useMemo(() => {
    if (visibleColumns === 'all') return columns;
    return columns.filter((column) => Array.from(visibleColumns).includes(column.uid));
  }, [visibleColumns]);

  // 本地搜索过滤（排序已由 API 完成）
  const filteredItems = useMemo(() => {
    if (!searchValue) {
      return fills;
    }
    return fills.filter((fill) =>
      fill.coin.toLowerCase().includes(searchValue.toLowerCase())
    );
  }, [fills, searchValue]);

  // 单元格渲染
  const renderCell = useCallback((fill: TraderFill, columnKey: ColumnKey) => {
    switch (columnKey) {
      case 'trade_time':
        return (
          <div className="flex flex-col">
            <span className="text-xs">{new Date(fill.trade_time).toLocaleDateString()}</span>
            <span className="text-xs text-gray-500">{new Date(fill.trade_time).toLocaleTimeString()}</span>
          </div>
        );
      case 'coin':
        return <span className="font-bold">{fill.coin}</span>;
      case 'side':
        return (
          <Chip
            size="sm"
            color={fill.side === 'B' ? 'success' : 'danger'}
            variant="flat"
          >
            {fill.side === 'B' ? 'BUY' : 'SELL'}
          </Chip>
        );
      case 'trade_type':
        const tradeTypeMap: Record<string, { label: string; color: 'success' | 'danger' | 'warning' | 'default' }> = {
          'open_long': { label: '开多', color: 'success' },
          'add_long': { label: '加多', color: 'success' },
          'close_long': { label: '平多', color: 'warning' },
          'open_short': { label: '开空', color: 'danger' },
          'add_short': { label: '加空', color: 'danger' },
          'close_short': { label: '平空', color: 'warning' },
        };
        const typeInfo = fill.trade_type ? tradeTypeMap[fill.trade_type] : null;

        return (
          <Chip
            size="sm"
            color={typeInfo?.color || 'default'}
            variant="flat"
          >
            {typeInfo?.label || '-'}
          </Chip>
        );
      case 'px':
        return <span>${formatNumber(fill.px, 4)}</span>;
      case 'sz':
        return <span>{formatNumber(fill.sz, 4)}</span>;
      case 'start_position':
        return <span>{fill.start_position != null ? formatNumber(fill.start_position, 4) : '-'}</span>;
      case 'value':
        return <span>${formatNumber(fill.px * fill.sz, 2)}</span>;
      case 'closed_pnl':
        return (
          <span className={fill.closed_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
            ${formatNumber(fill.closed_pnl)}
          </span>
        );
      case 'roi':
        const roi = calculateROI(fill);
        return (
          <span className={`font-bold ${roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>
            {roi.toFixed(2)}%
          </span>
        );
      case 'fee':
        return <span className="text-orange-500">${formatNumber(fill.fee, 4)}</span>;
      default:
        return null;
    }
  }, []);

  // 搜索变化处理
  const onSearchChange = useCallback((value?: string) => {
    setSearchValue(value || '');
    onPageChange(1);
  }, [onPageChange]);

  // 获取当前筛选状态文本
  const getActiveFiltersCount = useCallback(() => {
    let count = 0;
    if (selectedCoin !== 'all') count++;
    if (pnlFilter !== 'all') count++;
    if (tradeTypeFilter !== 'all') count++;
    if (searchValue) count++;
    if (dateRange) count++;
    return count;
  }, [selectedCoin, pnlFilter, tradeTypeFilter, searchValue, dateRange]);

  // 页码跳转
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      onPageChange(pageNum);
      setJumpPage('');
    }
  };

  // 表格顶部内容
  const topContent = useMemo(() => {
    const activeFilters = getActiveFiltersCount();

    return (
      <div className="flex flex-col gap-4">
        {/* 统计信息 */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 p-4 bg-default-100 rounded-lg">
          <div>
            <p className="text-xs text-default-500">总交易</p>
            <p className="text-lg font-bold text-default-800">{fillsStats?.total ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">盈利笔数</p>
            <p className="text-lg font-bold text-success">{fillsStats?.profitable ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">亏损笔数</p>
            <p className="text-lg font-bold text-danger">{fillsStats?.losing ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-default-500">胜率</p>
            <p className="text-lg font-bold text-default-800">{(fillsStats?.win_rate ?? 0).toFixed(2)}%</p>
          </div>
          <div>
            <p className="text-xs text-default-500">总盈亏</p>
            <p className={`text-lg font-bold ${(fillsStats?.total_pnl ?? 0) >= 0 ? 'text-success' : 'text-danger'}`}>
              ${formatNumber(fillsStats?.total_pnl ?? 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-default-500">总手续费</p>
            <p className="text-lg font-bold text-warning">${formatNumber(fillsStats?.total_fees ?? 0)}</p>
          </div>
        </div>

        {/* 筛选工具栏 */}
        <div className="flex items-center justify-between gap-4 px-[6px] py-[4px]">
          {/* 左侧：筛选条件 */}
          <div className="flex items-center gap-4 overflow-auto">
            {/* 币种筛选 */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm whitespace-nowrap">币种</span>
              <Select
                className="min-w-[160px]"
                size="sm"
                selectedKeys={[selectedCoin]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  onCoinChange(selected || 'all');
                }}
                popoverProps={{
                  classNames: {
                    content: "max-h-60 overflow-y-auto"
                  }
                }}
              >
                {coins.map((coin) => (
                  <SelectItem key={coin}>{coin === 'all' ? '全部' : coin}</SelectItem>
                ))}
              </Select>
            </div>

            {/* 盈亏筛选 */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm whitespace-nowrap">盈亏</span>
              <Select
                className="min-w-[100px]"
                size="sm"
                selectedKeys={[pnlFilter]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  onPnlFilterChange((selected || 'all') as 'all' | 'profit' | 'loss');
                }}
              >
                <SelectItem key="all">全部</SelectItem>
                <SelectItem key="profit">盈利</SelectItem>
                <SelectItem key="loss">亏损</SelectItem>
              </Select>
            </div>

            {/* 类型筛选 */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm whitespace-nowrap">类型</span>
              <Select
                className="min-w-[100px]"
                size="sm"
                selectedKeys={[tradeTypeFilter]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  onTradeTypeFilterChange(selected || 'all');
                }}
              >
                <SelectItem key="all">全部</SelectItem>
                <SelectItem key="open_long">开多</SelectItem>
                <SelectItem key="add_long">加多</SelectItem>
                <SelectItem key="close_long">平多</SelectItem>
                <SelectItem key="open_short">开空</SelectItem>
                <SelectItem key="add_short">加空</SelectItem>
                <SelectItem key="close_short">平空</SelectItem>
              </Select>
            </div>

            {/* Date Range Picker */}
            <div className="flex items-center gap-2 whitespace-nowrap shrink-0">
              <span className="text-sm">日期范围</span>
              <DateRangePicker
                className="w-auto"
                value={dateRange}
                onChange={onDateRangeChange}
                visibleMonths={2}
              />
            </div>

            {activeFilters > 0 && (
              <Button
                className="bg-default-100 text-default-800 shrink-0"
                size="sm"
                variant="flat"
                onPress={onReset}
                startContent={
                  <Icon className="text-default-400" icon="solar:restart-linear" width={16} />
                }
              >
                重置
              </Button>
            )}
          </div>

          {/* 右侧：排序和列 */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Sort 下拉 */}
            <Dropdown>
              <DropdownTrigger>
                <Button
                  className="bg-default-100 text-default-800"
                  size="sm"
                  startContent={
                    <Icon className="text-default-400" icon="solar:sort-linear" width={16} />
                  }
                >
                  排序
                </Button>
              </DropdownTrigger>
              <DropdownMenu
                aria-label="Sort"
                items={columns.filter((c) => c.sortable)}
              >
                {(item) => (
                  <DropdownItem
                    key={item.uid}
                    onPress={() => {
                      onSortChange({
                        column: item.uid,
                        direction:
                          sortDescriptor.direction === 'ascending' ? 'descending' : 'ascending',
                      });
                    }}
                  >
                    {item.name}
                  </DropdownItem>
                )}
              </DropdownMenu>
            </Dropdown>

            {/* Columns 下拉 */}
            <Dropdown closeOnSelect={false}>
              <DropdownTrigger>
                <Button
                  className="bg-default-100 text-default-800"
                  size="sm"
                  startContent={
                    <Icon
                      className="text-default-400"
                      icon="solar:sort-horizontal-linear"
                      width={16}
                    />
                  }
                >
                  列
                </Button>
              </DropdownTrigger>
              <DropdownMenu
                disallowEmptySelection
                aria-label="Columns"
                items={columns}
                selectedKeys={visibleColumns}
                selectionMode="multiple"
                onSelectionChange={setVisibleColumns}
              >
                {(item) => <DropdownItem key={item.uid}>{item.name}</DropdownItem>}
              </DropdownMenu>
            </Dropdown>
          </div>
        </div>
      </div>
    );
  }, [fillsStats, selectedCoin, pnlFilter, tradeTypeFilter, dateRange, coins, sortDescriptor, visibleColumns, onCoinChange, onPnlFilterChange, onTradeTypeFilterChange, onDateRangeChange, onSortChange, onReset, getActiveFiltersCount]);

  // 表格底部内容
  const bottomContent = useMemo(() => {
    return (
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2">
        <span className="text-sm text-gray-500">
          显示 {Math.min((page - 1) * rowsPerPage + 1, totalCount)} - {Math.min(page * rowsPerPage, totalCount)} 条，共 {totalCount} 条记录
        </span>
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
          <div className="flex items-center gap-1">
            <span className="text-sm text-gray-500">跳转</span>
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
            <span className="text-sm text-gray-500">页</span>
          </div>
        </div>
      </div>
    );
  }, [page, totalPages, totalCount, rowsPerPage, jumpPage, onPageChange]);

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold">历史交易记录</h2>
            <Chip size="sm" variant="flat" className="text-default-500">
              {totalCount}
            </Chip>
          </div>
        </div>
      </CardHeader>
      <CardBody>
        {fillsLoading ? (
          <div className="flex justify-center items-center h-64">
            <Spinner size="lg" />
          </div>
        ) : (
          <Table
            isHeaderSticky
            aria-label="Trade history table"
            topContent={topContent}
            topContentPlacement="outside"
            bottomContent={bottomContent}
            bottomContentPlacement="outside"
            sortDescriptor={sortDescriptor}
            onSortChange={onSortChange}
            classNames={{
              wrapper: 'max-h-[600px]',
            }}
          >
            <TableHeader columns={headerColumns}>
              {(column) => (
                <TableColumn
                  key={column.uid}
                  allowsSorting={column.sortable}
                >
                  {column.name}
                </TableColumn>
              )}
            </TableHeader>
            <TableBody
              items={filteredItems}
              emptyContent="暂无交易记录"
            >
              {(item) => (
                <TableRow key={item.id}>
                  {(columnKey) => (
                    <TableCell>{renderCell(item, columnKey as ColumnKey)}</TableCell>
                  )}
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </CardBody>
    </Card>
  );
}
