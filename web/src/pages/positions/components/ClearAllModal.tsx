import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button } from "@heroui/react";

interface ClearAllModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function ClearAllModal({ isOpen, onClose, onConfirm }: ClearAllModalProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
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
          <Button variant="flat" onPress={onClose}>
            Cancel
          </Button>
          <Button color="danger" onPress={onConfirm}>
            Clear All
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
