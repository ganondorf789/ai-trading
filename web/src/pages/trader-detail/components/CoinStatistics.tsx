import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { FillsSummary } from '@/services/api';

interface CoinStatisticsProps {
  fillsSummary: FillsSummary | null;
}

export function CoinStatistics({ fillsSummary }: CoinStatisticsProps) {
  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  return (
    <Card className="mt-6">
      <CardHeader>
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-bold">币种统计</h2>
          <Chip size="sm" variant="flat" className="text-default-500">
            {fillsSummary?.by_coin?.length || 0} 个币种
          </Chip>
        </div>
      </CardHeader>
      <CardBody>
        {fillsSummary?.by_coin && fillsSummary.by_coin.length > 0 ? (
          <Table
            isHeaderSticky
            aria-label="Coin statistics table"
            classNames={{
              wrapper: 'max-h-[400px]',
            }}
          >
            <TableHeader>
              <TableColumn key="coin" allowsSorting>币种</TableColumn>
              <TableColumn key="count" allowsSorting>交易次数</TableColumn>
              <TableColumn key="total_pnl" allowsSorting>总盈亏</TableColumn>
              <TableColumn key="avg_pnl">平均盈亏</TableColumn>
              <TableColumn key="pnl_ratio">盈亏占比</TableColumn>
            </TableHeader>
            <TableBody items={fillsSummary.by_coin}>
              {(item) => (
                <TableRow key={item.coin}>
                  <TableCell>
                    <span className="font-bold">{item.coin}</span>
                  </TableCell>
                  <TableCell>{item.count}</TableCell>
                  <TableCell>
                    <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                      ${formatNumber(item.total_pnl)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={(item.total_pnl / item.count) >= 0 ? 'text-green-500' : 'text-red-500'}>
                      ${formatNumber(item.total_pnl / item.count)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={item.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                      {fillsSummary.total_pnl !== 0
                        ? formatPercent(Math.abs(item.total_pnl) / Math.abs(fillsSummary.total_pnl))
                        : '0%'}
                    </span>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        ) : (
          <div className="text-center text-gray-500 py-8">暂无币种统计数据</div>
        )}
      </CardBody>
    </Card>
  );
}
