/**
 * CategoryGroup — collapsible watchlist group in the left panel.
 *
 * Owns: expanded state, quote data, add-input visibility, keyboard navigation.
 * Fires: onSymbolSelect(symbol) upward to dashboard.
 * Handles keyboard nav (up/down to navigate, left to delete) when containing the selected symbol.
 */

import {
  Component,
  Show,
  For,
  createSignal,
  onMount,
  createEffect,
  onCleanup,
  untrack,
} from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
import { SymbolRow } from "./symbol-row";
import { navigateQuotes } from "./watchlist-utils";
import type { QuoteResponse, WatchlistSummary } from "./types";

interface CategoryGroupProps {
  watchlist: WatchlistSummary;
  initiallyExpanded: boolean;
  selectedSymbol: string | null;
  refreshSignal: number;
  onSymbolSelect: (symbol: string | null) => void;
  onExpandChange: (watchlistId: number, expanded: boolean) => void;
}

export const CategoryGroup: Component<CategoryGroupProps> = (props) => {
  const [expanded, setExpanded] = createSignal(props.initiallyExpanded);
  const [quotes, setQuotes] = createSignal<QuoteResponse[]>([]);
  const [quotesLoading, setQuotesLoading] = createSignal(false);
  const [quotesError, setQuotesError] = createSignal(false);
  const [loaded, setLoaded] = createSignal(false);

  const [showAddInput, setShowAddInput] = createSignal(false);
  const [addValue, setAddValue] = createSignal("");
  const [addError, setAddError] = createSignal<string | null>(null);
  const [addLoading, setAddLoading] = createSignal(false);

  const [refreshing, setRefreshing] = createSignal(false);
  const [removeError, setRemoveError] = createSignal<string | null>(null);

  async function fetchQuotes() {
    setQuotesLoading(true);
    setQuotesError(false);
    try {
      const data = await watchlistsAPI.getQuotes(props.watchlist.id);
      setQuotes(data);
      setLoaded(true);
    } catch {
      setQuotesError(true);
    } finally {
      setQuotesLoading(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    await fetchQuotes();
    setRefreshing(false);
  }

  function toggleExpand() {
    const next = !expanded();
    setExpanded(next);
    props.onExpandChange(props.watchlist.id, next);
    if (next && !loaded()) {
      fetchQuotes();
    }
  }

  async function handleRemove(symbol: string) {
    setRemoveError(null);  // clear previous error
    const original = quotes();
    const idx = original.findIndex((q) => q.symbol === symbol);
    // Optimistic remove
    setQuotes(original.filter((q) => q.symbol !== symbol));
    // Clear selection if removing the currently selected symbol
    if (props.selectedSymbol === symbol) {
      props.onSymbolSelect(null);
    }
    try {
      await watchlistsAPI.symbols.remove(props.watchlist.id, symbol);
    } catch {
      // Restore at original index on error
      const restored = [...quotes()];
      restored.splice(idx, 0, original[idx]);
      setQuotes(restored);
      setRemoveError(`Failed to remove ${symbol}`);
    }
  }

  onMount(() => {
    if (props.initiallyExpanded) {
      fetchQuotes();
    }

    // Keyboard navigation: only respond when this group contains the selected symbol
    const handleKeyDown = (e: KeyboardEvent) => {
      // Guard: only handle if this group contains the selected symbol
      if (!quotes().some(q => q.symbol === props.selectedSymbol)) return;

      // Only handle arrow keys if not in an input
      if (e.target instanceof HTMLInputElement) return;

      const currentQuotes = quotes();

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const nextSymbol = navigateQuotes(currentQuotes, props.selectedSymbol, "down");
        props.onSymbolSelect(nextSymbol);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const nextSymbol = navigateQuotes(currentQuotes, props.selectedSymbol, "up");
        props.onSymbolSelect(nextSymbol);
      } else if (e.key === "ArrowLeft" && props.selectedSymbol !== null) {
        e.preventDefault();
        const currentSymbol = props.selectedSymbol;
        const currentIndex = currentQuotes.findIndex(q => q.symbol === currentSymbol);

        // Calculate the next symbol BEFORE removing (while currentQuotes is still accurate)
        let nextSymbol: string | null = null;
        if (currentQuotes.length > 1) {
          const nextIndex = currentIndex >= currentQuotes.length - 1 ? currentIndex - 1 : currentIndex;
          nextSymbol = currentQuotes[nextIndex].symbol;
        }

        // Remove the selected symbol
        handleRemove(currentSymbol);

        // Select the pre-calculated next symbol
        props.onSymbolSelect(nextSymbol);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    onCleanup(() => {
      window.removeEventListener("keydown", handleKeyDown);
    });
  });

  // Watch refresh signal and fetch quotes when expanded and loaded.
  // untrack() for expanded/loaded prevents this effect from re-firing when those
  // signals change — it should only fire when the poll signal increments.
  createEffect(() => {
    props.refreshSignal; // Only track the poll signal
    if (untrack(expanded) && untrack(loaded)) {
      fetchQuotes();
    }
  });

  async function handleAdd() {
    const symbol = addValue().trim().toUpperCase();
    if (!symbol) return;
    setAddLoading(true);
    setAddError(null);
    try {
      await watchlistsAPI.symbols.add(props.watchlist.id, symbol);
      setAddValue("");
      setShowAddInput(false);
      await fetchQuotes(); // re-fetch to get price for new symbol
    } catch (err: unknown) {
      const msg: string = err instanceof Error ? err.message : "";
      if (msg.includes("not found")) {
        setAddError(`"${symbol}" not found`);
      } else if (msg.includes("already exists")) {
        setAddError(`"${symbol}" already in this list`);
      } else {
        setAddError("Failed to add — try again");
      }
    } finally {
      setAddLoading(false);
    }
  }

  return (
    <div class="category-group">
      {/* Header */}
      <div class="category-group__header" onClick={toggleExpand}>
        <span class="category-group__chevron">{expanded() ? "▼" : "▶"}</span>
        <span class="category-group__name">{props.watchlist.name}</span>
        <Show when={expanded()}>
          <button
            class="category-group__refresh"
            classList={{ spinning: refreshing() }}
            aria-label="Refresh quotes"
            onClick={(e) => { e.stopPropagation(); handleRefresh(); }}
          >
            ↻
          </button>
          <button
            class="category-group__add-btn"
            aria-label="Add symbol"
            onClick={(e) => { e.stopPropagation(); setShowAddInput(true); setAddError(null); }}
          >
            +
          </button>
        </Show>
      </div>

      {/* Symbol list */}
      <Show when={expanded()}>
        <div class="category-group__symbols">
          <Show when={quotesLoading() && !loaded()}>
            <For each={Array(Math.max(props.watchlist.symbol_count, 1)).fill(0)}>
              {() => <div class="symbol-row symbol-row--skeleton" />}
            </For>
          </Show>

          <Show when={!quotesLoading() || loaded()}>
            <For each={quotes()}>
              {(quote) => (
                <SymbolRow
                  quote={quote}
                  selected={props.selectedSymbol === quote.symbol}
                  onSelect={(sym) => props.onSymbolSelect(sym)}
                  onRemove={handleRemove}
                />
              )}
            </For>
          </Show>

          <Show when={quotesError()}>
            <div class="category-group__error">
              Prices unavailable —{" "}
              <button onClick={handleRefresh}>↻ retry</button>
            </div>
          </Show>

          <Show when={removeError()}>
            <div class="category-group__remove-error">
              {removeError()}
            </div>
          </Show>

          {/* Add symbol input */}
          <Show when={showAddInput()}>
            <div class="category-group__add-row">
              <input
                type="text"
                class="category-group__add-input"
                placeholder="Symbol (e.g. TSLA)"
                value={addValue()}
                onInput={(e) => setAddValue(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAdd();
                  if (e.key === "Escape") { setShowAddInput(false); setAddValue(""); }
                }}
                ref={(el) => setTimeout(() => el?.focus(), 0)}
              />
              <button
                class="category-group__add-confirm"
                disabled={addLoading()}
                onClick={handleAdd}
              >
                Add
              </button>
              <button
                class="category-group__add-cancel"
                onClick={() => { setShowAddInput(false); setAddValue(""); setAddError(null); }}
              >
                ✕
              </button>
            </div>
            <Show when={addError()}>
              <div class="category-group__add-error">{addError()}</div>
            </Show>
          </Show>
        </div>
      </Show>
    </div>
  );
};
