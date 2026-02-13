import { Drawer, DrawerContent, DrawerHeader, DrawerBody, DrawerFooter } from '@heroui/react';
import { Button } from '@heroui/button';
import { Select, SelectItem } from '@heroui/select';
import { Input } from '@heroui/input';
import { Icon } from '@iconify/react';
import { ADVANCED_FILTER_FIELDS, FILTER_OPERATORS } from '../constants';
import type { AdvancedFilterCondition } from '../types';

interface AdvancedFilterDrawerProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  conditions: AdvancedFilterCondition[];
  onConditionsChange: (conditions: AdvancedFilterCondition[]) => void;
  onApply: (conditions: AdvancedFilterCondition[]) => void;
}

export function AdvancedFilterDrawer({
  isOpen,
  onOpenChange,
  conditions,
  onConditionsChange,
  onApply,
}: AdvancedFilterDrawerProps) {
  const addCondition = () => {
    onConditionsChange([...conditions, { field: '', op: '>', value: undefined }]);
  };

  const removeCondition = (index: number) => {
    const next = conditions.filter((_, i) => i !== index);
    onConditionsChange(next.length ? next : [{ field: '', op: '>', value: undefined }]);
  };

  const updateCondition = (index: number, updates: Partial<AdvancedFilterCondition>) => {
    const next = [...conditions];
    next[index] = { ...next[index], ...updates };
    onConditionsChange(next);
  };

  const handleApply = () => {
    onApply(conditions);
    onOpenChange(false);
  };

  return (
    <Drawer
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      placement="right"
      size="md"
    >
      <DrawerContent>
        <DrawerHeader className="flex flex-col gap-1">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Icon icon="solar:filter-bold" width={20} />
            高级筛选
          </h3>
          <p className="text-xs text-default-400">添加条件筛选交易者</p>
        </DrawerHeader>

        <DrawerBody className="gap-4">
          {conditions.map((condition, index) => (
            <div key={index} className="flex items-end gap-2">
              <Select
                className="flex-1"
                label="字段"
                size="sm"
                placeholder="选择字段"
                selectedKeys={condition.field ? [condition.field] : []}
                onSelectionChange={(keys) => {
                  const field = Array.from(keys)[0] as string;
                  updateCondition(index, { field: field || '' });
                }}
              >
                {ADVANCED_FILTER_FIELDS.map(f => (
                  <SelectItem key={f.key} textValue={f.label}>{f.label}</SelectItem>
                ))}
              </Select>

              <Select
                className="w-[100px]"
                label="运算符"
                size="sm"
                selectedKeys={condition.op ? [condition.op] : []}
                onSelectionChange={(keys) => {
                  const op = Array.from(keys)[0] as string;
                  updateCondition(index, { op: op || '>' });
                }}
              >
                {FILTER_OPERATORS.map(op => (
                  <SelectItem key={op.key} textValue={op.label}>{op.label}</SelectItem>
                ))}
              </Select>

              {condition.op !== 'exist' ? (
                <Input
                  className="w-[110px]"
                  label="数值"
                  type="number"
                  size="sm"
                  placeholder="输入值"
                  value={condition.value?.toString() ?? ''}
                  onValueChange={(v) =>
                    updateCondition(index, { value: v ? parseFloat(v) : undefined })
                  }
                />
              ) : (
                <div className="w-[110px]" />
              )}

              <Button
                size="sm"
                variant="light"
                color="danger"
                isIconOnly
                className="shrink-0"
                onPress={() => removeCondition(index)}
              >
                <Icon icon="solar:trash-bin-trash-linear" width={16} />
              </Button>
            </div>
          ))}
        </DrawerBody>

        <DrawerFooter className="flex justify-between">
          <Button
            size="sm"
            variant="light"
            startContent={<Icon icon="solar:add-circle-linear" width={16} />}
            onPress={addCondition}
          >
            新增条件
          </Button>
          <Button
            size="sm"
            color="primary"
            variant="bordered"
            onPress={handleApply}
          >
            应用筛选
          </Button>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
