import { useState, useEffect, useMemo } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Button,
  Switch,
  Divider,
  Autocomplete,
  AutocompleteItem,
  Select,
  SelectItem,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { ImmediateCopyConfigRule, ImmediateCopyConfig, hyperliquidApi } from "@/services/api";

interface ConfigRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<ImmediateCopyConfigRule>) => void;
  editingRule: ImmediateCopyConfigRule | null;
  isSaving: boolean;
  existingSymbols?: string[];  // 已存在配置的币种列表
}

const defaultConfigData: Partial<ImmediateCopyConfig> = {
  copy_ratio: 0.1,
  max_position_size_usd: 500,
  min_position_size_usd: 20,
  max_leverage: 10,
  default_leverage: 3,
  slippage: 0.001,
  copy_leverage: false,
  margin_mode: 'cross',
  // 跟单行为
  copy_only_once: false,
  // 跟单条件
  min_trader_overall_score: 0,
  min_trader_leverage: 0,
  max_trader_leverage: 0,
  min_position_value_usd: 0,
  max_position_value_usd: 0,
  min_coin_price: 0,
  max_coin_price: 0,
  // 自动补仓
  auto_replenish: false,
  replenish_ratio: 0.5,
  replenish_min_value_usd: 10,
  replenish_max_value_usd: 100,
  take_profit_enabled: false,
  take_profit_percent: 50,
  stop_loss_enabled: false,
  stop_loss_percent: 20,
};

export default function ConfigRuleModal({
  isOpen,
  onClose,
  onSave,
  editingRule,
  isSaving,
  existingSymbols = [],
}: ConfigRuleModalProps) {
  // 基本信息
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [isEnabled, setIsEnabled] = useState(true);

  // 配置数据
  const [configData, setConfigData] = useState<Partial<ImmediateCopyConfig>>(defaultConfigData);

  // 币种选择
  const [availableCoins, setAvailableCoins] = useState<string[]>([]);

  // 加载币种列表
  useEffect(() => {
    const loadCoins = async () => {
      try {
        const response = await hyperliquidApi.getCoinNames();
        if (response.success && response.data) {
          setAvailableCoins(response.data);
        }
      } catch (error) {
        console.error("Failed to load coins:", error);
      }
    };
    if (isOpen) {
      loadCoins();
    }
  }, [isOpen]);

  // 初始化表单
  useEffect(() => {
    if (editingRule) {
      setName(editingRule.name);
      setSymbol(editingRule.symbol || "");
      setIsEnabled(editingRule.is_enabled);
      setConfigData({ ...defaultConfigData, ...editingRule.config_data });
    } else {
      setName("");
      setSymbol("");
      setIsEnabled(true);
      setConfigData(defaultConfigData);
    }
  }, [editingRule, isOpen]);

  // 过滤可选的币种（排除已存在配置的币种，但编辑时允许选择当前币种）
  const selectableCoins = useMemo(() => {
    return availableCoins.filter(
      (coin) => !existingSymbols.includes(coin) || coin === editingRule?.symbol
    );
  }, [availableCoins, existingSymbols, editingRule?.symbol]);

  const handleSave = () => {
    const data: Partial<ImmediateCopyConfigRule> = {
      name,
      symbol,
      is_enabled: isEnabled,
      config_data: configData,
    };
    if (editingRule?.id) {
      data.id = editingRule.id;
    }
    onSave(data);
  };

  // 验证：名称和币种都必须填写
  const isValid = name.trim().length > 0 && symbol.trim().length > 0;

  // 检查币种是否已存在配置
  const isSymbolDuplicate = Boolean(symbol && existingSymbols.includes(symbol) && symbol !== editingRule?.symbol);

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl" scrollBehavior="inside">
      <ModalContent>
        <ModalHeader>
          {editingRule ? "编辑配置规则" : "新增配置规则"}
        </ModalHeader>
        <ModalBody className="gap-6">
          {/* 基本信息 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:info" width={16} />
              基本信息
            </h4>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="规则名称"
                placeholder="例如：BTC 跟单配置"
                value={name}
                onValueChange={setName}
                isRequired
              />
              <Autocomplete
                label="币种"
                placeholder="选择币种"
                selectedKey={symbol}
                onSelectionChange={(key) => setSymbol(key as string || "")}
                isRequired
                isInvalid={isSymbolDuplicate}
                errorMessage={isSymbolDuplicate ? "该币种已存在配置" : undefined}
                description="每个币种最多只能有一个配置"
              >
                {selectableCoins.map((coin) => (
                  <AutocompleteItem key={coin}>
                    {coin}
                  </AutocompleteItem>
                ))}
              </Autocomplete>
            </div>
          </div>

          <Divider />

          {/* 跟单条件 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:filter" width={16} />
              跟单条件
            </h4>
            <p className="text-xs text-default-500">
              设置触发立即跟单的条件，符合以下所有条件时才会执行跟单
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                type="number"
                label="交易员最低评分"
                description="只跟单评分达到此值的交易员（0=不限制）"
                value={String(configData.min_trader_overall_score || 0)}
                onValueChange={(v) => setConfigData({ ...configData, min_trader_overall_score: parseFloat(v) || 0 })}
              />
              <Input
                type="number"
                label="目标最小杠杆"
                description="目标交易员杠杆>=此值时才跟单（0=不限制）"
                value={String(configData.min_trader_leverage || 0)}
                onValueChange={(v) => setConfigData({ ...configData, min_trader_leverage: parseFloat(v) || 0 })}
                endContent={<span className="text-default-400 text-sm">x</span>}
              />
              <Input
                type="number"
                label="目标最大杠杆"
                description="目标交易员杠杆<=此值时才跟单（0=不限制）"
                value={String(configData.max_trader_leverage || 0)}
                onValueChange={(v) => setConfigData({ ...configData, max_trader_leverage: parseFloat(v) || 0 })}
                endContent={<span className="text-default-400 text-sm">x</span>}
              />
              <Input
                type="number"
                label="最小仓位价值"
                description="目标仓位价值低于此值时不跟单（0=不限制）"
                value={String(configData.min_position_value_usd || 0)}
                onValueChange={(v) => setConfigData({ ...configData, min_position_value_usd: parseFloat(v) || 0 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
              />
              <Input
                type="number"
                label="最大仓位价值"
                description="目标仓位价值高于此值时不跟单（0=不限制）"
                value={String(configData.max_position_value_usd || 0)}
                onValueChange={(v) => setConfigData({ ...configData, max_position_value_usd: parseFloat(v) || 0 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
              />
              <Input
                type="number"
                label="币种最低价格"
                description="币种价格低于此值时不跟单（0=不限制）"
                value={String(configData.min_coin_price || 0)}
                onValueChange={(v) => setConfigData({ ...configData, min_coin_price: parseFloat(v) || 0 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
              />
              <Input
                type="number"
                label="币种最高价格"
                description="币种价格高于此值时不跟单（0=不限制）"
                value={String(configData.max_coin_price || 0)}
                onValueChange={(v) => setConfigData({ ...configData, max_coin_price: parseFloat(v) || 0 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
              />
            </div>
          </div>

          <Divider />

          {/* 跟单参数 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:copy" width={16} />
              跟单参数
            </h4>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                type="number"
                label="跟单比例"
                description="跟单目标仓位的百分比"
                value={String(((configData.copy_ratio || 0.1) * 100).toFixed(0))}
                onValueChange={(v) => setConfigData({ ...configData, copy_ratio: (parseFloat(v) || 10) / 100 })}
                endContent={<span className="text-default-400 text-sm">%</span>}
              />
              <Input
                type="number"
                label="滑点容忍度"
                value={String(((configData.slippage || 0.001) * 100).toFixed(2))}
                onValueChange={(v) => setConfigData({ ...configData, slippage: (parseFloat(v) || 0.1) / 100 })}
                endContent={<span className="text-default-400 text-sm">%</span>}
              />
              <Input
                type="number"
                label="最小仓位"
                value={String(configData.min_position_size_usd || 20)}
                onValueChange={(v) => setConfigData({ ...configData, min_position_size_usd: parseFloat(v) || 20 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
              />
              <Input
                type="number"
                label="最大仓位"
                value={String(configData.max_position_size_usd || 500)}
                onValueChange={(v) => setConfigData({ ...configData, max_position_size_usd: parseFloat(v) || 500 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
              />
              <Input
                type="number"
                label="最大杠杆"
                value={String(configData.max_leverage || 10)}
                onValueChange={(v) => setConfigData({ ...configData, max_leverage: parseInt(v) || 10 })}
                endContent={<span className="text-default-400 text-sm">x</span>}
              />
              <Input
                type="number"
                label="默认杠杆"
                value={String(configData.default_leverage || 3)}
                onValueChange={(v) => setConfigData({ ...configData, default_leverage: parseInt(v) || 3 })}
                endContent={<span className="text-default-400 text-sm">x</span>}
              />
              <Select
                label="保证金模式"
                selectedKeys={[configData.margin_mode || "cross"]}
                onSelectionChange={(keys) => {
                  const value = Array.from(keys)[0] as string;
                  if (value) setConfigData({ ...configData, margin_mode: value as 'cross' | 'isolated' });
                }}
                description="全仓共享保证金，逐仓独立保证金"
              >
                <SelectItem key="cross">全仓 (Cross)</SelectItem>
                <SelectItem key="isolated">逐仓 (Isolated)</SelectItem>
              </Select>
            </div>
          </div>

          <Divider />

          {/* 自动补仓配置 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:refresh-cw" width={16} />
              自动补仓
            </h4>
            <div className="flex items-center gap-2">
              <Switch
                size="sm"
                isSelected={configData.auto_replenish || false}
                onValueChange={(v) => setConfigData({ ...configData, auto_replenish: v })}
              />
              <span className="text-sm">启用自动补仓（当目标加仓时自动跟随补仓）</span>
            </div>
            {configData.auto_replenish && (
              <div className="grid gap-4 md:grid-cols-3">
                <Input
                  type="number"
                  label="补仓比例"
                  description="按目标补仓量的比例"
                  value={String(((configData.replenish_ratio || 0.5) * 100).toFixed(0))}
                  onValueChange={(v) => setConfigData({ ...configData, replenish_ratio: (parseFloat(v) || 50) / 100 })}
                  endContent={<span className="text-default-400 text-sm">%</span>}
                />
                <Input
                  type="number"
                  label="补仓最小价值"
                  description="单次补仓最小金额"
                  value={String(configData.replenish_min_value_usd || 10)}
                  onValueChange={(v) => setConfigData({ ...configData, replenish_min_value_usd: parseFloat(v) || 10 })}
                  startContent={<span className="text-default-400 text-sm">$</span>}
                />
                <Input
                  type="number"
                  label="补仓最大价值"
                  description="单次补仓最大金额"
                  value={String(configData.replenish_max_value_usd || 100)}
                  onValueChange={(v) => setConfigData({ ...configData, replenish_max_value_usd: parseFloat(v) || 100 })}
                  startContent={<span className="text-default-400 text-sm">$</span>}
                />
              </div>
            )}
          </div>

          <Divider />

          {/* 止盈止损配置 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:shield-check" width={16} />
              止盈止损
            </h4>
            <div className="grid grid-cols-2 gap-4">
              {/* 止盈 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Switch
                    size="sm"
                    isSelected={configData.take_profit_enabled || false}
                    onValueChange={(v) => setConfigData({ ...configData, take_profit_enabled: v })}
                  />
                  <span className="text-sm">启用止盈</span>
                </div>
                {configData.take_profit_enabled && (
                  <Input
                    type="number"
                    label="止盈百分比"
                    size="sm"
                    value={String(configData.take_profit_percent ?? 50)}
                    onValueChange={(v) => setConfigData({ ...configData, take_profit_percent: parseFloat(v) || 50 })}
                    endContent={<span className="text-default-400 text-sm">%</span>}
                  />
                )}
              </div>
              {/* 止损 */}
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Switch
                    size="sm"
                    isSelected={configData.stop_loss_enabled || false}
                    onValueChange={(v) => setConfigData({ ...configData, stop_loss_enabled: v })}
                  />
                  <span className="text-sm">启用止损</span>
                </div>
                {configData.stop_loss_enabled && (
                  <Input
                    type="number"
                    label="止损百分比"
                    size="sm"
                    value={String(configData.stop_loss_percent ?? 20)}
                    onValueChange={(v) => setConfigData({ ...configData, stop_loss_percent: parseFloat(v) || 20 })}
                    endContent={<span className="text-default-400 text-sm">%</span>}
                  />
                )}
              </div>
            </div>
          </div>

          <Divider />

          {/* 开关选项 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:toggle-left" width={16} />
              开关选项
            </h4>
            <div className="flex flex-wrap gap-6">
              <div className="flex items-center gap-2">
                <Switch size="sm" isSelected={isEnabled} onValueChange={setIsEnabled} />
                <span className="text-sm">启用规则</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  size="sm"
                  isSelected={configData.copy_leverage || false}
                  onValueChange={(v) => setConfigData({ ...configData, copy_leverage: v })}
                />
                <span className="text-sm">复制杠杆</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  size="sm"
                  isSelected={configData.copy_only_once || false}
                  onValueChange={(v) => setConfigData({ ...configData, copy_only_once: v })}
                />
                <span className="text-sm">只跟一次</span>
                <span className="text-xs text-default-400">（跟单后自动禁用规则）</span>
              </div>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose} isDisabled={isSaving}>
            取消
          </Button>
          <Button 
            color="primary" 
            onPress={handleSave} 
            isLoading={isSaving} 
            isDisabled={!isValid || isSymbolDuplicate}
          >
            保存
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
