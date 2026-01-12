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
  const [formData, setFormData] = useState({
    target_name: "",
    copy_ratio: 0.1,
    max_position_size_usd: 500,
    min_position_size_usd: 20,
    copy_leverage: true,
    max_leverage: 10,
    default_leverage: 5,
    slippage: 0.01,
  });
  const [saving, setSaving] = useState(false);

  // 当 tracking 变化时更新表单
  useEffect(() => {
    if (tracking) {
      setFormData({
        target_name: tracking.target_name || "",
        copy_ratio: tracking.copy_ratio,
        max_position_size_usd: tracking.max_position_size_usd,
        min_position_size_usd: tracking.min_position_size_usd,
        copy_leverage: tracking.copy_leverage,
        max_leverage: tracking.max_leverage,
        default_leverage: tracking.default_leverage,
        slippage: tracking.slippage,
      });
    }
  }, [tracking]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(formData);
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

            {/* 可编辑的配置 */}
            <Input
              label="交易员名称"
              placeholder="可选，用于标识"
              value={formData.target_name}
              onValueChange={(value) => setFormData({ ...formData, target_name: value })}
            />

            <div className="grid grid-cols-2 gap-4">
              <Input
                type="number"
                label="跟单比例"
                description="按目标仓位的比例跟单"
                value={String(formData.copy_ratio)}
                onValueChange={(value) => setFormData({ ...formData, copy_ratio: parseFloat(value) || 0 })}
                endContent={<span className="text-default-400">×</span>}
              />
              <Input
                type="number"
                label="滑点容忍度"
                description="下单时的滑点设置"
                value={String(formData.slippage)}
                onValueChange={(value) => setFormData({ ...formData, slippage: parseFloat(value) || 0 })}
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
