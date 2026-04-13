import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@solidjs/testing-library";
import { IntradayTab } from "~/pages/scanners/intraday-tab";

vi.mock("~/lib/scanners-api", () => ({
  listScanners: vi.fn().mockResolvedValue([
    { name: "momentum", timeframe: "daily", description: "RSI scan" },
  ]),
  runIntraday: vi.fn().mockResolvedValue({
    results: [{ scanner_name: "momentum", symbol: "TSLA", score: null, signal: "BUY",
                price: 173.0, volume: 5000000, change_pct: null, indicators_fired: [],
                matched_at: "2026-04-13T14:30:00" }],
    run_type: "intraday",
    date: "2026-04-13",
  }),
}));

vi.mock("~/lib/watchlists-api", () => ({
  watchlistsAPI: {
    list: vi.fn().mockResolvedValue({ categories: [] }),
    create: vi.fn().mockResolvedValue({ id: 1, name: "test" }),
  },
}));

describe("IntradayTab", () => {
  it("renders Run button", async () => {
    render(() => <IntradayTab />);
    await waitFor(() => expect(screen.getByText(/^Run$/)).toBeTruthy());
  });

  it("shows results after clicking Run", async () => {
    render(() => <IntradayTab />);
    await waitFor(() => screen.getByText(/^Run$/));
    fireEvent.click(screen.getByText(/^Run$/));
    await waitFor(() => expect(screen.getByText("TSLA")).toBeTruthy());
  });

  it("Save as Watchlist only appears after run returns results", async () => {
    render(() => <IntradayTab />);
    expect(screen.queryByText(/save as watchlist/i)).toBeNull();
    fireEvent.click(screen.getByText(/^Run$/));
    await waitFor(() => screen.getByText("TSLA"));
    expect(screen.getByText(/save as watchlist/i)).toBeTruthy();
  });
});
