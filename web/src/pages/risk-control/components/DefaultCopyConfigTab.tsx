import { useState, useEffect, useCallback, useMemo } from "react";
import {
  Card,
  CardBody,
  CardHeader,
  Input,
  Button,
  Spinner,
  addToast,
  Switch,
  Chip,
} from "@heroui/react";
import { Icon } from "@iconify/react";

import { riskControlApi, hyperliquidApi, DefaultCopyTradingConfig } from "@/services/api";

// 默认跟单配置
const defaultCopyConfig: DefaultCopyTradingConfig = {
  copy_ratio: 0.1,
  max_position_size_usd: 500,
  min_position_size_usd: 20,
  max_leverage: 10,
  default_leverage: 3,
  copy_leverage: false,
  slippage: 0.001,
  symbols_whitelist: [],
  symbols_blacklist: [],
};

interface DefaultCopyConfigTabProps {
  onHasChanges?: (hasChanges: boolean) => void;
}

export default function DefaultCopyConfigTab({ onHasChanges }: DefaultCopyConfigTabProps) {
  const [config, setConfig] = useState<DefaultCopyTradingConfig>(defaultCopyConfig);
  const [originalConfig, setOriginalConfig] = useState<DefaultCopyTradingConfig>(defaultCopyConfig);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // 币种相关状态
  const [availableCoins, setAvailableCoins] = useState<string[]>([]);
  const [coinsLoading, setCoinsLoading] = useState(false);
  const [whitelistInput, setWhitelistInput] = useState("");
  const [blacklistInput, setBlacklistInput] = useState("");
  const [whitelistHighlightIndex, setWhitelistHighlightIndex] = useState(-1);
  const [blacklistHighlightIndex, setBlacklistHighlightIndex] = useState(-1);

  // 检查配置是否有变更
  const hasChanges = useMemo(() => {
    return JSON.stringify(config) !== JSON.stringify(originalConfig);
  }, [config, originalConfig]);

  // 通知父组件变更状态
  useEffect(() => {
    onHasChanges?.(hasChanges);
  }, [hasChanges, onHasChanges]);

  // 过滤可用币种（用于下拉选择）
  const filteredWhitelistCoins = useMemo(() => {
    const input = whitelistInput.trim().toUpperCase();
    const existing = config.symbols_whitelist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, whitelistInput, config.symbols_whitelist]);

  const filteredBlacklistCoins = useMemo(() => {
    const input = blacklistInput.trim().toUpperCase();
    const existing = config.symbols_blacklist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, blacklistInput, config.symbols_blacklist]);

  // 加载配置
  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const response = await riskControlApi.getDefaultCopyConfig();
      if (response.success && response.data) {
        const loadedConfig = { ...defaultCopyConfig, ...response.data };
        setConfig(loadedConfig);
        setOriginalConfig(loadedConfig);
      }
    } catch (error) {
      console.error("Failed to load default copy config:", error);
      addToast({ title: "加载默认跟单配置失败", color: "danger" });
    } finally {
      setLoading(false);
    }
  }, []);

  // 加载币种列表
  const loadCoins = useCallback(async () => {
    try {
      const response = await hyperliquidApi.getCoinNames();
      if (response.success && response.data) {
        setAvailableCoins(response.data);
      }
    } catch (error) {
      console.error("Failed to load coins:", error);
    }
  }, []);

  useEffect(() => {
    loadConfig();
    loadCoins();
  }, [loadConfig, loadCoins]);

  // 同步币种列表
  const handleSyncCoins = async () => {
    setCoinsLoading(true);
    try {
      const response = await hyperliquidApi.syncCoins();
      if (response.success && response.data) {
        const coinNames = response.data.map((c) => c.name);
        setAvailableCoins(coinNames);
        addToast({ title: `已同步 ${coinNames.length} 个币种`, color: "success" });
      }
    } catch (error) {
      console.error("Failed to sync coins:", error);
      addToast({ title: "同步币种失败", color: "danger" });
    } finally {
      setCoinsLoading(false);
    }
  };

  // 保存配置
  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await riskControlApi.updateDefaultCopyConfig(config);
      if (response.success) {
        setOriginalConfig(config);
        addToast({ title: response.message || "保存成功", color: "success" });
      } else {
        addToast({ title: response.error || "保存失败", color: "danger" });
      }
    } catch (error) {
      console.error("Failed to save default copy config:", error);
      addToast({ title: "保存配置失败", color: "danger" });
    } finally {
      setSaving(false);
    }
  };

  // 重置为默认值
  const handleReset = () => {
    setConfig(defaultCopyConfig);
  };

  // 撤销更改
  const handleCancel = () => {
    setConfig(originalConfig);
  };

  // 添加币种到白名单
  const handleAddWhitelist = (coin?: string) => {
    const symbol = (coin || whitelistInput.trim()).toUpperCase();
    if (symbol && !config.symbols_whitelist?.includes(symbol)) {
      setConfig({
        ...config,
        symbols_whitelist: [...(config.symbols_whitelist || []), symbol],
      });
      setWhitelistInput("");
      setWhitelistHighlightIndex(-1);
    }
  };

  // 处理白名单键盘事件
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
        if (whitelistHighlightIndex >= 0 && whitelistHighlightIndex < filteredWhitelistCoins.length) {
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

  // 从白名单移除币种
  const handleRemoveWhitelist = (symbol: string) => {
    setConfig({
      ...config,
      symbols_whitelist: config.symbols_whitelist?.filter((s) => s !== symbol) || [],
    });
  };

  // 添加币种到黑名单
  const handleAddBlacklist = (coin?: string) => {
    const symbol = (coin || blacklistInput.trim()).toUpperCase();
    if (symbol && !config.symbols_blacklist?.includes(symbol)) {
      setConfig({
        ...config,
        symbols_blacklist: [...(config.symbols_blacklist || []), symbol],
      });
      setBlacklistInput("");
      setBlacklistHighlightIndex(-1);
    }
  };

  // 处理黑名单键盘事件
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
        if (blacklistHighlightIndex >= 0 && blacklistHighlightIndex < filteredBlacklistCoins.length) {
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

  // 从黑名单移除币种
  const handleRemoveBlacklist = (symbol: string) => {
    setConfig({
      ...config,
      symbols_blacklist: config.symbols_blacklist?.filter((s) => s !== symbol) || [],
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[400px]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* 变更提示 */}
      {hasChanges && (
        <div className="flex items-center gap-2 p-3 bg-warning-50 dark:bg-warning-900/20 rounded-lg border border-warning-200 dark:border-warning-800">
          <Icon icon="lucide:alert-triangle" width={20} className="text-warning" />
          <span className="text-warning-700 dark:text-warning-400">
            配置已修改，请记得保存更改
          </span>
        </div>
      )}

      {/* 基础跟单配置 */}
      <Card className="shadow-sm">
        <CardHeader className="flex gap-3 pb-0">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
              <Icon icon="lucide:copy" width={20} className="text-primary" />
            </div>
            <h3 className="text-lg font-semibold">跟单参数</h3>
          </div>
        </CardHeader>
        <CardBody className="gap-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              type="number"
              label="跟单比例"
              description="跟单目标仓位的百分比"
              value={String(((config.copy_ratio || 0.1) * 100).toFixed(0))}
              onValueChange={(v) => setConfig({ ...config, copy_ratio: (parseFloat(v) || 10) / 100 })}
              endContent={<span className="text-default-400 text-sm">%</span>}
              classNames={{ label: "font-medium", description: "text-xs" }}
            />
            <Input
              type="number"
              label="滑点容忍度"
              description="允许的最大滑点百分比"
              value={String(((config.slippage || 0.001) * 100).toFixed(2))}
              onValueChange={(v) => setConfig({ ...config, slippage: (parseFloat(v) || 0.1) / 100 })}
              endContent={<span className="text-default-400 text-sm">%</span>}
              classNames={{ label: "font-medium", description: "text-xs" }}
            />
            <Input
              type="number"
              label="最大仓位"
              description="单个跟单仓位的最大价值"
              value={String(config.max_position_size_usd || 500)}
              onValueChange={(v) => setConfig({ ...config, max_position_size_usd: parseFloat(v) || 500 })}
              startContent={<span className="text-default-400 text-sm">$</span>}
              classNames={{ label: "font-medium", description: "text-xs" }}
            />
            <Input
              type="number"
              label="最小仓位"
              description="单个跟单仓位的最小价值"
              value={String(config.min_position_size_usd || 20)}
              onValueChange={(v) => setConfig({ ...config, min_position_size_usd: parseFloat(v) || 20 })}
              startContent={<span className="text-default-400 text-sm">$</span>}
              classNames={{ label: "font-medium", description: "text-xs" }}
            />
            <Input
              type="number"
              label="最大杠杆"
              description="允许使用的最大杠杆倍数"
              value={String(config.max_leverage || 10)}
              onValueChange={(v) => setConfig({ ...config, max_leverage: parseInt(v) || 10 })}
              endContent={<span className="text-default-400 text-sm">x</span>}
              classNames={{ label: "font-medium", description: "text-xs" }}
            />
            <Input
              type="number"
              label="默认杠杆"
              description="不复制杠杆时使用的默认杠杆"
              value={String(config.default_leverage || 3)}
              onValueChange={(v) => setConfig({ ...config, default_leverage: parseInt(v) || 3 })}
              endContent={<span className="text-default-400 text-sm">x</span>}
              classNames={{ label: "font-medium", description: "text-xs" }}
            />
          </div>
        </CardBody>
      </Card>

      {/* 币种限制 */}
      <Card className="shadow-sm">
        <CardHeader className="flex gap-3 pb-0">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
              <Icon icon="lucide:filter" width={20} className="text-primary" />
            </div>
            <h3 className="text-lg font-semibold">币种限制</h3>
          </div>
          <div className="ml-auto">
            <Button
              size="sm"
              variant="flat"
              isLoading={coinsLoading}
              onPress={handleSyncCoins}
              startContent={!coinsLoading && <Icon icon="lucide:refresh-cw" width={14} />}
            >
              {availableCoins.length > 0 ? `已加载 ${availableCoins.length} 币种` : "同步币种"}
            </Button>
          </div>
        </CardHeader>
        <CardBody className="gap-4">
          <p className="text-xs text-default-500">
            白名单：只跟单这些币种（留空表示不限制）；黑名单：不跟单这些币种
          </p>

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
              {config.symbols_whitelist?.length === 0 ? (
                <span className="text-xs text-default-400">不限制（跟单所有币种）</span>
              ) : (
                config.symbols_whitelist?.map((symbol) => (
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
              {config.symbols_blacklist?.length === 0 ? (
                <span className="text-xs text-default-400">无黑名单</span>
              ) : (
                config.symbols_blacklist?.map((symbol) => (
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
        </CardBody>
      </Card>

      {/* 开关选项 */}
      <Card className="shadow-sm">
        <CardHeader className="flex gap-3 pb-0">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-primary-100 dark:bg-primary-900/30 rounded-lg">
              <Icon icon="lucide:toggle-left" width={20} className="text-primary" />
            </div>
            <h3 className="text-lg font-semibold">功能开关</h3>
          </div>
        </CardHeader>
        <CardBody>
          <div className="flex items-center justify-between p-3 bg-default-50 dark:bg-default-100/5 rounded-lg max-w-sm">
            <div>
              <p className="text-sm font-medium">复制杠杆</p>
              <p className="text-xs text-default-500">复制目标的杠杆设置</p>
            </div>
            <Switch
              isSelected={config.copy_leverage}
              onValueChange={(v) => setConfig({ ...config, copy_leverage: v })}
            />
          </div>
        </CardBody>
      </Card>

      {/* 操作按钮 */}
      <div className="flex justify-end gap-2">
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
              onPress={handleReset}
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
  );
}
