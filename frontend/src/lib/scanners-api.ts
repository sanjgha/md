/**
 * Scanner API client.
 * Provides methods for querying scanner results and running intraday scans.
 */

import { apiFetch } from "./api";
import type {
  GetResultsFilters,
  IntradayRunRequest,
  RunDateEntry,
  ScannerMeta,
  ScannerResultsResponse,
} from "../pages/scanners/types";

export type { RunDateEntry } from "../pages/scanners/types";

/**
 * List all available scanners
 */
export const listScanners = (): Promise<ScannerMeta[]> =>
  apiFetch("/api/scanners");

/**
 * Get scanner results with optional filters
 */
export const getResults = (
  filters: GetResultsFilters = {}
): Promise<ScannerResultsResponse> => {
  const params = new URLSearchParams();
  if (filters.run_type) params.set("run_type", filters.run_type);
  if (filters.date) params.set("date", filters.date);
  if (filters.scanners?.length) params.set("scanners", filters.scanners.join(","));
  const qs = params.toString();
  return apiFetch(`/api/scanners/results${qs ? `?${qs}` : ""}`);
};

/**
 * Get available run dates
 */
export const getRunDates = (): Promise<RunDateEntry[]> =>
  apiFetch("/api/scanners/run-dates");

/**
 * Run intraday scan with specified parameters
 */
export const runIntraday = (
  req: IntradayRunRequest
): Promise<ScannerResultsResponse> =>
  apiFetch("/api/scanners/run", {
    method: "POST",
    body: JSON.stringify(req),
  });
