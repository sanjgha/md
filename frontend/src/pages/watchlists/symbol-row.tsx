/**
 * SymbolRow — a single stock row in the watchlist panel.
 *
 * Shows: source dot, ticker, sparkline (trend), range bar (position),
 * last price, change%, remove button on hover.
 * Supports keyboard focus indication (distinct from mouse selection).
 */

import { Component } from "solid-js";
import { Sparkline } from "./sparkline";
import { RangeBar } from "./range-bar";
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

function getSparklineColor(quote: QuoteResponse): "green" | "red" | "gray" {
  if (quote.source === "eod" || quote.intraday.length === 0) {
    return "gray";
  }
  return quote.change !== null && quote.change >= 0 ? "green" : "red";
}

export const SymbolRow: Component<SymbolRowProps> = (props) => {
  const isPositive = () => props.quote.change !== null && props.quote.change >= 0;
  const changeClass = () =>
    props.quote.change === null ? "neutral" : isPositive() ? "positive" : "negative";

  const sparklineColor = () => getSparklineColor(props.quote);

  return (
    <div
      class="symbol-row"
      classList={{ selected: props.selected, focused: props.focused }}
      onClick={() => props.onSelect(props.quote.symbol)}
    >
      {/* Source dot */}
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

      {/* Ticker */}
      <span class="symbol-ticker">{props.quote.symbol}</span>

      {/* Sparkline */}
      <div class="symbol-sparkline">
        <Sparkline
          data={props.quote.intraday}
          color={sparklineColor()}
          width={48}
          height={16}
        />
      </div>

      {/* Range bar */}
      <div class="symbol-range">
        <RangeBar
          low={props.quote.low}
          high={props.quote.high}
          current={props.quote.last ?? 0}
          width={32}
          height={14}
        />
      </div>

      {/* Last price */}
      <span class="symbol-last">{fmt(props.quote.last)}</span>

      {/* Change percent */}
      <span class={`symbol-change ${changeClass()}`}>
        {props.quote.change_pct !== null ? `${fmtChange(props.quote.change_pct)}%` : "—"}
      </span>

      {/* Remove button */}
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
