import { useState, useEffect, useCallback, useMemo } from "react";
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
  Select,
  SelectItem,
  Switch,
  Tooltip,
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { positionTrackingApi, PositionTracking, PositionTrackingStats, PaginationInfo } from "@/services/api";
import { TablePagination } from "@/components/TablePagination";
import TrackingFormModal from "./components/TrackingFormModal";
import DeleteConfirmModal from "./components/DeleteConfirmModal";
import StatsCards from "./components/StatsCards";

// 状态颜色映射
const statusColors: Record<string, "success" | "primary" | "warning" | "danger" | "default"> = {
  pending: "warning",
  active: "success",
  closed: "primary",
  stopped: "danger",
};

const statusLabels: Record<string, string> = {
  pending: "等待开仓",
  active: "跟单中",
  closed: "已平仓",
  stopped: "已停止",
};

export default function PositionTrackingPage() {
  // 数据状态
  const [trackings, setTrackings] = useState<PositionTracking[]>([]);
  const [stats, setStats] = useState<PositionTrackingStats | null>(null);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [enabledFilter, setEnabledFilter] = useState<string>("all");

  // Modal 状态
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingTracking, setEditingTracking] = useState<PositionTracking | null>(null);

  // 加载数据
  const loadTrackings = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit: 20,
      };

      if (statusFilter !== "all") params.status = statusFilter;
      if (enabledFilter !== "all") params.is_enabled = enabledFilter === "enabled";

      const response = await positionTrackingApi.getTrackings(params);
      if (response.success && response.data) {
        setTrackings(response.data);
        if (response.pagination) {
          setPagination(response.pagination);
        }
      }
    } catch (error) {
      console.error("Failed to load trackings:", error);
      addToast({ title: "加载失败", description: "无法获取仓位跟单列表", color: "danger" });
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, enabledFilter]);

  const loadStats = useCallback(async () => {
    try {
      const response = await positionTrackingApi.getStats();
      if (response.success && response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  }, []);

  useEffect(() => {
    loadTrackings();
  }, [loadTrackings]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // 打开编辑弹窗
  const handleOpenEditModal = useCallback((tracking: PositionTracking) => {
    setEditingTracking(tracking);
    setIsFormModalOpen(true);
  }, []);

  // 保存跟单配置
  const handleSaveTracking = async (data: Partial<PositionTracking>) => {
    try {
      if (editingTracking) {
        await positionTrackingApi.updateTracking(editingTracking.id, data);
        addToast({ title: "更新成功", color: "success" });
      }
      setIsFormModalOpen(false);
      setEditingTracking(null);
      loadTrackings();
      loadStats();
    } catch (error) {
      console.error("Failed to save tracking:", error);
      addToast({ title: "保存失败", color: "danger" });
    }
  };

  // 打开删除确认弹窗
  const handleOpenDeleteModal = useCallback((id: number) => {
    setDeletingId(id);
    setIsDeleteModalOpen(true);
  }, []);

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingId) return;
    try {
      await positionTrackingApi.deleteTracking(deletingId);
      addToast({ title: "删除成功", color: "success" });
      setIsDeleteModalOpen(false);
      setDeletingId(null);
      loadTrackings();
      loadStats();
    } catch (error: any) {
      console.error("Failed to delete tracking:", error);
      addToast({
        title: "删除失败",
        description: error?.response?.data?.error || "操作失败",
        color: "danger"
      });
    }
  };

  // 处理启用/禁用
  const handleToggle = useCallback(async (id: number, isEnabled: boolean) => {
    // 乐观更新
    setTrackings((prev) =>
      prev.map((t) => (t.id === id ? { ...t, is_enabled: isEnabled } : t))
    );

    try {
      await positionTrackingApi.toggleTracking(id, isEnabled);
    } catch (error) {
      // 回滚
      setTrackings((prev) =>
        prev.map((t) => (t.id === id ? { ...t, is_enabled: !isEnabled } : t))
      );
      console.error("Failed to toggle tracking:", error);
      addToast({ title: "操作失败", color: "danger" });
    }
  }, []);

  // 处理停止跟单
  const handleStop = useCallback(async (id: number) => {
    try {
      await positionTrackingApi.stopTracking(id);
      addToast({ title: "已停止跟单", color: "success" });
      loadTrackings();
      loadStats();
    } catch (error: any) {
      console.error("Failed to stop tracking:", error);
      addToast({
        title: "停止失败",
        description: error?.response?.data?.error || "操作失败",
        color: "danger"
      });
    }
  }, [loadTrackings, loadStats]);

  // 格式化地址
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 格式化时间
  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return "-";
    return new Date(timeStr).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // 表格列
  const columns = [
    { key: "enabled", label: "启用" },
    { key: "status", label: "状态" },
    { key: "target", label: "目标交易员" },
    { key: "symbol", label: "币种" },
    { key: "copy_ratio", label: "跟单比例" },
    { key: "position_size", label: "仓位范围" },
    { key: "leverage", label: "杠杆" },
    { key: "target_position", label: "目标仓位" },
    { key: "my_position", label: "我方仓位" },
    { key: "pnl", label: "盈亏" },
    { key: "created_at", label: "创建时间" },
    { key: "actions", label: "操作" },
  ];

  // 渲染单元格
  const renderCell = useCallback(
    (item: PositionTracking, columnKey: string) => {
      switch (columnKey) {
        case "enabled":
          return (
            <Switch
              size="sm"
              isSelected={item.is_enabled}
              isDisabled={item.status === "closed" || item.status === "stopped"}
              onChange={(e) => handleToggle(item.id, e.target.checked)}
            />
          );
        case "status":
          return (
            <Chip size="sm" color={statusColors[item.status] || "default"} variant="flat">
              {statusLabels[item.status] || item.status}
            </Chip>
          );
        case "target":
          return (
            <div className="flex flex-col">
              <a
                href={`/traders/${item.target_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-sm text-primary hover:underline"
              >
                {item.target_name || formatAddress(item.target_address)}
              </a>
              {item.target_name && (
                <span className="text-xs text-default-400 font-mono">
                  {formatAddress(item.target_address)}
                </span>
              )}
            </div>
          );
        case "symbol":
          return <span className="font-semibold">{item.symbol}</span>;
        case "copy_ratio":
          return `${(item.copy_ratio * 100).toFixed(0)}%`;
        case "position_size":
          return (
            <span className="text-sm">
              ${item.min_position_size_usd} - ${item.max_position_size_usd}
            </span>
          );
        case "leverage":
          return item.copy_leverage ? (
            <span>复制 (≤{item.max_leverage}x)</span>
          ) : (
            <span>{item.default_leverage}x</span>
          );
        case "target_position":
          if (!item.target_initial_size) return "-";
          return (
            <div className="flex flex-col">
              <span className={item.target_initial_side === "long" ? "text-success" : "text-danger"}>
                {item.target_initial_side?.toUpperCase()} {item.target_initial_size?.toFixed(4)}
              </span>
              {item.target_initial_entry_price && (
                <span className="text-xs text-default-400">
                  @ ${item.target_initial_entry_price.toFixed(2)}
                </span>
              )}
            </div>
          );
        case "my_position":
          if (!item.my_size || item.my_size === 0) return "-";
          return (
            <div className="flex flex-col">
              <span className={item.my_side === "long" ? "text-success" : "text-danger"}>
                {item.my_side?.toUpperCase()} {item.my_size?.toFixed(4)}
              </span>
              {item.my_entry_price && (
                <span className="text-xs text-default-400">
                  @ ${item.my_entry_price.toFixed(2)}
                </span>
              )}
            </div>
          );
        case "pnl":
          if (item.status !== "closed" || item.closed_pnl === null) return "-";
          return (
            <span className={item.closed_pnl >= 0 ? "text-success" : "text-danger"}>
              {item.closed_pnl >= 0 ? "+" : ""}${item.closed_pnl.toFixed(2)}
            </span>
          );
        case "created_at":
          return <span className="text-sm text-default-500">{formatTime(item.created_at)}</span>;
        case "actions":
          return (
            <div className="flex gap-1">
              <Tooltip content="编辑配置">
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  onPress={() => handleOpenEditModal(item)}
                  isDisabled={item.status === "closed" || item.status === "stopped"}
                >
                  <Icon icon="lucide:edit" width={16} />
                </Button>
              </Tooltip>
              {(item.status === "pending" || item.status === "active") && (
                <Tooltip content="停止跟单">
                  <Button
                    isIconOnly
                    size="sm"
                    variant="light"
                    color="warning"
                    onPress={() => handleStop(item.id)}
                  >
                    <Icon icon="lucide:stop-circle" width={16} />
                  </Button>
                </Tooltip>
              )}
              <Tooltip content="删除">
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  color="danger"
                  onPress={() => handleOpenDeleteModal(item.id)}
                  isDisabled={item.status === "active"}
                >
                  <Icon icon="lucide:trash-2" width={16} />
                </Button>
              </Tooltip>
            </div>
          );
        default:
          return null;
      }
    },
    [handleToggle, handleOpenEditModal, handleStop, handleOpenDeleteModal]
  );

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-4">
        {/* 标题 */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">仓位跟单管理</h1>
            <p className="text-default-500 text-sm mt-1">
              第二种跟单模式：跟单特定交易员的特定仓位
            </p>
          </div>
          <Button
            color="primary"
            variant="flat"
            startContent={<Icon icon="lucide:refresh-cw" width={18} />}
            onPress={() => {
              loadTrackings();
              loadStats();
            }}
          >
            刷新
          </Button>
        </div>

        {/* 统计卡片 */}
        {stats && <StatsCards stats={stats} />}

        {/* 筛选工具栏 */}
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">状态</span>
            <Select
              className="min-w-[120px]"
              size="sm"
              selectedKeys={[statusFilter]}
              onSelectionChange={(keys) => {
                const value = Array.from(keys)[0] as string;
                setStatusFilter(value);
                setPage(1);
              }}
            >
              <SelectItem key="all">全部</SelectItem>
              <SelectItem key="pending">等待开仓</SelectItem>
              <SelectItem key="active">跟单中</SelectItem>
              <SelectItem key="closed">已平仓</SelectItem>
              <SelectItem key="stopped">已停止</SelectItem>
            </Select>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">启用状态</span>
            <Select
              className="min-w-[100px]"
              size="sm"
              selectedKeys={[enabledFilter]}
              onSelectionChange={(keys) => {
                const value = Array.from(keys)[0] as string;
                setEnabledFilter(value);
                setPage(1);
              }}
            >
              <SelectItem key="all">全部</SelectItem>
              <SelectItem key="enabled">已启用</SelectItem>
              <SelectItem key="disabled">已禁用</SelectItem>
            </Select>
          </div>
        </div>

        {/* 数据表格 */}
        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner size="lg" />
          </div>
        ) : (
          <>
            <Table aria-label="仓位跟单列表">
              <TableHeader columns={columns}>
                {(column) => (
                  <TableColumn key={column.key}>{column.label}</TableColumn>
                )}
              </TableHeader>
              <TableBody items={trackings} emptyContent="暂无仓位跟单记录">
                {(item) => (
                  <TableRow key={item.id}>
                    {(columnKey) => <TableCell>{renderCell(item, columnKey as string)}</TableCell>}
                  </TableRow>
                )}
              </TableBody>
            </Table>

            {/* 分页 */}
            {pagination && pagination.total_pages > 0 && (
              <TablePagination
                page={page}
                totalPages={pagination.total_pages}
                onPageChange={setPage}
                totalCount={pagination.total_count}
                rowsPerPage={20}
                className="mt-4"
              />
            )}
          </>
        )}

        {/* Modals */}
        <TrackingFormModal
          isOpen={isFormModalOpen}
          onClose={() => {
            setIsFormModalOpen(false);
            setEditingTracking(null);
          }}
          tracking={editingTracking}
          onSave={handleSaveTracking}
        />

        <DeleteConfirmModal
          isOpen={isDeleteModalOpen}
          onClose={() => {
            setIsDeleteModalOpen(false);
            setDeletingId(null);
          }}
          onConfirm={handleConfirmDelete}
          tracking={trackings.find((t) => t.id === deletingId) || null}
        />
      </div>
    </DefaultLayout>
  );
}