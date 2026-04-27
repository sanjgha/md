/**
 * Tests for watchlist utility functions
 */

import { describe, it, expect } from "vitest";
import { navigateQuotes, sortQuotes } from "./watchlist-utils";
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

describe("sortQuotes", () => {
  const createQuote = (
    symbol: string,
    last: number | null,
    change_pct: number | null,
  ): QuoteResponse => ({
    symbol,
    last,
    low: 95.0,
    high: 105.0,
    change: null,
    change_pct,
    source: "realtime",
    date: null,
    intraday: [],
  });

  it("returns original order when col is null", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, null, "asc");
    expect(result).toEqual(quotes);
    // Verify it's a new array
    expect(result).not.toBe(quotes);
  });

  it("sorts by ticker ascending (alphabetical)", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "ticker", "asc");
    expect(result[0].symbol).toBe("AAPL");
    expect(result[1].symbol).toBe("GOOGL");
    expect(result[2].symbol).toBe("MSFT");
  });

  it("sorts by ticker descending (reverse alphabetical)", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "ticker", "desc");
    expect(result[0].symbol).toBe("MSFT");
    expect(result[1].symbol).toBe("GOOGL");
    expect(result[2].symbol).toBe("AAPL");
  });

  it("sorts by last price ascending", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "last", "asc");
    expect(result[0].symbol).toBe("AAPL");
    expect(result[1].symbol).toBe("MSFT");
    expect(result[2].symbol).toBe("GOOGL");
  });

  it("sorts by last price descending", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "last", "desc");
    expect(result[0].symbol).toBe("GOOGL");
    expect(result[1].symbol).toBe("MSFT");
    expect(result[2].symbol).toBe("AAPL");
  });

  it("sorts by chg_pct ascending", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, -1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "chg_pct", "asc");
    expect(result[0].symbol).toBe("AAPL"); // -1.5%
    expect(result[1].symbol).toBe("MSFT"); // 2.5%
    expect(result[2].symbol).toBe("GOOGL"); // 3.5%
  });

  it("sorts by chg_pct descending", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, -1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "chg_pct", "desc");
    expect(result[0].symbol).toBe("GOOGL"); // 3.5%
    expect(result[1].symbol).toBe("MSFT"); // 2.5%
    expect(result[2].symbol).toBe("AAPL"); // -1.5%
  });

  it("uses -Infinity for null last values (ascending)", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", null, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "last", "asc");
    expect(result[0].symbol).toBe("AAPL"); // null -> -Infinity
    expect(result[1].symbol).toBe("MSFT");
    expect(result[2].symbol).toBe("GOOGL");
  });

  it("uses -Infinity for null chg_pct values (ascending)", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, null),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "chg_pct", "asc");
    expect(result[0].symbol).toBe("AAPL"); // null -> -Infinity
    expect(result[1].symbol).toBe("MSFT");
    expect(result[2].symbol).toBe("GOOGL");
  });

  it("uses -Infinity for null last values (descending)", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", null, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "last", "desc");
    expect(result[0].symbol).toBe("GOOGL");
    expect(result[1].symbol).toBe("MSFT");
    expect(result[2].symbol).toBe("AAPL"); // null -> -Infinity
  });

  it("uses -Infinity for null chg_pct values (descending)", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, null),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const result = sortQuotes(quotes, "chg_pct", "desc");
    expect(result[0].symbol).toBe("GOOGL");
    expect(result[1].symbol).toBe("MSFT");
    expect(result[2].symbol).toBe("AAPL"); // null -> -Infinity
  });

  it("handles empty array", () => {
    const result = sortQuotes([], "ticker", "asc");
    expect(result).toEqual([]);
  });

  it("does not mutate original array", () => {
    const quotes = [
      createQuote("MSFT", 300.0, 2.5),
      createQuote("AAPL", 150.0, 1.5),
      createQuote("GOOGL", 2500.0, 3.5),
    ];
    const originalOrder = [...quotes];
    sortQuotes(quotes, "ticker", "asc");
    expect(quotes).toEqual(originalOrder);
  });
});
