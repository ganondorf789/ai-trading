import { useState, useEffect, useCallback } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  Input,
  Button,
  Spinner,
  Divider,
  addToast,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import DefaultLayout from "@/layouts/default";
import { riskControlApi, RiskControlConfig } from "@/services/api";

// 默认配置
const defaultConfig: RiskControlConfig = {
  max_total_positions: 10,
  max_daily_trades: 50,
  max_single_loss_usd: 100.0,
  max_daily_loss_usd: 500.0,
  max_drawdown_pct: 10.0,
  max_margin_usage_pct: 80.0,
  pause_on_consecutive_losses: 5,
  max_order_retries: 3,
  retry_base_delay: 1.0,
};

// 配置字段信息
const configFields = [
  {
    category: "仓位限制",
    icon: "lucide:layers",
    fields: [
      {
        key: "max_total_positions",
        label: "最大持仓数量",
        description: "同时持有的最大仓位数量",
        type: "number",
        min: 1,
        max: 100,
        step: 1,
        unit: "个",
      },
      {
        key: "max_daily_trades",
        label: "每日最大交易次数",
        description: "每天允许的最大交易次数",
        type: "number",
        min: 1,
        max: 1000,
        step: 1,
        unit: "次",
      },
    ],
  },
  {
    category: "止损设置",
    icon: "lucide:shield-alert",
    fields: [
      {
        key: "max_single_loss_usd",
        label: "单笔最大亏损",
        description: "单笔交易允许的最大亏损金额",
        type: "number",
        min: 0,
        max: 100000,
        step: 10,
        unit: "USD",
      },
      {
        key: "max_daily_loss_usd",
        label: "每日最大亏损",
        description: "每天允许的最大累计亏损金额，超过后暂停交易",
        type: "number",
        min: 0,
        max: 1000000,
        step: 100,
        unit: "USD",
      },
      {
        key: "max_drawdown_pct",
        label: "最大回撤",
        description: "允许的最大回撤百分比",
        type: "number",
        min: 0,
        max: 100,
        step: 1,
        unit: "%",
      },
    ],
  },
  {
    category: "资金管理",
    icon: "lucide:wallet",
    fields: [
      {
        key: "max_margin_usage_pct",
        label: "最大保证金使用率",
        description: "保证金使用率上限，超过后不开新仓",
        type: "number",
        min: 0,
        max: 100,
        step: 5,
        unit: "%",
      },
    ],
  },
  {
    category: "暂停条件",
    icon: "lucide:pause-circle",
    fields: [
      {
        key: "pause_on_consecutive_losses",
        label: "连续亏损暂停阈值",
        description: "连续亏损达到此次数后暂停交易",
        type: "number",
        min: 1,
        max: 100,
        step: 1,
        unit: "次",
      },
    ],
  },
  {
    category: "订单重试",
    icon: "lucide:refresh-cw",
    fields: [
      {
        key: "max_order_retries",
        label: "订单最大重试次数",
        description: "订单失败后的最大重试次数",
        type: "number",
        min: 0,
        max: 10,
        step: 1,
        unit: "次",
      },
      {
        key: "retry_base_delay",
        label: "重试基础延迟",
        description: "订单重试的基础延迟时间（指数退避）",
        type: "number",
        min: 0.1,
        max: 60,
        step: 0.5,
        unit: "秒",
      },
    ],
  },
];

export default function RiskControlPage() {
  const [config, setConfig] = useState<RiskControlConfig>(defaultConfig);
  const [originalConfig, setOriginalConfig] = useState<RiskControlConfig>(defaultConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // 加载配置
  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const response = await riskControlApi.getConfig();
      if (response.success && response.data) {
        const loadedConfig = { ...defaultConfig, ...response.data };
        setConfig(loadedConfig);
        setOriginalConfig(loadedConfig);
        setHasChanges(false);
      }
    } catch (error) {
      console.error("Failed to load risk control config:", error);
      addToast({ title: "加载配置失败", color: "danger" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // 检查是否有变更
  useEffect(() => {
    const changed = JSON.stringify(config) !== JSON.stringify(originalConfig);
    setHasChanges(changed);
  }, [config, originalConfig]);

  // 更新配置字段
  const handleFieldChange = (key: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setConfig((prev) => ({
      ...prev,
      [key]: numValue,
    }));
  };

  // 保存配置
  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await riskControlApi.updateConfig(config);
      if (response.success) {
        setOriginalConfig(config);
        setHasChanges(false);
        addToast({ title: response.message || "保存成功", color: "success" });
      } else {
        addToast({ title: response.error || "保存失败", color: "danger" });
      }
    } catch (error) {
      console.error("Failed to save risk control config:", error);
      addToast({ title: "保存配置失败", color: "danger" });
    } finally {
      setSaving(false);
    }
  };

  // 重置为默认值
  const handleResetToDefault = () => {
    setConfig(defaultConfig);
  };

  // 撤销更改
  const handleCancel = () => {
    setConfig(originalConfig);
  };

  if (loading) {
    return (
      <DefaultLayout>
        <div className="flex justify-center items-center min-h-[400px]">
          <Spinner size="lg" />
        </div>
      </DefaultLayout>
    );
  }

  return (
    <DefaultLayout>
      <div className="flex flex-col gap-6 max-w-4xl mx-auto">
        {/* 标题栏 */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Icon icon="lucide:shield-check" width={28} />
              风控配置
            </h1>
            <p className="text-default-500 mt-1">
              配置跟单交易的风险控制参数，保护账户安全
            </p>
          </div>
          <div className="flex gap-2">
            {hasChanges && (
              <>
                <Button
                  variant="flat"
                  onPress={handleCancel}
                  startContent={<Icon icon="lucide:x" width={18} />}
                >
                  撤销
                </Button>
                <Button
                  variant="flat"
                  color="warning"
                  onPress={handleResetToDefault}
                  startContent={<Icon icon="lucide:rotate-ccw" width={18} />}
                >
                  重置默认
                </Button>
              </>
            )}
            <Button
              color="primary"
              isDisabled={!hasChanges}
              isLoading={saving}
              onPress={handleSave}
              startContent={!saving && <Icon icon="lucide:save" width={18} />}
            >
              保存配置
            </Button>
          </div>
        </div>

        {/* 变更提示 */}
        {hasChanges && (
          <div className="flex items-center gap-2 p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg border border-warning-200 dark:border-warning-800">
            <Icon icon="lucide:alert-triangle" width={20} className="text-warning" />
            <span className="text-warning-700 dark:text-warning-400">
              配置已修改，请记得保存更改
            </span>
          </div>
        )}

        {/* 配置表单 */}
        <div className="grid gap-6">
          {configFields.map((category) => (
            <Card key={category.category} className="shadow-sm">
              <CardHeader className="flex gap-3 pb-0">
                <div className="flex items-center gap-2">
                  <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
                    <Icon icon={category.icon} width={20} className="text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold">{category.category}</h3>
                </div>
              </CardHeader>
              <CardBody className="gap-4">
                <div className="grid gap-4 md:grid-cols-2">
                  {category.fields.map((field) => (
                    <div key={field.key} className="space-y-1">
                      <Input
                        type="number"
                        label={field.label}
                        description={field.description}
                        value={String(config[field.key as keyof RiskControlConfig])}
                        onValueChange={(value) => handleFieldChange(field.key, value)}
                        min={field.min}
                        max={field.max}
                        step={field.step}
                        endContent={
                          <span className="text-default-400 text-sm">{field.unit}</span>
                        }
                        classNames={{
                          label: "font-medium",
                          description: "text-xs",
                        }}
                      />
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
          ))}
        </div>

        {/* 说明卡片 */}
        <Card className="shadow-sm bg-default-50 dark:bg-default-100/5">
          <CardBody className="gap-3">
            <div className="flex items-center gap-2">
              <Icon icon="lucide:info" width={20} className="text-primary" />
              <h4 className="font-semibold">风控说明</h4>
            </div>
            <Divider />
            <ul className="space-y-2 text-sm text-default-600">
              <li className="flex items-start gap-2">
                <Icon icon="lucide:check" width={16} className="text-success mt-0.5" />
                <span>
                  <strong>仓位限制</strong>：控制同时持有的仓位数量和每日交易频率，避免过度交易
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Icon icon="lucide:check" width={16} className="text-success mt-0.5" />
                <span>
                  <strong>止损设置</strong>：设置单笔和每日亏损上限，当达到阈值时自动停止交易
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Icon icon="lucide:check" width={16} className="text-success mt-0.5" />
                <span>
                  <strong>资金管理</strong>：限制保证金使用率，保留足够的缓冲资金应对市场波动
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Icon icon="lucide:check" width={16} className="text-success mt-0.5" />
                <span>
                  <strong>暂停条件</strong>：连续亏损达到阈值后暂停交易，避免情绪化操作
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Icon icon="lucide:check" width={16} className="text-success mt-0.5" />
                <span>
                  <strong>订单重试</strong>：订单失败时自动重试，使用指数退避策略避免频繁请求
                </span>
              </li>
            </ul>
          </CardBody>
        </Card>

        {/* 底部操作栏（移动端友好） */}
        <div className="sticky bottom-4 md:hidden">
          {hasChanges && (
            <div className="flex gap-2 p-3 bg-background/80 backdrop-blur-lg rounded-lg border shadow-lg">
              <Button
                variant="flat"
                className="flex-1"
                onPress={handleCancel}
              >
                撤销
              </Button>
              <Button
                color="primary"
                className="flex-1"
                isLoading={saving}
                onPress={handleSave}
              >
                保存
              </Button>
            </div>
          )}
        </div>
      </div>
    </DefaultLayout>
  );
}
