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
  Card,
  CardBody,
  Tooltip,
  addToast,
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { copyPositionStatesApi, CopyPositionState, CopyPositionStats } from "@/services/api";

export default function PositionsPage() {
  const navigate = useNavigate();

  // 数据状态
  const [positions, setPositions] = useState<CopyPositionState[]>([]);
  const [stats, setStats] = useState<CopyPositionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);

  // 筛选状态
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<string>("all");
  const [targetFilter, setTargetFilter] = useState<string>("all");

  // 删除确认弹窗
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<{ address: string; symbol?: string } | null>(null);
  const [clearAllOpen, setClearAllOpen] = useState(false);

  // 加载仓位列表
  const fetchPositions = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {};

      if (targetFilter !== "all") {
        params.target_address = targetFilter;
      }

      const response = await copyPositionStatesApi.getPositions(params);

      if (response.success && response.data) {
        let filtered = response.data;

        // 本地筛选
        if (search) {
          const searchLower = search.toLowerCase();
          filtered = filtered.filter(
            (p) =>
              p.symbol.toLowerCase().includes(searchLower) ||
              p.target_address.toLowerCase().includes(searchLower) ||
              (p.target_name && p.target_name.toLowerCase().includes(searchLower))
          );
        }

        if (sideFilter !== "all") {
          filtered = filtered.filter((p) => p.side === sideFilter);
        }

        setPositions(filtered);
      }
    } catch (error) {
      console.error("Failed to fetch positions:", error);
      addToast({
        title: "Error",
        description: "Failed to load positions",
        color: "danger",
      });
    } finally {
      setLoading(false);
    }
  }, [search, sideFilter, targetFilter]);

  // 加载统计数据
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const response = await copyPositionStatesApi.getStats();

      if (response.success && response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // 删除单个仓位
  const handleDeletePosition = async () => {
    if (!deleteTarget) return;

    try {
      if (deleteTarget.symbol) {
        // 删除单个仓位
        const response = await copyPositionStatesApi.deletePosition(
          deleteTarget.address,
          deleteTarget.symbol
        );

        if (response.success) {
          addToast({
            title: "Success",
            description: response.message || "Position deleted",
            color: "success",
          });
          fetchPositions();
          fetchStats();
        }
      } else {
        // 清空目标所有仓位
        const response = await copyPositionStatesApi.clearTargetPositions(deleteTarget.address);

        if (response.success) {
          addToast({
            title: "Success",
            description: response.message || "All positions cleared",
            color: "success",
          });
          fetchPositions();
          fetchStats();
        }
      }
    } catch (error) {
      console.error("Failed to delete position:", error);
      addToast({
        title: "Error",
        description: "Failed to delete position",
        color: "danger",
      });
    } finally {
      onClose();
      setDeleteTarget(null);
    }
  };

  // 清空所有仓位
  const handleClearAll = async () => {
    try {
      const response = await copyPositionStatesApi.clearAll();

      if (response.success) {
        addToast({
          title: "Success",
          description: response.message || "All positions cleared",
          color: "success",
        });
        fetchPositions();
        fetchStats();
      }
    } catch (error) {
      console.error("Failed to clear all positions:", error);
      addToast({
        title: "Error",
        description: "Failed to clear all positions",
        color: "danger",
      });
    } finally {
      setClearAllOpen(false);
    }
  };

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // 格式化时间
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

  // 格式化地址
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  // 格式化数字
  const formatNumber = (num: number | null, decimals: number = 2) => {
    if (num === null || num === undefined) return "-";

    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  // 渲染统计卡片
  const renderStatsCards = () => {
    if (statsLoading) {
      return (
        <div className="flex justify-center py-4">
          <Spinner size="sm" />
        </div>
      );
    }

    if (!stats) return null;

    const longCount = stats.by_side?.long?.count || 0;
    const shortCount = stats.by_side?.short?.count || 0;
    const longNotional = stats.by_side?.long?.notional || 0;
    const shortNotional = stats.by_side?.short?.notional || 0;

    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold">{stats.total_positions}</div>
            <div className="text-sm text-default-500">Total Positions</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold text-success">{longCount}</div>
            <div className="text-sm text-default-500">Long (${formatNumber(longNotional)})</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold text-danger">{shortCount}</div>
            <div className="text-sm text-default-500">Short (${formatNumber(shortNotional)})</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className="text-2xl font-bold text-primary">{stats.by_target?.length || 0}</div>
            <div className="text-sm text-default-500">Active Targets</div>
          </CardBody>
        </Card>
      </div>
    );
  };

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold">Position Management</h1>
            <p className="text-default-500">
              Manage copy trading position states (used for recovery after restart)
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              color="danger"
              startContent={<Icon icon="solar:trash-bin-trash-linear" width={18} />}
              variant="flat"
              onPress={() => setClearAllOpen(true)}
            >
              Clear All
            </Button>
            <Button
              color="primary"
              startContent={<Icon icon="solar:refresh-linear" width={18} />}
              variant="flat"
              onPress={() => {
                fetchPositions();
                fetchStats();
              }}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        {renderStatsCards()}

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <Input
            className="w-64"
            placeholder="Search symbol or address..."
            startContent={<Icon icon="solar:magnifer-linear" width={18} />}
            value={search}
            onValueChange={setSearch}
          />
          <div className="flex items-center gap-2">
            <span className="text-sm text-default-500 whitespace-nowrap">Side:</span>
            <Select
              className="w-28"
              aria-label="Side"
              selectedKeys={[sideFilter]}
              size="sm"
              onSelectionChange={(keys) => {
                const value = Array.from(keys)[0] as string;
                setSideFilter(value);
              }}
            >
              <SelectItem key="all">All</SelectItem>
              <SelectItem key="long">Long</SelectItem>
              <SelectItem key="short">Short</SelectItem>
            </Select>
          </div>
          {stats && stats.by_target && stats.by_target.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-default-500 whitespace-nowrap">Target:</span>
              <Select
                className="w-40"
                aria-label="Target"
                selectedKeys={[targetFilter]}
                size="sm"
                items={[
                  { key: "all", label: "All Targets" },
                  ...stats.by_target.map((t) => ({
                    key: t.target_address,
                    label: `${t.target_name || formatAddress(t.target_address)} (${t.position_count})`,
                  })),
                ]}
                onSelectionChange={(keys) => {
                  const value = Array.from(keys)[0] as string;
                  setTargetFilter(value);
                }}
              >
                {(item) => <SelectItem key={item.key}>{item.label}</SelectItem>}
              </Select>
            </div>
          )}
        </div>

        {/* Positions Table */}
        <Table aria-label="Positions table">
          <TableHeader>
            <TableColumn>Target</TableColumn>
            <TableColumn>Symbol</TableColumn>
            <TableColumn>Side</TableColumn>
            <TableColumn>Size</TableColumn>
            <TableColumn>Entry Price</TableColumn>
            <TableColumn>Notional</TableColumn>
            <TableColumn>Leverage</TableColumn>
            <TableColumn>Updated</TableColumn>
            <TableColumn>Actions</TableColumn>
          </TableHeader>
          <TableBody emptyContent="No positions found" isLoading={loading} loadingContent={<Spinner />}>
            {positions.map((position) => (
              <TableRow key={`${position.target_address}-${position.symbol}`}>
                <TableCell>
                  <Tooltip content={position.target_address}>
                    <span
                      className="font-mono text-sm cursor-pointer hover:text-primary"
                      onClick={() => navigate(`/traders/${position.target_address}`)}
                    >
                      {position.target_name || formatAddress(position.target_address)}
                    </span>
                  </Tooltip>
                </TableCell>
                <TableCell>
                  <span className="font-medium">{position.symbol}</span>
                </TableCell>
                <TableCell>
                  <Chip color={position.side === "long" ? "success" : "danger"} size="sm" variant="flat">
                    {position.side.toUpperCase()}
                  </Chip>
                </TableCell>
                <TableCell>
                  <span className="font-mono">{formatNumber(Math.abs(position.size), 4)}</span>
                </TableCell>
                <TableCell>
                  <span className="font-mono">${formatNumber(position.entry_price, 2)}</span>
                </TableCell>
                <TableCell>
                  <span className="font-mono">${formatNumber(position.notional, 2)}</span>
                </TableCell>
                <TableCell>
                  <span className="font-mono">{position.leverage}x</span>
                </TableCell>
                <TableCell>
                  <span className="text-sm text-default-500">{formatTime(position.updated_at)}</span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Tooltip content="Delete this position state">
                      <Button
                        isIconOnly
                        color="danger"
                        size="sm"
                        variant="light"
                        onPress={() => {
                          setDeleteTarget({
                            address: position.target_address,
                            symbol: position.symbol,
                          });
                          onOpen();
                        }}
                      >
                        <Icon icon="solar:trash-bin-trash-linear" width={16} />
                      </Button>
                    </Tooltip>
                    <Tooltip content="Clear all positions for this target">
                      <Button
                        isIconOnly
                        color="warning"
                        size="sm"
                        variant="light"
                        onPress={() => {
                          setDeleteTarget({
                            address: position.target_address,
                          });
                          onOpen();
                        }}
                      >
                        <Icon icon="solar:eraser-linear" width={16} />
                      </Button>
                    </Tooltip>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {/* Delete Confirmation Modal */}
        <Modal isOpen={isOpen} onClose={onClose}>
          <ModalContent>
            <ModalHeader>Confirm Delete</ModalHeader>
            <ModalBody>
              {deleteTarget?.symbol ? (
                <p>
                  Are you sure you want to delete the position state for{" "}
                  <strong>{deleteTarget.symbol}</strong> of target{" "}
                  <strong>{formatAddress(deleteTarget.address)}</strong>?
                </p>
              ) : deleteTarget ? (
                <p>
                  Are you sure you want to clear <strong>all position states</strong> for target{" "}
                  <strong>{formatAddress(deleteTarget.address)}</strong>?
                </p>
              ) : null}
              <p className="text-warning text-sm mt-2">
                ⚠️ This will affect the copy trading bot's ability to track this position after restart.
              </p>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={onClose}>
                Cancel
              </Button>
              <Button color="danger" onPress={handleDeletePosition}>
                Delete
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Clear All Confirmation Modal */}
        <Modal isOpen={clearAllOpen} onClose={() => setClearAllOpen(false)}>
          <ModalContent>
            <ModalHeader>⚠️ Clear All Positions</ModalHeader>
            <ModalBody>
              <p>
                Are you sure you want to clear <strong>ALL position states</strong>?
              </p>
              <p className="text-danger text-sm mt-2">
                This action cannot be undone. The copy trading bot will lose track of all currently
                copied positions after restart.
              </p>
            </ModalBody>
            <ModalFooter>
              <Button variant="flat" onPress={() => setClearAllOpen(false)}>
                Cancel
              </Button>
              <Button color="danger" onPress={handleClearAll}>
                Clear All
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </div>
    </DefaultLayout>
  );
}

