import { useState, useEffect, useMemo, useCallback } from "react";
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Input,
  Button,
  Checkbox,
  Chip,
  Select,
  SelectItem,
  Slider,
  Tooltip,
  Spinner,
  Divider,
} from "@heroui/react";
import { Icon } from "@iconify/react";
import type { CopyTradingAddress, AssetPosition } from "@/types/api";
import { traderApi } from "@/services/api";

// ==================== Types ====================

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

export type { AddressFormModalProps };

type CopyMode = 'asset_ratio' | 'position_ratio' | 'fixed_value';
type MarginMode = 'follow_target' | 'cross' | 'isolated';
type SymbolListMode = 'whitelist' | 'blacklist' | 'none';

// ==================== Helpers ====================

function fmt(n: number, d = 2) {
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}

// ==================== Left Panel: Positions ====================

function PositionsPanel({ address }: { address: string }) {
  const [positions, setPositions] = useState<AssetPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalValue, setTotalValue] = useState(0);
  const [totalUpnl, setTotalUpnl] = useState(0);

  useEffect(() => {
    if (!address || !address.startsWith('0x') || address.length !== 42) return;
    setLoading(true);
    traderApi.getTraderPositions(address)
      .then(res => {
        if (res.success && res.data) {
          setPositions(res.data);
          const tv = res.data.reduce((s, p) => s + Math.abs(p.position_value), 0);
          const tu = res.data.reduce((s, p) => s + p.unrealized_pnl, 0);
          setTotalValue(tv);
          setTotalUpnl(tu);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [address]);

  if (!address || address.length !== 42) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-default-400 py-12">
        <Icon icon="solar:wallet-line-duotone" width={40} />
        <p className="mt-2 text-sm">输入地址后查看持仓</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="sm" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Summary */}
      <div className="flex justify-between items-center">
        <div>
          <p className="text-xs text-default-400">总持仓价值</p>
          <p className="text-sm font-bold">$ {fmt(totalValue, 4)}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-default-400">未实现盈亏</p>
          <p className={`text-sm font-bold ${totalUpnl >= 0 ? 'text-success' : 'text-danger'}`}>
            $ {fmt(totalUpnl)}
          </p>
        </div>
      </div>

      <Divider />

      {/* Position List */}
      {positions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-default-400">
          <Icon icon="solar:inbox-line-duotone" width={32} />
          <p className="mt-1 text-xs">暂无持仓</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2 max-h-[400px] overflow-y-auto pr-1">
          {positions.map(pos => {
            const isLong = pos.szi > 0;
            const pnlPct = pos.return_on_equity * 100;
            return (
              <div key={pos.id} className="bg-default-50 rounded-lg p-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold">{pos.coin}</span>
                    <Chip
                      size="sm"
                      color={isLong ? 'success' : 'danger'}
                      variant="flat"
                      classNames={{ content: 'text-[10px] font-semibold px-1' }}
                    >
                      {pos.leverage_type === 'isolated' ? '逐仓' : '全仓'} {pos.leverage_value}x
                    </Chip>
                  </div>
                </div>
                <div className="flex justify-between mt-1.5 text-xs">
                  <div>
                    <span className="text-default-400">持仓价值</span>
                    <p className="font-semibold">$ {fmt(Math.abs(pos.position_value))}</p>
                    <p className="text-default-400 text-[10px]">{fmt(Math.abs(pos.szi), 4)} {pos.coin}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-default-400">未实现盈亏</span>
                    <p className={`font-semibold ${pos.unrealized_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
                      $ {fmt(pos.unrealized_pnl)}
                    </p>
                    <p className={`text-[10px] ${pnlPct >= 0 ? 'text-success' : 'text-danger'}`}>
                      {pnlPct >= 0 ? '+' : ''}{fmt(pnlPct, 2)}%
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ==================== Main Component ====================

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
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [coinInput, setCoinInput] = useState("");
  const [showCoinInput, setShowCoinInput] = useState(false);

  // Load coins on mount if empty
  useEffect(() => {
    if (isOpen && availableCoins.length === 0) {
      onSyncCoins();
    }
  }, [isOpen]);

  const copyMode = (formData.copy_mode || 'asset_ratio') as CopyMode;
  const marginMode = (formData.margin_mode || 'cross') as MarginMode;
  const symbolListMode = (formData.symbol_list_mode || 'none') as SymbolListMode;

  // Current symbol list based on mode
  const currentSymbols = useMemo(() => {
    if (symbolListMode === 'whitelist') return formData.symbols_whitelist || [];
    if (symbolListMode === 'blacklist') return formData.symbols_blacklist || [];
    return [];
  }, [symbolListMode, formData.symbols_whitelist, formData.symbols_blacklist]);

  const handleAddCoin = useCallback(() => {
    const symbol = coinInput.trim().toUpperCase();
    if (!symbol) return;
    if (currentSymbols.includes(symbol)) return;

    const newList = [...currentSymbols, symbol];
    if (symbolListMode === 'whitelist') {
      setFormData({ ...formData, symbols_whitelist: newList, symbols_blacklist: [] });
    } else if (symbolListMode === 'blacklist') {
      setFormData({ ...formData, symbols_blacklist: newList, symbols_whitelist: [] });
    }
    setCoinInput("");
  }, [coinInput, currentSymbols, symbolListMode, formData, setFormData]);

  const handleRemoveCoin = useCallback((symbol: string) => {
    const newList = currentSymbols.filter(s => s !== symbol);
    if (symbolListMode === 'whitelist') {
      setFormData({ ...formData, symbols_whitelist: newList });
    } else {
      setFormData({ ...formData, symbols_blacklist: newList });
    }
  }, [currentSymbols, symbolListMode, formData, setFormData]);

  const handleSymbolListModeChange = (mode: SymbolListMode) => {
    setFormData({
      ...formData,
      symbol_list_mode: mode,
      symbols_whitelist: [],
      symbols_blacklist: [],
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="4xl" scrollBehavior="inside">
      <ModalContent>
        <ModalHeader>{editingAddress ? "编辑跟单地址" : "添加跟单地址"}</ModalHeader>
        <ModalBody>
          <div className="flex gap-6">
            {/* ====== Left Panel: Positions ====== */}
            <div className="w-[320px] shrink-0 flex flex-col gap-3">
              <Input
                placeholder="0x..."
                size="sm"
                startContent={<Icon icon="solar:magnifer-linear" width={14} className="text-default-400" />}
                value={formData.address || ""}
                onValueChange={(v) => setFormData({ ...formData, address: v })}
                isDisabled={!!editingAddress}
              />
              <PositionsPanel address={formData.address || ''} />
            </div>

            {/* ====== Right Panel: Config ====== */}
            <div className="flex-1 flex flex-col gap-4 min-w-0">

              {/* 杠杆 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">杠杆</span>
                  <Checkbox
                    size="sm"
                    isSelected={formData.copy_leverage ?? true}
                    onValueChange={v => setFormData({ ...formData, copy_leverage: v })}
                  >
                    <span className="text-xs">跟随目标杠杆</span>
                  </Checkbox>
                </div>
                <div className="flex items-center gap-3">
                  <Slider
                    aria-label="杠杆"
                    size="sm"
                    step={1}
                    minValue={1}
                    maxValue={40}
                    value={formData.max_leverage || 1}
                    onChange={v => setFormData({ ...formData, max_leverage: v as number })}
                    isDisabled={formData.copy_leverage}
                    className="flex-1"
                    showSteps={false}
                    marks={[
                      { value: 1, label: '1x' },
                      { value: 10, label: '10x' },
                      { value: 20, label: '20x' },
                      { value: 40, label: '40x' },
                    ]}
                  />
                  <Input
                    type="number"
                    size="sm"
                    className="w-20"
                    value={String(formData.max_leverage || 1)}
                    onValueChange={v => setFormData({ ...formData, max_leverage: parseInt(v) || 1 })}
                    isDisabled={formData.copy_leverage}
                    endContent={<span className="text-default-400 text-xs">x</span>}
                  />
                </div>
              </div>

              {/* 保证金模式 */}
              <div className="space-y-2">
                <span className="text-sm font-medium">保证金模式</span>
                <div className="flex gap-2">
                  {([
                    { key: 'follow_target', label: '跟随目标' },
                    { key: 'cross', label: '全仓' },
                    { key: 'isolated', label: '逐仓' },
                  ] as const).map(opt => (
                    <Button
                      key={opt.key}
                      size="sm"
                      variant={marginMode === opt.key ? 'solid' : 'bordered'}
                      color={marginMode === opt.key ? 'primary' : 'default'}
                      className="flex-1"
                      onPress={() => setFormData({ ...formData, margin_mode: opt.key })}
                    >
                      {opt.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* 跟单模式 */}
              <div className="space-y-2">
                <span className="text-sm font-medium">跟单模式</span>
                <div className="flex gap-2">
                  {([
                    { key: 'asset_ratio', label: '资产等比', tip: '按资产比例等比跟单' },
                    { key: 'position_ratio', label: '仓位等比', tip: '按仓位比例等比跟单' },
                    { key: 'fixed_value', label: '固定价值', tip: '每笔跟单使用固定金额' },
                  ] as const).map(opt => (
                    <Tooltip key={opt.key} content={opt.tip} delay={300}>
                      <Button
                        size="sm"
                        variant={copyMode === opt.key ? 'solid' : 'bordered'}
                        color={copyMode === opt.key ? 'primary' : 'default'}
                        className="flex-1"
                        onPress={() => setFormData({ ...formData, copy_mode: opt.key })}
                        endContent={<Icon icon="solar:question-circle-linear" width={14} className="text-default-400" />}
                      >
                        {opt.label}
                      </Button>
                    </Tooltip>
                  ))}
                </div>
              </div>

              {/* 跟单参数（根据模式不同） */}
              <div className="grid grid-cols-2 gap-3">
                {copyMode === 'fixed_value' ? (
                  <Input
                    type="number"
                    label="固定开仓价值"
                    size="sm"
                    value={String(formData.fixed_position_value_usd ?? 100)}
                    onValueChange={v => setFormData({ ...formData, fixed_position_value_usd: parseFloat(v) || 100 })}
                    startContent={<span className="text-default-400 text-xs">$</span>}
                  />
                ) : (
                  <Input
                    type="number"
                    label="跟单比例"
                    size="sm"
                    value={String(((formData.copy_ratio ?? 1) * 100).toFixed(0))}
                    onValueChange={v => setFormData({ ...formData, copy_ratio: (parseFloat(v) || 10) / 100 })}
                    endContent={<span className="text-default-400 text-xs">%</span>}
                  />
                )}
                <Input
                  type="number"
                  label="高保证金使用率保护"
                  size="sm"
                  value={String(formData.high_margin_protection_pct ?? 70)}
                  onValueChange={v => setFormData({ ...formData, high_margin_protection_pct: parseFloat(v) || 70 })}
                  endContent={<span className="text-default-400 text-xs">%</span>}
                />
              </div>

              {/* 高级选项 */}
              <div>
                <button
                  className="flex items-center gap-1 text-sm text-primary cursor-pointer"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  <Icon
                    icon={showAdvanced ? "solar:alt-arrow-up-linear" : "solar:alt-arrow-down-linear"}
                    width={16}
                  />
                  高级选项
                </button>

                {showAdvanced && (
                  <div className="mt-3 space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        type="number"
                        label="最小开仓价值"
                        placeholder="可选"
                        size="sm"
                        value={formData.min_position_size_usd ? String(formData.min_position_size_usd) : ''}
                        onValueChange={v => setFormData({ ...formData, min_position_size_usd: parseFloat(v) || 0 })}
                        startContent={<span className="text-default-400 text-xs">$</span>}
                      />
                      <Input
                        type="number"
                        label="最大开仓价值"
                        placeholder="无上限 (可选)"
                        size="sm"
                        value={formData.max_position_size_usd ? String(formData.max_position_size_usd) : ''}
                        onValueChange={v => setFormData({ ...formData, max_position_size_usd: parseFloat(v) || 0 })}
                        startContent={<span className="text-default-400 text-xs">$</span>}
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <Input
                        type="number"
                        label="止盈 %"
                        placeholder="0-2000 (可选)"
                        size="sm"
                        value={formData.take_profit_percent ? String(formData.take_profit_percent) : ''}
                        onValueChange={v => {
                          const val = parseFloat(v);
                          setFormData({
                            ...formData,
                            take_profit_enabled: !isNaN(val) && val > 0,
                            take_profit_percent: val || 0,
                          });
                        }}
                        endContent={<span className="text-default-400 text-xs">%</span>}
                      />
                      <Input
                        type="number"
                        label="止损 %"
                        placeholder="0-100 (可选)"
                        size="sm"
                        value={formData.stop_loss_percent ? String(formData.stop_loss_percent) : ''}
                        onValueChange={v => {
                          const val = parseFloat(v);
                          setFormData({
                            ...formData,
                            stop_loss_enabled: !isNaN(val) && val > 0,
                            stop_loss_percent: val || 0,
                          });
                        }}
                        endContent={<span className="text-default-400 text-xs">%</span>}
                      />
                    </div>

                    {/* Checkboxes */}
                    <div className="flex flex-wrap gap-x-4 gap-y-2">
                      <Checkbox
                        size="sm"
                        isSelected={formData.follow_add_position ?? false}
                        onValueChange={v => setFormData({ ...formData, follow_add_position: v })}
                      >
                        <span className="text-xs">跟随加仓</span>
                      </Checkbox>
                      <Checkbox
                        size="sm"
                        isSelected={formData.follow_reduce_position ?? false}
                        onValueChange={v => setFormData({ ...formData, follow_reduce_position: v })}
                      >
                        <span className="text-xs">跟随减仓</span>
                      </Checkbox>
                      <Checkbox
                        size="sm"
                        isSelected={formData.slippage_protection ?? false}
                        onValueChange={v => setFormData({ ...formData, slippage_protection: v })}
                      >
                        <span className="text-xs">滑点保护</span>
                      </Checkbox>
                      <Checkbox
                        size="sm"
                        isSelected={formData.add_position_order ?? false}
                        onValueChange={v => setFormData({ ...formData, add_position_order: v })}
                      >
                        <span className="text-xs">加仓开单</span>
                      </Checkbox>
                      <Checkbox
                        size="sm"
                        isSelected={formData.reverse_copy ?? false}
                        onValueChange={v => setFormData({ ...formData, reverse_copy: v })}
                      >
                        <span className="text-xs">反向跟单</span>
                      </Checkbox>
                    </div>
                  </div>
                )}
              </div>

              <Divider />

              {/* 币种黑白名单 */}
              <div className="space-y-2">
                <span className="text-sm font-medium">币种黑白名单</span>
                <div className="flex flex-wrap items-center gap-1.5">
                  {/* 模式选择 */}
                  <Select
                    aria-label="名单模式"
                    size="sm"
                    className="w-[100px] shrink-0"
                    variant="bordered"
                    selectedKeys={[symbolListMode]}
                    onSelectionChange={keys => {
                      const val = Array.from(keys)[0] as SymbolListMode;
                      if (val) handleSymbolListModeChange(val);
                    }}
                  >
                    <SelectItem key="none">不设置</SelectItem>
                    <SelectItem key="whitelist">白名单</SelectItem>
                    <SelectItem key="blacklist">黑名单</SelectItem>
                  </Select>

                  {/* 已选币种 chips */}
                  {symbolListMode !== 'none' && currentSymbols.map(symbol => (
                    <Chip
                      key={symbol}
                      size="sm"
                      color={symbolListMode === 'whitelist' ? 'success' : 'danger'}
                      variant="flat"
                      onClose={() => handleRemoveCoin(symbol)}
                    >
                      {symbol}
                    </Chip>
                  ))}

                  {/* 添加币种 */}
                  {symbolListMode !== 'none' && (
                    showCoinInput ? (
                      <Input
                        size="sm"
                        className="w-[100px] shrink-0"
                        variant="bordered"
                        placeholder="输入币种"
                        autoFocus
                        value={coinInput}
                        onValueChange={setCoinInput}
                        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddCoin(); } }}
                        onBlur={() => { handleAddCoin(); setShowCoinInput(false); }}
                      />
                    ) : (
                      <Button
                        size="sm"
                        variant="bordered"
                        className="h-8 shrink-0"
                        startContent={<Icon icon="solar:add-circle-linear" width={14} />}
                        onPress={() => setShowCoinInput(true)}
                      >
                        添加币种
                      </Button>
                    )
                  )}
                </div>
              </div>

              {/* 备注 */}
              <Input
                label="备注"
                placeholder="可选"
                size="sm"
                value={formData.remark || ''}
                onValueChange={v => setFormData({ ...formData, remark: v })}
              />
            </div>
          </div>
        </ModalBody>
        <ModalFooter>
          <Button variant="flat" onPress={onClose}>
            取消
          </Button>
          <Button color="primary" onPress={onSave}>
            {editingAddress ? '保存' : '创建'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}
