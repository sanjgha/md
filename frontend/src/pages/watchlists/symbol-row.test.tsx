import { render, fireEvent } from "@solidjs/testing-library";
import { describe, it, expect, vi } from "vitest";
import { SymbolRow } from "./symbol-row";
import type { QuoteResponse } from "./types";

const realtimeQuote: QuoteResponse = {
  symbol: "AAPL",
  last: 186.59,
  change: 9.31,
  change_pct: 5.25,
  source: "realtime",
  date: null,
};

const eodQuote: QuoteResponse = {
  symbol: "GSAT",
  last: 79.85,
  change: -0.04,
  change_pct: -0.05,
  source: "eod",
  date: "2026-04-15",
};

describe("SymbolRow", () => {
  it("renders symbol ticker", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(getByText("AAPL")).toBeInTheDocument();
  });

  it("renders last price", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(getByText("186.59")).toBeInTheDocument();
  });

  it("renders positive change in green", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    const changeEl = getByText("+9.31");
    expect(changeEl.className).toContain("positive");
  });

  it("renders negative change in red", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={eodQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    const changeEl = getByText("-0.04");
    expect(changeEl.className).toContain("negative");
  });

  it("calls onSelect when row is clicked", () => {
    const onSelect = vi.fn();
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={onSelect}
        onRemove={vi.fn()}
      />
    ));
    fireEvent.click(getByText("AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("calls onRemove when remove button is clicked", () => {
    const onRemove = vi.fn();
    const { getByRole } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={onRemove}
      />
    ));
    fireEvent.click(getByRole("button", { name: /remove aapl/i }));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
  });

  it("renders — for null change", () => {
    const nullQuote: QuoteResponse = { ...eodQuote, change: null, change_pct: null };
    const { getAllByText } = render(() => (
      <SymbolRow
        quote={nullQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("adds selected class when selected=true", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={true}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(container.firstChild).toHaveClass("selected");
  });
});
