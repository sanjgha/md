/**
 * Tests for scanners API client
 *
 * TDD: These tests verify the API client methods match backend endpoints
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { apiFetch } from "~/lib/api";

// Mock the apiFetch function
vi.mock("~/lib/api", () => ({
  apiFetch: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
}));

describe("scanners-api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("listScanners", () => {
    it("should call GET /api/scanners", async () => {
      const mockData = [
        { name: "momentum", timeframe: "daily", description: "RSI scan" },
        { name: "volume", timeframe: "daily", description: "Volume scan" },
      ];

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { listScanners } = await import("~/lib/scanners-api");
      const result = await listScanners();

      expect(apiFetch).toHaveBeenCalledWith("/api/scanners");
      expect(result).toEqual(mockData);
    });
  });

  describe("getResults", () => {
    it("should call GET /api/scanners/results without filters", async () => {
      const mockData = { results: [], run_type: "eod", date: "2026-04-13" };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { getResults } = await import("~/lib/scanners-api");
      const result = await getResults();

      expect(apiFetch).toHaveBeenCalledWith("/api/scanners/results");
      expect(result).toEqual(mockData);
    });

    it("should call GET /api/scanners/results with run_type filter", async () => {
      const mockData = {
        results: [
          {
            scanner_name: "momentum",
            symbol: "AAPL",
            score: 85,
            signal: "buy",
            price: 150.25,
            volume: 1000000,
            change_pct: 2.5,
            indicators_fired: ["rsi", "macd"],
            matched_at: "2026-04-13T16:00:00Z",
          },
        ],
        run_type: "eod",
        date: "2026-04-13",
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { getResults } = await import("~/lib/scanners-api");
      const result = await getResults({ run_type: "eod" });

      expect(apiFetch).toHaveBeenCalledWith(
        "/api/scanners/results?run_type=eod"
      );
      expect(result.run_type).toBe("eod");
    });

    it("should call GET /api/scanners/results with scanners filter", async () => {
      const mockData = { results: [], run_type: "eod", date: "2026-04-13" };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { getResults } = await import("~/lib/scanners-api");
      await getResults({ scanners: ["momentum", "volume"] });

      expect(apiFetch).toHaveBeenCalledWith(
        "/api/scanners/results?scanners=momentum%2Cvolume"
      );
    });

    it("should call GET /api/scanners/results with all filters", async () => {
      const mockData = { results: [], run_type: "eod", date: "2026-04-13" };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { getResults } = await import("~/lib/scanners-api");
      await getResults({
        run_type: "eod",
        scanners: ["momentum"],
        date: "2026-04-13",
      });

      expect(apiFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/scanners/results?")
      );
    });
  });

  describe("runIntraday", () => {
    it("should call POST /api/scanners/run with request body", async () => {
      const mockData = {
        results: [
          {
            scanner_name: "momentum",
            symbol: "AAPL",
            score: 85,
            signal: "buy",
            price: 150.25,
            volume: 1000000,
            change_pct: 2.5,
            indicators_fired: ["rsi"],
            matched_at: "2026-04-13T16:00:00Z",
          },
        ],
        run_type: "intraday",
        date: "2026-04-13",
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { runIntraday } = await import("~/lib/scanners-api");
      const result = await runIntraday({
        scanners: ["momentum"],
        timeframe: "15m",
        input_scope: "universe",
      });

      expect(apiFetch).toHaveBeenCalledWith("/api/scanners/run", {
        method: "POST",
        body: JSON.stringify({
          scanners: ["momentum"],
          timeframe: "15m",
          input_scope: "universe",
        }),
      });
      expect(result.run_type).toBe("intraday");
    });

    it("should support watchlist_id as input_scope", async () => {
      const mockData = {
        results: [],
        run_type: "intraday",
        date: "2026-04-13",
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockData);

      const { runIntraday } = await import("~/lib/scanners-api");
      await runIntraday({
        scanners: ["momentum"],
        timeframe: "1h",
        input_scope: 123,
      });

      expect(apiFetch).toHaveBeenCalledWith("/api/scanners/run", {
        method: "POST",
        body: JSON.stringify({
          scanners: ["momentum"],
          timeframe: "1h",
          input_scope: 123,
        }),
      });
    });
  });
});
