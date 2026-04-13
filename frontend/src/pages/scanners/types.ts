/**
 * TypeScript types for Scanner API.
 * Matches Pydantic schemas in src/api/scanners/schemas.py
 */

export interface ScannerMeta {
  name: string;
  timeframe: string;
  description: string;
}

export interface ScannerResultItem {
  scanner_name: string;
  symbol: string;
  score: number | null;
  signal: string | null;
  price: number | null;
  volume: number | null;
  change_pct: number | null;
  indicators_fired: string[];
  matched_at: string; // ISO datetime
}

export interface ScannerResultsResponse {
  results: ScannerResultItem[];
  run_type: string;
  date: string;
}

export interface GetResultsFilters {
  scanners?: string[];
  run_type?: "eod" | "pre_close";
  date?: string; // ISO date
}

export interface IntradayRunRequest {
  scanners: string[];
  timeframe: "15m" | "1h";
  input_scope: "universe" | number; // 'universe' or watchlist_id
}
