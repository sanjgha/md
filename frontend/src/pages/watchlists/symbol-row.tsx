/**
 * SymbolRow — a single stock row in the watchlist panel.
 * Shows: source dot, ticker, last price, change, change%, remove button on hover.
 * Supports keyboard focus indication (distinct from mouse selection).
 */

import { Component } from "solid-js";
import type { QuoteResponse } from "./types";

interface SymbolRowProps {
  quote: QuoteResponse;
  selected: boolean;
  focused: boolean;
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}

function fmt(n: number | null, decimals = 2): string {
  if (n === null) return "—";
  return n.toFixed(decimals);
}

function fmtChange(n: number | null): string {
  if (n === null) return "—";
  return n >= 0 ? `+${n.toFixed(2)}` : `${n.toFixed(2)}`;
}

export const SymbolRow: Component<SymbolRowProps> = (props) => {
  const isPositive = () => props.quote.change !== null && props.quote.change >= 0;
  const changeClass = () =>
    props.quote.change === null ? "neutral" : isPositive() ? "positive" : "negative";

  return (
    <div
      class="symbol-row"
      classList={{ selected: props.selected, focused: props.focused }}
      onClick={() => props.onSelect(props.quote.symbol)}
    >
      <span
        class="source-dot"
        classList={{
          "source-dot--realtime": props.quote.source === "realtime",
          "source-dot--eod": props.quote.source === "eod",
        }}
        title={
          props.quote.source === "realtime"
            ? "Realtime"
            : props.quote.date
              ? `End of day (${props.quote.date})`
              : "End of day"
        }
      />
      <span class="symbol-ticker">{props.quote.symbol}</span>
      <span class="symbol-last">{fmt(props.quote.last)}</span>
      <span class={`symbol-change ${changeClass()}`}>{fmtChange(props.quote.change)}</span>
      <span class={`symbol-change-pct ${changeClass()}`}>
        {props.quote.change_pct !== null ? `${fmtChange(props.quote.change_pct)}%` : "—"}
      </span>
      <button
        class="symbol-remove"
        aria-label={`Remove ${props.quote.symbol}`}
        onClick={(e) => {
          e.stopPropagation();
          props.onRemove(props.quote.symbol);
        }}
      >
        ✕
      </button>
    </div>
  );
};
