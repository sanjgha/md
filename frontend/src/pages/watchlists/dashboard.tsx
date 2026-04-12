/**
 * Watchlist Dashboard Component
 *
 * Displays all watchlists grouped by category with symbol counts
 */

import { Component, Show, For, createSignal, onMount } from 'solid-js';
import { watchlistsAPI } from '~/lib/watchlists-api';
import { ShowCreateWatchlistModal } from './create-modal';
import type { CategoryWatchlists } from '~/pages/watchlists/types';

export function ShowWatchlistsDashboard() {
  const [categories, setCategories] = createSignal<CategoryWatchlists[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);
  const [showCreateModal, setShowCreateModal] = createSignal(false);

  onMount(async () => {
    try {
      const response = await watchlistsAPI.list();
      setCategories(response.categories);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlists');
    } finally {
      setLoading(false);
    }
  });

  const handleCreateSuccess = () => {
    // Reload the watchlists
    watchlistsAPI.list().then((response) => {
      setCategories(response.categories);
    });
  };

  return (
    <div class="watchlist-dashboard">
      <ShowCreateWatchlistModal
        isOpen={showCreateModal()}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCreateSuccess}
      />

      <header class="dashboard-header">
        <h1>Watchlists</h1>
        <button onClick={() => setShowCreateModal(true)}>
          + New Watchlist
        </button>
      </header>

      <Show when={loading()}>
        <div class="loading">Loading...</div>
      </Show>

      <Show when={error()}>
        <div class="error">Failed to load watchlists. Please try again.</div>
      </Show>

      <Show when={!loading() && !error() && categories().length === 0}>
        <div class="empty-state">
          <h2>No watchlists yet</h2>
          <p>Create your first watchlist to get started tracking stocks.</p>
        </div>
      </Show>

      <Show when={!loading() && !error() && categories().length > 0}>
        <For each={categories()}>
          {(category) => (
            <section class="category-section">
              <h2 class="category-header">
                <Show when={category.category_icon}>
                  <span class="category-icon">{category.category_icon}</span>
                </Show>
                {category.category_name}
              </h2>
              <div class="watchlist-grid">
                <For each={category.watchlists}>
                  {(watchlist) => (
                    <div class="watchlist-card">
                      <h3>{watchlist.name}</h3>
                      <Show when={watchlist.description}>
                        <p class="description">{watchlist.description}</p>
                      </Show>
                      <p class="symbol-count">{watchlist.symbol_count} stocks</p>
                      <Show when={watchlist.is_auto_generated}>
                        <span class="badge">Auto-generated</span>
                      </Show>
                    </div>
                  )}
                </For>
              </div>
            </section>
          )}
        </For>
      </Show>
    </div>
  );
}
