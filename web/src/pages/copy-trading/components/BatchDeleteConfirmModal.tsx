import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
} from "@heroui/react";
import { Icon } from "@iconify/react";

interface BatchDeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  selectedCount: number;
}

export default function BatchDeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  selectedCount,
}: BatchDeleteConfirmModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm">
      <ModalContent>
        <ModalHeader className="flex items-center gap-2">
          <Icon icon="lucide:alert-triangle" className="text-danger" width={20} />
          确认批量删除
        </ModalHeader>
        <ModalBody>
          <p>确定要删除选中的 <strong>{selectedCount}</strong> 个跟单地址吗？此操作无法撤销。</p>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose}>
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
