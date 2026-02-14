import axios from 'axios';
import type { SpotMetaAndAssetCtxs, PortfolioResponse, ClearinghouseState } from '@/types/hyperliquid';

const HYPERLIQUID_API = 'https://api.hyperliquid.xyz';

const client = axios.create({
  baseURL: HYPERLIQUID_API,
});

export const hyperliquidApi = {
  getSpotMetaAndAssetCtxs: async (): Promise<SpotMetaAndAssetCtxs> => {
    const { data } = await client.post<SpotMetaAndAssetCtxs>('/info', {
      type: 'spotMetaAndAssetCtxs',
    });
    return data;
  },

  getPortfolio: async (user: string): Promise<PortfolioResponse> => {
    const { data } = await client.post<PortfolioResponse>('/info', {
      type: 'portfolio',
      user,
    });
    return data;
  },

  getClearinghouseState: async (user: string): Promise<ClearinghouseState> => {
    const { data } = await client.post<ClearinghouseState>('/info', {
      type: 'clearinghouseState',
      user,
    });
    return data;
  },
};
