import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
  Pagination,
  Input,
  Button,
  Chip,
  Spinner,
  Select,
  SelectItem,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
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
import { copyTradingApi, hyperliquidApi, CopyTradingAddress, CopyTradingGroup, PaginationInfo } from "@/services/api";

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
  const [groups, setGroups] = useState<CopyTradingGroup[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选状态
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState("updated_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // 选择状态 - HeroUI Selection 可以是 "all" 或 Set<Key>
  const [selectedKeys, setSelectedKeys] = useState<"all" | Set<string>>(new Set());

  // Modal 状态
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingAddress, setDeletingAddress] = useState<string | null>(null);
  const [editingAddress, setEditingAddress] = useState<CopyTradingAddress | null>(null);

  // 表单状态
  const [formData, setFormData] = useState<Partial<CopyTradingAddress>>({
    address: "",
    name: "",
    group_id: null,
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
    sync_position: true,
  });

  // 分组表单
  const [groupFormData, setGroupFormData] = useState({
    name: "",
    description: "",
    color: "#3B82F6",
  });

  // 页码跳转
  const [jumpPage, setJumpPage] = useState("");

  // 币种输入临时状态
  const [whitelistInput, setWhitelistInput] = useState("");
  const [blacklistInput, setBlacklistInput] = useState("");
  const [whitelistHighlightIndex, setWhitelistHighlightIndex] = useState(-1);
  const [blacklistHighlightIndex, setBlacklistHighlightIndex] = useState(-1);

  // 可用币种列表
  const [availableCoins, setAvailableCoins] = useState<string[]>([]);
  const [coinsLoading, setCoinsLoading] = useState(false);

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

  // 添加币种到白名单
  const handleAddWhitelist = (coin?: string) => {
    const symbol = (coin || whitelistInput.trim()).toUpperCase();
    if (symbol && !formData.symbols_whitelist?.includes(symbol)) {
      setFormData({
        ...formData,
        symbols_whitelist: [...(formData.symbols_whitelist || []), symbol],
      });
      setWhitelistInput("");
      setWhitelistHighlightIndex(-1);
    }
  };

  // 处理白名单键盘事件
  const handleWhitelistKeyDown = (e: React.KeyboardEvent) => {
    if (!whitelistInput || filteredWhitelistCoins.length === 0) {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddWhitelist();
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setWhitelistHighlightIndex((prev) =>
          prev < filteredWhitelistCoins.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setWhitelistHighlightIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (whitelistHighlightIndex >= 0 && whitelistHighlightIndex < filteredWhitelistCoins.length) {
          handleAddWhitelist(filteredWhitelistCoins[whitelistHighlightIndex]);
        } else {
          handleAddWhitelist();
        }
        break;
      case "Escape":
        setWhitelistInput("");
        setWhitelistHighlightIndex(-1);
        break;
    }
  };

  // 从白名单移除币种
  const handleRemoveWhitelist = (symbol: string) => {
    setFormData({
      ...formData,
      symbols_whitelist: formData.symbols_whitelist?.filter((s) => s !== symbol) || [],
    });
  };

  // 添加币种到黑名单
  const handleAddBlacklist = (coin?: string) => {
    const symbol = (coin || blacklistInput.trim()).toUpperCase();
    if (symbol && !formData.symbols_blacklist?.includes(symbol)) {
      setFormData({
        ...formData,
        symbols_blacklist: [...(formData.symbols_blacklist || []), symbol],
      });
      setBlacklistInput("");
      setBlacklistHighlightIndex(-1);
    }
  };

  // 处理黑名单键盘事件
  const handleBlacklistKeyDown = (e: React.KeyboardEvent) => {
    if (!blacklistInput || filteredBlacklistCoins.length === 0) {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddBlacklist();
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setBlacklistHighlightIndex((prev) =>
          prev < filteredBlacklistCoins.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setBlacklistHighlightIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (blacklistHighlightIndex >= 0 && blacklistHighlightIndex < filteredBlacklistCoins.length) {
          handleAddBlacklist(filteredBlacklistCoins[blacklistHighlightIndex]);
        } else {
          handleAddBlacklist();
        }
        break;
      case "Escape":
        setBlacklistInput("");
        setBlacklistHighlightIndex(-1);
        break;
    }
  };

  // 从黑名单移除币种
  const handleRemoveBlacklist = (symbol: string) => {
    setFormData({
      ...formData,
      symbols_blacklist: formData.symbols_blacklist?.filter((s) => s !== symbol) || [],
    });
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
      if (selectedGroup !== null) params.group_id = selectedGroup;
      if (statusFilter !== "all") params.is_enabled = statusFilter === "enabled";

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
  }, [page, search, selectedGroup, statusFilter, sortBy, sortOrder]);

  const loadGroups = useCallback(async () => {
    try {
      const response = await copyTradingApi.getGroups();
      if (response.success && response.data) {
        setGroups(response.data);
      }
    } catch (error) {
      console.error("Failed to load groups:", error);
    }
  }, []);

  useEffect(() => {
    loadAddresses();
  }, [loadAddresses]);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  useEffect(() => {
    loadAvailableCoins();
  }, [loadAvailableCoins]);

  // 过滤可用币种（用于下拉选择）
  const filteredWhitelistCoins = useMemo(() => {
    const input = whitelistInput.trim().toUpperCase();
    const existing = formData.symbols_whitelist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, whitelistInput, formData.symbols_whitelist]);

  const filteredBlacklistCoins = useMemo(() => {
    const input = blacklistInput.trim().toUpperCase();
    const existing = formData.symbols_blacklist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, blacklistInput, formData.symbols_blacklist]);

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
        group_id: address.group_id,
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
        sync_position: address.sync_position ?? true,
      });
    } else {
      setEditingAddress(null);
      setFormData({
        address: "",
        name: "",
        group_id: null,
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
        sync_position: true,
      });
    }
    // 重置临时输入状态
    setWhitelistInput("");
    setBlacklistInput("");
    setWhitelistHighlightIndex(-1);
    setBlacklistHighlightIndex(-1);
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
      loadGroups(); // 更新分组计数
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

  // 处理同步仓位开关（使用乐观更新避免无限循环）
  const handleToggleSyncPosition = async (address: string, syncPosition: boolean) => {
    // 乐观更新本地状态
    setAddresses((prev) =>
      prev.map((a) => (a.address === address ? { ...a, sync_position: syncPosition } : a))
    );

    try {
      await copyTradingApi.toggleSyncPosition(address, syncPosition);
    } catch (error) {
      // 失败时回滚状态
      setAddresses((prev) =>
        prev.map((a) => (a.address === address ? { ...a, sync_position: !syncPosition } : a))
      );
      console.error("Failed to toggle sync position:", error);
      addToast({ title: "操作失败", color: "danger" });
    }
  };

  // 批量删除确认状态
  const [isBatchDeleteModalOpen, setIsBatchDeleteModalOpen] = useState(false);

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
      loadGroups(); // 更新分组计数
    } catch (error) {
      console.error("Failed to batch delete:", error);
      addToast({ title: "批量删除失败", color: "danger" });
    }
  };

  // 分组管理
  const handleSaveGroup = async () => {
    try {
      await copyTradingApi.createGroup(groupFormData);
      addToast({ title: "分组创建成功", color: "success" });
      setIsGroupModalOpen(false);
      setGroupFormData({ name: "", description: "", color: "#3B82F6" });
      loadGroups();
    } catch (error) {
      console.error("Failed to create group:", error);
      addToast({ title: "创建失败", color: "danger" });
    }
  };

  const handleDeleteGroup = async (groupId: number) => {
    if (!confirm("确定要删除这个分组吗？分组下的地址将移至默认分组。")) return;
    try {
      await copyTradingApi.deleteGroup(groupId);
      addToast({ title: "分组删除成功", color: "success" });
      loadGroups();
      if (selectedGroup === groupId) {
        setSelectedGroup(null);
      }
    } catch (error) {
      console.error("Failed to delete group:", error);
      addToast({ title: "删除失败", color: "danger" });
    }
  };


  // 页码跳转
  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pagination && pageNum >= 1 && pageNum <= pagination.total_pages) {
      setPage(pageNum);
      setJumpPage("");
    }
  };

  // 格式化地址
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 复制地址
  const copyAddress = (address: string) => {
    navigator.clipboard.writeText(address);
    addToast({ title: "已复制地址", color: "success" });
  };

  // 表格列
  const columns = [
    { key: "status", label: "状态" },
    { key: "address", label: "地址" },
    { key: "name", label: "名称" },
    { key: "group", label: "分组" },
    { key: "rating", label: "评级" },
    { key: "win_rate", label: "胜率" },
    { key: "trader_pnl", label: "盈亏" },
    { key: "copy_ratio", label: "跟单比例" },
    { key: "position_size", label: "仓位范围" },
    { key: "max_leverage", label: "最大杠杆" },
    { key: "sync_position", label: "同步仓位" },
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
            <div className="flex items-center gap-2">
              <Tooltip content={item.address}>
                <span
                  className="cursor-pointer hover:text-primary"
                  onClick={() => navigate(`/traders/${item.address}`)}
                >
                  {formatAddress(item.address)}
                </span>
              </Tooltip>
              <Button
                isIconOnly
                size="sm"
                variant="light"
                onPress={() => copyAddress(item.address)}
              >
                <Icon icon="lucide:copy" width={14} />
              </Button>
            </div>
          );
        case "name":
          return item.name || "-";
        case "group":
          return item.group_name ? (
            <Chip size="sm" style={{ backgroundColor: item.group_color || "#6B7280", color: "white" }}>
              {item.group_name}
            </Chip>
          ) : (
            "-"
          );
        case "rating":
          return item.rating ? (
            <Chip size="sm" color={ratingColors[item.rating] || "default"}>
              {item.rating}
            </Chip>
          ) : (
            "-"
          );
        case "win_rate":
          return item.win_rate !== undefined ? `${(item.win_rate * 100).toFixed(1)}%` : "-";
        case "trader_pnl":
          return item.trader_pnl !== undefined ? (
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
        case "sync_position":
          return (
            <Switch
              size="sm"
              isSelected={item.sync_position}
              onChange={(e) => handleToggleSyncPosition(item.address, e.target.checked)}
            />
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
        case "updated_at":
          return new Date(item.updated_at).toLocaleDateString();
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
            selectedKeys={[statusFilter]}
            onSelectionChange={(keys) => {
              const value = Array.from(keys)[0] as string;
              setStatusFilter(value);
              setPage(1);
            }}
          >
            <SelectItem key="all">全部</SelectItem>
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

          <Button variant="flat" onPress={() => loadAddresses()}>
            <Icon icon="lucide:refresh-cw" width={18} />
          </Button>

          <Button variant="flat" onPress={() => setIsGroupModalOpen(true)}>
            <Icon icon="lucide:folder-plus" width={18} />
            管理分组
          </Button>
        </div>

        {/* 分组标签 */}
        <div className="flex gap-2 flex-wrap">
          <Chip
            className="cursor-pointer"
            variant={selectedGroup === null ? "solid" : "flat"}
            onClose={undefined}
            onClick={() => {
              setSelectedGroup(null);
              setPage(1);
            }}
          >
            全部 ({groups.reduce((sum, g) => sum + (g.address_count || 0), 0)})
          </Chip>
          {groups.map((group) => (
            <Chip
              key={group.id}
              className="cursor-pointer"
              variant={selectedGroup === group.id ? "solid" : "flat"}
              style={
                selectedGroup === group.id
                  ? { backgroundColor: group.color, color: "white" }
                  : { borderColor: group.color }
              }
              onClick={() => {
                setSelectedGroup(group.id);
                setPage(1);
              }}
            >
              {group.name} ({group.address_count || 0})
            </Chip>
          ))}
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
            {pagination && pagination.total_pages > 1 && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2 mt-4">
                <span className="text-sm text-default-500">
                  显示 {Math.min((page - 1) * 10 + 1, pagination.total_count)} - {Math.min(page * 10, pagination.total_count)} 条，共 {pagination.total_count} 条记录
                </span>
                <div className="flex items-center gap-3">
                  <Pagination
                    isCompact
                    showControls
                    showShadow
                    color="primary"
                    total={pagination.total_pages}
                    page={page}
                    onChange={setPage}
                  />
                  <div className="flex items-center gap-1">
                    <span className="text-sm text-default-500">跳转</span>
                    <Input
                      type="number"
                      size="sm"
                      className="w-16"
                      min={1}
                      max={pagination.total_pages}
                      value={jumpPage}
                      onValueChange={setJumpPage}
                      onKeyDown={(e) => e.key === "Enter" && handleJumpPage()}
                    />
                    <span className="text-sm text-default-500">页</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* 添加/编辑 Modal */}
        <Modal isOpen={isAddModalOpen} onClose={() => setIsAddModalOpen(false)} size="2xl" scrollBehavior="inside">
          <ModalContent>
            <ModalHeader>{editingAddress ? "编辑跟单地址" : "添加跟单地址"}</ModalHeader>
            <ModalBody className="max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                {/* 基础信息 */}
                <Input
                  label="地址"
                  placeholder="0x..."
                  value={formData.address || ""}
                  onValueChange={(v) => setFormData({ ...formData, address: v })}
                  isDisabled={!!editingAddress}
                  className="col-span-2"
                />
                <Input
                  label="名称"
                  placeholder="备注名称"
                  value={formData.name || ""}
                  onValueChange={(v) => setFormData({ ...formData, name: v })}
                />
                <Select
                  label="分组"
                  selectedKeys={formData.group_id ? [String(formData.group_id)] : []}
                  onSelectionChange={(keys) => {
                    const value = Array.from(keys)[0];
                    setFormData({ ...formData, group_id: value ? Number(value) : null });
                  }}
                >
                  {groups.map((g) => (
                    <SelectItem key={String(g.id)}>{g.name}</SelectItem>
                  ))}
                </Select>

                {/* 跟单配置 */}
                <Input
                  type="number"
                  label="跟单比例"
                  placeholder="10"
                  value={String(((formData.copy_ratio || 0.1) * 100).toFixed(0))}
                  onValueChange={(v) => setFormData({ ...formData, copy_ratio: (parseFloat(v) || 10) / 100 })}
                  endContent="%"
                  description="输入 10 表示跟单 10%"
                />
                <Input
                  type="number"
                  label="最大仓位"
                  placeholder="500"
                  value={String(formData.max_position_size_usd || 500)}
                  onValueChange={(v) => setFormData({ ...formData, max_position_size_usd: parseFloat(v) || 500 })}
                  startContent="$"
                />
                <Input
                  type="number"
                  label="最小仓位"
                  placeholder="20"
                  value={String(formData.min_position_size_usd || 20)}
                  onValueChange={(v) => setFormData({ ...formData, min_position_size_usd: parseFloat(v) || 20 })}
                  startContent="$"
                />
                <Input
                  type="number"
                  label="最大杠杆"
                  placeholder="10"
                  value={String(formData.max_leverage || 10)}
                  onValueChange={(v) => setFormData({ ...formData, max_leverage: parseInt(v) || 10 })}
                  endContent="x"
                />
                <Input
                  type="number"
                  label="默认杠杆"
                  placeholder="5"
                  value={String(formData.default_leverage || 5)}
                  onValueChange={(v) => setFormData({ ...formData, default_leverage: parseInt(v) || 5 })}
                  endContent="x"
                />
                <Input
                  type="number"
                  label="最大持仓数"
                  placeholder="10"
                  value={String(formData.max_total_positions || 10)}
                  onValueChange={(v) => setFormData({ ...formData, max_total_positions: parseInt(v) || 10 })}
                />
                <Input
                  type="number"
                  label="日交易上限"
                  placeholder="50"
                  value={String(formData.max_daily_trades || 50)}
                  onValueChange={(v) => setFormData({ ...formData, max_daily_trades: parseInt(v) || 50 })}
                />
                <Input
                  type="number"
                  label="检查间隔"
                  placeholder="10"
                  value={String(formData.check_interval || 10)}
                  onValueChange={(v) => setFormData({ ...formData, check_interval: parseFloat(v) || 10 })}
                  endContent="秒"
                />

                {/* 币种限制 */}
                <div className="col-span-2 border rounded-lg p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium text-default-700">币种限制</h4>
                    <Button
                      size="sm"
                      variant="flat"
                      isLoading={coinsLoading}
                      onPress={handleSyncCoins}
                      startContent={!coinsLoading && <Icon icon="lucide:refresh-cw" width={14} />}
                    >
                      {availableCoins.length > 0 ? `已加载 ${availableCoins.length} 币种` : "同步币种"}
                    </Button>
                  </div>
                  <p className="text-xs text-default-500">
                    白名单：只跟单这些币种（留空表示不限制）；黑名单：不跟单这些币种
                  </p>

                  {/* 白名单 */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-success font-medium w-16">白名单</span>
                      <div className="flex-1 relative">
                        <Input
                          size="sm"
                          placeholder="输入搜索币种..."
                          value={whitelistInput}
                          onValueChange={(v) => {
                            setWhitelistInput(v);
                            setWhitelistHighlightIndex(-1);
                          }}
                          onKeyDown={handleWhitelistKeyDown}
                        />
                        {whitelistInput && filteredWhitelistCoins.length > 0 && (
                          <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-content1 border border-default-200 rounded-lg shadow-lg max-h-40 overflow-auto">
                            {filteredWhitelistCoins.map((coin, index) => (
                              <div
                                key={coin}
                                className={`px-3 py-2 cursor-pointer text-sm ${
                                  index === whitelistHighlightIndex
                                    ? "bg-primary-100 text-primary"
                                    : "hover:bg-default-100"
                                }`}
                                onClick={() => handleAddWhitelist(coin)}
                                onMouseEnter={() => setWhitelistHighlightIndex(index)}
                              >
                                {coin}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <Button
                        size="sm"
                        color="success"
                        variant="flat"
                        isIconOnly
                        onPress={() => handleAddWhitelist()}
                        isDisabled={!whitelistInput.trim()}
                      >
                        <Icon icon="lucide:plus" width={16} />
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-1 min-h-[32px]">
                      {formData.symbols_whitelist?.length === 0 ? (
                        <span className="text-xs text-default-400">不限制（跟单所有币种）</span>
                      ) : (
                        formData.symbols_whitelist?.map((symbol) => (
                          <Chip
                            key={symbol}
                            size="sm"
                            color="success"
                            variant="flat"
                            onClose={() => handleRemoveWhitelist(symbol)}
                          >
                            {symbol}
                          </Chip>
                        ))
                      )}
                    </div>
                  </div>

                  {/* 黑名单 */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-danger font-medium w-16">黑名单</span>
                      <div className="flex-1 relative">
                        <Input
                          size="sm"
                          placeholder="输入搜索币种..."
                          value={blacklistInput}
                          onValueChange={(v) => {
                            setBlacklistInput(v);
                            setBlacklistHighlightIndex(-1);
                          }}
                          onKeyDown={handleBlacklistKeyDown}
                        />
                        {blacklistInput && filteredBlacklistCoins.length > 0 && (
                          <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-content1 border border-default-200 rounded-lg shadow-lg max-h-40 overflow-auto">
                            {filteredBlacklistCoins.map((coin, index) => (
                              <div
                                key={coin}
                                className={`px-3 py-2 cursor-pointer text-sm ${
                                  index === blacklistHighlightIndex
                                    ? "bg-primary-100 text-primary"
                                    : "hover:bg-default-100"
                                }`}
                                onClick={() => handleAddBlacklist(coin)}
                                onMouseEnter={() => setBlacklistHighlightIndex(index)}
                              >
                                {coin}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <Button
                        size="sm"
                        color="danger"
                        variant="flat"
                        isIconOnly
                        onPress={() => handleAddBlacklist()}
                        isDisabled={!blacklistInput.trim()}
                      >
                        <Icon icon="lucide:plus" width={16} />
                      </Button>
                    </div>
                    <div className="flex flex-wrap gap-1 min-h-[32px]">
                      {formData.symbols_blacklist?.length === 0 ? (
                        <span className="text-xs text-default-400">无黑名单</span>
                      ) : (
                        formData.symbols_blacklist?.map((symbol) => (
                          <Chip
                            key={symbol}
                            size="sm"
                            color="danger"
                            variant="flat"
                            onClose={() => handleRemoveBlacklist(symbol)}
                          >
                            {symbol}
                          </Chip>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                {/* 开关选项 */}
                <div className="col-span-2 flex flex-wrap gap-6">
                  <Switch
                    isSelected={formData.is_enabled}
                    onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                  >
                    启用跟单
                  </Switch>
                  <Switch
                    isSelected={formData.copy_leverage}
                    onChange={(e) => setFormData({ ...formData, copy_leverage: e.target.checked })}
                  >
                    复制杠杆
                  </Switch>
                  <Tooltip content="启用后将同步目标交易者的现有仓位">
                    <div>
                      <Switch
                        isSelected={formData.sync_position}
                        onChange={(e) => setFormData({ ...formData, sync_position: e.target.checked })}
                      >
                        同步仓位
                      </Switch>
                    </div>
                  </Tooltip>
                  <Switch
                    isSelected={formData.dry_run}
                    onChange={(e) => setFormData({ ...formData, dry_run: e.target.checked })}
                  >
                    模拟模式
                  </Switch>
                </div>
              </div>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setIsAddModalOpen(false)}>
                取消
              </Button>
              <Button color="primary" onPress={handleSaveAddress}>
                保存
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* 分组管理 Modal */}
        <Modal isOpen={isGroupModalOpen} onClose={() => setIsGroupModalOpen(false)} scrollBehavior="inside">
          <ModalContent>
            <ModalHeader>分组管理</ModalHeader>
            <ModalBody className="max-h-[70vh] overflow-y-auto">
              {/* 现有分组列表 */}
              <div className="space-y-2 mb-4">
                {groups.map((group) => (
                  <div key={group.id} className="flex items-center justify-between p-2 border rounded">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-4 h-4 rounded"
                        style={{ backgroundColor: group.color }}
                      />
                      <span>{group.name}</span>
                      <span className="text-sm text-gray-500">({group.address_count || 0})</span>
                    </div>
                    {group.id !== 1 && (
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                        color="danger"
                        onPress={() => handleDeleteGroup(group.id)}
                      >
                        <Icon icon="lucide:trash-2" width={16} />
                      </Button>
                    )}
                  </div>
                ))}
              </div>

              {/* 新建分组 */}
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium mb-2">新建分组</h4>
                <div className="space-y-2">
                  <Input
                    label="分组名称"
                    placeholder="输入分组名称"
                    value={groupFormData.name}
                    onValueChange={(v) => setGroupFormData({ ...groupFormData, name: v })}
                  />
                  <Input
                    label="描述"
                    placeholder="可选的描述"
                    value={groupFormData.description}
                    onValueChange={(v) => setGroupFormData({ ...groupFormData, description: v })}
                  />
                  <Input
                    type="color"
                    label="颜色"
                    value={groupFormData.color}
                    onValueChange={(v) => setGroupFormData({ ...groupFormData, color: v })}
                  />
                </div>
              </div>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setIsGroupModalOpen(false)}>
                关闭
              </Button>
              <Button
                color="primary"
                onPress={handleSaveGroup}
                isDisabled={!groupFormData.name}
              >
                创建分组
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* 删除确认 Modal */}
        <Modal isOpen={isDeleteModalOpen} onClose={() => setIsDeleteModalOpen(false)} size="sm">
          <ModalContent>
            <ModalHeader className="flex items-center gap-2">
              <Icon icon="lucide:alert-triangle" className="text-danger" width={20} />
              确认删除
            </ModalHeader>
            <ModalBody>
              <p>确定要删除这个跟单地址吗？此操作无法撤销。</p>
              {deletingAddress && (
                <p className="text-sm text-default-500 font-mono mt-2">
                  {deletingAddress.slice(0, 10)}...{deletingAddress.slice(-8)}
                </p>
              )}
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setIsDeleteModalOpen(false)}>
                取消
              </Button>
              <Button color="danger" onPress={handleConfirmDelete}>
                确认删除
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* 批量删除确认 Modal */}
        <Modal isOpen={isBatchDeleteModalOpen} onClose={() => setIsBatchDeleteModalOpen(false)} size="sm">
          <ModalContent>
            <ModalHeader className="flex items-center gap-2">
              <Icon icon="lucide:alert-triangle" className="text-danger" width={20} />
              确认批量删除
            </ModalHeader>
            <ModalBody>
              <p>确定要删除选中的 <strong>{selectedCount}</strong> 个跟单地址吗？此操作无法撤销。</p>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setIsBatchDeleteModalOpen(false)}>
                取消
              </Button>
              <Button color="danger" onPress={handleConfirmBatchDelete}>
                确认删除
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </div>
    </DefaultLayout>
  );
}
