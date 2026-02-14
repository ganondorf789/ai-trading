import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Spinner } from '@heroui/spinner';
import { Select, SelectItem } from '@heroui/select';
import { Divider } from '@heroui/divider';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { hyperliquidApi } from '@/services/hyperliquid';
import type { PortfolioPeriod, PortfolioPeriodData } from '@/types/hyperliquid';
import type { AccountOverviewData } from './AccountOverview';

// ==================== 类型 ====================

type TimeRange = '1d' | '1w' | '1m' | 'all';
type MetricType = 'pnl' | 'account_value';

interface PnlCurveChartProps {
  address: string;
  accountData?: AccountOverviewData | null;
}

// ==================== 常量 ====================

const TIME_RANGES: { key: TimeRange; label: string }[] = [
  { key: '1d', label: '1 Day' },
  { key: '1w', label: '1 Week' },
  { key: '1m', label: '1 Month' },
  { key: 'all', label: 'All' },
];

const METRICS: { key: MetricType; label: string }[] = [
  { key: 'pnl', label: 'Total PnL' },
  { key: 'account_value', label: 'Account Value' },
];

const TIME_RANGE_TO_PERIOD: Record<TimeRange, PortfolioPeriod> = {
  '1d': 'day',
  '1w': 'week',
  '1m': 'month',
  'all': 'allTime',
};

function formatTime(ts: number, range: TimeRange): string {
  const d = new Date(ts);
  if (range === '1d') {
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  }
  if (range === '1w') {
    return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
  }
  return `${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}-${d.getDate().toString().padStart(2, '0')}`;
}

function formatDollar(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `$ ${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$ ${(v / 1_000).toFixed(1)}K`;
  return `$ ${v.toFixed(2)}`;
}

function formatFullDollar(v: number): string {
  return `$ ${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const GREEN = '#17c964';
const RED = '#f31260';

// ==================== PriceTag 子组件 ====================

function PriceTag({ viewBox, value }: { viewBox?: { x: number; y: number; width: number }; value: number }) {
  if (!viewBox) return null;
  const color = value >= 0 ? GREEN : RED;
  const text = formatFullDollar(value);
  const x = viewBox.x + viewBox.width + 2;
  const y = viewBox.y;
  const paddingX = 8;
  const boxH = 22;
  // 用隐藏 text 测量宽度，估算：每字符约 6.6px (fontSize 11)
  const estimatedTextW = text.length * 6.6;
  const boxW = estimatedTextW + paddingX * 2;

  return (
    <g style={{ zIndex: 10 }}>
      <rect x={x} y={y - boxH / 2} width={boxW} height={boxH} rx={3} fill={color} />
      <text
        x={x + paddingX}
        y={y + 4}
        fill="#fff"
        fontSize={11}
        fontWeight="bold"
        dominantBaseline="middle"
        dy={0}
      >
        {text}
      </text>
    </g>
  );
}

function formatPnl(n: number): string {
  const prefix = n >= 0 ? '+' : '';
  return `${prefix}${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ==================== Progress Bar 子组件 ====================

function ProgressBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="w-full h-2 bg-default-200 rounded-full overflow-hidden">
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${Math.min(value, 100)}%`, backgroundColor: color }}
      />
    </div>
  );
}

// ==================== Position Panel 子组件 ====================

function PositionPanel({ data }: { data: AccountOverviewData }) {
  const fmt = (n: number) =>
    n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const longPct = data.direction_bias.long_exposure_pct;
  const shortPct = data.direction_bias.short_exposure_pct;
  const totalDist = data.position_distribution.long_value + data.position_distribution.short_value;
  const longDistPct = totalDist > 0 ? (data.position_distribution.long_value / totalDist) * 100 : 0;

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Perp Total Value */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-default-400">Perp Total Value</span>
          <Chip size="sm" variant="bordered" className="text-[10px]">Current Positions</Chip>
        </div>
        <p className="text-2xl font-bold">$ {fmt(data.positions.perp_total_value)}</p>
      </div>

      {/* Average Margin Used Ratio */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-default-400">Average Margin Used Ratio</span>
          <span className="text-xs font-semibold">{data.positions.avg_margin_used_ratio} %</span>
        </div>
        <ProgressBar value={data.positions.avg_margin_used_ratio} color="#22d3ee" />
      </div>

      <Divider className="my-0.5" />

      {/* Direction Bias */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-default-400">Direction Bias</span>
          <span className="text-xs font-bold">{data.direction_bias.bias}</span>
        </div>

        <div className="space-y-2">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-default-400">Long Exposure</span>
              <span className="text-xs font-semibold text-success">{longPct} %</span>
            </div>
            <ProgressBar value={longPct} color="#17c964" />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs text-default-400">Short Exposure</span>
              <span className="text-xs font-semibold text-danger">{shortPct} %</span>
            </div>
            <ProgressBar value={shortPct} color="#f31260" />
          </div>
        </div>
      </div>

      <Divider className="my-0.5" />

      {/* Position Distribution */}
      <div>
        <p className="text-xs text-default-400 mb-2">Position Distribution</p>
        <div className="flex justify-between mb-1">
          <div>
            <p className="text-[10px] text-default-400">Long Value</p>
            <p className="text-sm font-bold text-success">$ {fmt(data.position_distribution.long_value)}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-default-400">Short Value</p>
            <p className="text-sm font-bold text-danger">$ {fmt(data.position_distribution.short_value)}</p>
          </div>
        </div>
        {/* Stacked bar */}
        <div className="w-full h-2 rounded-full overflow-hidden flex">
          <div
            className="h-full rounded-l-full"
            style={{ width: `${longDistPct}%`, backgroundColor: '#17c964' }}
          />
          <div
            className="h-full rounded-r-full flex-1"
            style={{ backgroundColor: '#f31260' }}
          />
        </div>
      </div>

      <Divider className="my-0.5" />

      {/* ROE & uPnL */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">ROE</span>
          <span className={`text-sm font-bold ${data.profit_loss.roe >= 0 ? 'text-success' : 'text-danger'}`}>
            {data.profit_loss.roe >= 0 ? '+' : ''}{data.profit_loss.roe} %
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">uPnL</span>
          <span className={`text-sm font-bold ${data.profit_loss.unrealized_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
            $ {formatPnl(data.profit_loss.unrealized_pnl)}
          </span>
        </div>
      </div>
    </div>
  );
}

// ==================== 主组件 ====================

export function PnlCurveChart({ address, accountData }: PnlCurveChartProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>('1w');
  const [metric, setMetric] = useState<MetricType>('pnl');
  const [portfolioMap, setPortfolioMap] = useState<Map<PortfolioPeriod, PortfolioPeriodData> | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    hyperliquidApi.getPortfolio(address).then((res) => {
      const map = new Map<PortfolioPeriod, PortfolioPeriodData>();
      for (const [period, data] of res) {
        map.set(period, data);
      }
      setPortfolioMap(map);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [address]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // 构建图表数据
  const chartData = useMemo(() => {
    if (!portfolioMap) return [];
    const periodKey = TIME_RANGE_TO_PERIOD[timeRange];
    const periodData = portfolioMap.get(periodKey);
    if (!periodData) return [];

    const pnlHistory = periodData.pnlHistory;
    const accountValueHistory = periodData.accountValueHistory;

    // 以 accountValueHistory 的时间戳为基准构建数据点
    const pnlMap = new Map(pnlHistory.map(([ts, val]) => [ts, parseFloat(val)]));

    let points = accountValueHistory.map(([ts, val]) => ({
      time: ts,
      label: formatTime(ts, timeRange),
      account_value: parseFloat(val),
      pnl: pnlMap.get(ts) ?? 0,
    }));

    // 降采样：点太多时只保留一部分，提高渲染性能
    const MAX_POINTS = 500;
    if (points.length > MAX_POINTS) {
      const step = Math.ceil(points.length / MAX_POINTS);
      points = points.filter((_, i) => i % step === 0 || i === points.length - 1);
    }

    return points;
  }, [portfolioMap, timeRange]);

  // 计算变化额和变化率
  const summary = useMemo(() => {
    if (chartData.length < 2) return null;
    const first = chartData[0];
    const last = chartData[chartData.length - 1];
    const key = metric;
    const change = last[key] - first[key];
    const pct = first[key] !== 0 ? (change / Math.abs(first[key])) * 100 : 0;
    return { change, pct, current: last[key] };
  }, [chartData, metric]);

  // 计算 Y 轴范围
  const yDomain = useMemo(() => {
    if (chartData.length === 0) return [0, 0];
    const values = chartData.map((d) => d[metric]);
    let min = Math.min(...values);
    let max = Math.max(...values);
    // PnL 模式下确保 0 在可视范围内
    if (metric === 'pnl') {
      min = Math.min(min, 0);
      max = Math.max(max, 0);
    }
    const range = max - min || Math.abs(max) * 0.1 || 1;
    const padding = range * 0.1;
    return [min - padding, max + padding];
  }, [chartData, metric]);

  // 0 轴在渐变中的位置 (0=顶部, 1=底部)
  const gradientOffset = useMemo(() => {
    const [min, max] = yDomain;
    if (max <= 0) return 0;
    if (min >= 0) return 1;
    return max / (max - min);
  }, [yDomain]);

  const lastValue = chartData.length > 0 ? chartData[chartData.length - 1][metric] : 0;
  const lastValueColor = lastValue >= 0 ? GREEN : RED;

  return (
    <>
      <div className="flex gap-4">
        {/* 左侧 Position Panel */}
        {accountData && (
          <Card className="w-[280px] flex-shrink-0 hidden lg:block">
            <CardBody className="p-4">
              <PositionPanel data={accountData} />
            </CardBody>
          </Card>
        )}

        {/* 右侧 Chart */}
        <Card className="flex-1 min-w-0">
          <CardBody className="py-4">
            {/* 头部：汇总 + 右侧下拉 */}
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              {/* 汇总数值 */}
              {summary && !loading ? (
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold">{formatDollar(summary.current)}</span>
                  <span className={`text-sm font-semibold ${summary.change >= 0 ? 'text-success' : 'text-danger'}`}>
                    {summary.change >= 0 ? '+' : ''}
                    {formatDollar(summary.change)} ({summary.pct >= 0 ? '+' : ''}{summary.pct.toFixed(2)}%)
                  </span>
                </div>
              ) : (
                <div />
              )}

              {/* 右侧：指标 + 时间范围 Select */}
              <div className="flex items-center gap-2">
                <Select
                  size="sm"
                  variant="bordered"
                  selectedKeys={new Set([metric])}
                  onSelectionChange={(keys) => {
                    const key = Array.from(keys)[0] as MetricType;
                    if (key) setMetric(key);
                  }}
                  className="w-[140px]"
                  aria-label="Metric"
                >
                  {METRICS.map((m) => (
                    <SelectItem key={m.key}>{m.label}</SelectItem>
                  ))}
                </Select>
                <Select
                  size="sm"
                  variant="bordered"
                  selectedKeys={new Set([timeRange])}
                  onSelectionChange={(keys) => {
                    const key = Array.from(keys)[0] as TimeRange;
                    if (key) setTimeRange(key);
                  }}
                  className="w-[120px]"
                  aria-label="Time range"
                >
                  {TIME_RANGES.map((r) => (
                    <SelectItem key={r.key}>{r.label}</SelectItem>
                  ))}
                </Select>
              </div>
            </div>

            {/* Chart */}
            {loading ? (
              <div className="flex justify-center items-center h-[380px]">
                <Spinner size="lg" />
              </div>
            ) : chartData.length === 0 ? (
              <div className="flex justify-center items-center h-[380px] text-default-400">
                No data available for this time range
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={380}>
                <AreaChart data={chartData} margin={{ top: 5, right: 125, left: 10, bottom: 5 }}>
                  <defs>
                    {/* 折线渐变：0 以上绿色，0 以下红色 */}
                    <linearGradient id="pnl-stroke-split" x1="0" y1="0" x2="0" y2="1">
                      <stop offset={0} stopColor={GREEN} />
                      <stop offset={gradientOffset} stopColor={GREEN} />
                      <stop offset={gradientOffset} stopColor={RED} />
                      <stop offset={1} stopColor={RED} />
                    </linearGradient>
                    {/* 面积填充渐变：靠近曲线较深，向 0 轴透明 */}
                    <linearGradient id="pnl-fill-split" x1="0" y1="0" x2="0" y2="1">
                      <stop offset={0} stopColor={GREEN} stopOpacity={0.3} />
                      <stop offset={gradientOffset} stopColor={GREEN} stopOpacity={0.02} />
                      <stop offset={gradientOffset} stopColor={RED} stopOpacity={0.02} />
                      <stop offset={1} stopColor={RED} stopOpacity={0.3} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.1} vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: '#333' }}
                    minTickGap={40}
                  />
                  <YAxis
                    orientation="right"
                    domain={yDomain}
                    tickFormatter={formatDollar}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={120}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(0,0,0,0.85)',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                    formatter={(value: any) => {
                      const v = Number(value);
                      const color = v >= 0 ? GREEN : RED;
                      return [
                        <span style={{ color }}>{formatFullDollar(v)}</span>,
                        metric === 'pnl' ? 'Total PnL' : 'Account Value',
                      ];
                    }}
                    labelFormatter={(label) => label}
                  />
                  <Area
                    type="monotone"
                    dataKey={metric}
                    stroke="url(#pnl-stroke-split)"
                    strokeWidth={2}
                    fill="url(#pnl-fill-split)"
                    baseValue={0}
                    dot={false}
                    activeDot={({ cx, cy, payload }: any) => {
                      const v = payload[metric];
                      const color = v >= 0 ? GREEN : RED;
                      return <circle cx={cx} cy={cy} r={4} fill="#fff" stroke={color} strokeWidth={2} />;
                    }}
                  />
                  {/* 当前值虚线 + 价格标签（放在最后确保层级最高） */}
                  <ReferenceLine
                    y={lastValue}
                    stroke={lastValueColor}
                    strokeDasharray="4 4"
                    strokeOpacity={0.6}
                    ifOverflow="extendDomain"
                    label={<PriceTag value={lastValue} />}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      {/* 小屏幕下 Position Panel 显示在图表下方 */}
      {accountData && (
        <Card className="block lg:hidden">
          <CardBody className="p-4">
            <PositionPanel data={accountData} />
          </CardBody>
        </Card>
      )}
    </>
  );
}
