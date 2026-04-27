/**
 * Tests for watchlist utility functions
 */

import { describe, it, expect } from "vitest";
import { navigateQuotes } from "./watchlist-utils";
import type { QuoteResponse } from "./types";

describe("navigateQuotes", () => {
  const createQuote = (symbol: string): QuoteResponse => ({
    symbol,
    last: 100.0,
    low: 95.0,
    high: 105.0,
    change: 1.0,
    change_pct: 1.0,
    source: "realtime",
    date: null,
    intraday: [],
  });

  it("returns null for empty quotes array", () => {
    const result = navigateQuotes([], "AAPL", "down");
    expect(result).toBeNull();
  });

  it("returns first symbol when currentSymbol is null", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT"), createQuote("GOOGL")];
    const result = navigateQuotes(quotes, null, "down");
    expect(result).toBe("AAPL");
  });

  it("returns first symbol when currentSymbol is unknown", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT"), createQuote("GOOGL")];
    const result = navigateQuotes(quotes, "UNKNOWN", "down");
    expect(result).toBe("AAPL");
  });

  it("navigates to next symbol on ArrowDown", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT"), createQuote("GOOGL")];
    const result = navigateQuotes(quotes, "AAPL", "down");
    expect(result).toBe("MSFT");
  });

  it("wraps from last to first on ArrowDown", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT"), createQuote("GOOGL")];
    const result = navigateQuotes(quotes, "GOOGL", "down");
    expect(result).toBe("AAPL");
  });

  it("navigates to previous symbol on ArrowUp", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT"), createQuote("GOOGL")];
    const result = navigateQuotes(quotes, "MSFT", "up");
    expect(result).toBe("AAPL");
  });

  it("wraps from first to last on ArrowUp", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT"), createQuote("GOOGL")];
    const result = navigateQuotes(quotes, "AAPL", "up");
    expect(result).toBe("GOOGL");
  });

  it("handles single-item list", () => {
    const quotes = [createQuote("AAPL")];
    const resultDown = navigateQuotes(quotes, "AAPL", "down");
    const resultUp = navigateQuotes(quotes, "AAPL", "up");

    expect(resultDown).toBe("AAPL");
    expect(resultUp).toBe("AAPL");
  });

  it("handles two-item list with wraparound", () => {
    const quotes = [createQuote("AAPL"), createQuote("MSFT")];

    const resultDown = navigateQuotes(quotes, "AAPL", "down");
    expect(resultDown).toBe("MSFT");

    const resultDownWrap = navigateQuotes(quotes, "MSFT", "down");
    expect(resultDownWrap).toBe("AAPL");

    const resultUp = navigateQuotes(quotes, "MSFT", "up");
    expect(resultUp).toBe("AAPL");

    const resultUpWrap = navigateQuotes(quotes, "AAPL", "up");
    expect(resultUpWrap).toBe("MSFT");
  });
});
