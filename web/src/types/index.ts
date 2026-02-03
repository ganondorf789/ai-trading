import { SVGProps } from "react";

export type IconSvgProps = SVGProps<SVGSVGElement> & {
  size?: number;
};

// Export all API types
export type {
  // Trader types
  Trader,
  TraderFill,
  AssetPosition,
  ChartDataPoint,
  TraderHistory,
  TraderAIAnalysis,
  // Common response types
  PaginationInfo,
  FillsStats,
  ApiResponse,
  // Copy trading types
  CopyTradingGroup,
  CopyTradingAddress,
  CopyPositionState,
  CopyPositionStats,
  // Hyperliquid types
  HyperliquidCoin,
} from './api';
