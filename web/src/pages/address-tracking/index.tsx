import { useState, useEffect, useCallback } from "react";
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
  Input,
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { addressTrackingApi, AddressTracking, PaginationInfo } from "@/services/api";
import { TablePagination } from "@/components/TablePagination";
import { TrackingFormModal, DeleteConfirmModal } from "./components";

// 监控事件标签
const eventLabels: Record<string, string> = {
  open: "开仓",
  close: "平仓",
  add: "加仓",
  reduce: "减仓",
};

// 监控事件颜色
const eventColors: Record<string, "success" | "danger" | "primary" | "warning"> = {
  open: "success",
  close: "danger",
  add: "primary",
  reduce: "warning",
};

export default function AddressTrackingPage() {
  // 数据状态
  const [trackings, setTrackings] = useState<AddressTracking[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [page, setPage] = useState(1);
  const [enabledFilter, setEnabledFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Modal 状态
  const [isFormModalOpen, setIsFormModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingTracking, setEditingTracking] = useState<AddressTracking | null>(null);

  // 加载数据
  const loadTrackings = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit: 20,
      };

      if (enabledFilter !== "all") params.is_enabled = enabledFilter === "enabled";
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const response = await addressTrackingApi.getTrackings(params);
      if (response.success && response.data) {
        setTrackings(response.data);
        if (response.pagination) {
          setPagination(response.pagination);
        }
      }
    } catch (error) {
      console.error("Failed to load trackings:", error);
      addToast({ title: "加载失败", description: "无法获取地址跟踪列表", color: "danger" });
    } finally {
      setLoading(false);
    }
  }, [page, enabledFilter, searchQuery]);

  useEffect(() => {
    loadTrackings();
  }, [loadTrackings]);

  // 打开添加弹窗
  const handleOpenAddModal = useCallback(() => {
    setEditingTracking(null);
    setIsFormModalOpen(true);
  }, []);

  // 打开编辑弹窗
  const handleOpenEditModal = useCallback((tracking: AddressTracking) => {
    setEditingTracking(tracking);
    setIsFormModalOpen(true);
  }, []);

  // 保存跟踪配置
  const handleSaveTracking = async (data: Partial<AddressTracking>) => {
    try {
      if (editingTracking) {
        await addressTrackingApi.updateTracking(editingTracking.id, data);
        addToast({ title: "更新成功", color: "success" });
      } else {
        const response = await addressTrackingApi.createTracking({
          tracking_address: data.tracking_address || "",
          address_remark: data.address_remark,
          is_enabled: data.is_enabled,
          enable_notification: data.enable_notification,
          monitor_events: data.monitor_events,
        });
        if (response.success) {
          addToast({ title: "添加成功", color: "success" });
        } else {
          throw new Error(response.error || "添加失败");
        }
      }
      setIsFormModalOpen(false);
      setEditingTracking(null);
      loadTrackings();
    } catch (error: any) {
      console.error("Failed to save tracking:", error);
      const errorMessage = error?.response?.data?.error || error?.message || "操作失败";
      addToast({ title: "保存失败", description: errorMessage, color: "danger" });
    }
  };

  // 打开删除确认弹窗
  const handleOpenDeleteModal = useCallback((id: string) => {
    setDeletingId(id);
    setIsDeleteModalOpen(true);
  }, []);

  // 确认删除
  const handleConfirmDelete = async () => {
    try {
      if (deletingId) {
        await addressTrackingApi.deleteTracking(deletingId);
        addToast({ title: "删除成功", color: "success" });
      }
      setIsDeleteModalOpen(false);
      setDeletingId(null);
      loadTrackings();
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
  const handleToggle = useCallback(async (id: string, isEnabled: boolean) => {
    // 乐观更新
    setTrackings((prev) =>
      prev.map((t) => (t.id === id ? { ...t, is_enabled: isEnabled } : t))
    );

    try {
      await addressTrackingApi.toggleTracking(id, isEnabled);
    } catch (error) {
      // 回滚
      setTrackings((prev) =>
        prev.map((t) => (t.id === id ? { ...t, is_enabled: !isEnabled } : t))
      );
      console.error("Failed to toggle tracking:", error);
      addToast({ title: "操作失败", color: "danger" });
    }
  }, []);

  // 处理通知开关
  const handleToggleNotification = useCallback(async (id: string, enableNotification: boolean) => {
    // 乐观更新
    setTrackings((prev) =>
      prev.map((t) => (t.id === id ? { ...t, enable_notification: enableNotification } : t))
    );

    try {
      await addressTrackingApi.toggleNotification(id, enableNotification);
    } catch (error) {
      // 回滚
      setTrackings((prev) =>
        prev.map((t) => (t.id === id ? { ...t, enable_notification: !enableNotification } : t))
      );
      console.error("Failed to toggle notification:", error);
      addToast({ title: "操作失败", color: "danger" });
    }
  }, []);

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
    { key: "address", label: "跟踪地址" },
    { key: "remark", label: "备注" },
    { key: "notification", label: "通知" },
    { key: "events", label: "监控事件" },
    { key: "created_at", label: "创建时间" },
    { key: "actions", label: "操作" },
  ];

  // 渲染单元格
  const renderCell = useCallback(
    (item: AddressTracking, columnKey: string) => {
      switch (columnKey) {
        case "enabled":
          return (
            <Switch
              size="sm"
              isSelected={item.is_enabled}
              onValueChange={(checked) => handleToggle(item.id, checked)}
            />
          );
        case "address":
          return (
            <a
              href={`/traders/${item.tracking_address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm text-primary hover:underline"
            >
              {formatAddress(item.tracking_address)}
            </a>
          );
        case "remark":
          return (
            <span className="text-sm">
              {item.address_remark || <span className="text-default-400">-</span>}
            </span>
          );
        case "notification":
          return (
            <Switch
              size="sm"
              isSelected={item.enable_notification}
              onValueChange={(checked) => handleToggleNotification(item.id, checked)}
            />
          );
        case "events":
          return (
            <div className="flex flex-wrap gap-1">
              {item.monitor_events.map((event) => (
                <Chip
                  key={event}
                  size="sm"
                  color={eventColors[event] || "default"}
                  variant="flat"
                >
                  {eventLabels[event] || event}
                </Chip>
              ))}
            </div>
          );
        case "created_at":
          return <span className="text-sm text-default-500">{formatTime(item.created_at)}</span>;
        case "actions":
          return (
            <div className="flex gap-1">
              <Tooltip content="编辑">
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  onPress={() => handleOpenEditModal(item)}
                >
                  <Icon icon="lucide:edit" width={16} />
                </Button>
              </Tooltip>
              <Tooltip content="删除">
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  color="danger"
                  onPress={() => handleOpenDeleteModal(item.id)}
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
    [handleToggle, handleToggleNotification, handleOpenEditModal, handleOpenDeleteModal]
  );

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-4">
        {/* 标题 */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">地址跟踪</h1>
          </div>
          <div className="flex gap-2">
            <Button
              color="primary"
              startContent={<Icon icon="lucide:plus" width={18} />}
              onPress={handleOpenAddModal}
            >
              添加跟踪
            </Button>
          </div>
        </div>

        {/* 筛选工具栏 */}
        <div className="flex flex-wrap gap-3 items-center">
          <Input
            className="w-64"
            size="sm"
            placeholder="搜索地址或备注..."
            value={searchQuery}
            onValueChange={setSearchQuery}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setPage(1);
                loadTrackings();
              }
            }}
            startContent={<Icon icon="lucide:search" width={16} className="text-default-400" />}
            isClearable
            onClear={() => {
              setSearchQuery("");
              setPage(1);
            }}
          />
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm whitespace-nowrap">状态</span>
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
            <Table aria-label="地址跟踪列表">
              <TableHeader columns={columns}>
                {(column) => (
                  <TableColumn key={column.key}>
                    {column.label}
                  </TableColumn>
                )}
              </TableHeader>
              <TableBody items={trackings} emptyContent="暂无地址跟踪记录">
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
