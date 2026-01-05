import { useState } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Button,
  Tooltip,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { CopyTradingGroup } from "@/services/api";

// 预设分组颜色
const presetColors = [
  "#3B82F6", // 蓝色
  "#10B981", // 绿色
  "#F59E0B", // 橙色
  "#EF4444", // 红色
  "#8B5CF6", // 紫色
  "#EC4899", // 粉色
  "#06B6D4", // 青色
  "#84CC16", // 黄绿
  "#F97316", // 橘色
  "#6366F1", // 靛蓝
  "#14B8A6", // 蓝绿
  "#A855F7", // 紫罗兰
];

interface GroupManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  groups: CopyTradingGroup[];
  onSaveGroup: (data: { name: string; description: string; color: string }) => void;
  onEditGroup: (group: CopyTradingGroup) => void;
  onDeleteGroup: (groupId: number) => void;
  editingGroup: CopyTradingGroup | null;
  onCancelEdit: () => void;
}

export default function GroupManagementModal({
  isOpen,
  onClose,
  groups,
  onSaveGroup,
  onEditGroup,
  onDeleteGroup,
  editingGroup,
  onCancelEdit,
}: GroupManagementModalProps) {
  const [groupFormData, setGroupFormData] = useState({
    name: editingGroup?.name || "",
    description: editingGroup?.description || "",
    color: editingGroup?.color || "#3B82F6",
  });

  // 当 editingGroup 改变时更新表单数据
  useState(() => {
    if (editingGroup) {
      setGroupFormData({
        name: editingGroup.name,
        description: editingGroup.description || "",
        color: editingGroup.color || "#3B82F6",
      });
    } else {
      setGroupFormData({ name: "", description: "", color: "#3B82F6" });
    }
  });

  const handleSave = () => {
    onSaveGroup(groupFormData);
    setGroupFormData({ name: "", description: "", color: "#3B82F6" });
  };

  const handleCancelEdit = () => {
    onCancelEdit();
    setGroupFormData({ name: "", description: "", color: "#3B82F6" });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} scrollBehavior="inside">
      <ModalContent>
        <ModalHeader>分组管理</ModalHeader>
        <ModalBody className="max-h-[70vh] overflow-y-auto">
          {/* 现有分组列表 */}
          <div className="space-y-2 mb-4">
            {groups.map((group) => (
              <div
                key={group.id}
                className={`flex items-center justify-between p-2 border rounded transition-colors ${
                  editingGroup?.id === group.id ? "border-primary bg-primary-50" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-4 h-4 rounded"
                    style={{ backgroundColor: group.color }}
                  />
                  <span>{group.name}</span>
                  <span className="text-sm text-gray-500">({group.address_count || 0})</span>
                </div>
                <div className="flex gap-1">
                  <Tooltip content="编辑">
                    <Button
                      isIconOnly
                      size="sm"
                      variant="light"
                      color="primary"
                      onPress={() => onEditGroup(group)}
                    >
                      <Icon icon="lucide:edit" width={16} />
                    </Button>
                  </Tooltip>
                  {group.id !== 1 && (
                    <Tooltip content="删除">
                      <Button
                        isIconOnly
                        size="sm"
                        variant="light"
                        color="danger"
                        onPress={() => onDeleteGroup(group.id)}
                      >
                        <Icon icon="lucide:trash-2" width={16} />
                      </Button>
                    </Tooltip>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* 新建/编辑分组 */}
          <div className="border-t pt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium">
                {editingGroup ? "编辑分组" : "新建分组"}
              </h4>
              {editingGroup && (
                <Button
                  size="sm"
                  variant="flat"
                  onPress={handleCancelEdit}
                >
                  取消编辑
                </Button>
              )}
            </div>
            <div className="space-y-2">
              <Input
                label="分组名称"
                placeholder="输入分组名称"
                value={groupFormData.name}
                onValueChange={(v) => setGroupFormData({ ...groupFormData, name: v })}
              />
              <Input
                label="描述"
                placeholder="可选的描述"
                value={groupFormData.description}
                onValueChange={(v) => setGroupFormData({ ...groupFormData, description: v })}
              />
              <div className="space-y-2">
                <label className="text-sm text-default-600">颜色</label>
                <div className="grid grid-cols-6 gap-2">
                  {presetColors.map((color) => (
                    <div
                      key={color}
                      className={`w-8 h-8 rounded-lg cursor-pointer transition-all ${
                        groupFormData.color === color
                          ? "ring-2 ring-offset-2 ring-primary scale-110"
                          : "hover:scale-105"
                      }`}
                      style={{ backgroundColor: color }}
                      onClick={() => setGroupFormData({ ...groupFormData, color })}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={() => {
            onClose();
            handleCancelEdit();
          }}>
            关闭
          </Button>
          <Button
            color="primary"
            onPress={handleSave}
            isDisabled={!groupFormData.name}
          >
            {editingGroup ? "更新分组" : "创建分组"}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
