import { apiFetch } from "./api";

export interface IVRData {
  symbol: string;
  ivr: number;
  current_value: number;
  calculation_basis: string;
  as_of_date: string;
}

export interface RegimeData {
  symbol: string;
  regime: "trending" | "ranging" | "transitional";
  direction: string | null;
  adx: number;
  atr_pct: number;
  as_of_date: string;
}

export const optionsAPI = {
  getIVR: (symbol: string): Promise<IVRData> =>
    apiFetch(`/api/options/ivr/${symbol}`),

  getIVRBulk: (symbols: string[]): Promise<IVRData[]> =>
    apiFetch(`/api/options/ivr?symbols=${symbols.join(",")}`),

  getRegime: (symbol: string): Promise<RegimeData> =>
    apiFetch(`/api/options/regime/${symbol}`),

  getRegimeBulk: (symbols: string[]): Promise<RegimeData[]> =>
    apiFetch(`/api/options/regime?symbols=${symbols.join(",")}`),
};
