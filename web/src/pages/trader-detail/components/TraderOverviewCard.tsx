import { Card, CardHeader, CardBody } from '@heroui/card';
import { Button } from '@heroui/button';
import { Divider } from '@heroui/divider';
import { Icon } from '@iconify/react';
import { Trader } from '@/services/api';

interface TraderOverviewCardProps {
  trader: Trader;
  address: string;
  aiAnalyzing: boolean;
  aiAnalysisData: any;
  refreshing: boolean;
  onAiAnalysis: () => void;
  onRefresh: () => void;
  isStarLoading?: boolean;
  onToggleStar?: (address: string, isStarred: boolean) => void;
}

export function TraderOverviewCard({
  trader,
  address,
  aiAnalyzing,
  aiAnalysisData,
  refreshing,
  onAiAnalysis,
  onRefresh,
  isStarLoading = false,
  onToggleStar,
}: TraderOverviewCardProps) {
  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  const getRatingColor = (rating: string) => {
    const colors: Record<string, string> = {
      S: 'text-purple-500',
      A: 'text-blue-500',
      B: 'text-green-500',
      C: 'text-yellow-500',
      D: 'text-orange-500',
      F: 'text-red-500',
    };
    return colors[rating] || 'text-gray-500';
  };

  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex justify-between items-center w-full">
          <div className="flex items-center gap-3">
            <Button
              isIconOnly
              size="lg"
              variant="light"
              color={trader.is_starred ? "warning" : "default"}
              isLoading={isStarLoading}
              onPress={() => onToggleStar?.(address, !trader.is_starred)}
            >
              <Icon 
                icon={trader.is_starred ? "solar:star-bold" : "solar:star-line-duotone"} 
                width={24} 
                className={trader.is_starred ? "text-warning" : "text-default-400"}
              />
            </Button>
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                {trader.display_name ? trader.display_name : 'Trader Overview'}
              </h1>
              <p className="text-sm text-gray-500 font-mono mt-1">{address}</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Button
              size="sm"
              color="secondary"
              variant="flat"
              isLoading={aiAnalyzing}
              onPress={onAiAnalysis}
              startContent={!aiAnalyzing && <Icon icon={aiAnalysisData ? "solar:eye-linear" : "solar:magic-stick-2-linear"} width={16} />}
            >
              {aiAnalyzing ? 'AI分析中...' : aiAnalysisData ? '查看AI分析' : 'AI深度分析'}
            </Button>
            <Button
              size="sm"
              color="primary"
              variant="flat"
              isLoading={refreshing}
              onPress={onRefresh}
              startContent={!refreshing && <Icon icon="solar:refresh-linear" width={16} />}
            >
              {refreshing ? '分析中...' : '刷新分析'}
            </Button>
            <div className="text-right">
              <p className="text-sm text-gray-500">Rating</p>
              <p className={`text-4xl font-bold ${getRatingColor(trader.rating)}`}>
                {trader.rating}
              </p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Score</p>
              <p className="text-2xl font-bold">{formatNumber(trader.overall_score)}</p>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardBody>
        {/* 基础统计 */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">基础统计</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <p className="text-xs text-gray-500">总交易数</p>
              <p className="text-lg font-bold">{trader.total_trades}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">盈利笔数</p>
              <p className="text-lg font-bold text-green-500">{trader.winning_trades || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">亏损笔数</p>
              <p className="text-lg font-bold text-red-500">{trader.losing_trades || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">胜率</p>
              <p className="text-lg font-bold">{formatPercent(trader.win_rate)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">活跃天数</p>
              <p className="text-lg font-bold">{trader.active_days}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">交易品种数</p>
              <p className="text-lg font-bold">{trader.unique_symbols || 0}</p>
            </div>
          </div>
        </div>

        <Divider className="my-3" />

        {/* 盈亏指标 */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">盈亏指标</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <p className="text-xs text-gray-500">总盈亏</p>
              <p className={`text-lg font-bold ${trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${formatNumber(trader.total_pnl)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">已实现盈亏</p>
              <p className={`text-lg font-bold ${(trader.realized_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${formatNumber(trader.realized_pnl || 0)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">未实现盈亏</p>
              <p className={`text-lg font-bold ${(trader.unrealized_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${formatNumber(trader.unrealized_pnl || 0)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">ROI</p>
              <p className={`text-lg font-bold ${trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                {formatPercent(trader.roi)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">盈亏比</p>
              <p className="text-lg font-bold">{formatNumber(trader.profit_factor)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">7天盈亏</p>
              <p className={`text-lg font-bold ${(trader.recent_7d_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                ${formatNumber(trader.recent_7d_pnl || 0)}
              </p>
            </div>
          </div>
        </div>

        <Divider className="my-3" />

        {/* 风险指标 */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">风险指标</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <p className="text-xs text-gray-500">最大回撤</p>
              <p className="text-lg font-bold text-red-500">{formatPercent(trader.max_drawdown)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">最大回撤 (USD)</p>
              <p className="text-lg font-bold text-red-500">${formatNumber(trader.max_drawdown_abs || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Sharpe Ratio</p>
              <p className="text-lg font-bold">{formatNumber(trader.sharpe_ratio)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Sortino Ratio</p>
              <p className="text-lg font-bold">{formatNumber(trader.sortino_ratio || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Calmar Ratio</p>
              <p className="text-lg font-bold">{formatNumber(trader.calmar_ratio || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">平均杠杆</p>
              <p className="text-lg font-bold">{formatNumber(trader.avg_leverage || 1)}x</p>
            </div>
          </div>
          {/* VaR 指标 */}
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4 mt-3">
            <div>
              <p className="text-xs text-gray-500">95% VaR</p>
              <p className="text-lg font-bold text-orange-500">${formatNumber(trader.var_95 || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">99% VaR</p>
              <p className="text-lg font-bold text-orange-500">${formatNumber(trader.var_99 || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">95% CVaR</p>
              <p className="text-lg font-bold text-orange-500">${formatNumber(trader.cvar_95 || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">最大杠杆</p>
              <p className="text-lg font-bold">{formatNumber(trader.max_leverage || trader.avg_leverage || 1)}x</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">最大单笔盈利</p>
              <p className="text-lg font-bold text-green-500">${formatNumber(trader.max_single_win || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">最大单笔亏损</p>
              <p className="text-lg font-bold text-red-500">${formatNumber(trader.max_single_loss || 0)}</p>
            </div>
          </div>
        </div>

        <Divider className="my-3" />

        {/* 交易特征 */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">交易特征</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <p className="text-xs text-gray-500">最大连赢</p>
              <p className="text-lg font-bold text-green-500">{trader.max_consecutive_wins || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">最大连亏</p>
              <p className="text-lg font-bold text-red-500">{trader.max_consecutive_losses || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">平均盈利金额</p>
              <p className="text-lg font-bold text-green-500">${formatNumber(trader.avg_win_amount || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">平均亏损金额</p>
              <p className="text-lg font-bold text-red-500">${formatNumber(trader.avg_loss_amount || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">多空比</p>
              <p className="text-lg font-bold">{formatPercent(trader.long_short_ratio || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">常用品种</p>
              <p className="text-lg font-bold">{trader.favorite_symbol || '-'}</p>
            </div>
          </div>
        </div>

        <Divider className="my-3" />

        {/* 时间周期统计 */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">时间周期统计</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {/* 今日统计 */}
            <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
              <h4 className="text-xs font-semibold text-gray-500 mb-3">今日</h4>
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-gray-500">PnL</p>
                  <p className={`text-base font-bold ${(trader.daily_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${formatNumber(trader.daily_pnl || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">ROI</p>
                  <p className={`text-base font-bold ${(trader.daily_roi || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatPercent(trader.daily_roi || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">交易量</p>
                  <p className="text-base font-bold">${formatNumber(trader.daily_volume || 0)}</p>
                </div>
              </div>
            </div>

            {/* 近7天统计 */}
            <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
              <h4 className="text-xs font-semibold text-gray-500 mb-3">近7天</h4>
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-gray-500">PnL</p>
                  <p className={`text-base font-bold ${(trader.weekly_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${formatNumber(trader.weekly_pnl || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">ROI</p>
                  <p className={`text-base font-bold ${(trader.weekly_roi || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatPercent(trader.weekly_roi || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">交易量</p>
                  <p className="text-base font-bold">${formatNumber(trader.weekly_volume || 0)}</p>
                </div>
              </div>
            </div>

            {/* 近30天统计 */}
            <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
              <h4 className="text-xs font-semibold text-gray-500 mb-3">近30天</h4>
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-gray-500">PnL</p>
                  <p className={`text-base font-bold ${(trader.monthly_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${formatNumber(trader.monthly_pnl || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">ROI</p>
                  <p className={`text-base font-bold ${(trader.monthly_roi || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatPercent(trader.monthly_roi || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">交易量</p>
                  <p className="text-base font-bold">${formatNumber(trader.monthly_volume || 0)}</p>
                </div>
              </div>
            </div>

            {/* 总统计 */}
            <div className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg">
              <h4 className="text-xs font-semibold text-gray-500 mb-3">总计</h4>
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-gray-500">PnL</p>
                  <p className={`text-base font-bold ${trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ${formatNumber(trader.total_pnl)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">ROI</p>
                  <p className={`text-base font-bold ${trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                    {formatPercent(trader.roi)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">交易量</p>
                  <p className="text-base font-bold">${formatNumber(trader.total_volume || 0)}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <Divider className="my-3" />

        {/* 账户状态 */}
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-gray-400 mb-2">账户状态</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
            <div>
              <p className="text-xs text-gray-500">当前权益</p>
              <p className="text-lg font-bold">${formatNumber(trader.current_equity)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">当前持仓</p>
              <p className="text-lg font-bold">{trader.current_positions || 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">7天胜率</p>
              <p className="text-lg font-bold">{formatPercent(trader.recent_7d_win_rate || 0)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">首次交易</p>
              <p className="text-sm">{trader.first_trade_time ? formatDateTime(trader.first_trade_time) : '-'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">最后交易</p>
              <p className="text-sm">{formatDateTime(trader.last_trade_time)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">分析时间</p>
              <p className="text-sm">{trader.analyzed_at ? formatDateTime(trader.analyzed_at) : '-'}</p>
            </div>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
