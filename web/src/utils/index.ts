// Rating color utilities
export const getRatingColor = (rating: string | undefined | null): string => {
  if (!rating) return 'text-gray-500';
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

// Number formatting utilities
export const formatNumber = (num: number | null | undefined, decimals = 2): string => {
  if (num === undefined || num === null) return '-';
  return num.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
};

export const formatUSD = (num: number | null | undefined): string => {
  if (num === undefined || num === null) return '-';
  const sign = num >= 0 ? '' : '-';
  return `${sign}$${Math.abs(num).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};

export const formatPercent = (num: number | null | undefined, decimals = 2): string => {
  if (num === undefined || num === null) return '-';
  return `${(num * 100).toFixed(decimals)}%`;
};

// Date and time formatting utilities
export const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
  } catch {
    return '-';
  }
};

export const formatTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '-';
  try {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '-';
  }
};
