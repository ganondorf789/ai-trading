import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter } from '@heroui/modal';
import { Button } from '@heroui/button';
import { Card, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Tabs, Tab } from '@heroui/tabs';
import { Icon } from '@iconify/react';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css/github-markdown-light.css';

import type { PositionsAIAnalysis } from '@/services/api';

interface PositionsAIAnalysisModalProps {
  isOpen: boolean;
  analysisData: PositionsAIAnalysis | null;
  analyzing: boolean;
  analysisType: 'overall' | 'coin' | 'single';
  coinName?: string;
  onClose: () => void;
  onReanalyze?: () => void;
}

export function PositionsAIAnalysisModal({
  isOpen,
  analysisData,
  analyzing,
  analysisType,
  coinName,
  onClose,
  onReanalyze,
}: PositionsAIAnalysisModalProps) {
  const getTitle = () => {
    switch (analysisType) {
      case 'overall':
        return '整体持仓 AI 分析';
      case 'coin':
        return `${coinName || ''} 持仓 AI 分析`;
      case 'single':
        return '仓位风险 AI 分析';
      default:
        return 'AI 分析';
    }
  };

  const getIcon = () => {
    switch (analysisType) {
      case 'overall':
        return 'solar:chart-2-bold-duotone';
      case 'coin':
        return 'solar:dollar-bold-duotone';
      case 'single':
        return 'solar:shield-warning-bold-duotone';
      default:
        return 'solar:magic-stick-2-bold-duotone';
    }
  };

  const renderOverallAnalysis = () => {
    if (!analysisData?.sections) return null;
    const sections = analysisData.sections;

    return (
      <div className="space-y-6">
        {/* 市场情绪概览 */}
        {sections.market_sentiment && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:emoticon-cool-bold-duotone" width={20} className="text-blue-500" />
              市场情绪概览
            </h3>
            <Card className="bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.market_sentiment}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 多空力量分析 */}
        {sections.long_short_analysis && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:scale-bold-duotone" width={20} className="text-purple-500" />
              多空力量分析
            </h3>
            <Card className="bg-purple-50 dark:bg-purple-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.long_short_analysis}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 热门币种解读 */}
        {sections.hot_coins && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:fire-bold-duotone" width={20} className="text-orange-500" />
              热门币种解读
            </h3>
            <Card className="bg-orange-50 dark:bg-orange-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.hot_coins}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 风险聚集警示 */}
        {sections.risk_warning && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:danger-triangle-bold-duotone" width={20} className="text-red-500" />
              风险聚集警示
            </h3>
            <Card className="bg-red-50 dark:bg-red-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.risk_warning}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 关注要点 */}
        {sections.key_points && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:star-bold-duotone" width={20} className="text-yellow-500" />
              关注要点
            </h3>
            <Card className="bg-yellow-50 dark:bg-yellow-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.key_points}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 操作建议 */}
        {sections.suggestions && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:lightbulb-bolt-bold-duotone" width={20} className="text-green-500" />
              操作建议
            </h3>
            <Card className="bg-green-50 dark:bg-green-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.suggestions}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    );
  };

  const renderCoinAnalysis = () => {
    if (!analysisData?.sections) return null;
    const sections = analysisData.sections;

    return (
      <div className="space-y-6">
        {/* 多空力量对比 */}
        {sections.long_short_comparison && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:scale-bold-duotone" width={20} className="text-purple-500" />
              多空力量对比
            </h3>
            <Card className="bg-purple-50 dark:bg-purple-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.long_short_comparison}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 关键价位分析 */}
        {sections.key_levels && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:chart-bold-duotone" width={20} className="text-blue-500" />
              关键价位分析
            </h3>
            <Card className="bg-blue-50 dark:bg-blue-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.key_levels}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 交易员共识 */}
        {sections.trader_consensus && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:users-group-two-rounded-bold-duotone" width={20} className="text-indigo-500" />
              交易员共识
            </h3>
            <Card className="bg-indigo-50 dark:bg-indigo-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.trader_consensus}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 风险评估 */}
        {sections.risk_assessment && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:danger-triangle-bold-duotone" width={20} className="text-red-500" />
              风险评估
            </h3>
            <Card className="bg-red-50 dark:bg-red-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.risk_assessment}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 操作建议 */}
        {sections.suggestions && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:lightbulb-bolt-bold-duotone" width={20} className="text-green-500" />
              操作建议
            </h3>
            <Card className="bg-green-50 dark:bg-green-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.suggestions}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    );
  };

  const renderSingleAnalysis = () => {
    if (!analysisData?.sections) return null;
    const sections = analysisData.sections;

    return (
      <div className="space-y-6">
        {/* 风险评级 */}
        {sections.risk_level && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:shield-warning-bold-duotone" width={20} className="text-orange-500" />
              风险评级
            </h3>
            <Card className="bg-gradient-to-r from-orange-50 to-red-50 dark:from-orange-900/20 dark:to-red-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.risk_level}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 关键风险点 */}
        {sections.key_risks && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:danger-triangle-bold-duotone" width={20} className="text-red-500" />
              关键风险点
            </h3>
            <Card className="bg-red-50 dark:bg-red-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.key_risks}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 盈亏分析 */}
        {sections.pnl_analysis && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:dollar-bold-duotone" width={20} className="text-blue-500" />
              盈亏分析
            </h3>
            <Card className="bg-blue-50 dark:bg-blue-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.pnl_analysis}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}

        {/* 建议 */}
        {sections.suggestions && (
          <div>
            <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
              <Icon icon="solar:lightbulb-bolt-bold-duotone" width={20} className="text-green-500" />
              建议
            </h3>
            <Card className="bg-green-50 dark:bg-green-900/20">
              <CardBody>
                <div className="markdown-body">
                  <ReactMarkdown>{sections.suggestions}</ReactMarkdown>
                </div>
              </CardBody>
            </Card>
          </div>
        )}
      </div>
    );
  };

  const renderContent = () => {
    if (analyzing) {
      return (
        <div className="flex flex-col items-center justify-center py-16">
          <Spinner size="lg" color="primary" />
          <p className="mt-4 text-gray-500">AI 正在分析中，请稍候...</p>
          <p className="mt-2 text-sm text-gray-400">分析可能需要 30-60 秒</p>
        </div>
      );
    }

    if (!analysisData) {
      return (
        <div className="text-center py-16">
          <Icon icon="solar:magic-stick-2-bold-duotone" width={48} className="mx-auto text-gray-300 mb-4" />
          <p className="text-gray-500">暂无分析结果</p>
        </div>
      );
    }

    return (
      <Tabs aria-label="分析内容" color="primary" variant="underlined" classNames={{ tabList: "mb-4" }}>
        <Tab key="sections" title="分析报告">
          {analysisType === 'overall' && renderOverallAnalysis()}
          {analysisType === 'coin' && renderCoinAnalysis()}
          {analysisType === 'single' && renderSingleAnalysis()}
        </Tab>
        <Tab key="full" title="完整内容">
          <Card>
            <CardBody>
              <div className="markdown-body">
                <ReactMarkdown>{analysisData.analysis_text}</ReactMarkdown>
              </div>
            </CardBody>
          </Card>
        </Tab>
      </Tabs>
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="5xl"
      scrollBehavior="inside"
    >
      <ModalContent>
        {(onCloseModal) => (
          <>
            <ModalHeader className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <Icon icon={getIcon()} width={24} className="text-primary" />
                <span>{getTitle()}</span>
              </div>
              {analysisData && (
                <p className="text-sm font-normal text-gray-500">
                  分析 {analysisData.position_count || 0} 个持仓
                </p>
              )}
            </ModalHeader>
            <ModalBody>
              {renderContent()}
            </ModalBody>
            <ModalFooter>
              {onReanalyze && (
                <Button
                  color="secondary"
                  variant="flat"
                  isLoading={analyzing}
                  onPress={onReanalyze}
                  startContent={!analyzing && <Icon icon="solar:refresh-bold" width={16} />}
                >
                  {analyzing ? '分析中...' : '重新分析'}
                </Button>
              )}
              <Button color="primary" variant="light" onPress={onCloseModal}>
                关闭
              </Button>
            </ModalFooter>
          </>
        )}
      </ModalContent>
    </Modal>
  );
}
