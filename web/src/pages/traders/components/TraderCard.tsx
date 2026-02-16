import { useMemo, useId } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Tooltip } from '@heroui/react';
import { Icon } from '@iconify/react';
import { AreaChart, Area, YAxis, ResponsiveContainer } from 'recharts';
import type { Trader } from '@/services/api';
import { formatNumber, getRatingColor } from '@/utils';

const GREEN = '#17c964';
const RED = '#f31260';

// English display labels for tags
const TAG_EN_LABELS: Record<string, string> = {
  // account_value
  small_capital: 'Small Cap',
  medium_capital: 'Mid Cap',
  whale: 'Whale',
  // trading_rhythm
  long_term: 'Long-term',
  swing: 'Swing',
  short_term: 'Short-term',
  ultra_short: 'Ultra Short',
  // profit_status
  consistent_profit: 'Sustained Profit',
  volatile_profit: 'Mid Gain',
  break_even: 'Break Even',
  // direction_preference
  bearish: 'Bearish',
  neutral: 'Neutral',
  bullish: 'Bullish',
  // trading_style
  high_freq_stable: 'Cons. Hi-Freq',
  high_freq_aggressive: 'Volatile Strategy',
  low_freq_stable: 'Low-Freq Stable',
  stable_profit: 'Stable Profit',
  high_risk_high_return: 'High Risk',
  asymmetric_master: 'Asymmetric',
};

interface TraderCardProps {
  trader: Trader;
  onToggleStar: (address: string, isStarred: boolean) => void;
  isStarLoading: boolean;
}

function MiniSparkline({ data }: { data: [number, number][] }) {
  const uid = useId().replace(/:/g, '');
  const chartData = useMemo(() => data.map(([t, pnl]) => ({ t, pnl })), [data]);

  const yDomain = useMemo<[number, number]>(() => {
    if (chartData.length === 0) return [0, 0];
    const values = chartData.map((d) => d.pnl);
    let min = Math.min(...values, 0);
    let max = Math.max(...values, 0);
    const range = max - min || Math.abs(max) * 0.1 || 1;
    const padding = range * 0.05;
    return [min - padding, max + padding];
  }, [chartData]);

  const gradientOffset = useMemo(() => {
    const [min, max] = yDomain;
    if (max <= 0) return 0;
    if (min >= 0) return 1;
    return max / (max - min);
  }, [yDomain]);

  if (chartData.length < 2) return null;

  const strokeId = `sparkStroke-${uid}`;
  const fillId = `sparkFill-${uid}`;

  return (
    <ResponsiveContainer width="100%" height={56}>
      <AreaChart data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <defs>
          <linearGradient id={strokeId} x1="0" y1="0" x2="0" y2="1">
            <stop offset={0} stopColor={GREEN} />
            <stop offset={gradientOffset} stopColor={GREEN} />
            <stop offset={gradientOffset} stopColor={RED} />
            <stop offset={1} stopColor={RED} />
          </linearGradient>
          <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
            <stop offset={0} stopColor={GREEN} stopOpacity={0.3} />
            <stop offset={gradientOffset} stopColor={GREEN} stopOpacity={0.02} />
            <stop offset={gradientOffset} stopColor={RED} stopOpacity={0.02} />
            <stop offset={1} stopColor={RED} stopOpacity={0.3} />
          </linearGradient>
        </defs>
        <YAxis domain={yDomain} hide />
        <Area
          type="monotone"
          dataKey="pnl"
          stroke={`url(#${strokeId})`}
          strokeWidth={1.5}
          fill={`url(#${fillId})`}
          baseValue={0}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Format dollar amount with commas: $ 4,787,309.85 */
function formatDollar(value: number): string {
  return `$ ${formatNumber(Math.abs(value))}`;
}

/** Format PnL with sign: $ +2,119,507.62 or $ -500.00 */
function formatPnlDollar(value: number): string {
  const sign = value >= 0 ? '+' : '-';
  return `$ ${sign}${formatNumber(Math.abs(value))}`;
}

/** Format percent with space: 66.67 % */
function fmtPct(value: number): string {
  return `${(value * 100).toFixed(2)} %`;
}

export function TraderCard({ trader, onToggleStar, isStarLoading }: TraderCardProps) {
  const navigate = useNavigate();

  // Collect tags
  const tags = useMemo(() => {
    const result: { key: string; label: string }[] = [];
    const tagFields: (string | undefined)[] = [
      trader.tag_direction_preference,
      trader.tag_profit_status,
      trader.tag_trading_rhythm,
      trader.tag_account_value,
    ];
    for (const value of tagFields) {
      if (value) {
        result.push({ key: value, label: TAG_EN_LABELS[value] || value });
      }
    }
    if (trader.tag_trading_style) {
      for (const s of trader.tag_trading_style.split(',')) {
        const trimmed = s.trim();
        if (trimmed) {
          result.push({ key: trimmed, label: TAG_EN_LABELS[trimmed] || trimmed });
        }
      }
    }
    return result;
  }, [trader]);

  const totalPnl = trader.total_pnl || 0;
  const longPnl = trader.long_realized_pnl || 0;
  const shortPnl = trader.short_realized_pnl || 0;
  const accountValue = trader.account_value || trader.current_equity || 0;
  const perpValue = trader.perp_total_value || 0;
  const spotValue = Math.max(0, accountValue - perpValue);

  return (
    <Card
      isPressable
      onPress={() => navigate(`/traders/${trader.address}`)}
      className="w-full bg-content1 border border-default-200 dark:border-default-100"
    >
      <CardBody className="p-0">
        {/* Header: green dot + full address + action icons */}
        <div className="flex items-center justify-between px-5 py-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className={`shrink-0 text-sm font-bold ${getRatingColor(trader.rating)}`}>
              {trader.rating || '?'}
            </span>
            <span className="font-mono text-sm text-foreground truncate">
              {trader.display_name || trader.address}
            </span>
          </div>
          <div className="flex items-center gap-0.5 shrink-0">
            {/* Star */}
            <Tooltip content={trader.is_starred ? '取消收藏' : '收藏'} delay={300}>
              <button
                className="p-1.5 rounded-lg hover:bg-default-100 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isStarLoading) onToggleStar(trader.address, !trader.is_starred);
                }}
              >
                <Icon
                  icon={trader.is_starred ? 'solar:star-bold' : 'solar:star-line-duotone'}
                  width={20}
                  className={trader.is_starred ? 'text-warning' : 'text-default-400'}
                />
              </button>
            </Tooltip>
            {/* Dashboard */}
            <Tooltip content="Dashboard" delay={300}>
              <button
                className="p-1.5 rounded-lg hover:bg-default-100 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/traders/${trader.address}`);
                }}
              >
                <Icon icon="solar:chart-square-line-duotone" width={20} className="text-default-400" />
              </button>
            </Tooltip>
            {/* Copy address */}
            <Tooltip content="Copy address" delay={300}>
              <button
                className="p-1.5 rounded-lg hover:bg-default-100 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  navigator.clipboard.writeText(trader.address);
                }}
              >
                <Icon icon="solar:clipboard-line-duotone" width={20} className="text-default-400" />
              </button>
            </Tooltip>
            {/* Copy trading */}
            <Tooltip content="Copy Trading" delay={300}>
              <button
                className="p-1.5 rounded-lg hover:bg-default-100 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/copy-trading?address=${trader.address}`);
                }}
              >
                <Icon icon="solar:users-group-two-rounded-line-duotone" width={20} className="text-default-400" />
              </button>
            </Tooltip>
          </div>
        </div>

        {/* 5-section grid */}
        <div className="grid grid-cols-5 gap-0 divide-x divide-default-200 dark:divide-default-100 mx-4 mb-4 border border-default-200 dark:border-default-100 rounded-lg overflow-hidden">
          {/* Section 1: Tags + Metrics */}
          <div className="p-3 flex flex-col gap-2">
            <div className="flex flex-wrap gap-1">
              {tags.map((tag) => (
                <Chip
                  key={tag.key}
                  size="sm"
                  variant="bordered"
                  classNames={{
                    base: 'h-6 border-cyan-600/60',
                    content: 'text-[11px] text-cyan-400 px-1.5',
                  }}
                >
                  {tag.label}
                </Chip>
              ))}
            </div>
            <div className="text-xs text-default-500 space-y-1 mt-auto">
              <div className="flex justify-between">
                <span>Sharpe Ratio</span>
                <span className="text-foreground">{formatNumber(trader.sharpe_ratio)}</span>
              </div>
              <div className="flex justify-between">
                <span>Max Drawdown</span>
                <span className="text-foreground">{fmtPct(trader.max_drawdown)}</span>
              </div>
              <div className="flex justify-between">
                <span>Positions</span>
                <span className="text-foreground">{trader.current_positions || 0}</span>
              </div>
            </div>
          </div>

          {/* Section 2: Win Rate */}
          <div className="p-3 flex flex-col gap-2">
            <div className="text-xs text-default-400">Win Rate</div>
            <div className="text-2xl font-bold tracking-tight">{fmtPct(trader.win_rate)}</div>
            <div className="text-xs text-default-500 space-y-1 mt-auto">
              <div className="flex justify-between">
                <span>Long</span>
                <span className="text-foreground">{fmtPct(trader.long_win_rate || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span>Short</span>
                <span className="text-foreground">{fmtPct(trader.short_win_rate || 0)}</span>
              </div>
            </div>
          </div>

          {/* Section 3: Account Total Value */}
          <div className="p-3 flex flex-col gap-2">
            <div className="text-xs text-default-400">Account Total Value</div>
            <div className="text-lg font-bold tracking-tight">{formatDollar(accountValue)}</div>
            <div className="text-xs text-default-500 space-y-1 mt-auto">
              <div className="flex justify-between">
                <span>Perpetual</span>
                <span className="text-foreground">{formatDollar(perpValue)}</span>
              </div>
              <div className="flex justify-between">
                <span>Spot</span>
                <span className="text-foreground">{formatDollar(spotValue)}</span>
              </div>
            </div>
          </div>

          {/* Section 4: Net PnL */}
          <div className="p-3 flex flex-col gap-2">
            <div className="text-xs text-default-400">Net PnL</div>
            <div className={`text-lg font-bold tracking-tight ${totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatPnlDollar(totalPnl)}
            </div>
            <div className="text-xs space-y-1 mt-auto">
              <div className="flex justify-between">
                <span className="text-default-500">Long</span>
                <span className={longPnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                  {formatPnlDollar(longPnl)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-default-500">Short</span>
                <span className={shortPnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                  {formatPnlDollar(shortPnl)}
                </span>
              </div>
            </div>
          </div>

          {/* Section 5: Total PnL + Sparkline */}
          <div className="p-3 flex flex-col gap-1">
            <div className="flex items-center gap-1">
              <span className="text-xs text-default-400">Total PnL</span>
              <Tooltip content="Cumulative PnL from all-time history" delay={300}>
                <span><Icon icon="solar:info-circle-line-duotone" width={14} className="text-default-400" /></span>
              </Tooltip>
            </div>
            <div className={`text-lg font-bold tracking-tight ${totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatPnlDollar(totalPnl)}
            </div>
            <div className="flex-1 min-h-[56px]">
              {trader.pnl_sparkline && trader.pnl_sparkline.length > 1 ? (
                <MiniSparkline data={trader.pnl_sparkline} />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-[10px] text-default-300">
                  No data
                </div>
              )}
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
