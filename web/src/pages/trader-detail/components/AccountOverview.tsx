import { useState, useEffect, useCallback } from 'react';
import { Card, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Chip } from '@heroui/chip';
import { Button } from '@heroui/button';
import { addToast } from '@heroui/react';
import { Icon } from '@iconify/react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { traderApi, addressTrackingApi, copyTradingApi, hyperliquidApi } from '@/services/api';
import type { CopyTradingAddress, AddressTracking } from '@/services/api';
import { TradingStatisticsModal } from './TradingStatisticsModal';
import TrackingFormModal from '@/components/TrackingFormModal';
import AddressFormModal from '@/components/AddressFormModal';

// ==================== 类型 ====================

interface TagItem {
  key: string;
  label: string;
  category: string;
}

interface TraderInfo {
  address: string;
  display_name: string;
  tags: TagItem[];
}

interface AccountOverviewData {
  trader_info: TraderInfo;
  account_total: {
    total_value: number;
    perpetual_value: number;
    spot_value: number;
  };
  margin: {
    free_margin: number;
    withdrawable_pct: number;
  };
  positions: {
    total_position_value: number;
    leverage_ratio: number;
    perp_total_value: number;
    avg_margin_used_ratio: number;
  };
  direction_bias: {
    bias: string;
    long_exposure_pct: number;
    short_exposure_pct: number;
  };
  position_distribution: {
    long_value: number;
    short_value: number;
  };
  profit_loss: {
    roe: number;
    unrealized_pnl: number;
  };
  trading_performance_1w: {
    win_rate: number;
    max_drawdown: number;
    trades: number;
    closed_positions: number;
  };
}

export type { AccountOverviewData };

interface AccountOverviewProps {
  address: string;
  onAccountValueLoaded?: (value: number) => void;
  onDataLoaded?: (data: AccountOverviewData) => void;
}

// ==================== 标签颜色映射 ====================

const TAG_COLORS: Record<string, 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'default'> = {
  whale: 'primary',
  medium_capital: 'secondary',
  small_capital: 'default',
  bullish: 'success',
  bearish: 'danger',
  neutral: 'default',
  consistent_profit: 'success',
  volatile_profit: 'warning',
  break_even: 'default',
  long_term: 'primary',
  swing: 'secondary',
  short_term: 'warning',
  ultra_short: 'danger',
  high_freq_stable: 'success',
  high_freq_aggressive: 'danger',
  low_freq_stable: 'primary',
  stable_profit: 'success',
  high_risk_high_return: 'warning',
  asymmetric_master: 'secondary',
};

// ==================== 辅助函数 ====================

function shortenAddress(addr: string): string {
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).then(() => {
    addToast({ title: 'Copied', color: 'success' });
  });
}

function fmt(n: number, d = 2) {
  return n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
}

// ==================== Mini Donut ====================

function MiniDonut({ data, colors, size = 72 }: { data: { value: number }[]; colors: string[]; size?: number }) {
  return (
    <ResponsiveContainer width={size} height={size}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={size * 0.32}
          outerRadius={size * 0.48}
          dataKey="value"
          strokeWidth={0}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={colors[i % colors.length]} />
          ))}
        </Pie>
      </PieChart>
    </ResponsiveContainer>
  );
}

// ==================== 组件 ====================

export function AccountOverview({ address, onAccountValueLoaded, onDataLoaded }: AccountOverviewProps) {
  const [data, setData] = useState<AccountOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsModalOpen, setStatsModalOpen] = useState(false);

  // One-click Monitor (TrackingFormModal)
  const [trackingModalOpen, setTrackingModalOpen] = useState(false);

  // Copy Trading (AddressFormModal)
  const [copyModalOpen, setCopyModalOpen] = useState(false);
  const [copyFormData, setCopyFormData] = useState<Partial<CopyTradingAddress>>({
    address: '',
    is_enabled: true,
    copy_ratio: 0.1,
    max_position_size_usd: 500,
    min_position_size_usd: 20,
    max_leverage: 10,
    slippage: 0.001,
    copy_leverage: true,
    copy_once: false,
    margin_mode: 'cross',
    symbols_whitelist: [],
    symbols_blacklist: [],
    auto_replenish: false,
    replenish_ratio: 0.5,
    replenish_min_value_usd: 10,
    replenish_max_value_usd: 100,
    take_profit_enabled: false,
    take_profit_percent: 50,
    stop_loss_enabled: false,
    stop_loss_percent: 20,
  });
  const [availableCoins, setAvailableCoins] = useState<string[]>([]);
  const [coinsLoading, setCoinsLoading] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await traderApi.getAccountOverview(address);
      if (res.success && res.data) {
        setData(res.data);
        onAccountValueLoaded?.(res.data.account_total.total_value);
        onDataLoaded?.(res.data);
      }
    } catch {
      // 静默失败
    } finally {
      setLoading(false);
    }
  }, [address, onAccountValueLoaded, onDataLoaded]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // One-click Monitor handlers
  const handleOpenTracking = useCallback(() => {
    setTrackingModalOpen(true);
  }, []);

  const handleSaveTracking = useCallback(async (formData: Partial<AddressTracking>) => {
    try {
      const res = await addressTrackingApi.createTracking({
        tracking_address: formData.tracking_address || '',
        address_remark: formData.address_remark,
        is_enabled: formData.is_enabled,
        enable_notification: formData.enable_notification,
        monitor_events: formData.monitor_events,
      });
      if (res.success) {
        addToast({ title: '监控添加成功', color: 'success' });
        setTrackingModalOpen(false);
      }
    } catch (err: any) {
      addToast({ title: '添加失败', description: err.message, color: 'danger' });
    }
  }, []);

  // Copy Trading handlers
  const handleOpenCopyTrading = useCallback(() => {
    setCopyFormData((prev) => ({ ...prev, address }));
    setCopyModalOpen(true);
  }, [address]);

  const handleSaveCopyTrading = useCallback(async () => {
    try {
      const res = await copyTradingApi.createAddress(copyFormData);
      if (res.success) {
        addToast({ title: '跟单添加成功', color: 'success' });
        setCopyModalOpen(false);
      }
    } catch (err: any) {
      addToast({ title: '添加失败', description: err.message, color: 'danger' });
    }
  }, [copyFormData]);

  const handleSyncCoins = useCallback(async () => {
    setCoinsLoading(true);
    try {
      const res = await hyperliquidApi.getCoinNames();
      if (res.success && res.data) {
        setAvailableCoins(res.data);
      }
    } catch {
      // silent
    } finally {
      setCoinsLoading(false);
    }
  }, []);

  if (loading) {
    return (
      <Card>
        <CardBody>
          <div className="flex justify-center py-8">
            <Spinner size="sm" />
          </div>
        </CardBody>
      </Card>
    );
  }

  if (!data) return null;

  const { trader_info } = data;

  // Donut data
  const accountDonut = [
    { value: data.account_total.perpetual_value },
    { value: data.account_total.spot_value },
  ];
  const marginDonut = [
    { value: data.margin.withdrawable_pct },
    { value: 100 - data.margin.withdrawable_pct },
  ];
  const leverageMax = 20;
  const leverageDonut = [
    { value: Math.min(data.positions.leverage_ratio, leverageMax) },
    { value: Math.max(leverageMax - data.positions.leverage_ratio, 0) },
  ];
  const perfDonut = [
    { value: data.trading_performance_1w.win_rate },
    { value: 100 - data.trading_performance_1w.win_rate },
  ];

  return (
    <>
      {/* ===== 交易员信息头部 ===== */}
      <Card>
        <CardBody className="py-3">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            {/* 左侧：头像 + 地址 + 名称 + 标签 */}
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-default-100 flex items-center justify-center">
                <Icon icon="solar:user-bold" width={20} className="text-default-400" />
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono text-default-500">
                    {shortenAddress(address)}
                  </span>
                  <button
                    onClick={() => copyToClipboard(address)}
                    className="text-default-400 hover:text-default-600 transition-colors"
                  >
                    <Icon icon="solar:copy-linear" width={14} />
                  </button>
                </div>
                {trader_info.display_name && (
                  <span className="text-sm font-semibold">{trader_info.display_name}</span>
                )}
                {trader_info.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {trader_info.tags.map((tag) => (
                      <Chip key={tag.key} size="sm" variant="flat" color={TAG_COLORS[tag.key] || 'default'}>
                        {tag.label}
                      </Chip>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 右侧：操作按钮 */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <Button size="sm" color="primary" variant="flat" startContent={<Icon icon="solar:refresh-bold" width={16} />} onPress={loadData}>
                Real-time Data
              </Button>
              <Button size="sm" variant="flat" startContent={<Icon icon="solar:chart-2-bold" width={16} />} onPress={() => setStatsModalOpen(true)}>
                Trading Statistics
              </Button>
              <Button size="sm" variant="flat" startContent={<Icon icon="solar:eye-bold" width={16} />} onPress={handleOpenTracking}>
                One-click Monitor
              </Button>
              <Button size="sm" variant="flat" startContent={<Icon icon="solar:copy-bold" width={16} />} onPress={handleOpenCopyTrading}>
                Copy Trading
              </Button>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* ===== 4 Stats Cards ===== */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* Card 1: Account Total Value */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-default-400 mb-1">Account Total Value</p>
                <p className="text-xl font-bold">$ {fmt(data.account_total.total_value)}</p>
                <div className="mt-2 space-y-1">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0" />
                    <span className="text-default-400">Perpetual</span>
                    <span className="ml-auto font-semibold">$ {fmt(data.account_total.perpetual_value)}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full bg-[#4b5563] flex-shrink-0" />
                    <span className="text-default-400">Spot</span>
                    <span className="ml-auto font-semibold">$ {fmt(data.account_total.spot_value)}</span>
                  </div>
                </div>
              </div>
              <div className="flex-shrink-0">
                <MiniDonut data={accountDonut} colors={['#3b82f6', '#4b5563']} />
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Card 2: Free margin available */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-default-400 mb-1">Free margin available</p>
                <p className="text-xl font-bold">$ {fmt(data.margin.free_margin)}</p>
                <div className="mt-2">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full bg-warning flex-shrink-0" />
                    <span className="text-default-400">Withdrawable</span>
                    <span className="ml-auto font-semibold">{data.margin.withdrawable_pct} %</span>
                  </div>
                </div>
              </div>
              <div className="flex-shrink-0">
                <MiniDonut data={marginDonut} colors={['#f5a524', '#3f3f46']} />
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Card 3: Total Position Value */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-default-400 mb-1">Total Position Value</p>
                <p className="text-xl font-bold">$ {fmt(data.positions.total_position_value)}</p>
                <div className="mt-2">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="w-2 h-2 rounded-full bg-success flex-shrink-0" />
                    <span className="text-default-400">Leverage Ratio</span>
                    <span className="ml-auto font-semibold">{data.positions.leverage_ratio}x</span>
                  </div>
                </div>
              </div>
              <div className="flex-shrink-0">
                <MiniDonut data={leverageDonut} colors={['#17c964', '#3f3f46']} />
              </div>
            </div>
          </CardBody>
        </Card>

        {/* Card 4: Trading Performance (1W) */}
        <Card>
          <CardBody className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-default-400 mb-1">Trading Performance (1W)</p>
                <div className="flex gap-4 mt-0.5">
                  <div>
                    <p className="text-[10px] text-default-400">Win Rate</p>
                    <p className="text-lg font-bold">{fmt(data.trading_performance_1w.win_rate)} %</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-default-400">Max Drawdown</p>
                    <p className="text-lg font-bold text-danger">{fmt(data.trading_performance_1w.max_drawdown)} %</p>
                  </div>
                </div>
                <div className="mt-1 flex items-center gap-4 text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-warning flex-shrink-0" />
                    <span className="text-default-400">Trades</span>
                    <span className="font-semibold">{data.trading_performance_1w.trades.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-success flex-shrink-0" />
                    <span className="text-default-400">Closed Positions</span>
                    <span className="font-semibold">{data.trading_performance_1w.closed_positions}</span>
                  </div>
                </div>
              </div>
              <div className="flex-shrink-0">
                <MiniDonut data={perfDonut} colors={['#17c964', '#3f3f46']} />
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      <TradingStatisticsModal
        isOpen={statsModalOpen}
        onClose={() => setStatsModalOpen(false)}
        address={address}
      />

      <TrackingFormModal
        isOpen={trackingModalOpen}
        onClose={() => setTrackingModalOpen(false)}
        tracking={null}
        onSave={handleSaveTracking}
        initialAddress={address}
      />

      <AddressFormModal
        isOpen={copyModalOpen}
        onClose={() => setCopyModalOpen(false)}
        editingAddress={null}
        formData={copyFormData}
        setFormData={setCopyFormData}
        onSave={handleSaveCopyTrading}
        availableCoins={availableCoins}
        coinsLoading={coinsLoading}
        onSyncCoins={handleSyncCoins}
      />
    </>
  );
}
