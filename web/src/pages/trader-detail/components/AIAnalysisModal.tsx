import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter } from '@heroui/modal';
import { Button } from '@heroui/button';
import { Card, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Icon } from '@iconify/react';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css/github-markdown-light.css';

interface AIAnalysisModalProps {
  isOpen: boolean;
  aiAnalysisData: any;
  aiAnalyzing: boolean;
  onClose: () => void;
  onReanalyze: () => void;
}

export function AIAnalysisModal({
  isOpen,
  aiAnalysisData,
  aiAnalyzing,
  onClose,
  onReanalyze,
}: AIAnalysisModalProps) {
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
                <Icon icon="solar:magic-stick-2-bold-duotone" width={24} className="text-purple-500" />
                <span>AI深度分析报告</span>
              </div>
              {aiAnalysisData && (
                <p className="text-sm font-normal text-gray-500">
                  分析时间: {aiAnalysisData.analyzed_at
                    ? new Date(aiAnalysisData.analyzed_at).toLocaleString('zh-CN', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                      })
                    : '未知'}
                  {aiAnalysisData.ai_provider && ` | 提供商: ${aiAnalysisData.ai_provider}`}
                </p>
              )}
            </ModalHeader>
            <ModalBody>
              {aiAnalysisData ? (
                <div className="space-y-6">
                  {/* 综合评价 */}
                  {aiAnalysisData.summary && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:star-bold-duotone" width={20} className="text-yellow-500" />
                        综合评价
                      </h3>
                      <Card className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20">
                        <CardBody>
                          <ReactMarkdown>{aiAnalysisData.summary}</ReactMarkdown>
                        </CardBody>
                      </Card>
                    </div>
                  )}

                  {/* 优势分析 */}
                  {aiAnalysisData.strengths && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:shield-check-bold-duotone" width={20} className="text-green-500" />
                        优势分析
                      </h3>
                      <Card className="bg-green-50 dark:bg-green-900/20">
                        <CardBody>
                          <div className="markdown-body">
                            <ReactMarkdown>{aiAnalysisData.strengths}</ReactMarkdown>
                          </div>
                        </CardBody>
                      </Card>
                    </div>
                  )}

                  {/* 风险提示 */}
                  {aiAnalysisData.risks && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:danger-triangle-bold-duotone" width={20} className="text-red-500" />
                        风险提示
                      </h3>
                      <Card className="bg-red-50 dark:bg-red-900/20">
                        <CardBody>
                          <div className="markdown-body">
                            <ReactMarkdown>{aiAnalysisData.risks}</ReactMarkdown>
                          </div>
                        </CardBody>
                      </Card>
                    </div>
                  )}

                  {/* 交易风格 */}
                  {aiAnalysisData.trading_style && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:graph-new-bold-duotone" width={20} className="text-blue-500" />
                        交易风格
                      </h3>
                      <Card>
                        <CardBody>
                          <div className="markdown-body">
                            <ReactMarkdown>{aiAnalysisData.trading_style}</ReactMarkdown>
                          </div>
                        </CardBody>
                      </Card>
                    </div>
                  )}

                  {/* 跟单建议 */}
                  {aiAnalysisData.copy_trading_advice && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:user-check-bold-duotone" width={20} className="text-indigo-500" />
                        跟单建议
                      </h3>
                      <Card className="bg-indigo-50 dark:bg-indigo-900/20">
                        <CardBody>
                          <div className="markdown-body">
                            <ReactMarkdown>{aiAnalysisData.copy_trading_advice}</ReactMarkdown>
                          </div>
                        </CardBody>
                      </Card>
                    </div>
                  )}

                  {/* 改进建议 */}
                  {aiAnalysisData.improvement_suggestions && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:lightbulb-bolt-bold-duotone" width={20} className="text-orange-500" />
                        改进建议
                      </h3>
                      <Card className="bg-orange-50 dark:bg-orange-900/20">
                        <CardBody>
                          <div className="markdown-body">
                            <ReactMarkdown>{aiAnalysisData.improvement_suggestions}</ReactMarkdown>
                          </div>
                        </CardBody>
                      </Card>
                    </div>
                  )}

                  {/* 完整分析文本（支持Markdown） */}
                  {aiAnalysisData.analysis_text && (
                    <div>
                      <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <Icon icon="solar:document-text-bold-duotone" width={20} className="text-gray-500" />
                        完整分析报告
                      </h3>
                      <Card>
                        <CardBody>
                          <div className="markdown-body">
                            <ReactMarkdown>{aiAnalysisData.analysis_text}</ReactMarkdown>
                          </div>
                        </CardBody>
                      </Card>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Spinner size="lg" />
                  <p className="mt-4 text-gray-500">加载中...</p>
                </div>
              )}
            </ModalBody>
            <ModalFooter>
              <Button
                color="secondary"
                variant="flat"
                isLoading={aiAnalyzing}
                onPress={onReanalyze}
                startContent={!aiAnalyzing && <Icon icon="solar:refresh-bold" width={16} />}
              >
                {aiAnalyzing ? '重新分析中...' : '重新分析'}
              </Button>
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
