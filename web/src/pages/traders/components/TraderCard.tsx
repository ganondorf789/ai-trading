import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Button, Tooltip } from '@heroui/react';
import { Icon } from '@iconify/react';
import { AreaChart, Area, YAxis } from 'recharts';
import type { Trader } from '@/services/api';
import { getRatingColor, formatNumber, formatPercent } from '@/utils';
import { TAG_OPTIONS } from '../constants';

const GREEN = '#17c964';
const RED = '#f31260';

// Build a lookup map from tag key → label
const TAG_LABEL_MAP: Record<string, string> = {};
for (const group of Object.values(TAG_OPTIONS)) {
  for (const opt of group) {
    TAG_LABEL_MAP[opt.key] = opt.label;
  }
}

// Tag category → chip color
const TAG_CATEGORY_COLORS: Record<string, 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger'> = {
  tag_account_value: 'warning',
  tag_direction_preference: 'primary',
  tag_profit_status: 'success',
  tag_trading_rhythm: 'secondary',
  tag_trading_style: 'default',
};

interface TraderCardProps {
  trader: Trader;
  onToggleStar: (address: string, isStarred: boolean) => void;
  isStarLoading: boolean;
}

function MiniSparkline({ data }: { data: [number, number][] }) {
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

  return (
    <AreaChart width={120} height={48} data={chartData} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
      <defs>
        <linearGradient id="sparkStroke" x1="0" y1="0" x2="0" y2="1">
          <stop offset={0} stopColor={GREEN} />
          <stop offset={gradientOffset} stopColor={GREEN} />
          <stop offset={gradientOffset} stopColor={RED} />
          <stop offset={1} stopColor={RED} />
        </linearGradient>
        <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
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
        stroke="url(#sparkStroke)"
        strokeWidth={1.5}
        fill="url(#sparkFill)"
        baseValue={0}
        dot={false}
        isAnimationActive={false}
      />
    </AreaChart>
  );
}

function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${formatNumber(value, 0)}`;
}

function formatPnl(value: number): string {
  const prefix = value >= 0 ? '+' : '';
  return `${prefix}${formatCompact(value)}`;
}

export function TraderCard({ trader, onToggleStar, isStarLoading }: TraderCardProps) {
  const navigate = useNavigate();
  const shortAddr = `${trader.address.slice(0, 6)}...${trader.address.slice(-4)}`;

  // Collect tags
  const tags = useMemo(() => {
    const result: { key: string; label: string; category: string }[] = [];
    const tagFields: [string, string | undefined][] = [
      ['tag_account_value', trader.tag_account_value],
      ['tag_direction_preference', trader.tag_direction_preference],
      ['tag_profit_status', trader.tag_profit_status],
      ['tag_trading_rhythm', trader.tag_trading_rhythm],
    ];
    for (const [category, value] of tagFields) {
      if (value) {
        result.push({ key: value, label: TAG_LABEL_MAP[value] || value, category });
      }
    }
    if (trader.tag_trading_style) {
      for (const s of trader.tag_trading_style.split(',')) {
        const trimmed = s.trim();
        if (trimmed) {
          result.push({ key: trimmed, label: TAG_LABEL_MAP[trimmed] || trimmed, category: 'tag_trading_style' });
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

  return (
    <Card
      isPressable
      onPress={() => navigate(`/traders/${trader.address}`)}
      className="w-full dark:bg-content1 hover:bg-content2 transition-colors"
    >
      <CardBody className="p-0">
        {/* Header row: rating + address + actions */}
        <div className="flex items-center justify-between px-4 pt-3 pb-1">
          <div className="flex items-center gap-2 min-w-0">
            <span className={`font-bold text-lg ${getRatingColor(trader.rating)}`}>
              {trader.rating}
            </span>
            <Tooltip content={trader.address} placement="top" delay={300}>
              <span className="font-mono text-sm text-default-500 truncate">
                {trader.display_name ? (
                  <>
                    <span className="font-medium text-foreground">{trader.display_name}</span>
                    {' '}
                    <span className="text-xs text-default-400">({shortAddr})</span>
                  </>
                ) : shortAddr}
              </span>
            </Tooltip>
            <span className="text-xs text-default-400">
              Score: {formatNumber(trader.overall_score)}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <Button
              isIconOnly
              size="sm"
              variant="light"
              color={trader.is_starred ? 'warning' : 'default'}
              isLoading={isStarLoading}
              onPress={() => onToggleStar(trader.address, !trader.is_starred)}
              onClick={(e) => e.stopPropagation()}
            >
              <Icon
                icon={trader.is_starred ? 'solar:star-bold' : 'solar:star-line-duotone'}
                width={18}
                className={trader.is_starred ? 'text-warning' : 'text-default-400'}
              />
            </Button>
            <Button
              isIconOnly
              size="sm"
              variant="light"
              onPress={() => navigator.clipboard.writeText(trader.address)}
              onClick={(e) => e.stopPropagation()}
            >
              <Icon icon="solar:copy-line-duotone" width={16} className="text-default-400" />
            </Button>
          </div>
        </div>

        {/* 5-section grid */}
        <div className="grid grid-cols-5 gap-0 divide-x divide-divider px-2 pb-3">
          {/* Section 1: Tags + Metrics */}
          <div className="px-2 flex flex-col gap-1.5">
            <div className="flex flex-wrap gap-1">
              {tags.slice(0, 4).map((tag) => (
                <Chip
                  key={tag.key}
                  size="sm"
                  variant="flat"
                  color={TAG_CATEGORY_COLORS[tag.category] || 'default'}
                  classNames={{ base: 'h-5', content: 'text-[10px] px-1' }}
                >
                  {tag.label}
                </Chip>
              ))}
              {tags.length > 4 && (
                <Chip size="sm" variant="flat" classNames={{ base: 'h-5', content: 'text-[10px] px-1' }}>
                  +{tags.length - 4}
                </Chip>
              )}
            </div>
            <div className="text-[11px] text-default-500 space-y-0.5">
              <div>Sharpe: {formatNumber(trader.sharpe_ratio)}</div>
              <div>MaxDD: {formatPercent(trader.max_drawdown)}</div>
              <div>Pos: {trader.current_positions || 0}</div>
            </div>
          </div>

          {/* Section 2: Win Rate */}
          <div className="px-3 flex flex-col justify-center gap-1">
            <div className="text-[10px] text-default-400 uppercase tracking-wide">Win Rate</div>
            <div className="text-xl font-bold">{formatPercent(trader.win_rate)}</div>
            <div className="text-[11px] text-default-500 space-y-0.5">
              <div>
                <span className="text-green-500">L</span> {formatPercent(trader.long_win_rate || 0)}
              </div>
              <div>
                <span className="text-red-500">S</span> {formatPercent(trader.short_win_rate || 0)}
              </div>
            </div>
          </div>

          {/* Section 3: Account Value */}
          <div className="px-3 flex flex-col justify-center gap-1">
            <div className="text-[10px] text-default-400 uppercase tracking-wide">Account</div>
            <div className="text-sm font-semibold">{formatCompact(accountValue)}</div>
            <div className="text-[11px] text-default-500 space-y-0.5">
              <div>Perp {formatCompact(perpValue)}</div>
            </div>
          </div>

          {/* Section 4: Net PnL */}
          <div className="px-3 flex flex-col justify-center gap-1">
            <div className="text-[10px] text-default-400 uppercase tracking-wide">Net PnL</div>
            <div className={`text-sm font-semibold ${totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatPnl(totalPnl)}
            </div>
            <div className="text-[11px] text-default-500 space-y-0.5">
              <div>
                <span className="text-green-500">L</span>{' '}
                <span className={longPnl >= 0 ? 'text-green-500' : 'text-red-500'}>{formatPnl(longPnl)}</span>
              </div>
              <div>
                <span className="text-red-500">S</span>{' '}
                <span className={shortPnl >= 0 ? 'text-green-500' : 'text-red-500'}>{formatPnl(shortPnl)}</span>
              </div>
            </div>
          </div>

          {/* Section 5: Total PnL + Sparkline */}
          <div className="px-3 flex flex-col justify-center gap-1">
            <div className="text-[10px] text-default-400 uppercase tracking-wide">Total PnL</div>
            <div className={`text-sm font-semibold ${totalPnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {formatPnl(totalPnl)}
            </div>
            {trader.pnl_sparkline && trader.pnl_sparkline.length > 1 && (
              <MiniSparkline data={trader.pnl_sparkline} />
            )}
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
