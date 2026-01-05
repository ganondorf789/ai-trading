import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter, Button } from "@heroui/react";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  deleteTarget: { address: string; symbol?: string } | null;
}

export function DeleteConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  deleteTarget,
}: DeleteConfirmModalProps) {
  const formatAddress = (address: string) => {
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  return (
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
          <Button color="danger" onPress={onConfirm}>
            Delete
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
