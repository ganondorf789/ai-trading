import { Card, CardHeader, CardBody } from '@heroui/card';
import { Chip } from '@heroui/chip';
import { GroupComparisonSession } from '@/services/api';
import { formatTime } from '../utils';
import { StatusBadge } from './StatusBadge';

interface SessionListProps {
  sessions: GroupComparisonSession[];
  selectedSessionId: number | null;
  onSessionSelect: (sessionId: number) => void;
}

export const SessionList = ({ sessions, selectedSessionId, onSessionSelect }: SessionListProps) => {
  return (
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
                selectedSessionId === session.id
                  ? 'bg-primary/20 border border-primary/50'
                  : 'bg-content2/50 hover:bg-content2'
              }`}
              onClick={() => onSessionSelect(session.id)}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {session.rating && (
                    <span
                      className={`text-sm font-bold ${
                        session.rating === 'S' ? 'text-purple-500' :
                        session.rating === 'A' ? 'text-blue-500' :
                        session.rating === 'B' ? 'text-green-500' :
                        session.rating === 'C' ? 'text-yellow-500' :
                        session.rating === 'D' ? 'text-orange-500' :
                        session.rating === 'F' ? 'text-red-500' :
                        'text-gray-500'
                      }`}
                    >
                      {session.rating}
                    </span>
                  )}
                </div>
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
  );
};
