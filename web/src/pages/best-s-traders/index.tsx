import { useState, useEffect, useCallback } from 'react';
import { Card, CardBody, CardHeader } from '@heroui/card';
import { Divider } from '@heroui/divider';
import { addToast } from '@heroui/react';
import DefaultLayout from '@/layouts/default';
import { bestSTradersApi, traderApi, type BestSTrader, type BestSPreset, type BestSTraderParams } from '@/services/api';
import { PresetSelector, FilterForm, TradersTable, StatsCards } from './components';

const DEFAULT_PARAMS: BestSTraderParams = {
  preset: 'default',
  limit: 20,
  require_recent_profit: true,
  sort_by: 'recent_pnl',
};

export default function BestSTradersPage() {
  const [traders, setTraders] = useState<BestSTrader[]>([]);
  const [presets, setPresets] = useState<BestSPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [presetsLoading, setPresetsLoading] = useState(true);
  const [params, setParams] = useState<BestSTraderParams>(DEFAULT_PARAMS);
  const [currentPreset, setCurrentPreset] = useState<{ name: string; description: string } | null>(null);
  const [starLoadingAddresses, setStarLoadingAddresses] = useState<Set<string>>(new Set());

  // 加载预设列表
  useEffect(() => {
    const loadPresets = async () => {
      try {
        setPresetsLoading(true);
        const response = await bestSTradersApi.getPresets();
        if (response.success && response.data) {
          setPresets(response.data);
        }
      } catch (error) {
        console.error('Failed to load presets:', error);
      } finally {
        setPresetsLoading(false);
      }
    };
    loadPresets();
  }, []);

  // 加载交易员列表
  const loadTraders = useCallback(async () => {
    try {
      setLoading(true);
      const response = await bestSTradersApi.getBestSTraders(params);
      if (response.success && response.data) {
        setTraders(response.data);
        if (response.preset) {
          setCurrentPreset({
            name: response.preset.name,
            description: response.preset.description,
          });
        }
      } else {
        addToast({
          title: '加载失败',
          description: response.error || '无法加载交易员数据',
          color: 'danger',
        });
      }
    } catch (error: any) {
      console.error('Failed to load traders:', error);
      addToast({
        title: '加载失败',
        description: error.message || '网络错误',
        color: 'danger',
      });
    } finally {
      setLoading(false);
    }
  }, [params]);

  // 初始加载
  useEffect(() => {
    loadTraders();
  }, []);

  // 预设变更
  const handlePresetChange = useCallback((presetKey: string) => {
    const preset = presets.find((p) => p.key === presetKey);
    if (preset) {
      setParams({
        ...preset.params,
        preset: presetKey,
        limit: params.limit || 20,
      });
    }
  }, [presets, params.limit]);

  // 参数变更
  const handleParamsChange = useCallback((newParams: BestSTraderParams) => {
    setParams(newParams);
  }, []);

  // 重置
  const handleReset = useCallback(() => {
    setParams(DEFAULT_PARAMS);
  }, []);

  // 切换收藏
  const handleToggleStar = useCallback(async (address: string, isStarred: boolean) => {
    setStarLoadingAddresses((prev) => new Set(prev).add(address));
    try {
      const response = await traderApi.toggleStar(address, isStarred);
      if (response.success) {
        setTraders((prev) =>
          prev.map((t) => (t.address === address ? { ...t, is_starred: isStarred } : t))
        );
        addToast({
          title: isStarred ? '已收藏' : '已取消收藏',
          color: 'success',
        });
      }
    } catch (error) {
      console.error('Toggle star failed:', error);
      addToast({
        title: '操作失败',
        color: 'danger',
      });
    } finally {
      setStarLoadingAddresses((prev) => {
        const next = new Set(prev);
        next.delete(address);
        return next;
      });
    }
  }, []);

  return (
    <DefaultLayout>
      <section className="flex flex-col gap-4 py-4">
        {/* 标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">S级优选</h1>
            <p className="text-default-500 text-sm">
              从 S 级交易员中筛选最优秀的、近期值得跟单的交易员
            </p>
          </div>
        </div>

        {/* 统计卡片 */}
        <StatsCards
          traders={traders}
          presetName={currentPreset?.name}
          presetDescription={currentPreset?.description}
        />

        {/* 筛选区域 */}
        <Card>
          <CardHeader className="flex gap-4 items-center">
            <PresetSelector
              presets={presets}
              selectedPreset={params.preset || 'default'}
              onPresetChange={handlePresetChange}
              isLoading={presetsLoading}
            />
          </CardHeader>
          <Divider />
          <CardBody>
            <FilterForm
              params={params}
              onChange={handleParamsChange}
              onSearch={loadTraders}
              onReset={handleReset}
              isLoading={loading}
            />
          </CardBody>
        </Card>

        {/* 交易员表格 */}
        <Card>
          <CardBody>
            <TradersTable
              traders={traders}
              isLoading={loading}
              onToggleStar={handleToggleStar}
              starLoadingAddresses={starLoadingAddresses}
            />
          </CardBody>
        </Card>
      </section>
    </DefaultLayout>
  );
}
