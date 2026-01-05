export const getRatingColor = (rating: string): string => {
  const colors: Record<string, string> = {
    S: 'text-purple-500',
    A: 'text-blue-500',
    B: 'text-green-500',
    C: 'text-yellow-500',
    D: 'text-orange-500',
    F: 'text-red-500',
  };
  return colors[rating] || 'text-gray-500';
};

export const formatNumber = (num: number, decimals = 2): string => {
  return num.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

export const formatPercent = (num: number): string => {
  return `${(num * 100).toFixed(2)}%`;
};

export const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
  } catch {
    return '-';
  }
};
