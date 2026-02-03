import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Input,
  Button,
  Chip,
  Spinner,
  Select,
  SelectItem,
  Switch,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Tooltip,
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { copyTradingApi, hyperliquidApi, CopyTradingAddress, PaginationInfo } from "@/services/api";
import { TablePagination } from "@/components/TablePagination";
import AddressFormModal from "./components/AddressFormModal";
import DeleteConfirmModal from "./components/DeleteConfirmModal";
import BatchDeleteConfirmModal from "./components/BatchDeleteConfirmModal";

// 评级颜色映射
const ratingColors: Record<string, "success" | "primary" | "secondary" | "warning" | "danger" | "default"> = {
  S: "success",
  A: "primary",
  B: "secondary",
  C: "warning",
  D: "danger",
  F: "default",
};

export default function CopyTradingPage() {
  const navigate = useNavigate();

  // 数据状态
  const [addresses, setAddresses] = useState<CopyTradingAddress[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortBy] = useState("updated_at");
  const [sortOrder] = useState<"asc" | "desc">("desc");

  // 选择状态 - HeroUI Selection 可以是 "all" 或 Set<Key>
  const [selectedKeys, setSelectedKeys] = useState<"all" | Set<string>>(new Set());

  // Modal 状态
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingAddress, setDeletingAddress] = useState<string | null>(null);
  const [editingAddress, setEditingAddress] = useState<CopyTradingAddress | null>(null);

  // 表单状态
  const [formData, setFormData] = useState<Partial<CopyTradingAddress>>({
    address: "",
    name: "",
    is_enabled: true,
    copy_ratio: 0.1,
    max_position_size_usd: 500,
    min_position_size_usd: 20,
    copy_leverage: true,
    max_leverage: 10,
    default_leverage: 5,
    max_total_positions: 10,
    max_daily_trades: 50,
    slippage: 0.01,
    symbols_whitelist: [],
    symbols_blacklist: [],
    check_interval: 10,
    dry_run: true,
    auto_replenish: false,
    replenish_ratio: 0.5,
    replenish_min_value_usd: 10,
    replenish_max_value_usd: 100,
  });


  // 可用币种列表
  const [availableCoins, setAvailableCoins] = useState<string[]>([]);
  const [coinsLoading, setCoinsLoading] = useState(false);

  // 批量删除确认状态
  const [isBatchDeleteModalOpen, setIsBatchDeleteModalOpen] = useState(false);

  // 加载可用币种
  const loadAvailableCoins = useCallback(async () => {
    try {
      const response = await hyperliquidApi.getCoinNames();
      if (response.success && response.data) {
        setAvailableCoins(response.data);
      }
    } catch (error) {
      console.error("Failed to load coins:", error);
    }
  }, []);

  // 同步币种
  const handleSyncCoins = async () => {
    setCoinsLoading(true);
    try {
      const response = await hyperliquidApi.syncCoins();
      if (response.success) {
        addToast({ title: response.message || "同步成功", color: "success" });
        await loadAvailableCoins();
      }
    } catch (error) {
      console.error("Failed to sync coins:", error);
      addToast({ title: "同步失败", color: "danger" });
    } finally {
      setCoinsLoading(false);
    }
  };

  // 加载数据
  const loadAddresses = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        limit: 10,
        sort_by: sortBy,
        sort_order: sortOrder,
      };

      if (search) params.search = search;
      if (statusFilter) params.is_enabled = statusFilter === "enabled";

      const response = await copyTradingApi.getAddresses(params);
      if (response.success && response.data) {
        setAddresses(response.data);
        if (response.pagination) {
          setPagination(response.pagination);
        }
      }
    } catch (error) {
      console.error("Failed to load addresses:", error);
      addToast({ title: "加载失败", description: "无法获取跟单地址列表", color: "danger" });
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, sortBy, sortOrder]);

  useEffect(() => {
    loadAddresses();
  }, [loadAddresses]);

  useEffect(() => {
    loadAvailableCoins();
  }, [loadAvailableCoins]);

  // 处理搜索
  const handleSearch = useCallback(() => {
    setPage(1);
    loadAddresses();
  }, [loadAddresses]);

  // 处理添加/编辑
  const handleOpenAddModal = (address?: CopyTradingAddress) => {
    if (address) {
      setEditingAddress(address);
      setFormData({
        address: address.address,
        name: address.name,
        is_enabled: address.is_enabled,
        copy_ratio: address.copy_ratio,
        max_position_size_usd: address.max_position_size_usd,
        min_position_size_usd: address.min_position_size_usd,
        copy_leverage: address.copy_leverage,
        max_leverage: address.max_leverage,
        default_leverage: address.default_leverage,
        max_total_positions: address.max_total_positions,
        max_daily_trades: address.max_daily_trades,
        slippage: address.slippage,
        symbols_whitelist: address.symbols_whitelist || [],
        symbols_blacklist: address.symbols_blacklist || [],
        check_interval: address.check_interval,
        dry_run: address.dry_run,
        auto_replenish: address.auto_replenish ?? false,
        replenish_ratio: address.replenish_ratio ?? 0.5,
        replenish_min_value_usd: address.replenish_min_value_usd ?? 10,
        replenish_max_value_usd: address.replenish_max_value_usd ?? 100,
      });
    } else {
      setEditingAddress(null);
      setFormData({
        address: "",
        name: "",
        is_enabled: true,
        copy_ratio: 0.1,
        max_position_size_usd: 500,
        min_position_size_usd: 20,
        copy_leverage: true,
        max_leverage: 10,
        default_leverage: 5,
        max_total_positions: 10,
        max_daily_trades: 50,
        slippage: 0.01,
        symbols_whitelist: [],
        symbols_blacklist: [],
        check_interval: 10,
        dry_run: true,
        auto_replenish: false,
        replenish_ratio: 0.5,
        replenish_min_value_usd: 10,
        replenish_max_value_usd: 100,
      });
    }
    setIsAddModalOpen(true);
  };

  const handleSaveAddress = async () => {
    try {
      if (editingAddress) {
        await copyTradingApi.updateAddress(editingAddress.address, formData);
        addToast({ title: "更新成功", color: "success" });
      } else {
        await copyTradingApi.createAddress(formData);
        addToast({ title: "添加成功", color: "success" });
      }
      setIsAddModalOpen(false);
      loadAddresses();
    } catch (error) {
      console.error("Failed to save address:", error);
      addToast({ title: "保存失败", color: "danger" });
    }
  };

  // 打开删除确认弹窗
  const handleOpenDeleteModal = (address: string) => {
    setDeletingAddress(address);
    setIsDeleteModalOpen(true);
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingAddress) return;
    try {
      await copyTradingApi.deleteAddress(deletingAddress);
      addToast({ title: "删除成功", color: "success" });
      setIsDeleteModalOpen(false);
      setDeletingAddress(null);
      loadAddresses();
    } catch (error) {
      console.error("Failed to delete address:", error);
      addToast({ title: "删除失败", color: "danger" });
    }
  };

  // 处理启用/禁用（使用乐观更新避免无限循环）
  const handleToggle = async (address: string, isEnabled: boolean) => {
    // 乐观更新本地状态
    setAddresses((prev) =>
      prev.map((a) => (a.address === address ? { ...a, is_enabled: isEnabled } : a))
    );

    try {
      await copyTradingApi.toggleAddress(address, isEnabled);
    } catch (error) {
      // 失败时回滚状态
      setAddresses((prev) =>
        prev.map((a) => (a.address === address ? { ...a, is_enabled: !isEnabled } : a))
      );
      console.error("Failed to toggle address:", error);
      addToast({ title: "操作失败", color: "danger" });
    }
  };

  // 获取选中的地址列表
  const getSelectedAddressList = (): string[] => {
    if (selectedKeys === "all") {
      return addresses.map((a) => a.address);
    }
    return Array.from(selectedKeys);
  };

  // 获取选中数量
  const selectedCount = selectedKeys === "all" ? addresses.length : selectedKeys.size;

  // 批量操作
  const handleBatchAction = async (action: "enable" | "disable" | "delete") => {
    const addressList = getSelectedAddressList();
    if (addressList.length === 0) return;

    // 批量删除使用 Modal 确认
    if (action === "delete") {
      setIsBatchDeleteModalOpen(true);
      return;
    }

    try {
      await copyTradingApi.batchAction(action, addressList);
      addToast({ title: "批量操作成功", color: "success" });
      setSelectedKeys(new Set());
      loadAddresses();
    } catch (error) {
      console.error("Failed to batch action:", error);
      addToast({ title: "批量操作失败", color: "danger" });
    }
  };

  // 确认批量删除
  const handleConfirmBatchDelete = async () => {
    try {
      const addressList = getSelectedAddressList();
      await copyTradingApi.batchAction("delete", addressList);
      addToast({ title: "批量删除成功", color: "success" });
      setSelectedKeys(new Set());
      setIsBatchDeleteModalOpen(false);
      loadAddresses();
    } catch (error) {
      console.error("Failed to batch delete:", error);
      addToast({ title: "批量删除失败", color: "danger" });
    }
  };


  // 格式化地址
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 表格列
  const columns = [
    { key: "status", label: "状态" },
    { key: "address", label: "地址" },
    { key: "name", label: "名称" },
    { key: "rating", label: "评级" },
    { key: "win_rate", label: "胜率" },
    { key: "trader_pnl", label: "盈亏" },
    { key: "copy_ratio", label: "跟单比例" },
    { key: "position_size", label: "仓位范围" },
    { key: "max_leverage", label: "最大杠杆" },
    { key: "auto_replenish", label: "自动补仓" },
    { key: "symbols", label: "币种限制" },
    { key: "updated_at", label: "更新时间" },
    { key: "actions", label: "操作" },
  ];

  // 渲染单元格
  const renderCell = useCallback(
    (item: CopyTradingAddress, columnKey: string) => {
      switch (columnKey) {
        case "status":
          return (
            <Switch
              size="sm"
              isSelected={item.is_enabled}
              onChange={(e) => handleToggle(item.address, e.target.checked)}
            />
          );
        case "address":
          return (
            <a
              href={`/traders/${item.address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {formatAddress(item.address)}
            </a>
          );
        case "name":
          return item.name || "-";
        case "rating":
          return item.rating ? (
            <Chip size="sm" color={ratingColors[item.rating] || "default"}>
              {item.rating}
            </Chip>
          ) : (
            "-"
          );
        case "win_rate":
          return item.win_rate != null ? `${(item.win_rate * 100).toFixed(1)}%` : "-";
        case "trader_pnl":
          return item.trader_pnl != null ? (
            <span className={item.trader_pnl >= 0 ? "text-success" : "text-danger"}>
              ${item.trader_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          ) : (
            "-"
          );
        case "copy_ratio":
          return `${(item.copy_ratio * 100).toFixed(0)}%`;
        case "position_size":
          return (
            <span className="text-sm">
              ${item.min_position_size_usd} - ${item.max_position_size_usd}
            </span>
          );
        case "max_leverage":
          return `${item.max_leverage}x`;
        case "auto_replenish":
          return item.auto_replenish ? (
            <Chip size="sm" color="success" variant="flat">
              已启用
            </Chip>
          ) : (
            <Chip size="sm" color="default" variant="flat">
              未启用
            </Chip>
          );
        case "symbols":
          const whiteCount = item.symbols_whitelist?.length || 0;
          const blackCount = item.symbols_blacklist?.length || 0;
          if (whiteCount === 0 && blackCount === 0) {
            return <span className="text-default-400">不限制</span>;
          }
          return (
            <Tooltip
              content={
                <div className="text-xs space-y-1">
                  {whiteCount > 0 && (
                    <div>
                      <span className="text-success">白名单: </span>
                      {item.symbols_whitelist?.join(", ")}
                    </div>
                  )}
                  {blackCount > 0 && (
                    <div>
                      <span className="text-danger">黑名单: </span>
                      {item.symbols_blacklist?.join(", ")}
                    </div>
                  )}
                </div>
              }
            >
              <div className="flex gap-1">
                {whiteCount > 0 && (
                  <Chip size="sm" color="success" variant="flat">
                    +{whiteCount}
                  </Chip>
                )}
                {blackCount > 0 && (
                  <Chip size="sm" color="danger" variant="flat">
                    -{blackCount}
                  </Chip>
                )}
              </div>
            </Tooltip>
          );
        case "updated_at": {
          const date = new Date(item.updated_at);
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          return `${year}-${month}-${day}`;
        }
        case "actions":
          return (
            <div className="flex gap-1">
              <Tooltip content="编辑">
                <Button
                  isIconOnly
                  size="sm"
                  variant="light"
                  onPress={() => handleOpenAddModal(item)}
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
                  onPress={() => handleOpenDeleteModal(item.address)}
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
    [navigate]
  );

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-4">
        {/* 标题和操作栏 */}
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">跟单管理</h1>
          <div className="flex gap-2">
            <Button
              color="primary"
              startContent={<Icon icon="lucide:plus" width={18} />}
              onPress={() => handleOpenAddModal()}
            >
              添加地址
            </Button>
          </div>
        </div>

        {/* 筛选工具栏 */}
        <div className="flex flex-wrap gap-3 items-center">
          <Input
            className="w-64"
            placeholder="搜索地址或名称..."
            value={search}
            onValueChange={setSearch}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            startContent={<Icon icon="lucide:search" width={18} />}
          />
          <Select
            className="w-40"
            placeholder="启用状态"
            selectedKeys={statusFilter ? [statusFilter] : []}
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string || "";
              setStatusFilter(value);
              setPage(1);
            }}
          >
            <SelectItem key="">全部</SelectItem>
            <SelectItem key="enabled">已启用</SelectItem>
            <SelectItem key="disabled">已禁用</SelectItem>
          </Select>

          {selectedCount > 0 && (
            <Dropdown>
              <DropdownTrigger>
                <Button variant="flat" color="primary">
                  批量操作 ({selectedKeys === "all" ? "全部" : selectedCount})
                </Button>
              </DropdownTrigger>
              <DropdownMenu>
                <DropdownItem
                  key="enable"
                  startContent={<Icon icon="lucide:toggle-right" width={16} className="text-success" />}
                  onPress={() => handleBatchAction("enable")}
                >
                  批量启用
                </DropdownItem>
                <DropdownItem
                  key="disable"
                  startContent={<Icon icon="lucide:toggle-left" width={16} className="text-warning" />}
                  onPress={() => handleBatchAction("disable")}
                >
                  批量禁用
                </DropdownItem>
                <DropdownItem
                  key="delete"
                  className="text-danger"
                  startContent={<Icon icon="lucide:trash-2" width={16} />}
                  onPress={() => handleBatchAction("delete")}
                >
                  批量删除
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
          )}

        </div>

        {/* 数据表格 */}
        {loading ? (
          <div className="flex justify-center py-8">
            <Spinner size="lg" />
          </div>
        ) : (
          <>
            <Table
              aria-label="跟单地址列表"
              color="primary"
              selectionMode="multiple"
              selectedKeys={selectedKeys}
              onSelectionChange={(keys) => setSelectedKeys(keys as "all" | Set<string>)}
            >
              <TableHeader columns={columns}>
                {(column) => (
                  <TableColumn key={column.key}>{column.label}</TableColumn>
                )}
              </TableHeader>
              <TableBody items={addresses} emptyContent="暂无跟单地址">
                {(item) => (
                  <TableRow key={item.address}>
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
                rowsPerPage={10}
                className="mt-4"
              />
            )}
          </>
        )}

        {/* Modals */}
        <AddressFormModal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          editingAddress={editingAddress}
          formData={formData}
          setFormData={setFormData}
          onSave={handleSaveAddress}
          availableCoins={availableCoins}
          coinsLoading={coinsLoading}
          onSyncCoins={handleSyncCoins}
        />

        <DeleteConfirmModal
          isOpen={isDeleteModalOpen}
          onClose={() => setIsDeleteModalOpen(false)}
          onConfirm={handleConfirmDelete}
          deletingAddress={deletingAddress}
        />

        <BatchDeleteConfirmModal
          isOpen={isBatchDeleteModalOpen}
          onClose={() => setIsBatchDeleteModalOpen(false)}
          onConfirm={handleConfirmBatchDelete}
          selectedCount={selectedCount}
        />
      </div>
    </DefaultLayout>
  );
}
