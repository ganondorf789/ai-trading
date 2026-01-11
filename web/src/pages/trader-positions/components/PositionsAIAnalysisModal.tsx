import { Modal, ModalContent, ModalHeader, ModalBody, ModalFooter } from '@heroui/modal';
import { Button } from '@heroui/button';
import { Card, CardBody } from '@heroui/card';
import { Spinner } from '@heroui/spinner';
import { Chip } from '@heroui/chip';
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
  cached?: boolean;  // 是否是缓存的结果
  analyzedAt?: string;  // 分析时间
}

export function PositionsAIAnalysisModal({
  isOpen,
  analysisData,
  analyzing,
  analysisType,
  coinName,
  onClose,
  onReanalyze,
  cached,
  analyzedAt,
}: PositionsAIAnalysisModalProps) {
  // 格式化时间
  const formatAnalyzedTime = (time?: string) => {
    if (!time) return '';
    try {
      const date = new Date(time);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return time;
    }
  };

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
      <Card>
        <CardBody>
          <div className="markdown-body">
            <ReactMarkdown>{analysisData.analysis_text}</ReactMarkdown>
          </div>
        </CardBody>
      </Card>
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
                {cached && (
                  <Chip size="sm" color="secondary" variant="flat">
                    历史分析
                  </Chip>
                )}
              </div>
              <div className="flex items-center gap-3 text-sm font-normal text-gray-500">
                {analysisData && (
                  <span>分析 {analysisData.position_count || 0} 个持仓</span>
                )}
                {analyzedAt && (
                  <span className="flex items-center gap-1">
                    <Icon icon="solar:calendar-bold-duotone" width={14} />
                    分析时间: {formatAnalyzedTime(analyzedAt)}
                  </span>
                )}
              </div>
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
