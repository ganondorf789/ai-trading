import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardBody } from '@heroui/card';
import { Button } from '@heroui/button';
import { Spinner } from '@heroui/spinner';
import { ButtonGroup } from '@heroui/button';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { traderApi } from '@/services/api';

// ==================== 类型 ====================

interface PnlPoint {
  time: number;
  amount: number;
  fee: number;
  type: string;
  coin: string;
  cumulative_pnl: number;
  cumulative_funding: number;
  cumulative_deposit: number;
  cumulative_total: number;
}

interface PnlCurveData {
  base: {
    pnl: number;
    funding: number;
    deposit: number;
    total: number;
  };
  points: PnlPoint[];
}

type TimeRange = '1d' | '1w' | '1m' | 'all';
type MetricType = 'pnl' | 'account_value';

interface PnlCurveChartProps {
  address: string;
  accountValue?: number;
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

// ==================== 辅助函数 ====================

function getDateRange(range: TimeRange): { start_date?: string; end_date?: string } {
  if (range === 'all') return {};
  const now = new Date();
  const start = new Date(now);
  switch (range) {
    case '1d':
      start.setDate(start.getDate() - 1);
      break;
    case '1w':
      start.setDate(start.getDate() - 7);
      break;
    case '1m':
      start.setMonth(start.getMonth() - 1);
      break;
  }
  const fmt = (d: Date) => d.toISOString().split('T')[0];
  return { start_date: fmt(start), end_date: fmt(now) };
}

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
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`;
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}K`;
  return `$${v.toFixed(2)}`;
}

// ==================== 组件 ====================

export function PnlCurveChart({ address, accountValue }: PnlCurveChartProps) {
  const [timeRange, setTimeRange] = useState<TimeRange>('1w');
  const [metric, setMetric] = useState<MetricType>('pnl');
  const [curveData, setCurveData] = useState<PnlCurveData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadCurve = useCallback(async () => {
    setLoading(true);
    try {
      const params = getDateRange(timeRange);
      const res = await traderApi.getPnlCurve(address, params);
      if (res.success && res.data) {
        setCurveData(res.data);
      }
    } catch {
      // 静默
    } finally {
      setLoading(false);
    }
  }, [address, timeRange]);

  useEffect(() => {
    loadCurve();
  }, [loadCurve]);

  // 构建图表数据
  const chartData = useMemo(() => {
    if (!curveData || curveData.points.length === 0) return [];

    const points = curveData.points;
    const latestTotal = points[points.length - 1].cumulative_total;

    // 降采样：点太多时只保留一部分，提高渲染性能
    let sampled = points;
    const MAX_POINTS = 500;
    if (points.length > MAX_POINTS) {
      const step = Math.ceil(points.length / MAX_POINTS);
      sampled = points.filter((_, i) => i % step === 0 || i === points.length - 1);
    }

    return sampled.map((p) => ({
      time: p.time,
      label: formatTime(p.time, timeRange),
      pnl: p.cumulative_total,
      account_value:
        accountValue != null
          ? accountValue - (latestTotal - p.cumulative_total)
          : p.cumulative_total,
    }));
  }, [curveData, timeRange, accountValue]);

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

  const lineColor = summary && summary.change >= 0 ? '#17c964' : '#f31260';
  const gradientId = `pnl-gradient-${metric}`;

  return (
    <Card>
      <CardBody className="py-4">
        {/* 头部：指标切换 + 汇总 + 时间范围 */}
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div className="flex items-center gap-4">
            {/* 指标切换 */}
            <ButtonGroup size="sm" variant="flat">
              {METRICS.map((m) => (
                <Button
                  key={m.key}
                  color={metric === m.key ? 'primary' : 'default'}
                  variant={metric === m.key ? 'solid' : 'flat'}
                  onPress={() => setMetric(m.key)}
                >
                  {m.label}
                </Button>
              ))}
            </ButtonGroup>

            {/* 汇总数值 */}
            {summary && !loading && (
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold">{formatDollar(summary.current)}</span>
                <span className={`text-sm font-semibold ${summary.change >= 0 ? 'text-success' : 'text-danger'}`}>
                  {summary.change >= 0 ? '+' : ''}
                  {formatDollar(summary.change)} ({summary.pct >= 0 ? '+' : ''}{summary.pct.toFixed(2)}%)
                </span>
              </div>
            )}
          </div>

          {/* 时间范围 */}
          <ButtonGroup size="sm" variant="flat">
            {TIME_RANGES.map((r) => (
              <Button
                key={r.key}
                color={timeRange === r.key ? 'primary' : 'default'}
                variant={timeRange === r.key ? 'solid' : 'flat'}
                onPress={() => setTimeRange(r.key)}
              >
                {r.label}
              </Button>
            ))}
          </ButtonGroup>
        </div>

        {/* 图表 */}
        {loading ? (
          <div className="flex justify-center items-center h-[300px]">
            <Spinner size="lg" />
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex justify-center items-center h-[300px] text-default-400">
            No data available for this time range
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={lineColor} stopOpacity={0.15} />
                  <stop offset="95%" stopColor={lineColor} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.15} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                minTickGap={40}
              />
              <YAxis
                tickFormatter={(v) => formatDollar(v)}
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
                width={70}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(0,0,0,0.85)',
                  border: 'none',
                  borderRadius: '8px',
                  color: '#fff',
                  fontSize: '12px',
                }}
                formatter={(value: any) => [
                  `$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                  metric === 'pnl' ? 'Total PnL' : 'Account Value',
                ]}
                labelFormatter={(label) => label}
              />
              <Area
                type="monotone"
                dataKey={metric}
                stroke={lineColor}
                strokeWidth={2}
                fill={`url(#${gradientId})`}
                dot={false}
                activeDot={{ r: 4, fill: lineColor }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardBody>
    </Card>
  );
}
