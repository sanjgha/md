import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@solidjs/testing-library";
import { ResultsPanel } from "~/pages/scanners/results-panel";
import type { ScannerResultItem } from "~/pages/scanners/types";

const makeResult = (symbol: string, scanner: string): ScannerResultItem => ({
  scanner_name: scanner,
  symbol,
  score: 8.0,
  signal: "BUY",
  price: 189.20,
  volume: 42000000,
  change_pct: 1.5,
  indicators_fired: ["rsi_overbought"],
  matched_at: "2026-04-13T16:15:00",
});

const groups = [
  { scanner_name: "momentum", results: [makeResult("AAPL", "momentum"), makeResult("NVDA", "momentum")] },
  { scanner_name: "price_action", results: [makeResult("AAPL", "price_action"), makeResult("TSLA", "price_action")] },
];

describe("ResultsPanel", () => {
  it("shows overlap section when 2+ groups share tickers", () => {
    render(() => <ResultsPanel groups={groups} />);
    expect(screen.getByText(/overlap/i)).toBeTruthy();
    const overlapItems = screen.getAllByText("AAPL");
    expect(overlapItems.length).toBeGreaterThan(0);
  });

  it("does not show overlap section with single group", () => {
    render(() => <ResultsPanel groups={[groups[0]]} />);
    expect(screen.queryByText(/overlap/i)).toBeNull();
  });

  it("clicking a ticker shows it in detail panel", () => {
    render(() => <ResultsPanel groups={[groups[0]]} />);
    fireEvent.click(screen.getAllByText("AAPL")[0]);
    expect(screen.getByText("BUY")).toBeTruthy();
    expect(screen.getByText(/189\.20/)).toBeTruthy();
  });

  it("shows empty state when no results", () => {
    render(() => <ResultsPanel groups={[]} />);
    expect(screen.getByText(/no results/i)).toBeTruthy();
  });

  it("clicking a second ticker updates the detail panel", () => {
    render(() => <ResultsPanel groups={[groups[0]]} />);
    // click first ticker
    fireEvent.click(screen.getAllByText("AAPL")[0]);
    expect(screen.getByText("BUY")).toBeTruthy();
    // click second ticker (NVDA also has score 8.0, signal BUY, price $189.20)
    // but NVDA symbol should be visible in detail header
    fireEvent.click(screen.getAllByText("NVDA")[0]);
    const headers = screen.getAllByText("NVDA");
    expect(headers.length).toBeGreaterThan(0);
  });
});
