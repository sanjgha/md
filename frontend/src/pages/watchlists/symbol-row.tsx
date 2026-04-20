/**
 * SymbolRow — a single stock row in the watchlist panel.
 * Shows: source dot, ticker, last price, change, change%, remove button on hover.
 */

import { Component, createResource, Show } from "solid-js";
import type { QuoteResponse } from "./types";
import { optionsAPI, type IVRData, type RegimeData } from "../../lib/options-api";

interface SymbolRowProps {
  quote: QuoteResponse;
  selected: boolean;
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

  const [ivr] = createResource<IVRData | null, string>(
    () => props.quote.symbol,
    async (sym: string): Promise<IVRData | null> => {
      try {
        return await optionsAPI.getIVR(sym);
      } catch {
        return null;
      }
    }
  );

  const [regime] = createResource<RegimeData | null, string>(
    () => props.quote.symbol,
    async (sym: string): Promise<RegimeData | null> => {
      try {
        return await optionsAPI.getRegime(sym);
      } catch {
        return null;
      }
    }
  );

  function ivrColor(val: number): string {
    if (val < 30) return "bg-green-100 text-green-800";
    if (val <= 70) return "bg-amber-100 text-amber-800";
    return "bg-red-100 text-red-800";
  }

  function regimeLabel(r: RegimeData): string {
    if (r.regime === "trending") {
      return r.direction === "bullish" ? "Trending ↑" : "Trending ↓";
    }
    if (r.regime === "ranging") return "Ranging";
    return "Transitional";
  }

  function regimeClass(r: RegimeData): string {
    if (r.regime === "trending" && r.direction === "bullish") return "bg-green-100 text-green-800";
    if (r.regime === "trending") return "bg-red-100 text-red-800";
    if (r.regime === "ranging") return "bg-gray-100 text-gray-700";
    return "bg-amber-100 text-amber-800";
  }

  return (
    <div
      class="symbol-row"
      classList={{ selected: props.selected }}
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
      <Show
        when={ivr()}
        fallback={<span class="symbol-ivr text-xs text-gray-400">—</span>}
      >
        {(data) => (
          <span
            class={`symbol-ivr text-xs font-medium px-1.5 py-0.5 rounded ${ivrColor(data().ivr)}`}
            title="Implied Volatility Rank — low = cheap premium, high = expensive"
          >
            IVR {Math.round(data().ivr)}
          </span>
        )}
      </Show>
      <Show when={regime()}>
        {(r) => (
          <span
            class={`symbol-regime text-xs font-medium px-1.5 py-0.5 rounded ${regimeClass(r())}`}
            title={`ADX ${r().adx.toFixed(1)} | ATR% ${(r().atr_pct * 100).toFixed(2)}%`}
          >
            {regimeLabel(r())}
          </span>
        )}
      </Show>
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
