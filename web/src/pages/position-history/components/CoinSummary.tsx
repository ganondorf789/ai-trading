import { Chip, Progress } from "@heroui/react";
import { PositionHistoryByCoin } from "@/services/api";

interface CoinSummaryProps {
  byCoin: PositionHistoryByCoin[];
}

export function CoinSummary({ byCoin }: CoinSummaryProps) {
  if (!byCoin || byCoin.length === 0) return null;

  const formatNumber = (num: number, decimals: number = 0) => {
    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(1)}%`;
  };

  const maxPnl = Math.max(...byCoin.map((c) => Math.abs(c.total_pnl)));

  // 只显示前10个币种
  const topCoins = byCoin.slice(0, 10);

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <span className="w-1 h-5 bg-primary rounded-full"></span>
        币种统计 (Top 10)
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {topCoins.map((coin) => (
          <div
            key={coin.coin}
            className="p-3 rounded-lg bg-content2/50 hover:bg-content2 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">{coin.coin}</span>
              <div className="flex gap-1">
                {(coin.long_count || 0) > 0 && (
                  <Chip size="sm" color="success" variant="flat" className="h-5 text-xs">
                    {coin.long_count}L
                  </Chip>
                )}
                {(coin.short_count || 0) > 0 && (
                  <Chip size="sm" color="danger" variant="flat" className="h-5 text-xs">
                    {coin.short_count}S
                  </Chip>
                )}
              </div>
            </div>
            <div className="text-xs text-default-500 mb-1">
              {coin.total_positions} 仓位 | 胜率 {formatPercent(coin.win_rate)}
            </div>
            <div className={`text-sm font-medium mb-2 ${coin.total_pnl >= 0 ? 'text-success' : 'text-danger'}`}>
              {coin.total_pnl >= 0 ? '+' : ''}${formatNumber(coin.total_pnl)}
            </div>
            <Progress
              size="sm"
              value={(Math.abs(coin.total_pnl) / maxPnl) * 100}
              classNames={{
                indicator: coin.total_pnl >= 0
                  ? "bg-gradient-to-r from-emerald-500 to-green-500"
                  : "bg-gradient-to-r from-rose-500 to-red-500",
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
