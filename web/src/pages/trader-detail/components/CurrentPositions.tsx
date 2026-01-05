import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Button } from '@heroui/button';
import { Spinner } from '@heroui/spinner';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Icon } from '@iconify/react';
import { AssetPosition } from '@/services/api';

interface CurrentPositionsProps {
  assetPositions: AssetPosition[];
  assetPositionsLoading: boolean;
  positionsRefreshing: boolean;
  onRefresh: () => void;
}

export function CurrentPositions({
  assetPositions,
  assetPositionsLoading,
  positionsRefreshing,
  onRefresh,
}: CurrentPositionsProps) {
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
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold">当前持仓</h2>
            <Chip size="sm" variant="flat" color="warning">
              {assetPositions.length}
            </Chip>
            {assetPositions.length > 0 && assetPositions[0]?.updated_at && (
              <span className="text-xs text-gray-500">
                更新于 {new Date(assetPositions[0].updated_at).toLocaleString()}
              </span>
            )}
          </div>
          <Button
            size="sm"
            color="primary"
            variant="flat"
            isLoading={positionsRefreshing}
            onPress={onRefresh}
            startContent={!positionsRefreshing && <Icon icon="solar:refresh-linear" width={16} />}
          >
            {positionsRefreshing ? '刷新中...' : '刷新持仓'}
          </Button>
        </div>
      </CardHeader>
      <CardBody>
        {assetPositionsLoading ? (
          <div className="flex justify-center items-center h-64">
            <Spinner size="lg" />
          </div>
        ) : assetPositions.length > 0 ? (
          <Table
            isHeaderSticky
            aria-label="Asset positions table"
            classNames={{
              wrapper: 'max-h-[400px]',
            }}
          >
            <TableHeader>
              <TableColumn key="coin">币种</TableColumn>
              <TableColumn key="side">方向</TableColumn>
              <TableColumn key="szi">数量</TableColumn>
              <TableColumn key="entry_px">开仓均价</TableColumn>
              <TableColumn key="position_value">持仓价值</TableColumn>
              <TableColumn key="unrealized_pnl">未实现盈亏</TableColumn>
              <TableColumn key="roe">ROE</TableColumn>
              <TableColumn key="leverage">杠杆</TableColumn>
              <TableColumn key="liquidation_px">清算价格</TableColumn>
            </TableHeader>
            <TableBody items={assetPositions}>
              {(item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <span className="font-bold">{item.coin}</span>
                  </TableCell>
                  <TableCell>
                    <Chip
                      size="sm"
                      color={item.szi > 0 ? 'success' : 'danger'}
                      variant="flat"
                    >
                      {item.szi > 0 ? 'LONG' : 'SHORT'}
                    </Chip>
                  </TableCell>
                  <TableCell>{formatNumber(Math.abs(item.szi), 4)}</TableCell>
                  <TableCell>${formatNumber(item.entry_px, 4)}</TableCell>
                  <TableCell>${formatNumber(Math.abs(item.position_value), 2)}</TableCell>
                  <TableCell>
                    <span className={item.unrealized_pnl >= 0 ? 'text-green-500' : 'text-red-500'}>
                      ${formatNumber(item.unrealized_pnl, 2)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={item.return_on_equity >= 0 ? 'text-green-500' : 'text-red-500'}>
                      {formatPercent(item.return_on_equity)}
                    </span>
                  </TableCell>
                  <TableCell>{item.leverage_value}x</TableCell>
                  <TableCell>
                    {item.liquidation_px ? `$${formatNumber(item.liquidation_px, 2)}` : '-'}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        ) : (
          <div className="text-center text-gray-500 py-8">暂无当前持仓</div>
        )}
      </CardBody>
    </Card>
  );
}
