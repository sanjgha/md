/**
 * WatchlistPanel — left pane of the watchlist page.
 *
 * Fetches all categories+watchlists on mount.
 * Persists expansion set in localStorage under "watchlist-expanded-ids".
 * Renders one CategoryGroup per watchlist (not per category header).
 * Category names appear as non-interactive section dividers.
 */

import { Component, For, Show, createSignal, onMount } from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
import { CategoryGroup } from "./category-group";
import type { CategoryWatchlists } from "./types";

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

  onMount(async () => {
    try {
      const data = await watchlistsAPI.list();
      setCategories(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
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
                    onSymbolSelect={props.onSymbolSelect}
                    onExpandChange={handleExpandChange}
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
