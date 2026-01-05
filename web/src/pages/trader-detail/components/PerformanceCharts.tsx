import { Card, CardBody } from '@heroui/card';
import { Tabs, Tab } from '@heroui/tabs';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { TraderHistory } from '@/services/api';

interface PerformanceChartsProps {
  history: TraderHistory | null;
  timeRange: number;
  chartLoading: boolean;
  onTimeRangeChange: (days: number) => void;
}

export function PerformanceCharts({
  history,
  timeRange,
  chartLoading,
  onTimeRangeChange,
}: PerformanceChartsProps) {
  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const formatChartData = (data: { timestamp: string; value: number }[]) => {
    return data.map((item) => ({
      ...item,
      date: new Date(item.timestamp).toLocaleDateString(),
    }));
  };

  return (
    <Card>
      <CardBody>
        {/* 时间范围选择器 */}
        <div className="flex gap-2 mb-4 flex-wrap">
          <span className="text-sm text-gray-500 self-center">时间范围:</span>
          {[
            { label: '7天', value: 7 },
            { label: '30天', value: 30 },
            { label: '90天', value: 90 },
            { label: '180天', value: 180 },
            { label: '1年', value: 365 },
            { label: '全部', value: 0 },
          ].map((range) => (
            <Button
              key={range.value}
              size="sm"
              variant={timeRange === range.value ? 'solid' : 'bordered'}
              color={timeRange === range.value ? 'primary' : 'default'}
              onPress={() => onTimeRangeChange(range.value)}
              isDisabled={chartLoading}
            >
              {range.label}
            </Button>
          ))}
        </div>

        <Tabs aria-label="Performance charts">
          <Tab key="roi" title="收益率 (ROI)">
            <div className="py-4">
              {chartLoading ? (
                <div className="flex justify-center items-center h-[400px]">
                  <Spinner size="lg" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={formatChartData(history?.roi || [])}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis
                      tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                    />
                    <Tooltip
                      formatter={(value) => [`${formatPercent(value as number)}`, 'ROI']}
                      labelStyle={{ color: '#000' }}
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#8b5cf6"
                      strokeWidth={2}
                      name="ROI"
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </Tab>
          <Tab key="pnl" title="收益额 (PnL)">
            <div className="py-4">
              {chartLoading ? (
                <div className="flex justify-center items-center h-[400px]">
                  <Spinner size="lg" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={formatChartData(history?.pnl || [])}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                    <Tooltip
                      formatter={(value) => [`$${formatNumber(value as number)}`, 'PnL']}
                      labelStyle={{ color: '#000' }}
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#10b981"
                      strokeWidth={2}
                      name="Total PnL"
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </Tab>
          <Tab key="equity" title="资产 (Equity)">
            <div className="py-4">
              {chartLoading ? (
                <div className="flex justify-center items-center h-[400px]">
                  <Spinner size="lg" />
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={formatChartData(history?.equity || [])}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12 }}
                      angle={-45}
                      textAnchor="end"
                      height={80}
                    />
                    <YAxis tickFormatter={(value) => `$${value.toFixed(0)}`} />
                    <Tooltip
                      formatter={(value) => [
                        `$${formatNumber(value as number)}`,
                        'Equity',
                      ]}
                      labelStyle={{ color: '#000' }}
                      contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      name="Current Equity"
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </Tab>
        </Tabs>
      </CardBody>
    </Card>
  );
}
