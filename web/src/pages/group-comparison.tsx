import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardHeader, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Button } from '@heroui/button';
import { Chip } from '@heroui/chip';
import { Accordion, AccordionItem } from '@heroui/accordion';
import { Icon } from '@iconify/react';
import DefaultLayout from '@/layouts/default';
import { groupComparisonApi, GroupComparisonSession } from '@/services/api';

// 格式化数字
const formatNumber = (num: number, decimals = 2) => {
  if (num === undefined || num === null) return '-';
  return num.toLocaleString('en-US', { maximumFractionDigits: decimals });
};

// 格式化美元
const formatUSD = (num: number) => {
  if (num === undefined || num === null) return '-';
  const sign = num >= 0 ? '' : '-';
  return `${sign}$${Math.abs(num).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};

// 格式化百分比
const formatPercent = (num: number) => {
  if (num === undefined || num === null) return '-';
  return `${(num * 100).toFixed(1)}%`;
};

// 格式化时间
const formatTime = (dateStr: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

// 状态徽章
const StatusBadge = ({ status }: { status: string }) => {
  const colors: Record<string, 'success' | 'warning' | 'danger' | 'default'> = {
    completed: 'success',
    running: 'warning',
    failed: 'danger',
    pending: 'default',
  };
  const labels: Record<string, string> = {
    completed: '已完成',
    running: '进行中',
    failed: '失败',
    pending: '待处理',
  };
  return (
    <Chip color={colors[status] || 'default'} size="sm" variant="flat">
      {labels[status] || status}
    </Chip>
  );
};

// 交易员卡片
const TraderCard = ({
  trader,
  rank,
  isFinalist,
  showEliminatedRound,
  onClick,
}: {
  trader: any;
  rank?: number;
  isFinalist?: boolean;
  showEliminatedRound?: boolean;
  onClick?: () => void;
}) => {
  const address = trader.address || '';
  const shortAddr = `${address.slice(0, 6)}...${address.slice(-4)}`;

  return (
    <Card
      isPressable={!!onClick}
      onPress={onClick}
      className={`bg-content2/50 ${isFinalist ? 'border-2 border-success/50' : ''} ${
        trader.eliminated_round ? 'opacity-75' : ''
      }`}
    >
      <CardBody className="p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {rank && (
              <span className={`text-lg font-bold ${rank <= 3 ? 'text-warning' : 'text-default-500'}`}>
                #{rank}
              </span>
            )}
            {isFinalist && (
              <Icon icon="solar:medal-ribbon-bold" className="text-success text-lg" />
            )}
            <span className="font-mono text-sm">{shortAddr}</span>
          </div>
          <div className="flex items-center gap-1">
            {showEliminatedRound && trader.eliminated_round && (
              <Chip size="sm" variant="flat" color="danger">
                第{trader.eliminated_round}轮淘汰
              </Chip>
            )}
            <Chip size="sm" variant="flat" color="primary">
              {formatNumber(trader.overall_score, 1)}分
            </Chip>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-default-500">总盈亏</span>
            <span className={trader.total_pnl >= 0 ? 'text-success' : 'text-danger'}>
              {formatUSD(trader.total_pnl)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-default-500">胜率</span>
            <span>{formatPercent(trader.win_rate)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-default-500">Sharpe</span>
            <span>{formatNumber(trader.sharpe_ratio)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-default-500">回撤</span>
            <span className="text-danger">{formatPercent(trader.max_drawdown)}</span>
          </div>
        </div>

        {trader.elimination_reason && (
          <div className="mt-2 text-xs text-danger">
            <Icon icon="solar:danger-triangle-linear" className="inline mr-1" />
            {trader.elimination_reason}
          </div>
        )}
      </CardBody>
    </Card>
  );
};

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

  if (loading) {
    return (
      <DefaultLayout>
        <div className="flex justify-center items-center h-96">
          <Spinner size="lg" />
        </div>
      </DefaultLayout>
    );
  }

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
            <Card>
              <CardHeader className="pb-2">
                <h3 className="font-semibold">分析记录</h3>
              </CardHeader>
              <CardBody className="pt-0">
                <div className="space-y-2">
                  {sessions.map((session) => (
                    <div
                      key={session.id}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedSession?.id === session.id
                          ? 'bg-primary/20 border border-primary/50'
                          : 'bg-content2/50 hover:bg-content2'
                      }`}
                      onClick={() => loadSessionDetail(session.id)}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium">#{session.id}</span>
                        <StatusBadge status={session.status} />
                      </div>
                      <div className="text-xs text-default-500">
                        {formatTime(session.created_at)}
                      </div>
                      <div className="flex flex-wrap gap-2 mt-2 text-xs">
                        <Chip size="sm" variant="flat">
                          {session.total_traders} 人
                        </Chip>
                        {session.total_rounds > 1 && (
                          <Chip size="sm" variant="flat" color="secondary">
                            {session.total_rounds} 轮
                          </Chip>
                        )}
                        <Chip size="sm" variant="flat" color="success">
                          晋级 {session.finalists_count}
                        </Chip>
                      </div>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>
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
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between w-full">
                      <h3 className="font-semibold">分析概览</h3>
                      <StatusBadge status={selectedSession.status} />
                    </div>
                  </CardHeader>
                  <CardBody>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                      <div className="text-center p-3 bg-content2/50 rounded-lg">
                        <div className="text-2xl font-bold text-primary">
                          {selectedSession.total_traders}
                        </div>
                        <div className="text-xs text-default-500">参与交易员</div>
                      </div>
                      <div className="text-center p-3 bg-content2/50 rounded-lg">
                        <div className="text-2xl font-bold text-secondary">
                          {selectedSession.total_rounds || 1}
                        </div>
                        <div className="text-xs text-default-500">淘汰轮次</div>
                      </div>
                      <div className="text-center p-3 bg-content2/50 rounded-lg">
                        <div className="text-2xl font-bold text-warning">
                          {selectedSession.num_groups}
                        </div>
                        <div className="text-xs text-default-500">总分组数</div>
                      </div>
                      <div className="text-center p-3 bg-content2/50 rounded-lg">
                        <div className="text-2xl font-bold text-success">
                          {selectedSession.finalists_count}
                        </div>
                        <div className="text-xs text-default-500">晋级决赛</div>
                      </div>
                      <div className="text-center p-3 bg-content2/50 rounded-lg">
                        <div className="text-2xl font-bold">
                          {selectedSession.group_size} → {selectedSession.top_per_group}
                        </div>
                        <div className="text-xs text-default-500">每组/晋级</div>
                      </div>
                    </div>

                    {/* 筛选条件 */}
                    {(selectedSession.min_sharpe || selectedSession.max_drawdown) && (
                      <div className="mt-4 pt-4 border-t border-divider">
                        <div className="text-xs text-default-500 mb-2">预筛选条件</div>
                        <div className="flex flex-wrap gap-2">
                          {selectedSession.min_sharpe && (
                            <Chip size="sm" variant="flat">
                              Sharpe ≥ {selectedSession.min_sharpe}
                            </Chip>
                          )}
                          {selectedSession.min_sortino && (
                            <Chip size="sm" variant="flat">
                              Sortino ≥ {selectedSession.min_sortino}
                            </Chip>
                          )}
                          {selectedSession.max_drawdown && (
                            <Chip size="sm" variant="flat">
                              回撤 ≤ {formatPercent(selectedSession.max_drawdown)}
                            </Chip>
                          )}
                          {selectedSession.min_win_rate && (
                            <Chip size="sm" variant="flat">
                              胜率 ≥ {formatPercent(selectedSession.min_win_rate)}
                            </Chip>
                          )}
                          {selectedSession.max_win_rate && (
                            <Chip size="sm" variant="flat">
                              胜率 ≤ {formatPercent(selectedSession.max_win_rate)}
                            </Chip>
                          )}
                        </div>
                      </div>
                    )}
                  </CardBody>
                </Card>

                {/* 晋级者列表 */}
                {selectedSession.finalists && selectedSession.finalists.length > 0 && (
                  <Card>
                    <CardHeader>
                      <h3 className="font-semibold flex items-center gap-2">
                        <Icon icon="solar:cup-star-bold" className="text-warning" />
                        决赛晋级者 ({selectedSession.finalists.length})
                      </h3>
                    </CardHeader>
                    <CardBody>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        {selectedSession.finalists.map((trader, index) => (
                          <TraderCard
                            key={trader.address}
                            trader={trader}
                            rank={trader.final_rank || index + 1}
                            isFinalist
                            onClick={() => handleTraderClick(trader.address)}
                          />
                        ))}
                      </div>
                    </CardBody>
                  </Card>
                )}

                {/* 分组详情 - 按轮次组织 */}
                {selectedSession.groups && selectedSession.groups.length > 0 && (
                  <Card>
                    <CardHeader>
                      <h3 className="font-semibold flex items-center gap-2">
                        <Icon icon="solar:users-group-rounded-bold" className="text-primary" />
                        淘汰赛详情
                      </h3>
                    </CardHeader>
                    <CardBody>
                      {/* 按轮次分组 */}
                      {(() => {
                        // 获取所有轮次
                        const rounds = [...new Set(selectedSession.groups?.map(g => g.round_num || 1))].sort((a, b) => a - b);

                        return (
                          <div className="space-y-6">
                            {rounds.map((roundNum) => {
                              const roundGroups = selectedSession.groups?.filter(g => (g.round_num || 1) === roundNum) || [];
                              // 计算本轮晋级和淘汰人数
                              const roundTraders = selectedSession.traders?.filter(t =>
                                roundGroups.some(g => g.id === t.group_id) ||
                                (t.eliminated_round === roundNum)
                              ) || [];
                              const promotedCount = roundTraders.filter(t => !t.eliminated_round || t.eliminated_round > roundNum).length;
                              const eliminatedCount = roundTraders.filter(t => t.eliminated_round === roundNum).length;

                              return (
                                <div key={roundNum} className="border border-divider rounded-lg overflow-hidden">
                                  {/* 轮次标题 */}
                                  <div className="bg-content2 px-4 py-3 flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                      <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                                        <span className="text-primary font-bold">{roundNum}</span>
                                      </div>
                                      <div>
                                        <h4 className="font-semibold">第 {roundNum} 轮淘汰</h4>
                                        <div className="text-xs text-default-500">
                                          {roundGroups.length} 个分组
                                        </div>
                                      </div>
                                    </div>
                                    <div className="flex gap-2">
                                      <Chip size="sm" variant="flat" color="success">
                                        <Icon icon="solar:arrow-up-bold" className="mr-1" />
                                        晋级 {promotedCount}
                                      </Chip>
                                      <Chip size="sm" variant="flat" color="danger">
                                        <Icon icon="solar:close-circle-bold" className="mr-1" />
                                        淘汰 {eliminatedCount}
                                      </Chip>
                                    </div>
                                  </div>

                                  {/* 本轮分组 */}
                                  <div className="p-4">
                                    <Accordion variant="splitted">
                                      {roundGroups.map((group) => {
                                        const groupTraders = selectedSession.traders?.filter(
                                          (t) => t.group_id === group.id
                                        ) || [];
                                        const promoted = groupTraders.filter(t => !t.eliminated_round || t.eliminated_round > roundNum);
                                        const eliminated = groupTraders.filter(t => t.eliminated_round === roundNum);

                                        return (
                                          <AccordionItem
                                            key={group.id}
                                            aria-label={`第 ${group.group_num} 组`}
                                            title={
                                              <div className="flex items-center gap-2">
                                                <span>第 {group.group_num} 组</span>
                                                <Chip size="sm" variant="flat">
                                                  {group.total_in_group} 人
                                                </Chip>
                                                <Chip size="sm" variant="flat" color="success">
                                                  晋级 {promoted.length}
                                                </Chip>
                                              </div>
                                            }
                                          >
                                            <div className="space-y-4">
                                              {/* 晋级者 */}
                                              {promoted.length > 0 && (
                                                <div>
                                                  <div className="text-xs text-success mb-2 flex items-center gap-1">
                                                    <Icon icon="solar:medal-ribbon-bold" />
                                                    晋级者
                                                  </div>
                                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    {promoted.map((trader) => (
                                                      <TraderCard
                                                        key={trader.address}
                                                        trader={trader}
                                                        isFinalist={trader.is_finalist}
                                                        onClick={() => handleTraderClick(trader.address)}
                                                      />
                                                    ))}
                                                  </div>
                                                </div>
                                              )}

                                              {/* 被淘汰者 */}
                                              {eliminated.length > 0 && (
                                                <div>
                                                  <div className="text-xs text-danger mb-2 flex items-center gap-1">
                                                    <Icon icon="solar:close-circle-bold" />
                                                    被淘汰
                                                  </div>
                                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                    {eliminated.map((trader) => (
                                                      <TraderCard
                                                        key={trader.address}
                                                        trader={trader}
                                                        showEliminatedRound
                                                        onClick={() => handleTraderClick(trader.address)}
                                                      />
                                                    ))}
                                                  </div>
                                                </div>
                                              )}

                                              {/* AI 分析 */}
                                              {group.analysis && (
                                                <div className="mt-4 p-4 bg-content2/50 rounded-lg">
                                                  <div className="text-xs text-default-500 mb-2 flex items-center gap-1">
                                                    <Icon icon="solar:magic-stick-3-bold" />
                                                    AI 分析
                                                  </div>
                                                  <div className="text-sm whitespace-pre-wrap">
                                                    {group.analysis}
                                                  </div>
                                                </div>
                                              )}
                                            </div>
                                          </AccordionItem>
                                        );
                                      })}
                                    </Accordion>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        );
                      })()}
                    </CardBody>
                  </Card>
                )}

                {/* 最终排名分析 */}
                {selectedSession.final_ranking && (
                  <Card>
                    <CardHeader>
                      <h3 className="font-semibold flex items-center gap-2">
                        <Icon icon="solar:document-text-bold" className="text-success" />
                        综合排名分析
                      </h3>
                    </CardHeader>
                    <CardBody>
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <div className="whitespace-pre-wrap text-sm">
                          {typeof selectedSession.final_ranking === 'string'
                            ? selectedSession.final_ranking
                            : JSON.stringify(selectedSession.final_ranking, null, 2)}
                        </div>
                      </div>
                    </CardBody>
                  </Card>
                )}
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

