import { useState, useEffect } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Button,
  Switch,
  Checkbox,
  CheckboxGroup,
} from "@heroui/react";
import { AddressTracking } from "@/services/api";

interface TrackingFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  tracking: AddressTracking | null;
  onSave: (data: Partial<AddressTracking>) => void;
  initialAddress?: string;
}

const MONITOR_EVENTS = [
  { value: "open", label: "开仓" },
  { value: "close", label: "平仓" },
  { value: "add", label: "加仓" },
  { value: "reduce", label: "减仓" },
];

export default function TrackingFormModal({
  isOpen,
  onClose,
  tracking,
  onSave,
  initialAddress,
}: TrackingFormModalProps) {
  const [formData, setFormData] = useState<Partial<AddressTracking>>({
    tracking_address: "",
    address_remark: "",
    is_enabled: true,
    enable_notification: true,
    monitor_events: ["open", "close", "add", "reduce"],
  });

  // 当编辑时填充表单数据
  useEffect(() => {
    if (tracking) {
      setFormData({
        tracking_address: tracking.tracking_address,
        address_remark: tracking.address_remark,
        is_enabled: tracking.is_enabled,
        enable_notification: tracking.enable_notification,
        monitor_events: tracking.monitor_events,
      });
    } else {
      setFormData({
        tracking_address: initialAddress || "",
        address_remark: "",
        is_enabled: true,
        enable_notification: true,
        monitor_events: ["open", "close", "add", "reduce"],
      });
    }
  }, [tracking, isOpen, initialAddress]);

  const handleSave = () => {
    onSave(formData);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="lg">
      <ModalContent>
        <ModalHeader>{tracking ? "编辑地址跟踪" : "添加地址跟踪"}</ModalHeader>
        <ModalBody>
          <div className="flex flex-col gap-4">
            {/* 跟踪地址 */}
            <Input
              label="跟踪地址"
              placeholder="0x..."
              value={formData.tracking_address || ""}
              onValueChange={(v) => setFormData({ ...formData, tracking_address: v })}
              isDisabled={!!tracking || !!initialAddress}
              description={tracking ? "地址不可修改" : initialAddress ? "地址已自动填充" : "输入要跟踪的以太坊地址"}
            />

            {/* 地址备注 */}
            <Input
              label="地址备注"
              placeholder="如：大佬A、KOL..."
              value={formData.address_remark || ""}
              onValueChange={(v) => setFormData({ ...formData, address_remark: v })}
              description="方便识别的备注名称"
            />

            {/* 监控事件 */}
            <div className="space-y-2">
              <p className="text-sm font-medium">监控事件</p>
              <CheckboxGroup
                orientation="horizontal"
                value={formData.monitor_events || []}
                onValueChange={(v) => setFormData({ ...formData, monitor_events: v as ('open' | 'close' | 'add' | 'reduce')[] })}
              >
                {MONITOR_EVENTS.map((event) => (
                  <Checkbox key={event.value} value={event.value}>
                    {event.label}
                  </Checkbox>
                ))}
              </CheckboxGroup>
              <p className="text-xs text-default-400">选择需要监控的交易事件类型</p>
            </div>

            {/* 开关选项 */}
            <div className="flex flex-col gap-3 mt-2">
              <Switch
                isSelected={formData.is_enabled}
                onValueChange={(v) => setFormData({ ...formData, is_enabled: v })}
              >
                <div className="flex flex-col">
                  <span>启用跟踪</span>
                  <span className="text-xs text-default-400">开启后将持续监控该地址的交易活动</span>
                </div>
              </Switch>

              <Switch
                isSelected={formData.enable_notification}
                onValueChange={(v) => setFormData({ ...formData, enable_notification: v })}
              >
                <div className="flex flex-col">
                  <span>开启通知</span>
                  <span className="text-xs text-default-400">当检测到交易活动时发送通知</span>
                </div>
              </Switch>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose}>
            取消
          </Button>
          <Button
            color="primary"
            onPress={handleSave}
            isDisabled={!formData.tracking_address?.trim()}
          >
            保存
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
