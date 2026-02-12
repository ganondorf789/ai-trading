import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '@heroui/tabs';
import {
  Table,
  TableHeader,
  TableColumn,
  TableBody,
  TableRow,
  TableCell,
} from '@heroui/table';
import { Chip } from '@heroui/chip';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { Card, CardBody } from '@heroui/card';
import { addToast } from '@heroui/react';
import { tradingApi } from '@/services/api';

// ==================== 类型定义 ====================

interface PerpPosition {
  coin: string;
  size: number;
  side: 'long' | 'short';
  entryPx: string;
  positionValue: string;
  unrealizedPnl: string;
  returnOnEquity: string;
  leverage: { type: string; value: number };
  liquidationPx: string | null;
  marginUsed: string;
  maxLeverage: number;
}

interface MarginSummary {
  accountValue: string;
  totalMarginUsed: string;
  totalNtlPos: string;
  totalRawUsd: string;
}

interface OpenOrder {
  coin: string;
  limitPx: string;
  oid: number;
  side: string;
  sz: string;
  timestamp: number;
  orderType: string;
  tif: string;
  origSz: string;
  isTrigger: boolean;
  triggerPx: string;
  triggerCondition: string;
  isPositionTpsl: boolean;
  children: any[];
  reduceOnly?: boolean;
  cloid?: string | null;
}

interface TwapSliceFill {
  coin: string;
  px: string;
  sz: string;
  side: string;
  time: number;
  fee: string;
  oid: number;
  twapId: number;
  closedPnl?: string;
}

// ==================== 工具函数 ====================

function fmt(value: string | number | null | undefined, decimals = 2): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtUsd(value: string | number | null | undefined): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return '$' + fmt(n);
}

function fmtPct(value: string | number | null | undefined): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return (n * 100).toFixed(2) + '%';
}

function pnlColor(value: string | number | null | undefined): string {
  if (value == null || value === '') return '';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '';
  return n >= 0 ? 'text-green-500' : 'text-red-500';
}

function fmtTime(ts: number): string {
  if (!ts) return '-';
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// ==================== 组件 ====================

export default function TraderDetailPage() {
  const { address } = useParams<{ address: string }>();
  const navigate = useNavigate();

  const [selectedTab, setSelectedTab] = useState<string>('positions');
  const [positions, setPositions] = useState<PerpPosition[]>([]);
  const [marginSummary, setMarginSummary] = useState<MarginSummary | null>(null);
  const [openOrders, setOpenOrders] = useState<OpenOrder[]>([]);
  const [twapFills, setTwapFills] = useState<TwapSliceFill[]>([]);
  const [loading, setLoading] = useState(false);

  const loadPositions = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getPositions(address);
      if (res.success && res.data) {
        setPositions(res.data.positions || []);
        setMarginSummary(res.data.marginSummary || null);
      }
    } catch (err: any) {
      addToast({ title: '获取持仓失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  const loadOpenOrders = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getOpenOrders(address);
      if (res.success) {
        setOpenOrders(res.data || []);
      }
    } catch (err: any) {
      addToast({ title: '获取挂单失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  const loadTwapFills = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getTwapSliceFills(address);
      if (res.success) {
        setTwapFills(res.data || []);
      }
    } catch (err: any) {
      addToast({ title: '获取TWAP失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  // 切换 tab 时加载对应数据
  useEffect(() => {
    if (selectedTab === 'positions') loadPositions();
    else if (selectedTab === 'orders') loadOpenOrders();
    else if (selectedTab === 'twap') loadTwapFills();
  }, [selectedTab, address]);

  return (
    <div className="flex flex-col gap-4 py-4 px-6 max-w-[1800px] mx-auto w-full">
      <div className="flex items-center justify-between">
        <Button size="sm" variant="light" onPress={() => navigate(-1)}>
          ← Back
        </Button>
        <span className="text-sm text-default-500 font-mono">{address}</span>
      </div>

      {/* 账户概览 */}
      {marginSummary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card shadow="sm"><CardBody className="p-3">
            <p className="text-xs text-default-500">Account Value</p>
            <p className="text-lg font-semibold">{fmtUsd(marginSummary.accountValue)}</p>
          </CardBody></Card>
          <Card shadow="sm"><CardBody className="p-3">
            <p className="text-xs text-default-500">Margin Used</p>
            <p className="text-lg font-semibold">{fmtUsd(marginSummary.totalMarginUsed)}</p>
          </CardBody></Card>
          <Card shadow="sm"><CardBody className="p-3">
            <p className="text-xs text-default-500">Total Notional</p>
            <p className="text-lg font-semibold">{fmtUsd(marginSummary.totalNtlPos)}</p>
          </CardBody></Card>
          <Card shadow="sm"><CardBody className="p-3">
            <p className="text-xs text-default-500">Total Raw USD</p>
            <p className="text-lg font-semibold">{fmtUsd(marginSummary.totalRawUsd)}</p>
          </CardBody></Card>
        </div>
      )}

      {/* Tabs */}
      <Tabs
        selectedKey={selectedTab}
        onSelectionChange={(key) => setSelectedTab(key as string)}
        aria-label="Trading data tabs"
        color="primary"
        variant="underlined"
      >
        <Tab key="positions" title={`Perp Positions (${positions.length})`} />
        <Tab key="orders" title={`Open Orders (${openOrders.length})`} />
        <Tab key="twap" title={`TWAP (${twapFills.length})`} />
      </Tabs>

      {/* 内容区域 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner size="lg" />
        </div>
      ) : (
        <>
          {/* ========== Perp Positions ========== */}
          {selectedTab === 'positions' && (
            <Table
              isHeaderSticky
              aria-label="Perp positions"
              classNames={{ wrapper: 'max-h-[600px]' }}
            >
              <TableHeader>
                <TableColumn>Coin</TableColumn>
                <TableColumn>Side</TableColumn>
                <TableColumn>Size</TableColumn>
                <TableColumn>Entry Price</TableColumn>
                <TableColumn>Position Value</TableColumn>
                <TableColumn>Unrealized PnL</TableColumn>
                <TableColumn>ROE</TableColumn>
                <TableColumn>Leverage</TableColumn>
                <TableColumn>Liq. Price</TableColumn>
                <TableColumn>Margin Used</TableColumn>
              </TableHeader>
              <TableBody emptyContent="No positions">
                {positions.map((pos, idx) => (
                  <TableRow key={`${pos.coin}-${idx}`}>
                    <TableCell><span className="font-bold">{pos.coin}</span></TableCell>
                    <TableCell>
                      <Chip size="sm" color={pos.side === 'long' ? 'success' : 'danger'} variant="flat">
                        {pos.side.toUpperCase()}
                      </Chip>
                    </TableCell>
                    <TableCell>{fmt(Math.abs(pos.size), 4)}</TableCell>
                    <TableCell>{fmtUsd(pos.entryPx)}</TableCell>
                    <TableCell>{fmtUsd(pos.positionValue)}</TableCell>
                    <TableCell>
                      <span className={pnlColor(pos.unrealizedPnl)}>{fmtUsd(pos.unrealizedPnl)}</span>
                    </TableCell>
                    <TableCell>
                      <span className={pnlColor(pos.returnOnEquity)}>{fmtPct(pos.returnOnEquity)}</span>
                    </TableCell>
                    <TableCell>
                      {pos.leverage?.value ?? '-'}x
                      <span className="text-xs text-default-400 ml-1">
                        ({pos.leverage?.type === 'cross' ? 'Cross' : 'Isolated'})
                      </span>
                    </TableCell>
                    <TableCell>{pos.liquidationPx ? fmtUsd(pos.liquidationPx) : '-'}</TableCell>
                    <TableCell>{fmtUsd(pos.marginUsed)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* ========== Open Orders ========== */}
          {selectedTab === 'orders' && (
            <Table
              isHeaderSticky
              aria-label="Open orders"
              classNames={{ wrapper: 'max-h-[600px]' }}
            >
              <TableHeader>
                <TableColumn>Coin</TableColumn>
                <TableColumn>Side</TableColumn>
                <TableColumn>Type</TableColumn>
                <TableColumn>Size</TableColumn>
                <TableColumn>Price</TableColumn>
                <TableColumn>Trigger</TableColumn>
                <TableColumn>TIF</TableColumn>
                <TableColumn>Reduce Only</TableColumn>
                <TableColumn>TP/SL</TableColumn>
                <TableColumn>Time</TableColumn>
              </TableHeader>
              <TableBody emptyContent="No open orders">
                {openOrders.map((order) => (
                  <TableRow key={order.oid}>
                    <TableCell><span className="font-bold">{order.coin}</span></TableCell>
                    <TableCell>
                      <Chip size="sm" color={order.side === 'B' ? 'success' : 'danger'} variant="flat">
                        {order.side === 'B' ? 'BUY' : 'SELL'}
                      </Chip>
                    </TableCell>
                    <TableCell>
                      <Chip size="sm" variant="bordered">
                        {order.orderType || 'Limit'}
                      </Chip>
                    </TableCell>
                    <TableCell>{fmt(order.sz, 4)}</TableCell>
                    <TableCell>{fmtUsd(order.limitPx)}</TableCell>
                    <TableCell>
                      {order.isTrigger ? (
                        <span className="text-xs">
                          {order.triggerCondition} {fmtUsd(order.triggerPx)}
                        </span>
                      ) : '-'}
                    </TableCell>
                    <TableCell>{order.tif || '-'}</TableCell>
                    <TableCell>{order.reduceOnly ? 'Yes' : 'No'}</TableCell>
                    <TableCell>{order.isPositionTpsl ? 'Yes' : '-'}</TableCell>
                    <TableCell className="text-xs">{fmtTime(order.timestamp)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* ========== TWAP ========== */}
          {selectedTab === 'twap' && (
            <Table
              isHeaderSticky
              aria-label="TWAP slice fills"
              classNames={{ wrapper: 'max-h-[600px]' }}
            >
              <TableHeader>
                <TableColumn>Coin</TableColumn>
                <TableColumn>Side</TableColumn>
                <TableColumn>Price</TableColumn>
                <TableColumn>Size</TableColumn>
                <TableColumn>Fee</TableColumn>
                <TableColumn>Closed PnL</TableColumn>
                <TableColumn>TWAP ID</TableColumn>
                <TableColumn>Order ID</TableColumn>
                <TableColumn>Time</TableColumn>
              </TableHeader>
              <TableBody emptyContent="No TWAP records">
                {twapFills.map((fill, idx) => (
                  <TableRow key={`${fill.oid}-${idx}`}>
                    <TableCell><span className="font-bold">{fill.coin}</span></TableCell>
                    <TableCell>
                      <Chip size="sm" color={fill.side === 'B' ? 'success' : 'danger'} variant="flat">
                        {fill.side === 'B' ? 'BUY' : 'SELL'}
                      </Chip>
                    </TableCell>
                    <TableCell>{fmtUsd(fill.px)}</TableCell>
                    <TableCell>{fmt(fill.sz, 4)}</TableCell>
                    <TableCell>{fmtUsd(fill.fee)}</TableCell>
                    <TableCell>
                      <span className={pnlColor(fill.closedPnl)}>{fmtUsd(fill.closedPnl)}</span>
                    </TableCell>
                    <TableCell>{fill.twapId}</TableCell>
                    <TableCell>{fill.oid}</TableCell>
                    <TableCell className="text-xs">{fmtTime(fill.time)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </>
      )}
    </div>
  );
}
