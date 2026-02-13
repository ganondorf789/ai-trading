import { useState, useEffect, useCallback } from 'react';
import { Card, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Chip } from '@heroui/chip';
import { Button } from '@heroui/button';
import { Divider } from '@heroui/divider';
import { addToast } from '@heroui/react';
import { Icon } from '@iconify/react';
import { traderApi } from '@/services/api';
import { TradingStatisticsModal } from './TradingStatisticsModal';

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

interface AccountOverviewProps {
  address: string;
  onAccountValueLoaded?: (value: number) => void;
}

// ==================== 标签颜色映射 ====================

const TAG_COLORS: Record<string, 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'default'> = {
  // account_value
  whale: 'primary',
  medium_capital: 'secondary',
  small_capital: 'default',
  // direction_preference
  bullish: 'success',
  bearish: 'danger',
  neutral: 'default',
  // profit_status
  consistent_profit: 'success',
  volatile_profit: 'warning',
  break_even: 'default',
  // trading_rhythm
  long_term: 'primary',
  swing: 'secondary',
  short_term: 'warning',
  ultra_short: 'danger',
  // trading_style
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

// ==================== 组件 ====================

export function AccountOverview({ address, onAccountValueLoaded }: AccountOverviewProps) {
  const [data, setData] = useState<AccountOverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [statsModalOpen, setStatsModalOpen] = useState(false);

  const fmt = (n: number, d = 2) =>
    n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await traderApi.getAccountOverview(address);
      if (res.success && res.data) {
        setData(res.data);
        onAccountValueLoaded?.(res.data.account_total.total_value);
      }
    } catch {
      // 静默失败
    } finally {
      setLoading(false);
    }
  }, [address, onAccountValueLoaded]);

  useEffect(() => {
    loadData();
  }, [loadData]);

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
  const biasColor = data.direction_bias.bias === 'Long' ? 'success' : data.direction_bias.bias === 'Short' ? 'danger' : 'default';

  return (
    <Card>
      <CardBody className="py-4 gap-4">
        {/* ===== 交易员信息头部 ===== */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          {/* 左侧：头像 + 地址 + 名称 + 标签 */}
          <div className="flex items-start gap-3">
            {/* 头像 */}
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-default-100 flex items-center justify-center">
              <Icon icon="solar:user-bold" width={24} className="text-default-400" />
            </div>

            <div className="flex flex-col gap-1.5">
              {/* 地址 + 复制 */}
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

              {/* 显示名称 */}
              {trader_info.display_name && (
                <p className="text-base font-semibold leading-tight">
                  {trader_info.display_name}
                </p>
              )}

              {/* 标签 */}
              {trader_info.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-0.5">
                  {trader_info.tags.map((tag) => (
                    <Chip
                      key={tag.key}
                      size="sm"
                      variant="flat"
                      color={TAG_COLORS[tag.key] || 'default'}
                    >
                      {tag.label}
                    </Chip>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 右侧：操作按钮 */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              size="sm"
              color="primary"
              variant="flat"
              startContent={<Icon icon="solar:refresh-bold" width={16} />}
              onPress={loadData}
            >
              Real-time Data
            </Button>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon="solar:chart-2-bold" width={16} />}
              onPress={() => setStatsModalOpen(true)}
            >
              Trading Statistics
            </Button>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon="solar:eye-bold" width={16} />}
              isDisabled
            >
              One-click Monitor
            </Button>
            <Button
              size="sm"
              variant="flat"
              startContent={<Icon icon="solar:copy-bold" width={16} />}
              isDisabled
            >
              Copy Trading
            </Button>
          </div>
        </div>

        <Divider />

        {/* ===== 账户数据概览 ===== */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
          {/* 账户总值 */}
          <div>
            <p className="text-xs text-default-400">Account Value</p>
            <p className="text-lg font-bold">${fmt(data.account_total.total_value)}</p>
            <div className="flex gap-2 text-xs text-default-400">
              <span>Perp ${fmt(data.account_total.perpetual_value, 0)}</span>
              <span>Spot ${fmt(data.account_total.spot_value, 0)}</span>
            </div>
          </div>

          {/* 持仓价值 & 杠杆 */}
          <div>
            <p className="text-xs text-default-400">Position Value</p>
            <p className="text-lg font-bold">${fmt(data.positions.total_position_value)}</p>
            <p className="text-xs text-default-400">Leverage {data.positions.leverage_ratio}x</p>
          </div>

          {/* 可用保证金 */}
          <div>
            <p className="text-xs text-default-400">Free Margin</p>
            <p className="text-lg font-bold">${fmt(data.margin.free_margin)}</p>
            <p className="text-xs text-default-400">Withdrawable {data.margin.withdrawable_pct}%</p>
          </div>

          {/* 方向偏好 */}
          <div>
            <p className="text-xs text-default-400">Direction</p>
            <div className="flex items-center gap-2 mt-1">
              <Chip size="sm" color={biasColor} variant="flat">
                {data.direction_bias.bias}
              </Chip>
            </div>
            <div className="flex gap-2 text-xs mt-1">
              <span className="text-success">{data.direction_bias.long_exposure_pct}% L</span>
              <span className="text-danger">{data.direction_bias.short_exposure_pct}% S</span>
            </div>
          </div>

          {/* 未实现盈亏 */}
          <div>
            <p className="text-xs text-default-400">Unrealized PnL</p>
            <p className={`text-lg font-bold ${data.profit_loss.unrealized_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
              ${fmt(data.profit_loss.unrealized_pnl)}
            </p>
            <p className={`text-xs ${data.profit_loss.roe >= 0 ? 'text-success' : 'text-danger'}`}>
              ROE {data.profit_loss.roe}%
            </p>
          </div>

          {/* 7天胜率 */}
          <div>
            <p className="text-xs text-default-400">Win Rate (7d)</p>
            <p className="text-lg font-bold">{fmt(data.trading_performance_1w.win_rate)}%</p>
            <p className="text-xs text-default-400">{data.trading_performance_1w.closed_positions} closed</p>
          </div>

          {/* 7天最大回撤 */}
          <div>
            <p className="text-xs text-default-400">Max DD (7d)</p>
            <p className="text-lg font-bold text-danger">{fmt(data.trading_performance_1w.max_drawdown)}%</p>
            <p className="text-xs text-default-400">{data.trading_performance_1w.trades} trades</p>
          </div>
        </div>
      </CardBody>

      <TradingStatisticsModal
        isOpen={statsModalOpen}
        onClose={() => setStatsModalOpen(false)}
        address={address}
      />
    </Card>
  );
}
