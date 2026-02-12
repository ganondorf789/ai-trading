import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '@heroui/tabs';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { Card, CardBody } from '@heroui/card';
import { addToast } from '@heroui/react';
import { tradingApi } from '@/services/api';
import { PerpPositions } from './components/PerpPositions';
import { OpenOrders } from './components/OpenOrders';
import { TwapSliceFills } from './components/TwapSliceFills';
import type { PerpPosition } from './components/PerpPositions';
import type { OpenOrderItem } from './components/OpenOrders';
import type { TwapSliceFill } from './components/TwapSliceFills';

// ==================== 类型 ====================

interface MarginSummary {
  accountValue: string;
  totalMarginUsed: string;
  totalNtlPos: string;
  totalRawUsd: string;
}

// ==================== 工具函数 ====================

function fmtUsd(value: string | number | null | undefined): string {
  if (value == null || value === '') return '-';
  const n = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(n)) return '-';
  return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ==================== 组件 ====================

export default function TraderDetailPage() {
  const { address } = useParams<{ address: string }>();
  const navigate = useNavigate();

  const [selectedTab, setSelectedTab] = useState<string>('positions');
  const [positions, setPositions] = useState<PerpPosition[]>([]);
  const [marginSummary, setMarginSummary] = useState<MarginSummary | null>(null);
  const [openOrders, setOpenOrders] = useState<OpenOrderItem[]>([]);
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
          {selectedTab === 'positions' && <PerpPositions positions={positions} />}
          {selectedTab === 'orders' && <OpenOrders orders={openOrders} />}
          {selectedTab === 'twap' && <TwapSliceFills fills={twapFills} />}
        </>
      )}
    </div>
  );
}
