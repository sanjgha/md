import { render, fireEvent, waitFor } from "@solidjs/testing-library";
import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { ChartPanel } from "./chart-panel";
import type { CandleResponse } from "../../lib/stocks-api";

// Mock lightweight-charts — WebGL unavailable in jsdom
vi.mock("lightweight-charts", () => {
  const mockSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
  };
  const mockPriceScale = {
    applyOptions: vi.fn(),
  };
  const mockChart = {
    addSeries: vi.fn(() => mockSeries),
    removeSeries: vi.fn(),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    priceScale: vi.fn(() => mockPriceScale),
  };
  return {
    createChart: vi.fn(() => mockChart),
    CandlestickSeries: "CandlestickSeries",
    AreaSeries: "AreaSeries",
    HistogramSeries: "HistogramSeries",
  };
});

// Mock stocksAPI
vi.mock("../../lib/stocks-api", () => ({
  stocksAPI: {
    getCandles: vi.fn(),
  },
}));

// Mock polling manager
vi.mock("~/lib/polling-manager", () => ({
  pollingManager: {
    start: vi.fn(),
    stop: vi.fn(),
    isPolling: vi.fn(() => false),
  },
}));

// Mock market hours
vi.mock("~/lib/market-hours", () => ({
  isMarketOpen: vi.fn(() => false),
}));

// Import after mocks
import { stocksAPI } from "../../lib/stocks-api";

// Polyfill ResizeObserver — not in jsdom
beforeAll(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  );
});

const mockCandles: CandleResponse[] = [
  { time: "2024-01-02", open: 100, high: 110, low: 95, close: 105, volume: 1000000 },
  { time: "2024-01-03", open: 105, high: 115, low: 100, close: 108, volume: 1200000 },
  { time: "2024-01-04", open: 108, high: 120, low: 105, close: 118, volume: 900000 },
];

const mockQuote = { last: 118.5, change: 2.3, change_pct: 1.98 };

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(stocksAPI.getCandles).mockResolvedValue(mockCandles);
});

describe("ChartPanel", () => {
  it("renders symbol name in header", async () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    expect(getByText("AAPL")).toBeInTheDocument();
  });

  it("renders last price from quote", async () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    expect(getByText("118.50")).toBeInTheDocument();
  });

  it("renders positive change with + prefix", async () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    const changeEl = getByText("+2.30 (1.98%)");
    expect(changeEl.className).toContain("positive");
  });

  it("renders negative change without + prefix", async () => {
    const negQuote = { last: 95.0, change: -3.5, change_pct: -3.55 };
    const { getByText } = render(() => (
      <ChartPanel
        symbol="TSLA"
        quote={negQuote}
        selectedSymbol={() => "TSLA"}
      />
    ));
    const changeEl = getByText("-3.50 (-3.55%)");
    expect(changeEl.className).toContain("negative");
  });

  it("renders all timeframe buttons", () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    expect(getByText("5m")).toBeInTheDocument();
    expect(getByText("15m")).toBeInTheDocument();
    expect(getByText("1h")).toBeInTheDocument();
    expect(getByText("D")).toBeInTheDocument();
  });

  it("shows daily range sub-buttons when D resolution is active", () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
        defaultResolution="D"
      />
    ));
    expect(getByText("1M")).toBeInTheDocument();
    expect(getByText("3M")).toBeInTheDocument();
    expect(getByText("1Y")).toBeInTheDocument();
  });

  it("hides daily range sub-buttons when intraday resolution is active", async () => {
    const { getByText, queryByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
        defaultResolution="D"
      />
    ));
    fireEvent.click(getByText("1h"));
    expect(queryByText("1M")).not.toBeInTheDocument();
    expect(queryByText("3M")).not.toBeInTheDocument();
  });

  it("switches resolution on button click", async () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    const btn = getByText("5m");
    fireEvent.click(btn);
    expect(btn.className).toContain("active");
  });

  it("toggles chart type button label", () => {
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    const toggleBtn = getByText("Candle");
    fireEvent.click(toggleBtn);
    expect(getByText("Area")).toBeInTheDocument();
  });

  it("shows loading skeleton while fetching", async () => {
    vi.mocked(stocksAPI.getCandles).mockReturnValue(new Promise(() => {})); // never resolves
    const { getByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    expect(getByText("Loading chart...")).toBeInTheDocument();
  });

  it("shows error message and retry button on fetch failure", async () => {
    vi.mocked(stocksAPI.getCandles).mockRejectedValue(new Error("Network error"));
    const { findByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    expect(await findByText("Network error")).toBeInTheDocument();
    expect(await findByText("↻ Retry")).toBeInTheDocument();
  });

  it("shows stats bar after candles load", async () => {
    const { findByText } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));
    // stats bar shows O (open of first candle)
    expect(await findByText(/O 100\.00/)).toBeInTheDocument();
  });

  it("calls getCandles with correct symbol on mount", async () => {
    render(() => (
      <ChartPanel
        symbol="MSFT"
        quote={mockQuote}
        selectedSymbol={() => "MSFT"}
      />
    ));
    await waitFor(() => {
      expect(stocksAPI.getCandles).toHaveBeenCalledWith(
        "MSFT",
        expect.any(String),
        expect.any(String),
        expect.any(String)
      );
    });
  });
});
