// 格式化数字
export const formatNumber = (num: number, decimals = 2) => {
  if (num === undefined || num === null) return '-';
  return num.toLocaleString('en-US', { maximumFractionDigits: decimals });
};

// 格式化美元
export const formatUSD = (num: number) => {
  if (num === undefined || num === null) return '-';
  const sign = num >= 0 ? '' : '-';
  return `${sign}$${Math.abs(num).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};

// 格式化百分比
export const formatPercent = (num: number) => {
  if (num === undefined || num === null) return '-';
  return `${(num * 100).toFixed(1)}%`;
};

// 格式化时间
export const formatTime = (dateStr: string) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};
