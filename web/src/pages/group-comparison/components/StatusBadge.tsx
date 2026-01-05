import { Chip } from '@heroui/chip';

interface StatusBadgeProps {
  status: string;
}

export const StatusBadge = ({ status }: StatusBadgeProps) => {
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
