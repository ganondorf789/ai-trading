import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Tabs, Tab } from '@heroui/tabs';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { addToast } from '@heroui/react';
import { tradingApi, traderApi } from '@/services/api';
import { PerpPositions } from './components/PerpPositions';
import { OpenOrders } from './components/OpenOrders';
import { TwapSliceFills } from './components/TwapSliceFills';
import { RecentFills } from './components/RecentFills';
import { CompletedTrades } from './components/CompletedTrades';
import { HistoricalOrders } from './components/HistoricalOrders';
import { FundingHistory } from './components/FundingHistory';
import { DepositsWithdrawals } from './components/DepositsWithdrawals';
import type { PerpPosition } from './components/PerpPositions';
import type { OpenOrderItem } from './components/OpenOrders';
import type { TwapSliceFill } from './components/TwapSliceFills';
import type { CompletedTradeItem } from './components/CompletedTrades';
import type { HistoricalOrderItem } from './components/HistoricalOrders';
import type { FundingHistoryItem } from './components/FundingHistory';
import type { LedgerItem } from './components/DepositsWithdrawals';

// ==================== Tab 定义 ====================

type TabKey = 'positions' | 'orders' | 'twap' | 'fills' | 'trades' | 'history' | 'funding' | 'ledger';

// ==================== 组件 ====================

export default function TraderDetailPage() {
  const { address } = useParams<{ address: string }>();
  const navigate = useNavigate();

  const [selectedTab, setSelectedTab] = useState<TabKey>('positions');
  const [loading, setLoading] = useState(false);

  // 各 tab 数据
  const [positions, setPositions] = useState<PerpPosition[]>([]);
  const [openOrders, setOpenOrders] = useState<OpenOrderItem[]>([]);
  const [twapFills, setTwapFills] = useState<TwapSliceFill[]>([]);
  const [completedTrades, setCompletedTrades] = useState<CompletedTradeItem[]>([]);
  const [historicalOrders, setHistoricalOrders] = useState<HistoricalOrderItem[]>([]);
  const [fundingRecords, setFundingRecords] = useState<FundingHistoryItem[]>([]);
  const [ledgerRecords, setLedgerRecords] = useState<LedgerItem[]>([]);

  // ==================== 数据加载 ====================

  const loadPositions = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getPositions(address);
      if (res.success && res.data) {
        setPositions(res.data.positions || []);
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
      if (res.success) setOpenOrders(res.data || []);
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
      if (res.success) setTwapFills(res.data || []);
    } catch (err: any) {
      addToast({ title: '获取TWAP失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  const loadRecentFills = useCallback(() => {
    // RecentFills 组件自行管理数据加载和分页
  }, []);

  const loadCompletedTrades = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await traderApi.getPositionHistory(address, { limit: 10000, sort_order: 'desc' });
      if (res.success) setCompletedTrades(res.data || []);
    } catch (err: any) {
      addToast({ title: '获取仓位历史失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  const loadHistoricalOrders = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getHistoricalOrders(address);
      if (res.success) setHistoricalOrders(res.data || []);
    } catch (err: any) {
      addToast({ title: '获取历史订单失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  const loadFundingHistory = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getFundingHistory(address);
      if (res.success) setFundingRecords(res.data || []);
    } catch (err: any) {
      addToast({ title: '获取资金费率失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  const loadLedgerUpdates = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    try {
      const res = await tradingApi.getLedgerUpdates(address);
      if (res.success) setLedgerRecords(res.data || []);
    } catch (err: any) {
      addToast({ title: '获取出入金失败', description: err.message, color: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [address]);

  // 切换 tab 时加载对应数据
  useEffect(() => {
    const loaders: Record<TabKey, () => void> = {
      positions: loadPositions,
      orders: loadOpenOrders,
      twap: loadTwapFills,
      fills: loadRecentFills,
      trades: loadCompletedTrades,
      history: loadHistoricalOrders,
      funding: loadFundingHistory,
      ledger: loadLedgerUpdates,
    };
    loaders[selectedTab]?.();
  }, [selectedTab, address]);

  return (
    <div className="flex flex-col gap-4 py-4 px-6 max-w-[1800px] mx-auto w-full">
      <div className="flex items-center justify-between">
        <Button size="sm" variant="light" onPress={() => navigate(-1)}>
          ← Back
        </Button>
        <span className="text-sm text-default-500 font-mono">{address}</span>
      </div>

      {/* Tabs */}
      <Tabs
        selectedKey={selectedTab}
        onSelectionChange={(key) => setSelectedTab(key as TabKey)}
        aria-label="Trading data tabs"
        color="primary"
        variant="underlined"
      >
        <Tab key="positions" title="Perp Positions" />
        <Tab key="orders" title="Open Orders" />
        <Tab key="twap" title="TWAP" />
        <Tab key="fills" title="Recent Fills" />
        <Tab key="trades" title="Completed Trades" />
        <Tab key="history" title="Historical Orders" />
        <Tab key="funding" title="Funding History" />
        <Tab key="ledger" title="Deposits & Withdrawals" />
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
          {selectedTab === 'fills' && address && <RecentFills address={address} />}
          {selectedTab === 'trades' && <CompletedTrades trades={completedTrades} />}
          {selectedTab === 'history' && <HistoricalOrders orders={historicalOrders} />}
          {selectedTab === 'funding' && <FundingHistory records={fundingRecords} />}
          {selectedTab === 'ledger' && <DepositsWithdrawals records={ledgerRecords} />}
        </>
      )}
    </div>
  );
}
