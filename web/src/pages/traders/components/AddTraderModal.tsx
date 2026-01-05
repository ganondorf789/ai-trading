import { useState } from 'react';
import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter } from '@heroui/modal';
import { Input } from '@heroui/input';
import { Button } from '@heroui/button';
import { traderApi } from '@/services/api';

interface AddTraderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function AddTraderModal({ isOpen, onClose, onSuccess }: AddTraderModalProps) {
  const [newAddress, setNewAddress] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const handleAddTrader = async () => {
    if (!newAddress.trim()) {
      setAddError('请输入地址');
      return;
    }

    const address = newAddress.trim();
    if (!address.startsWith('0x') || address.length !== 42) {
      setAddError('无效的以太坊地址格式');
      return;
    }

    try {
      setAddLoading(true);
      setAddError(null);

      const response = await traderApi.addTrader({ address });
      if (response.success) {
        onClose();
        setNewAddress('');
        onSuccess();
      } else {
        setAddError(response.error || '添加失败');
      }
    } catch (err: any) {
      setAddError(err.message || '添加失败');
    } finally {
      setAddLoading(false);
    }
  };

  const handleClose = () => {
    setNewAddress('');
    setAddError(null);
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} placement="center">
      <ModalContent>
        <ModalHeader>新增交易者</ModalHeader>
        <ModalBody>
          <Input
            label="交易者地址"
            placeholder="0x..."
            value={newAddress}
            onValueChange={(v) => {
              setNewAddress(v);
              setAddError(null);
            }}
            isInvalid={!!addError}
            errorMessage={addError}
            description="输入 Hyperliquid 交易者的以太坊地址"
          />
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={handleClose}>
            取消
          </Button>
          <Button
            color="primary"
            onPress={handleAddTrader}
            isLoading={addLoading}
          >
            确认添加
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
