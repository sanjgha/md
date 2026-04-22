/**
 * WatchlistPanel — left pane of the watchlist page.
 *
 * Fetches all categories+watchlists on mount.
 * Persists expansion set in localStorage under "watchlist-expanded-ids".
 * Renders one CategoryGroup per watchlist (not per category header).
 * Category names appear as non-interactive section dividers.
 * Supports keyboard navigation: up/down to navigate symbols, left to delete.
 */

import { Component, For, Show, createSignal, onMount, onCleanup } from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
import { CategoryGroup } from "./category-group";
import type { CategoryWatchlists, WatchlistSymbolRef } from "./types";

const LS_KEY = "watchlist-expanded-ids";

function loadExpandedIds(): Set<number> {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as number[]);
  } catch {
    return new Set();
  }
}

function saveExpandedIds(ids: Set<number>) {
  localStorage.setItem(LS_KEY, JSON.stringify([...ids]));
}

interface WatchlistPanelProps {
  selectedSymbol: string | null;
  onSymbolSelect: (symbol: string | null) => void;
}

export const WatchlistPanel: Component<WatchlistPanelProps> = (props) => {
  const [categories, setCategories] = createSignal<CategoryWatchlists[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal(false);
  const [expandedIds, setExpandedIds] = createSignal<Set<number>>(loadExpandedIds());
  const [symbolRefs, setSymbolRefs] = createSignal<WatchlistSymbolRef[]>([]);
  const [focusedSymbol, setFocusedSymbol] = createSignal<string | null>(null);

  onMount(async () => {
    try {
      const data = await watchlistsAPI.list();
      setCategories(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      const refs = symbolRefs();
      if (refs.length === 0) return;

      // Only handle arrow keys if not in an input
      if (e.target instanceof HTMLInputElement) return;

      const currentFocused = focusedSymbol();
      const currentIndex = currentFocused !== null
        ? refs.findIndex(r => r.symbol === currentFocused)
        : -1;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = currentIndex === -1 ? 0 : (currentIndex + 1) % refs.length;
        setFocusedSymbol(refs[next].symbol);
        props.onSymbolSelect(refs[next].symbol);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = currentIndex <= 0 ? refs.length - 1 : currentIndex - 1;
        setFocusedSymbol(refs[prev].symbol);
        props.onSymbolSelect(refs[prev].symbol);
      } else if (e.key === "ArrowLeft" && currentFocused !== null) {
        e.preventDefault();
        const ref = refs[currentIndex];
        ref.onRemove();
        // Move focus to next symbol, or previous if at end, or clear if last one
        if (refs.length > 1) {
          const nextIndex = currentIndex >= refs.length - 1 ? currentIndex - 1 : currentIndex;
          // Note: refs will update after deletion, so we set a fallback
          // The actual focus will be set when new refs are registered
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    onCleanup(() => window.removeEventListener("keydown", handleKeyDown));
  });

  function handleExpandChange(watchlistId: number, expanded: boolean) {
    const next = new Set(expandedIds());
    if (expanded) {
      next.add(watchlistId);
    } else {
      next.delete(watchlistId);
    }
    setExpandedIds(next);
    saveExpandedIds(next);
  }

  function handleRegisterSymbolRefs(refs: WatchlistSymbolRef[]) {
    setSymbolRefs(refs);
    // Preserve focused symbol if it still exists, otherwise set to first or null
    const current = focusedSymbol();
    if (refs.length === 0) {
      setFocusedSymbol(null);
    } else if (current !== null && refs.some(r => r.symbol === current)) {
      // Current focused symbol still exists, keep it
      return;
    } else {
      // Try to focus first symbol if we had something focused before
      setFocusedSymbol(refs[0].symbol);
      props.onSymbolSelect(refs[0].symbol);
    }
  }

  function handleSymbolSelect(symbol: string | null) {
    // Sync focus with selection when user clicks
    if (symbol !== null) {
      setFocusedSymbol(symbol);
    }
    props.onSymbolSelect(symbol);
  }

  return (
    <div class="watchlist-panel">
      <Show when={loading()}>
        <div class="watchlist-panel__loading">Loading…</div>
      </Show>

      <Show when={error()}>
        <div class="watchlist-panel__error">Failed to load watchlists</div>
      </Show>

      <Show when={!loading() && !error()}>
        <For each={categories()}>
          {(group) => (
            <>
              <div class="watchlist-panel__category-label">{group.category.name}</div>
              <For each={group.watchlists}>
                {(wl) => (
                  <CategoryGroup
                    watchlist={wl}
                    initiallyExpanded={expandedIds().has(wl.id)}
                    selectedSymbol={props.selectedSymbol}
                    focusedSymbol={focusedSymbol()}
                    onSymbolSelect={handleSymbolSelect}
                    onExpandChange={handleExpandChange}
                    onRegisterSymbolRefs={handleRegisterSymbolRefs}
                  />
                )}
              </For>
            </>
          )}
        </For>

        <Show when={categories().length === 0}>
          <div class="watchlist-panel__empty">No watchlists yet.</div>
        </Show>
      </Show>
    </div>
  );
};
