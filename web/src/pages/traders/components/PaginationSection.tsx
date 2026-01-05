import { useState } from 'react';
import { Pagination } from '@heroui/pagination';
import { Input } from '@heroui/input';

interface PaginationSectionProps {
  page: number;
  totalPages: number;
  totalCount: number;
  rowsPerPage: number;
  onPageChange: (page: number) => void;
}

export function PaginationSection({
  page,
  totalPages,
  totalCount,
  rowsPerPage,
  onPageChange,
}: PaginationSectionProps) {
  const [jumpPage, setJumpPage] = useState('');

  const handleJumpPage = () => {
    const pageNum = parseInt(jumpPage);
    if (pageNum >= 1 && pageNum <= totalPages) {
      onPageChange(pageNum);
      setJumpPage('');
    }
  };

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-2 py-2">
      <span className="text-sm text-gray-500">
        显示 {Math.min((page - 1) * rowsPerPage + 1, totalCount)} - {Math.min(page * rowsPerPage, totalCount)} 条，共 {totalCount} 条记录
      </span>
      <div className="flex items-center gap-3">
        <Pagination
          isCompact
          showControls
          showShadow
          color="primary"
          page={page}
          total={totalPages}
          onChange={onPageChange}
        />
        <div className="flex items-center gap-1">
          <span className="text-sm text-gray-500">跳转</span>
          <Input
            type="number"
            size="sm"
            className="w-16"
            min={1}
            max={totalPages}
            value={jumpPage}
            onValueChange={setJumpPage}
            onKeyDown={(e) => e.key === 'Enter' && handleJumpPage()}
          />
          <span className="text-sm text-gray-500">页</span>
        </div>
      </div>
    </div>
  );
}
