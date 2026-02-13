import { useState, useMemo } from "react";
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
  Select,
  SelectItem,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import { CopyTradingAddress } from "@/services/api";

interface AddressFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  editingAddress: CopyTradingAddress | null;
  formData: Partial<CopyTradingAddress>;
  setFormData: (data: Partial<CopyTradingAddress>) => void;
  onSave: () => void;
  availableCoins: string[];
  coinsLoading: boolean;
  onSyncCoins: () => void;
}

export default function AddressFormModal({
  isOpen,
  onClose,
  editingAddress,
  formData,
  setFormData,
  onSave,
  availableCoins,
  coinsLoading,
  onSyncCoins,
}: AddressFormModalProps) {
  // 币种输入临时状态
  const [whitelistInput, setWhitelistInput] = useState("");
  const [blacklistInput, setBlacklistInput] = useState("");
  const [whitelistHighlightIndex, setWhitelistHighlightIndex] = useState(-1);
  const [blacklistHighlightIndex, setBlacklistHighlightIndex] = useState(-1);

  // 过滤可用币种（用于下拉选择）
  const filteredWhitelistCoins = useMemo(() => {
    const input = whitelistInput.trim().toUpperCase();
    const existing = formData.symbols_whitelist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, whitelistInput, formData.symbols_whitelist]);

  const filteredBlacklistCoins = useMemo(() => {
    const input = blacklistInput.trim().toUpperCase();
    const existing = formData.symbols_blacklist || [];
    return availableCoins
      .filter((coin) => !existing.includes(coin))
      .filter((coin) => !input || coin.includes(input))
      .slice(0, 10);
  }, [availableCoins, blacklistInput, formData.symbols_blacklist]);

  // 添加币种到白名单
  const handleAddWhitelist = (coin?: string) => {
    const symbol = (coin || whitelistInput.trim()).toUpperCase();
    if (symbol && !formData.symbols_whitelist?.includes(symbol)) {
      setFormData({
        ...formData,
        symbols_whitelist: [...(formData.symbols_whitelist || []), symbol],
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
    setFormData({
      ...formData,
      symbols_whitelist: formData.symbols_whitelist?.filter((s) => s !== symbol) || [],
    });
  };

  // 添加币种到黑名单
  const handleAddBlacklist = (coin?: string) => {
    const symbol = (coin || blacklistInput.trim()).toUpperCase();
    if (symbol && !formData.symbols_blacklist?.includes(symbol)) {
      setFormData({
        ...formData,
        symbols_blacklist: [...(formData.symbols_blacklist || []), symbol],
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
    setFormData({
      ...formData,
      symbols_blacklist: formData.symbols_blacklist?.filter((s) => s !== symbol) || [],
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl" scrollBehavior="inside">
      <ModalContent>
        <ModalHeader>{editingAddress ? "编辑跟单地址" : "添加跟单地址"}</ModalHeader>
        <ModalBody className="max-h-[70vh] overflow-y-auto">
          <div className="flex flex-col gap-5">
            {/* 基础信息 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Icon icon="lucide:wallet" width={16} className="text-primary" />
                <h4 className="text-sm font-medium text-default-700">基础信息</h4>
              </div>
              <Input
                label="地址"
                placeholder="0x..."
                value={formData.address || ""}
                onValueChange={(v) => setFormData({ ...formData, address: v })}
                isDisabled={!!editingAddress}
              />
            </div>

            <Divider />

            {/* 跟单配置 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Icon icon="lucide:settings" width={16} className="text-primary" />
                <h4 className="text-sm font-medium text-default-700">跟单配置</h4>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  type="number"
                  label="跟单比例"
                  placeholder="10"
                  value={String(((formData.copy_ratio || 0.1) * 100).toFixed(0))}
                  onValueChange={(v) => setFormData({ ...formData, copy_ratio: (parseFloat(v) || 10) / 100 })}
                  endContent="%"
                  description="输入 10 表示跟单 10%"
                />
                <Input
                  type="number"
                  label="滑点容忍度"
                  value={String(((formData.slippage || 0.001) * 100).toFixed(2))}
                  onValueChange={(v) => setFormData({ ...formData, slippage: (parseFloat(v) || 0.1) / 100 })}
                  endContent="%"
                />
                <Input
                  type="number"
                  label="最小仓位"
                  placeholder="20"
                  value={String(formData.min_position_size_usd || 20)}
                  onValueChange={(v) => setFormData({ ...formData, min_position_size_usd: parseFloat(v) || 20 })}
                  startContent="$"
                />
                <Input
                  type="number"
                  label="最大仓位"
                  placeholder="500"
                  value={String(formData.max_position_size_usd || 500)}
                  onValueChange={(v) => setFormData({ ...formData, max_position_size_usd: parseFloat(v) || 500 })}
                  startContent="$"
                />
                <Input
                  type="number"
                  label="最大杠杆"
                  placeholder="10"
                  value={String(formData.max_leverage || 10)}
                  onValueChange={(v) => setFormData({ ...formData, max_leverage: parseInt(v) || 10 })}
                  endContent="x"
                />
                <Select
                  label="保证金模式"
                  selectedKeys={[formData.margin_mode || "cross"]}
                  onSelectionChange={(keys) => {
                    const value = Array.from(keys)[0] as string;
                    if (value) setFormData({ ...formData, margin_mode: value as 'cross' | 'isolated' });
                  }}
                  description="全仓共享保证金，逐仓独立保证金"
                >
                  <SelectItem key="cross">全仓 (Cross)</SelectItem>
                  <SelectItem key="isolated">逐仓 (Isolated)</SelectItem>
                </Select>
              </div>
            </div>

            <Divider />

            {/* 币种限制 */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon icon="lucide:coins" width={16} className="text-primary" />
                  <h4 className="text-sm font-medium text-default-700">币种限制</h4>
                </div>
                <Button
                  size="sm"
                  variant="flat"
                  isLoading={coinsLoading}
                  onPress={onSyncCoins}
                  startContent={!coinsLoading && <Icon icon="lucide:refresh-cw" width={14} />}
                >
                  {availableCoins.length > 0 ? `已加载 ${availableCoins.length} 币种` : "同步币种"}
                </Button>
              </div>
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
                      <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-content1 rounded-lg shadow-lg max-h-40 overflow-auto">
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
                  {formData.symbols_whitelist?.length === 0 ? (
                    <span className="text-xs text-default-400">不限制（跟单所有币种）</span>
                  ) : (
                    formData.symbols_whitelist?.map((symbol) => (
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
                      <div className="absolute top-full left-0 right-0 z-50 mt-1 bg-content1 rounded-lg shadow-lg max-h-40 overflow-auto">
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
                  {formData.symbols_blacklist?.length === 0 ? (
                    <span className="text-xs text-default-400">无黑名单</span>
                  ) : (
                    formData.symbols_blacklist?.map((symbol) => (
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

            <Divider />

            {/* 开关选项 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Icon icon="lucide:toggle-left" width={16} className="text-primary" />
                <h4 className="text-sm font-medium text-default-700">开关选项</h4>
              </div>
              <div className="flex flex-wrap gap-6">
                <Switch
                  isSelected={formData.is_enabled}
                  onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                >
                  启用跟单
                </Switch>
                <Switch
                  isSelected={formData.copy_leverage}
                  onChange={(e) => setFormData({ ...formData, copy_leverage: e.target.checked })}
                >
                  复制杠杆
                </Switch>
                <Switch
                  isSelected={formData.copy_once || false}
                  onChange={(e) => setFormData({ ...formData, copy_once: e.target.checked })}
                >
                  只跟一次
                </Switch>
              </div>
            </div>

            <Divider />

            {/* 自动补仓配置 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Icon icon="lucide:refresh-cw" width={16} className="text-primary" />
                <h4 className="text-sm font-medium text-default-700">自动补仓</h4>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  size="sm"
                  isSelected={formData.auto_replenish || false}
                  onValueChange={(v) => setFormData({ ...formData, auto_replenish: v })}
                />
                <span className="text-sm">启用自动补仓（当目标加仓时自动跟随补仓）</span>
              </div>
              {formData.auto_replenish && (
                <div className="grid gap-4 md:grid-cols-3">
                  <Input
                    type="number"
                    label="补仓比例"
                    description="按目标补仓量的比例"
                    size="sm"
                    value={String(((formData.replenish_ratio || 0.5) * 100).toFixed(0))}
                    onValueChange={(v) => setFormData({ ...formData, replenish_ratio: (parseFloat(v) || 50) / 100 })}
                    endContent={<span className="text-default-400 text-sm">%</span>}
                  />
                  <Input
                    type="number"
                    label="补仓最小价值"
                    description="单次补仓最小金额"
                    size="sm"
                    value={String(formData.replenish_min_value_usd || 10)}
                    onValueChange={(v) => setFormData({ ...formData, replenish_min_value_usd: parseFloat(v) || 10 })}
                    startContent={<span className="text-default-400 text-sm">$</span>}
                  />
                  <Input
                    type="number"
                    label="补仓最大价值"
                    description="单次补仓最大金额"
                    size="sm"
                    value={String(formData.replenish_max_value_usd || 100)}
                    onValueChange={(v) => setFormData({ ...formData, replenish_max_value_usd: parseFloat(v) || 100 })}
                    startContent={<span className="text-default-400 text-sm">$</span>}
                  />
                </div>
              )}
            </div>

            <Divider />

            {/* 止盈止损配置 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Icon icon="lucide:shield-check" width={16} className="text-primary" />
                <h4 className="text-sm font-medium text-default-700">止盈止损</h4>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {/* 止盈 */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      size="sm"
                      isSelected={formData.take_profit_enabled || false}
                      onValueChange={(v) => setFormData({ ...formData, take_profit_enabled: v })}
                    />
                    <span className="text-sm">启用止盈</span>
                  </div>
                  {formData.take_profit_enabled && (
                    <Input
                      type="number"
                      label="止盈百分比"
                      size="sm"
                      value={String(formData.take_profit_percent ?? 50)}
                      onValueChange={(v) => setFormData({ ...formData, take_profit_percent: parseFloat(v) || 50 })}
                      endContent={<span className="text-default-400 text-sm">%</span>}
                    />
                  )}
                </div>
                {/* 止损 */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Switch
                      size="sm"
                      isSelected={formData.stop_loss_enabled || false}
                      onValueChange={(v) => setFormData({ ...formData, stop_loss_enabled: v })}
                    />
                    <span className="text-sm">启用止损</span>
                  </div>
                  {formData.stop_loss_enabled && (
                    <Input
                      type="number"
                      label="止损百分比"
                      size="sm"
                      value={String(formData.stop_loss_percent ?? 20)}
                      onValueChange={(v) => setFormData({ ...formData, stop_loss_percent: parseFloat(v) || 20 })}
                      endContent={<span className="text-default-400 text-sm">%</span>}
                    />
                  )}
                </div>
              </div>
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose}>
            取消
          </Button>
          <Button color="primary" onPress={onSave}>
            保存
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
