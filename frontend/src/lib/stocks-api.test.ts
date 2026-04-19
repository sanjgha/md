import { describe, it, expect, vi, beforeEach } from "vitest";
import { stocksAPI } from "./stocks-api";

describe("stocksAPI", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("getCandles constructs correct query params", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    stocksAPI.getCandles("AAPL", "5m", "2026-04-16", "2026-04-17");

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/stocks/AAPL/candles?resolution=5m&from=2026-04-16&to=2026-04-17",
      {
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
  });

  it("getCandles surfaces 404 errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "Stock not found: AAPL" }),
    } as Response);

    await expect(stocksAPI.getCandles("AAPL", "D", "2026-04-16", "2026-04-17"))
      .rejects.toThrow("API error 404: Stock not found: AAPL");
  });

  it("getCandles returns parsed candle data", async () => {
    const mockCandles = [
      {
        time: "2026-04-16T09:30:00",
        open: 180.2,
        high: 188.4,
        low: 179.8,
        close: 186.59,
        volume: 52300000,
      },
    ];

    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => mockCandles,
    } as Response);

    const result = await stocksAPI.getCandles("AAPL", "5m", "2026-04-16", "2026-04-17");

    expect(result).toEqual(mockCandles);
  });
});
