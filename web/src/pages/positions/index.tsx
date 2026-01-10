import { useState, useEffect, useCallback, useMemo } from "react";
import { Button, addToast, useDisclosure } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { 
  copyPositionStatesApi, 
  CopyPositionState, 
  CopyPositionStats,
} from "@/services/api";

import { StatsCards } from "./components/StatsCards";
import { PositionFilters } from "./components/PositionFilters";
import { PositionsTable } from "./components/PositionsTable";
import { DeleteConfirmModal } from "./components/DeleteConfirmModal";
import { ClearAllModal } from "./components/ClearAllModal";

export default function PositionsPage() {
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
        setPositions(response.data);
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
  }, [targetFilter]);

  // 应用本地筛选
  const filteredPositions = useMemo(() => {
    let filtered = positions;

    // 搜索筛选
    if (search) {
      const searchLower = search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.symbol.toLowerCase().includes(searchLower) ||
          p.target_address.toLowerCase().includes(searchLower) ||
          (p.target_name && p.target_name.toLowerCase().includes(searchLower))
      );
    }

    // 方向筛选
    if (sideFilter !== "all") {
      filtered = filtered.filter((p) => p.side === sideFilter);
    }

    return filtered;
  }, [positions, search, sideFilter]);

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

  // 重置所有筛选
  const handleReset = () => {
    setSearch("");
    setSideFilter("all");
    setTargetFilter("all");
  };

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

  // 处理删除单个仓位按钮点击
  const handleDeleteClick = (address: string, symbol: string) => {
    setDeleteTarget({ address, symbol });
    onOpen();
  };

  // 处理清空目标所有仓位按钮点击
  const handleClearTargetClick = (address: string) => {
    setDeleteTarget({ address });
    onOpen();
  };

  useEffect(() => {
    fetchPositions();
  }, [fetchPositions]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return (
    <DefaultLayout>
      <div className="container mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent">
              仓位管理
            </h1>
            <p className="text-default-500">
              管理跟单仓位状态（用于重启后恢复）
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              color="danger"
              startContent={<Icon icon="solar:trash-bin-trash-linear" width={18} />}
              variant="flat"
              onPress={() => setClearAllOpen(true)}
            >
              清空全部
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
              刷新
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <StatsCards stats={stats} loading={statsLoading} />

        {/* Filters */}
        <PositionFilters
          search={search}
          onSearchChange={setSearch}
          sideFilter={sideFilter}
          onSideFilterChange={setSideFilter}
          targetFilter={targetFilter}
          onTargetFilterChange={setTargetFilter}
          stats={stats}
          onReset={handleReset}
        />

        {/* 显示筛选结果数量 */}
        {!loading && (
          <div className="mb-4 text-sm text-default-500">
            显示 {filteredPositions.length} / {positions.length} 条仓位记录
          </div>
        )}

        {/* Positions Table */}
        <PositionsTable
          positions={filteredPositions}
          loading={loading}
          onDeletePosition={handleDeleteClick}
          onClearTarget={handleClearTargetClick}
        />

        {/* Delete Confirmation Modal */}
        <DeleteConfirmModal
          isOpen={isOpen}
          onClose={onClose}
          onConfirm={handleDeletePosition}
          deleteTarget={deleteTarget}
        />

        {/* Clear All Confirmation Modal */}
        <ClearAllModal
          isOpen={clearAllOpen}
          onClose={() => setClearAllOpen(false)}
          onConfirm={handleClearAll}
        />
      </div>
    </DefaultLayout>
  );
}
