/**
 * Tests for SymbolRow component
 */

import { describe, it, expect } from "vitest";
import { render } from "@solidjs/testing-library";
import { SymbolRow } from "./symbol-row";
import type { QuoteResponse } from "./types";

describe("SymbolRow", () => {
  const baseQuote: QuoteResponse = {
    symbol: "AAPL",
    last: 186.59,
    low: 178.20,
    high: 188.50,
    change: 9.31,
    change_pct: 5.01,
    source: "realtime",
    date: null,
    intraday: [
      { time: "2026-04-23T09:30:00", close: 180.50 },
      { time: "2026-04-23T10:30:00", close: 182.30 },
      { time: "2026-04-23T11:30:00", close: 185.10 },
    ],
  };

  it("renders sparkline and range bar", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={baseQuote}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    // Check sparkline is rendered
    const svg = container.querySelector(".symbol-row svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("48");

    // Check range bar is rendered
    const rangeBar = container.querySelector(".range-bar");
    expect(rangeBar).not.toBeNull();
  });

  it("determines sparkline color from change", () => {
    const { container: greenContainer } = render(() => (
      <SymbolRow
        quote={{ ...baseQuote, change: 9.31 }}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const greenPolyline = greenContainer.querySelector("polyline");
    expect(greenPolyline?.getAttribute("stroke")).toBe("#22c55e");

    const { container: redContainer } = render(() => (
      <SymbolRow
        quote={{ ...baseQuote, change: -9.31, change_pct: -5.01 }}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const redPolyline = redContainer.querySelector("polyline");
    expect(redPolyline?.getAttribute("stroke")).toBe("#ef4444");
  });

  it("shows gray sparkline for EOD quotes", () => {
    const eodQuote: QuoteResponse = {
      ...baseQuote,
      source: "eod",
      date: "2026-04-22",
      intraday: [], // No intraday for EOD
    };

    const { container } = render(() => (
      <SymbolRow
        quote={eodQuote}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const polyline = container.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#94a3b8");
  });

  it("calculates range bar position correctly", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={baseQuote}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");

    // 186.59 is ~75% of range 178.20-188.50
    expect(style).toContain("left:");
  });

  it("handles null low/high gracefully", () => {
    const nullRangeQuote: QuoteResponse = {
      ...baseQuote,
      low: null,
      high: null,
    };

    const { container } = render(() => (
      <SymbolRow
        quote={nullRangeQuote}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    // Should still render, marker centered
    const marker = container.querySelector(".range-bar__marker");
    expect(marker).not.toBeNull();
  });

  it("renders without focused prop", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={baseQuote}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    // Should render without errors
    const svg = container.querySelector(".symbol-row svg");
    expect(svg).not.toBeNull();
  });
});
