/**
 * Stocks API client.
 * Provides methods for fetching OHLCV candle data.
 */

import { apiFetch } from "./api";

export interface CandleResponse {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Stocks API client object
 */
export const stocksAPI = {
  /**
   * Get OHLCV candles for a symbol
   */
  getCandles: (
    symbol: string,
    resolution: "5m" | "15m" | "1h" | "D",
    from: string,
    to: string
  ): Promise<CandleResponse[]> =>
    apiFetch(`/api/stocks/${symbol}/candles?resolution=${resolution}&from=${from}&to=${to}`),
};
