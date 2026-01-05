import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { Icon } from '@iconify/react';
import DefaultLayout from '@/layouts/default';
import { groupComparisonApi, GroupComparisonSession } from '@/services/api';
import { SessionList } from './components/SessionList';
import { SessionOverview } from './components/SessionOverview';
import { FinalistsList } from './components/FinalistsList';
import { RoundDetails } from './components/RoundDetails';
import { FinalRankingAnalysis } from './components/FinalRankingAnalysis';

export default function GroupComparisonPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<GroupComparisonSession[]>([]);
  const [selectedSession, setSelectedSession] = useState<GroupComparisonSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 加载会话列表
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await groupComparisonApi.getSessions({ limit: 20 });
      if (response.success && response.data) {
        setSessions(response.data);
        // 自动选择第一个会话
        if (response.data.length > 0) {
          loadSessionDetail(response.data[0].id);
        }
      }
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  const loadSessionDetail = async (sessionId: number) => {
    try {
      setDetailLoading(true);
      const response = await groupComparisonApi.getSession(sessionId);
      if (response.success && response.data) {
        setSelectedSession(response.data);
      }
    } catch (err: any) {
      console.error('加载会话详情失败:', err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleTraderClick = (address: string) => {
    navigate(`/traders/${address}`);
  };

  // Loading state
  if (loading) {
    return (
      <DefaultLayout>
        <div className="flex justify-center items-center h-96">
          <Spinner size="lg" />
        </div>
      </DefaultLayout>
    );
  }

  // Error state
  if (error) {
    return (
      <DefaultLayout>
        <Card className="bg-danger/10">
          <CardBody className="text-center py-8">
            <Icon icon="solar:danger-triangle-bold" className="text-4xl text-danger mb-2" />
            <p className="text-danger">{error}</p>
            <Button color="primary" className="mt-4" onPress={loadSessions}>
              重试
            </Button>
          </CardBody>
        </Card>
      </DefaultLayout>
    );
  }

  // Empty state
  if (sessions.length === 0) {
    return (
      <DefaultLayout>
        <Card>
          <CardBody className="text-center py-16">
            <Icon icon="solar:chart-2-bold-duotone" className="text-6xl text-default-300 mb-4" />
            <h3 className="text-xl font-semibold mb-2">暂无分组对比记录</h3>
            <p className="text-default-500 mb-4">
              运行分析脚本生成分组对比数据
            </p>
            <code className="bg-content2 px-4 py-2 rounded-lg text-sm">
              python scripts/analyze_top_traders.py
            </code>
          </CardBody>
        </Card>
      </DefaultLayout>
    );
  }

  return (
    <DefaultLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Icon icon="solar:ranking-bold-duotone" className="text-primary" />
              分组对比分析
            </h1>
            <p className="text-default-500 text-sm mt-1">
              AI 驱动的交易员分组淘汰赛，选出最优秀的交易员
            </p>
          </div>
          <Button
            color="primary"
            variant="flat"
            startContent={<Icon icon="solar:refresh-bold" />}
            onPress={loadSessions}
          >
            刷新
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* 左侧：会话列表 */}
          <div className="lg:col-span-1">
            <SessionList
              sessions={sessions}
              selectedSessionId={selectedSession?.id || null}
              onSessionSelect={loadSessionDetail}
            />
          </div>

          {/* 右侧：会话详情 */}
          <div className="lg:col-span-3 space-y-6">
            {detailLoading ? (
              <Card>
                <CardBody className="flex justify-center py-16">
                  <Spinner size="lg" />
                </CardBody>
              </Card>
            ) : selectedSession ? (
              <>
                {/* 会话概览 */}
                <SessionOverview session={selectedSession} />

                {/* 晋级者列表 */}
                <FinalistsList
                  finalists={selectedSession.finalists || []}
                  onTraderClick={handleTraderClick}
                />

                {/* 分组详情 - 按轮次组织 */}
                <RoundDetails
                  session={selectedSession}
                  onTraderClick={handleTraderClick}
                />

                {/* 最终排名分析 */}
                <FinalRankingAnalysis finalRanking={selectedSession.final_ranking} />
              </>
            ) : (
              <Card>
                <CardBody className="text-center py-16">
                  <Icon icon="solar:cursor-bold" className="text-4xl text-default-300 mb-2" />
                  <p className="text-default-500">选择一个分析记录查看详情</p>
                </CardBody>
              </Card>
            )}
          </div>
        </div>
      </div>
    </DefaultLayout>
  );
}
