import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@solidjs/testing-library";
import { EodTab } from "~/pages/scanners/eod-tab";

vi.mock("~/lib/scanners-api", () => ({
  listScanners: vi.fn().mockResolvedValue([
    { name: "momentum", timeframe: "daily", description: "RSI scan" },
    { name: "price_action", timeframe: "daily", description: "Price action" },
  ]),
  getResults: vi.fn().mockResolvedValue({
    results: [{ scanner_name: "momentum", symbol: "AAPL", score: 8.0, signal: "BUY",
                price: 189.20, volume: 42000000, change_pct: 1.5, indicators_fired: [],
                matched_at: "2026-04-13T16:15:00" }],
    run_type: "eod",
    date: "2026-04-13",
  }),
  getRunDates: vi.fn().mockResolvedValue([
    { date: "2026-04-13", run_type: "eod", time: "16:15" },
  ]),
}));

vi.mock("~/lib/watchlists-api", () => ({
  watchlistsAPI: { create: vi.fn().mockResolvedValue({ id: 1, name: "test" }) },
}));

describe("EodTab", () => {
  it("renders scanner pills from API", async () => {
    render(() => <EodTab />);
    await waitFor(() => expect(screen.getByText("momentum")).toBeTruthy());
    expect(screen.getByText("price_action")).toBeTruthy();
  });

  it("shows Save as Watchlist button when results present", async () => {
    render(() => <EodTab />);
    await waitFor(() => screen.getByText("AAPL"));
    expect(screen.getByText(/save as watchlist/i)).toBeTruthy();
  });
});
