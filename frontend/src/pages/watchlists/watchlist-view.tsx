/**
 * Watchlist Split-View Component
 *
 * Displays watchlist with stock list on left and chart pane on right
 */

import { Component, Show, For, createSignal, onMount } from 'solid-js';
import { useParams } from '@solidjs/router';
import { watchlistsAPI } from '~/lib/watchlists-api';
import type { Watchlist, WatchlistSymbol } from '~/pages/watchlists/types';

export function ShowWatchlistView() {
  const params = useParams();
  const [watchlist, setWatchlist] = createSignal<Watchlist | null>(null);
  const [symbols, setSymbols] = createSignal<WatchlistSymbol[]>([]);
  const [selectedSymbol, setSelectedSymbol] = createSignal<WatchlistSymbol | null>(null);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);

  onMount(async () => {
    try {
      const id = parseInt(params.id as string);
      const [watchlistData, symbolsData] = await Promise.all([
        watchlistsAPI.get(id),
        watchlistsAPI.symbols.list(id),
      ]);

      setWatchlist(watchlistData);
      setSymbols(symbolsData.symbols || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  });

  return (
    <div class="watchlist-view">
      <Show when={loading()}>
        <div class="loading">Loading...</div>
      </Show>

      <Show when={error()}>
        <div class="error">Failed to load watchlist. Please try again.</div>
      </Show>

      <Show when={!loading() && !error() && watchlist()}>
        <header class="watchlist-header">
          <h1>{watchlist()!.name}</h1>
          <Show when={watchlist()!.description}>
            <p class="description">{watchlist()!.description}</p>
          </Show>
          <Show when={watchlist()!.is_auto_generated}>
            <span class="badge">Auto-generated</span>
          </Show>
        </header>

        <Show when={symbols().length === 0}>
          <div class="empty-state">
            <p>No symbols in this watchlist.</p>
          </div>
        </Show>

        <Show when={symbols().length > 0}>
          <div class="split-view">
            <div class="stock-list-pane">
              <For each={symbols()}>
                {(symbol) => (
                  <div
                    class="stock-item"
                    classList={{ selected: selectedSymbol()?.id === symbol.id }}
                    onClick={() => setSelectedSymbol(symbol)}
                  >
                    <div class="symbol-info">
                      <span class="symbol">{symbol.symbol}</span>
                      <Show when={symbol.name}>
                        <span class="stock-name">{symbol.name}</span>
                      </Show>
                    </div>
                    <Show when={symbol.notes}>
                      <span class="notes">{symbol.notes}</span>
                    </Show>
                  </div>
                )}
              </For>
            </div>

            <div class="chart-pane">
              <Show when={selectedSymbol()}>
                <div class="chart-placeholder">
                  <h2>{selectedSymbol()!.symbol}</h2>
                  <p>Chart will appear here when charting is implemented</p>
                  <p class="chart-note">Charting sub-project (Phase 6)</p>
                </div>
              </Show>
              <Show when={!selectedSymbol()}>
                <div class="chart-placeholder empty">
                  <p>Select a stock to view chart</p>
                </div>
              </Show>
            </div>
          </div>
        </Show>
      </Show>
    </div>
  );
}
