import { useState, useEffect } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Input,
  Switch,
  Divider,
} from "@heroui/react";
import type { PositionTracking } from "@/services/api";

interface TrackingFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  tracking: PositionTracking | null;
  onSave: (data: Partial<PositionTracking>) => Promise<void>;
}

export default function TrackingFormModal({
  isOpen,
  onClose,
  tracking,
  onSave,
}: TrackingFormModalProps) {
  // 表单数据 - copy_ratio 和 slippage 内部以百分比形式存储（显示用）
  const [formData, setFormData] = useState({
    copy_ratio_percent: 10, // 显示用：10 表示 10%
    max_position_size_usd: 500,
    min_position_size_usd: 20,
    copy_leverage: true,
    max_leverage: 10,
    default_leverage: 5,
    slippage_percent: 1, // 显示用：1 表示 1%
    auto_replenish: false,
    replenish_ratio_percent: 50, // 显示用：50 表示 50%
    replenish_min_value_usd: 10,
    replenish_max_value_usd: 100,
    take_profit_enabled: false,
    take_profit_percent: 50,
    stop_loss_enabled: false,
    stop_loss_percent: 20,
  });
  const [saving, setSaving] = useState(false);

  // 当 tracking 变化时更新表单（将小数转为百分比显示）
  useEffect(() => {
    if (tracking) {
      setFormData({
        copy_ratio_percent: (tracking.copy_ratio || 0.1) * 100,
        max_position_size_usd: tracking.max_position_size_usd,
        min_position_size_usd: tracking.min_position_size_usd,
        copy_leverage: tracking.copy_leverage,
        max_leverage: tracking.max_leverage,
        default_leverage: tracking.default_leverage,
        slippage_percent: (tracking.slippage || 0.01) * 100,
        auto_replenish: tracking.auto_replenish || false,
        replenish_ratio_percent: (tracking.replenish_ratio || 0.5) * 100,
        replenish_min_value_usd: tracking.replenish_min_value_usd || 10,
        replenish_max_value_usd: tracking.replenish_max_value_usd || 100,
        take_profit_enabled: tracking.take_profit_enabled || false,
        take_profit_percent: tracking.take_profit_percent ?? 50,
        stop_loss_enabled: tracking.stop_loss_enabled || false,
        stop_loss_percent: tracking.stop_loss_percent ?? 20,
      });
    }
  }, [tracking]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // 将百分比转换回小数再保存
      await onSave({
        copy_ratio: formData.copy_ratio_percent / 100,
        max_position_size_usd: formData.max_position_size_usd,
        min_position_size_usd: formData.min_position_size_usd,
        copy_leverage: formData.copy_leverage,
        max_leverage: formData.max_leverage,
        default_leverage: formData.default_leverage,
        slippage: formData.slippage_percent / 100,
        auto_replenish: formData.auto_replenish,
        replenish_ratio: formData.replenish_ratio_percent / 100,
        replenish_min_value_usd: formData.replenish_min_value_usd,
        replenish_max_value_usd: formData.replenish_max_value_usd,
        take_profit_enabled: formData.take_profit_enabled,
        take_profit_percent: formData.take_profit_percent,
        stop_loss_enabled: formData.stop_loss_enabled,
        stop_loss_percent: formData.stop_loss_percent,
      });
    } finally {
      setSaving(false);
    }
  };

  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  if (!tracking) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl" scrollBehavior="inside">
      <ModalContent>
        <ModalHeader className="flex flex-col gap-1">
          编辑仓位跟单配置
          <span className="text-sm text-default-500 font-normal">
            {tracking.symbol} - {tracking.target_name || formatAddress(tracking.target_address)}
          </span>
        </ModalHeader>
        <ModalBody>
          <div className="flex flex-col gap-4">
            {/* 基本信息（只读） */}
            <div className="bg-default-100 rounded-lg p-4 space-y-2">
              <div className="flex justify-between">
                <span className="text-default-500">目标地址</span>
                <span className="font-mono">{formatAddress(tracking.target_address)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-default-500">币种</span>
                <span className="font-semibold">{tracking.symbol}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-default-500">状态</span>
                <span>{tracking.status}</span>
              </div>
            </div>

            <Divider />

            {/* 跟单比例和滑点（百分比显示） */}
            <div className="grid grid-cols-2 gap-4">
              <Input
                type="number"
                label="跟单比例"
                description="按目标仓位的比例跟单"
                value={String(formData.copy_ratio_percent)}
                onValueChange={(value) => setFormData({ ...formData, copy_ratio_percent: parseFloat(value) || 0 })}
                endContent={<span className="text-default-400">%</span>}
              />
              <Input
                type="number"
                label="滑点容忍度"
                description="下单时的滑点设置"
                value={String(formData.slippage_percent)}
                onValueChange={(value) => setFormData({ ...formData, slippage_percent: parseFloat(value) || 0 })}
                endContent={<span className="text-default-400">%</span>}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Input
                type="number"
                label="最小仓位 (USD)"
                value={String(formData.min_position_size_usd)}
                onValueChange={(value) => setFormData({ ...formData, min_position_size_usd: parseFloat(value) || 0 })}
                startContent={<span className="text-default-400">$</span>}
              />
              <Input
                type="number"
                label="最大仓位 (USD)"
                value={String(formData.max_position_size_usd)}
                onValueChange={(value) => setFormData({ ...formData, max_position_size_usd: parseFloat(value) || 0 })}
                startContent={<span className="text-default-400">$</span>}
              />
            </div>

            <Divider />

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">复制杠杆</p>
                <p className="text-sm text-default-500">跟随目标交易员的杠杆倍数</p>
              </div>
              <Switch
                isSelected={formData.copy_leverage}
                onValueChange={(value) => setFormData({ ...formData, copy_leverage: value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Input
                type="number"
                label="最大杠杆"
                description="复制杠杆时的上限"
                value={String(formData.max_leverage)}
                onValueChange={(value) => setFormData({ ...formData, max_leverage: parseInt(value) || 1 })}
                isDisabled={!formData.copy_leverage}
                endContent={<span className="text-default-400">×</span>}
              />
              <Input
                type="number"
                label="默认杠杆"
                description="不复制杠杆时使用"
                value={String(formData.default_leverage)}
                onValueChange={(value) => setFormData({ ...formData, default_leverage: parseInt(value) || 1 })}
                isDisabled={formData.copy_leverage}
                endContent={<span className="text-default-400">×</span>}
              />
            </div>

            <Divider />

            {/* 自动补仓配置 */}
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">自动补仓</p>
                <p className="text-sm text-default-500">当目标加仓时自动跟随补仓</p>
              </div>
              <Switch
                isSelected={formData.auto_replenish}
                onValueChange={(value) => setFormData({ ...formData, auto_replenish: value })}
              />
            </div>

            {formData.auto_replenish && (
              <div className="space-y-4">
                <Input
                  type="number"
                  label="补仓比例"
                  description="按目标补仓量的比例跟随补仓"
                  value={String(formData.replenish_ratio_percent)}
                  onValueChange={(value) => setFormData({ ...formData, replenish_ratio_percent: parseFloat(value) || 0 })}
                  endContent={<span className="text-default-400">%</span>}
                />
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    type="number"
                    label="补仓最小价值 (USD)"
                    description="单次补仓最小金额"
                    value={String(formData.replenish_min_value_usd)}
                    onValueChange={(value) => setFormData({ ...formData, replenish_min_value_usd: parseFloat(value) || 0 })}
                    startContent={<span className="text-default-400">$</span>}
                  />
                  <Input
                    type="number"
                    label="补仓最大价值 (USD)"
                    description="单次补仓最大金额"
                    value={String(formData.replenish_max_value_usd)}
                    onValueChange={(value) => setFormData({ ...formData, replenish_max_value_usd: parseFloat(value) || 0 })}
                    startContent={<span className="text-default-400">$</span>}
                  />
                </div>
              </div>
            )}

            <Divider />

            {/* 止盈止损配置 */}
            <div className="grid grid-cols-2 gap-4">
              {/* 止盈 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Switch
                    size="sm"
                    isSelected={formData.take_profit_enabled}
                    onValueChange={(value) => setFormData({ ...formData, take_profit_enabled: value })}
                  />
                  <span className="text-sm">启用止盈</span>
                </div>
                {formData.take_profit_enabled && (
                  <Input
                    type="number"
                    label="止盈百分比"
                    size="sm"
                    value={String(formData.take_profit_percent)}
                    onValueChange={(value) => setFormData({ ...formData, take_profit_percent: parseFloat(value) || 50 })}
                    endContent={<span className="text-default-400 text-sm">%</span>}
                  />
                )}
              </div>
              {/* 止损 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Switch
                    size="sm"
                    isSelected={formData.stop_loss_enabled}
                    onValueChange={(value) => setFormData({ ...formData, stop_loss_enabled: value })}
                  />
                  <span className="text-sm">启用止损</span>
                </div>
                {formData.stop_loss_enabled && (
                  <Input
                    type="number"
                    label="止损百分比"
                    size="sm"
                    value={String(formData.stop_loss_percent)}
                    onValueChange={(value) => setFormData({ ...formData, stop_loss_percent: parseFloat(value) || 20 })}
                    endContent={<span className="text-default-400 text-sm">%</span>}
                  />
                )}
              </div>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onPress={onClose}>
            取消
          </Button>
          <Button color="primary" onPress={handleSave} isLoading={saving}>
            保存
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}