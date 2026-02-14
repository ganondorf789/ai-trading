export interface SpotToken {
  name: string;
  szDecimals: number;
  weiDecimals: number;
  index: number;
  tokenId: string;
  isCanonical: boolean;
  evmContract: {
    address: string;
    evm_extra_wei_decimals: number;
  } | null;
  fullName: string | null;
  deployerTradingFeeShare: string;
}

export interface SpotPair {
  tokens: [number, number];
  name: string;
  index: number;
  isCanonical: boolean;
}

export interface SpotMeta {
  universe: SpotPair[];
  tokens: SpotToken[];
}

export interface SpotAssetCtx {
  prevDayPx: string;
  dayNtlVlm: string;
  markPx: string;
  midPx: string;
  circulatingSupply: string;
  coin: string;
  totalSupply: string;
  dayBaseVlm: string;
}

export type SpotMetaAndAssetCtxs = [SpotMeta, SpotAssetCtx[]];

// Portfolio
export type PortfolioPeriod = 'day' | 'week' | 'month' | 'allTime' | 'perpDay' | 'perpWeek' | 'perpMonth' | 'perpAllTime';

export interface PortfolioPeriodData {
  accountValueHistory: [number, string][];
  pnlHistory: [number, string][];
  vlm: string;
}

export type PortfolioResponse = [PortfolioPeriod, PortfolioPeriodData][];

// ClearinghouseState
export interface MarginSummary {
  accountValue: string;
  totalNtlPos: string;
  totalRawUsd: string;
  totalMarginUsed: string;
}

export interface ClearinghouseState {
  marginSummary: MarginSummary;
  crossMarginSummary: MarginSummary;
  crossMaintenanceMarginUsed: string;
  withdrawable: string;
  assetPositions: unknown[];
  time: number;
}
