import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
} from "@heroui/react";
import { Icon } from "@iconify/react";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  ruleName: string;
  isDeleting: boolean;
}

export default function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  ruleName,
  isDeleting,
}: DeleteConfirmModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} size="sm">
      <ModalContent>
        <ModalHeader className="flex items-center gap-2">
          <Icon icon="lucide:alert-triangle" className="text-danger" width={20} />
          确认删除
        </ModalHeader>
        <ModalBody>
          <p>
            确定要删除配置规则 <strong>{ruleName}</strong> 吗？
          </p>
          <p className="text-sm text-default-500 mt-2">
            此操作不可撤销，删除后将使用其他规则或默认配置。
          </p>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose} isDisabled={isDeleting}>
            取消
          </Button>
          <Button color="danger" onPress={onConfirm} isLoading={isDeleting}>
            删除
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
