import { apiFetch } from "./api";

export interface IVRData {
  symbol: string;
  ivr: number;
  current_hv: number;
  calculation_basis: string;
  as_of_date: string;
}

export const optionsAPI = {
  getIVR: (symbol: string): Promise<IVRData> =>
    apiFetch(`/api/options/ivr/${symbol}`),

  getIVRBulk: (symbols: string[]): Promise<IVRData[]> =>
    apiFetch(`/api/options/ivr?symbols=${symbols.join(",")}`),
};
