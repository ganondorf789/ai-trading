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
  Chip,
  Divider,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { DefaultCopyConfigRule, DefaultCopyTradingConfig, hyperliquidApi } from "@/services/api";

interface ConfigRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: Partial<DefaultCopyConfigRule>) => void;
  editingRule: DefaultCopyConfigRule | null;
  isSaving: boolean;
}

const defaultConfigData: Partial<DefaultCopyTradingConfig> = {
  copy_ratio: 0.1,
  max_position_size_usd: 500,
  min_position_size_usd: 20,
  max_leverage: 10,
  default_leverage: 3,
  slippage: 0.001,
  copy_leverage: false,
  symbols_whitelist: [],
  symbols_blacklist: [],
};

export default function ConfigRuleModal({
  isOpen,
  onClose,
  onSave,
  editingRule,
  isSaving,
}: ConfigRuleModalProps) {
  // 基本信息
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [leverageMin, setLeverageMin] = useState(0);
  const [leverageMax, setLeverageMax] = useState(100);
  const [priority, setPriority] = useState(0);
  const [isEnabled, setIsEnabled] = useState(true);
  const [isDefault, setIsDefault] = useState(false);

  // 配置数据
  const [configData, setConfigData] = useState<Partial<DefaultCopyTradingConfig>>(defaultConfigData);

  // 币种选择
  const [availableCoins, setAvailableCoins] = useState<string[]>([]);
  const [whitelistInput, setWhitelistInput] = useState("");
  const [blacklistInput, setBlacklistInput] = useState("");
  const [whitelistHighlightIndex, setWhitelistHighlightIndex] = useState(-1);
  const [blacklistHighlightIndex, setBlacklistHighlightIndex] = useState(-1);

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
      setDescription(editingRule.description || "");
      setLeverageMin(editingRule.leverage_min);
      setLeverageMax(editingRule.leverage_max);
      setPriority(editingRule.priority);
      setIsEnabled(editingRule.is_enabled);
      setIsDefault(editingRule.is_default);
      setConfigData({ ...defaultConfigData, ...editingRule.config_data });
    } else {
      setName("");
      setDescription("");
      setLeverageMin(0);
      setLeverageMax(100);
      setPriority(0);
      setIsEnabled(true);
      setIsDefault(false);
      setConfigData(defaultConfigData);
    }
    setWhitelistInput("");
    setBlacklistInput("");
  }, [editingRule, isOpen]);

  // 过滤可用币种
  const filteredWhitelistCoins = useMemo(() => {
    const input = whitelistInput.trim().toUpperCase();
    const existing = configData.symbols_whitelist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, whitelistInput, configData.symbols_whitelist]);

  const filteredBlacklistCoins = useMemo(() => {
    const input = blacklistInput.trim().toUpperCase();
    const existing = configData.symbols_blacklist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, blacklistInput, configData.symbols_blacklist]);

  // 白名单操作
  const handleAddWhitelist = (coin?: string) => {
    const symbol = (coin || whitelistInput.trim()).toUpperCase();
    if (symbol && !configData.symbols_whitelist?.includes(symbol)) {
      setConfigData({
        ...configData,
        symbols_whitelist: [...(configData.symbols_whitelist || []), symbol],
      });
      setWhitelistInput("");
      setWhitelistHighlightIndex(-1);
    }
  };

  const handleRemoveWhitelist = (symbol: string) => {
    setConfigData({
      ...configData,
      symbols_whitelist: configData.symbols_whitelist?.filter((s) => s !== symbol) || [],
    });
  };

  const handleWhitelistKeyDown = (e: React.KeyboardEvent) => {
    if (!whitelistInput || filteredWhitelistCoins.length === 0) {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddWhitelist();
      }
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setWhitelistHighlightIndex((prev) =>
          prev < filteredWhitelistCoins.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setWhitelistHighlightIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (whitelistHighlightIndex >= 0) {
          handleAddWhitelist(filteredWhitelistCoins[whitelistHighlightIndex]);
        } else {
          handleAddWhitelist();
        }
        break;
      case "Escape":
        setWhitelistInput("");
        setWhitelistHighlightIndex(-1);
        break;
    }
  };

  // 黑名单操作
  const handleAddBlacklist = (coin?: string) => {
    const symbol = (coin || blacklistInput.trim()).toUpperCase();
    if (symbol && !configData.symbols_blacklist?.includes(symbol)) {
      setConfigData({
        ...configData,
        symbols_blacklist: [...(configData.symbols_blacklist || []), symbol],
      });
      setBlacklistInput("");
      setBlacklistHighlightIndex(-1);
    }
  };

  const handleRemoveBlacklist = (symbol: string) => {
    setConfigData({
      ...configData,
      symbols_blacklist: configData.symbols_blacklist?.filter((s) => s !== symbol) || [],
    });
  };

  const handleBlacklistKeyDown = (e: React.KeyboardEvent) => {
    if (!blacklistInput || filteredBlacklistCoins.length === 0) {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddBlacklist();
      }
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setBlacklistHighlightIndex((prev) =>
          prev < filteredBlacklistCoins.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setBlacklistHighlightIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        e.preventDefault();
        if (blacklistHighlightIndex >= 0) {
          handleAddBlacklist(filteredBlacklistCoins[blacklistHighlightIndex]);
        } else {
          handleAddBlacklist();
        }
        break;
      case "Escape":
        setBlacklistInput("");
        setBlacklistHighlightIndex(-1);
        break;
    }
  };

  const handleSave = () => {
    const data: Partial<DefaultCopyConfigRule> = {
      name,
      description,
      leverage_min: leverageMin,
      leverage_max: leverageMax,
      priority,
      is_enabled: isEnabled,
      is_default: isDefault,
      config_data: configData,
    };
    if (editingRule?.id) {
      data.id = editingRule.id;
    }
    onSave(data);
  };

  const isValid = name.trim().length > 0;

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
                placeholder="例如：低杠杆配置"
                value={name}
                onValueChange={setName}
                isRequired
              />
              <Input
                label="规则描述"
                placeholder="可选描述"
                value={description}
                onValueChange={setDescription}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <Input
                type="number"
                label="杠杆下限"
                description="不包含此值"
                value={String(leverageMin)}
                onValueChange={(v) => setLeverageMin(parseFloat(v) || 0)}
                endContent={<span className="text-default-400 text-sm">x</span>}
              />
              <Input
                type="number"
                label="杠杆上限"
                description="包含此值"
                value={String(leverageMax)}
                onValueChange={(v) => setLeverageMax(parseFloat(v) || 100)}
                endContent={<span className="text-default-400 text-sm">x</span>}
              />
              <Input
                type="number"
                label="优先级"
                description="数字越小优先级越高"
                value={String(priority)}
                onValueChange={(v) => setPriority(parseInt(v) || 0)}
              />
            </div>
            <div className="flex gap-6">
              <div className="flex items-center gap-2">
                <Switch size="sm" isSelected={isEnabled} onValueChange={setIsEnabled} />
                <span className="text-sm">启用规则</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch size="sm" isSelected={isDefault} onValueChange={setIsDefault} />
                <span className="text-sm">设为默认（兜底配置）</span>
              </div>
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
                label="最大仓位"
                value={String(configData.max_position_size_usd || 500)}
                onValueChange={(v) => setConfigData({ ...configData, max_position_size_usd: parseFloat(v) || 500 })}
                startContent={<span className="text-default-400 text-sm">$</span>}
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
            </div>
            <div className="flex items-center gap-2">
              <Switch
                size="sm"
                isSelected={configData.copy_leverage || false}
                onValueChange={(v) => setConfigData({ ...configData, copy_leverage: v })}
              />
              <span className="text-sm">复制杠杆</span>
            </div>
          </div>

          <Divider />

          {/* 币种限制 */}
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-default-700 flex items-center gap-2">
              <Icon icon="lucide:filter" width={16} />
              币种限制
            </h4>

            {/* 白名单 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm text-success font-medium w-16">白名单</span>
                <div className="flex-1 relative">
                  <Input
                    size="sm"
                    placeholder="输入搜索币种..."
                    value={whitelistInput}
                    onValueChange={(v) => {
                      setWhitelistInput(v);
                      setWhitelistHighlightIndex(-1);
                    }}
                    onKeyDown={handleWhitelistKeyDown}
                  />
                  {whitelistInput && filteredWhitelistCoins.length > 0 && (
                    <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-content1 border border-default-200 rounded-lg shadow-lg max-h-40 overflow-auto">
                      {filteredWhitelistCoins.map((coin, index) => (
                        <div
                          key={coin}
                          className={`px-3 py-2 cursor-pointer text-sm ${
                            index === whitelistHighlightIndex
                              ? "bg-primary-100 text-primary"
                              : "hover:bg-default-100"
                          }`}
                          onClick={() => handleAddWhitelist(coin)}
                          onMouseEnter={() => setWhitelistHighlightIndex(index)}
                        >
                          {coin}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <Button
                  size="sm"
                  color="success"
                  variant="flat"
                  isIconOnly
                  onPress={() => handleAddWhitelist()}
                  isDisabled={!whitelistInput.trim()}
                >
                  <Icon icon="lucide:plus" width={16} />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 min-h-[32px]">
                {(configData.symbols_whitelist?.length || 0) === 0 ? (
                  <span className="text-xs text-default-400">不限制</span>
                ) : (
                  configData.symbols_whitelist?.map((symbol) => (
                    <Chip
                      key={symbol}
                      size="sm"
                      color="success"
                      variant="flat"
                      onClose={() => handleRemoveWhitelist(symbol)}
                    >
                      {symbol}
                    </Chip>
                  ))
                )}
              </div>
            </div>

            {/* 黑名单 */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-sm text-danger font-medium w-16">黑名单</span>
                <div className="flex-1 relative">
                  <Input
                    size="sm"
                    placeholder="输入搜索币种..."
                    value={blacklistInput}
                    onValueChange={(v) => {
                      setBlacklistInput(v);
                      setBlacklistHighlightIndex(-1);
                    }}
                    onKeyDown={handleBlacklistKeyDown}
                  />
                  {blacklistInput && filteredBlacklistCoins.length > 0 && (
                    <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-content1 border border-default-200 rounded-lg shadow-lg max-h-40 overflow-auto">
                      {filteredBlacklistCoins.map((coin, index) => (
                        <div
                          key={coin}
                          className={`px-3 py-2 cursor-pointer text-sm ${
                            index === blacklistHighlightIndex
                              ? "bg-primary-100 text-primary"
                              : "hover:bg-default-100"
                          }`}
                          onClick={() => handleAddBlacklist(coin)}
                          onMouseEnter={() => setBlacklistHighlightIndex(index)}
                        >
                          {coin}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <Button
                  size="sm"
                  color="danger"
                  variant="flat"
                  isIconOnly
                  onPress={() => handleAddBlacklist()}
                  isDisabled={!blacklistInput.trim()}
                >
                  <Icon icon="lucide:plus" width={16} />
                </Button>
              </div>
              <div className="flex flex-wrap gap-1 min-h-[32px]">
                {(configData.symbols_blacklist?.length || 0) === 0 ? (
                  <span className="text-xs text-default-400">无黑名单</span>
                ) : (
                  configData.symbols_blacklist?.map((symbol) => (
                    <Chip
                      key={symbol}
                      size="sm"
                      color="danger"
                      variant="flat"
                      onClose={() => handleRemoveBlacklist(symbol)}
                    >
                      {symbol}
                    </Chip>
                  ))
                )}
              </div>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose} isDisabled={isSaving}>
            取消
          </Button>
          <Button color="primary" onPress={handleSave} isLoading={isSaving} isDisabled={!isValid}>
            保存
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
