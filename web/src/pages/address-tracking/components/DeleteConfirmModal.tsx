import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { AddressTracking } from "@/services/api";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  tracking: AddressTracking | null;
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
    <Modal isOpen={isOpen} onClose={onClose} size="sm">
      <ModalContent>
        <ModalHeader className="flex items-center gap-2">
          <Icon icon="lucide:alert-triangle" className="text-danger" width={20} />
          确认删除
        </ModalHeader>
        <ModalBody>
          {tracking && (
            <p>
              确定要删除地址 <span className="font-mono font-semibold text-danger">
                {tracking.address_remark || formatAddress(tracking.tracking_address)}
              </span> 的跟踪记录吗？
            </p>
          )}
          <p className="text-sm text-default-500 mt-2">此操作无法撤销。</p>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose}>
            取消
          </Button>
          <Button color="danger" onPress={onConfirm}>
            删除
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
