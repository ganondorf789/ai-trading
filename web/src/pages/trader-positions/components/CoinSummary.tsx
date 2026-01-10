import { Card, CardBody, Chip, Progress, Tooltip } from "@heroui/react";
import { Icon } from "@iconify/react";
import { TraderPositionsStats } from "@/services/api";

interface CoinSummaryProps {
  stats: TraderPositionsStats | null;
  onAIAnalyzeCoin?: (coin: string) => void;
}

export function CoinSummary({ stats, onAIAnalyzeCoin }: CoinSummaryProps) {
  if (!stats || !stats.by_coin || stats.by_coin.length === 0) return null;

  const formatNumber = (num: number, decimals: number = 0) => {
    return num.toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const maxNotional = Math.max(...stats.by_coin.map((c) => c.notional));

  // 只显示前10个币种
  const topCoins = stats.by_coin.slice(0, 10);

  return (
    <Card className="mb-6 bg-content1/50 backdrop-blur-md">
      <CardBody>
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="w-1 h-5 bg-primary rounded-full"></span>
          币种分布 (Top 10)
          {onAIAnalyzeCoin && (
            <span className="text-xs text-default-400 font-normal ml-2">点击币种可 AI 分析</span>
          )}
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {topCoins.map((coin) => (
            <div
              key={coin.coin}
              className={`p-3 rounded-lg bg-content2/50 hover:bg-content2 transition-colors ${onAIAnalyzeCoin ? 'cursor-pointer group' : ''}`}
              onClick={() => onAIAnalyzeCoin?.(coin.coin)}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{coin.coin}</span>
                  {onAIAnalyzeCoin && (
                    <Tooltip content="AI 分析此币种">
                      <Icon 
                        icon="solar:magic-stick-2-bold-duotone" 
                        width={14} 
                        className="text-secondary opacity-0 group-hover:opacity-100 transition-opacity" 
                      />
                    </Tooltip>
                  )}
                </div>
                <div className="flex gap-1">
                  {coin.long > 0 && (
                    <Chip size="sm" color="success" variant="flat" className="h-5 text-xs">
                      {coin.long}L
                    </Chip>
                  )}
                  {coin.short > 0 && (
                    <Chip size="sm" color="danger" variant="flat" className="h-5 text-xs">
                      {coin.short}S
                    </Chip>
                  )}
                </div>
              </div>
              <div className="text-sm text-default-500 mb-2">
                ${formatNumber(coin.notional)}
              </div>
              <Progress
                size="sm"
                value={(coin.notional / maxNotional) * 100}
                classNames={{
                  indicator: "bg-gradient-to-r from-primary to-secondary",
                }}
              />
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
