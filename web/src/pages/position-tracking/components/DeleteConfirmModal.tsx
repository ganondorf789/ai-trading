import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import type { PositionTracking } from "@/services/api";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void>;
  tracking: PositionTracking | null;
}

export default function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  tracking,
}: DeleteConfirmModalProps) {
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="md">
      <ModalContent>
        <ModalHeader className="flex items-center gap-2">
          <Icon icon="lucide:alert-triangle" className="text-danger" width={24} />
          确认删除
        </ModalHeader>
        <ModalBody>
          {tracking && (
            <div className="space-y-2">
              <p>确定要删除以下仓位跟单记录吗？</p>
              <div className="bg-default-100 rounded-lg p-3 space-y-1">
                <div className="flex justify-between">
                  <span className="text-default-500">币种</span>
                  <span className="font-semibold">{tracking.symbol}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-default-500">目标</span>
                  <span className="font-mono">
                    {tracking.target_name || formatAddress(tracking.target_address)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-default-500">状态</span>
                  <span>{tracking.status}</span>
                </div>
              </div>
              <p className="text-sm text-danger">此操作无法撤销。</p>
            </div>
          )}
        </ModalBody>
        <ModalFooter>
          <Button variant="light" onPress={onClose}>
            取消
          </Button>
          <Button color="danger" onPress={onConfirm}>
            确认删除
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
