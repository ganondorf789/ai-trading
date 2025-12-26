import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Spinner } from '@heroui/spinner';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Input } from '@heroui/input';
import { Button } from '@heroui/button';
import DefaultLayout from '@/layouts/default';
import { traderApi, Trader } from '@/services/api';

export default function TradersPage() {
  const navigate = useNavigate();
  const [traders, setTraders] = useState<Trader[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchAddress, setSearchAddress] = useState('');
  const [selectedRating, setSelectedRating] = useState<string>('');

  const loadTraders = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = selectedRating
        ? await traderApi.getTradersByRating(selectedRating)
        : await traderApi.getTraders({ limit: 100 });

      if (response.success && response.data) {
        setTraders(response.data);
      } else {
        setError(response.error || 'Failed to load traders');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTraders();
  }, [selectedRating]);

  const filteredTraders = traders.filter((trader) =>
    trader.address.toLowerCase().includes(searchAddress.toLowerCase())
  );

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

  const formatNumber = (num: number, decimals = 2) => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number) => {
    return `${(num * 100).toFixed(2)}%`;
  };

  const handleRowClick = (address: string) => {
    navigate(`/traders/${address}`);
  };

  return (
    <DefaultLayout>
      <section className="flex flex-col gap-4 py-8 md:py-10">
        <div className="max-w-7xl w-full mx-auto">
          <Card>
            <CardHeader className="flex flex-col gap-3">
              <div className="flex justify-between items-center w-full">
                <h1 className="text-2xl font-bold">Trader Analytics</h1>
                <div className="flex gap-2">
                  {['S', 'A', 'B', 'C', 'D', 'F'].map((rating) => (
                    <Button
                      key={rating}
                      size="sm"
                      variant={selectedRating === rating ? 'solid' : 'bordered'}
                      color={selectedRating === rating ? 'primary' : 'default'}
                      onPress={() =>
                        setSelectedRating(selectedRating === rating ? '' : rating)
                      }
                    >
                      {rating}
                    </Button>
                  ))}
                </div>
              </div>
              <Input
                placeholder="Search by address..."
                value={searchAddress}
                onValueChange={setSearchAddress}
                size="sm"
                className="max-w-md"
              />
            </CardHeader>
            <CardBody>
              {loading ? (
                <div className="flex justify-center items-center h-64">
                  <Spinner size="lg" />
                </div>
              ) : error ? (
                <div className="text-center text-red-500 p-8">{error}</div>
              ) : (
                <Table
                  aria-label="Traders table"
                  selectionMode="single"
                  onRowAction={(key) => handleRowClick(key.toString())}
                  classNames={{
                    wrapper: 'min-h-[400px]',
                  }}
                >
                  <TableHeader>
                    <TableColumn>Rating</TableColumn>
                    <TableColumn>Address</TableColumn>
                    <TableColumn>Score</TableColumn>
                    <TableColumn>Total Trades</TableColumn>
                    <TableColumn>Win Rate</TableColumn>
                    <TableColumn>Total PnL</TableColumn>
                    <TableColumn>ROI</TableColumn>
                    <TableColumn>Profit Factor</TableColumn>
                    <TableColumn>Max DD</TableColumn>
                    <TableColumn>Sharpe</TableColumn>
                    <TableColumn>Equity</TableColumn>
                  </TableHeader>
                  <TableBody>
                    {filteredTraders.map((trader) => (
                      <TableRow
                        key={trader.address}
                        className="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
                      >
                        <TableCell>
                          <span
                            className={`font-bold text-lg ${getRatingColor(trader.rating)}`}
                          >
                            {trader.rating}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="font-mono text-sm">
                            {trader.address.slice(0, 6)}...{trader.address.slice(-4)}
                          </span>
                        </TableCell>
                        <TableCell>{formatNumber(trader.overall_score)}</TableCell>
                        <TableCell>{trader.total_trades}</TableCell>
                        <TableCell>{formatPercent(trader.win_rate)}</TableCell>
                        <TableCell
                          className={trader.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}
                        >
                          ${formatNumber(trader.total_pnl)}
                        </TableCell>
                        <TableCell
                          className={trader.roi >= 0 ? 'text-green-500' : 'text-red-500'}
                        >
                          {formatPercent(trader.roi)}
                        </TableCell>
                        <TableCell>{formatNumber(trader.profit_factor)}</TableCell>
                        <TableCell className="text-red-500">
                          {formatPercent(trader.max_drawdown)}
                        </TableCell>
                        <TableCell>{formatNumber(trader.sharpe_ratio)}</TableCell>
                        <TableCell>${formatNumber(trader.current_equity)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardBody>
          </Card>
        </div>
      </section>
    </DefaultLayout>
  );
}
