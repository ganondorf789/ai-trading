import { useState, useEffect, useCallback } from "react";
import { Button, addToast } from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { riskControlApi, DefaultCopyConfigRule } from "@/services/api";
import { ConfigRulesTable, ConfigRuleModal, DeleteConfirmModal } from "./components";

export default function DefaultConfigRulesPage() {
  const [rules, setRules] = useState<DefaultCopyConfigRule[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<DefaultCopyConfigRule | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  
  // Delete modal states
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deletingRule, setDeletingRule] = useState<DefaultCopyConfigRule | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // 加载规则列表
  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const response = await riskControlApi.getDefaultConfigRules();
      if (response.success && response.data) {
        setRules(response.data);
      }
    } catch (error) {
      console.error("Failed to load config rules:", error);
      addToast({ title: "加载配置规则失败", color: "danger" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  // 打开新增弹窗
  const handleAdd = () => {
    setEditingRule(null);
    setIsModalOpen(true);
  };

  // 打开编辑弹窗
  const handleEdit = (rule: DefaultCopyConfigRule) => {
    setEditingRule(rule);
    setIsModalOpen(true);
  };

  // 保存规则
  const handleSave = async (data: Partial<DefaultCopyConfigRule>) => {
    setIsSaving(true);
    try {
      let response;
      if (data.id) {
        response = await riskControlApi.updateDefaultConfigRule(data.id, data);
      } else {
        response = await riskControlApi.createDefaultConfigRule({
          name: data.name || "",
          description: data.description,
          leverage_min: data.leverage_min || 0,
          leverage_max: data.leverage_max || 100,
          config_data: data.config_data || {},
          priority: data.priority,
          is_enabled: data.is_enabled,
          is_default: data.is_default,
        });
      }
      
      if (response.success) {
        addToast({ title: response.message || "保存成功", color: "success" });
        setIsModalOpen(false);
        loadRules();
      } else {
        addToast({ title: response.error || "保存失败", color: "danger" });
      }
    } catch (error) {
      console.error("Failed to save config rule:", error);
      addToast({ title: "保存配置规则失败", color: "danger" });
    } finally {
      setIsSaving(false);
    }
  };

  // 切换启用状态
  const handleToggleEnabled = async (rule: DefaultCopyConfigRule, enabled: boolean) => {
    try {
      const response = await riskControlApi.updateDefaultConfigRule(rule.id!, {
        ...rule,
        is_enabled: enabled,
      });
      
      if (response.success) {
        addToast({ title: enabled ? "已启用" : "已禁用", color: "success" });
        loadRules();
      } else {
        addToast({ title: response.error || "更新失败", color: "danger" });
      }
    } catch (error) {
      console.error("Failed to toggle rule:", error);
      addToast({ title: "更新状态失败", color: "danger" });
    }
  };

  // 打开删除确认
  const handleDeleteClick = (rule: DefaultCopyConfigRule) => {
    setDeletingRule(rule);
    setIsDeleteModalOpen(true);
  };

  // 确认删除
  const handleDeleteConfirm = async () => {
    if (!deletingRule?.id) return;
    
    setIsDeleting(true);
    try {
      const response = await riskControlApi.deleteDefaultConfigRule(deletingRule.id);
      if (response.success) {
        addToast({ title: "删除成功", color: "success" });
        setIsDeleteModalOpen(false);
        setDeletingRule(null);
        loadRules();
      } else {
        addToast({ title: response.error || "删除失败", color: "danger" });
      }
    } catch (error) {
      console.error("Failed to delete config rule:", error);
      addToast({ title: "删除配置规则失败", color: "danger" });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6">
        {/* 标题栏 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Icon icon="lucide:copy" width={28} />
              默认跟单配置规则
            </h1>
            <p className="text-default-500 mt-1">
              根据目标杠杆匹配不同的跟单配置，优先级数字越小越先匹配
            </p>
          </div>
          <Button
            color="primary"
            startContent={<Icon icon="lucide:plus" width={18} />}
            onPress={handleAdd}
          >
            新增规则
          </Button>
        </div>

        {/* 规则表格 */}
        <ConfigRulesTable
          rules={rules}
          loading={loading}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
          onToggleEnabled={handleToggleEnabled}
        />

        {/* 编辑弹窗 */}
        <ConfigRuleModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSave={handleSave}
          editingRule={editingRule}
          isSaving={isSaving}
        />

        {/* 删除确认弹窗 */}
        <DeleteConfirmModal
          isOpen={isDeleteModalOpen}
          onClose={() => {
            setIsDeleteModalOpen(false);
            setDeletingRule(null);
          }}
          onConfirm={handleDeleteConfirm}
          ruleName={deletingRule?.name || ""}
          isDeleting={isDeleting}
        />
      </div>
    </DefaultLayout>
  );
}
