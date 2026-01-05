import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { Accordion, AccordionItem } from '@heroui/accordion';
import { Icon } from '@iconify/react';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css/github-markdown-light.css';
import { GroupComparisonSession } from '@/services/api';
import { TraderCard } from './TraderCard';

interface RoundDetailsProps {
  session: GroupComparisonSession;
  onTraderClick: (address: string) => void;
}

export const RoundDetails = ({ session, onTraderClick }: RoundDetailsProps) => {
  if (!session.groups || session.groups.length === 0) return null;

  // 获取所有轮次
  const rounds = [...new Set(session.groups?.map(g => g.round_num || 1))].sort((a, b) => a - b);

  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold flex items-center gap-2">
          <Icon icon="solar:users-group-rounded-bold" className="text-primary" />
          淘汰赛详情
        </h3>
      </CardHeader>
      <CardBody>
        <div className="space-y-6">
          {rounds.map((roundNum) => {
            const roundGroups = session.groups?.filter(g => (g.round_num || 1) === roundNum) || [];
            // 计算本轮晋级和淘汰人数
            const roundTraders = session.traders?.filter(t =>
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
                      晋级 {promotedCount}
                    </Chip>
                    <Chip size="sm" variant="flat" color="danger">
                      淘汰 {eliminatedCount}
                    </Chip>
                  </div>
                </div>

                {/* 本轮分组 */}
                <div className="p-4">
                  <Accordion variant="splitted">
                    {roundGroups.map((group) => {
                      const groupTraders = session.traders?.filter(
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
                                      onClick={() => onTraderClick(trader.address)}
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
                                      onClick={() => onTraderClick(trader.address)}
                                    />
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* AI 分析 */}
                            {group.analysis && (
                              <div className="markdown-body text-sm p-4 rounded-lg mt-4">
                                <ReactMarkdown>{group.analysis}</ReactMarkdown>
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
      </CardBody>
    </Card>
  );
};
