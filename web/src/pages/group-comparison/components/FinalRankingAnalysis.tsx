import { Card, CardHeader, CardBody } from '@heroui/card';
import { Icon } from '@iconify/react';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css/github-markdown-light.css';

interface FinalRankingAnalysisProps {
  finalRanking: string | any;
}

export const FinalRankingAnalysis = ({ finalRanking }: FinalRankingAnalysisProps) => {
  if (!finalRanking) return null;

  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold flex items-center gap-2">
          <Icon icon="solar:document-text-bold" className="text-success" />
          综合排名分析
        </h3>
      </CardHeader>
      <CardBody>
        <div className="markdown-body p-4 rounded-lg">
          <ReactMarkdown>
            {typeof finalRanking === 'string'
              ? finalRanking
              : JSON.stringify(finalRanking, null, 2)}
          </ReactMarkdown>
        </div>
      </CardBody>
    </Card>
  );
};
