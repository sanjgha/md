/**
 * Edit Watchlist Modal Component
 *
 * Modal form for editing existing watchlists
 */

import { Show, For, createSignal, onMount, JSX } from 'solid-js';
import { watchlistsAPI } from '~/lib/watchlists-api';
import type { Category, Watchlist } from '~/pages/watchlists/types';

interface ShowEditWatchlistModalProps {
  isOpen: boolean;
  watchlistId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export function ShowEditWatchlistModal(props: ShowEditWatchlistModalProps) {
  const [categories, setCategories] = createSignal<Category[]>([]);
  const [watchlist, setWatchlist] = createSignal<Watchlist | null>(null);
  const [loading, setLoading] = createSignal(false);
  const [loadingData, setLoadingData] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);
  const [name, setName] = createSignal('');
  const [categoryId, setCategoryId] = createSignal<number | null>(null);
  const [description, setDescription] = createSignal('');
  const [nameError, setNameError] = createSignal<string | null>(null);

  onMount(async () => {
    try {
      const [watchlistData, categoriesData] = await Promise.all([
        watchlistsAPI.get(props.watchlistId),
        watchlistsAPI.categories.list(),
      ]);

      setWatchlist(watchlistData);
      setCategories(categoriesData);

      // Pre-fill form
      setName(watchlistData.name);
      setCategoryId(watchlistData.category_id);
      setDescription(watchlistData.description || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlist');
    } finally {
      setLoadingData(false);
    }
  });

  const handleSubmit = async (e: Event) => {
    e.preventDefault();

    // Validate
    if (!name().trim()) {
      setNameError('Name is required');
      return;
    }

    setNameError(null);
    setLoading(true);
    setError(null);

    try {
      await watchlistsAPI.update(props.watchlistId, {
        name: name().trim(),
        category_id: categoryId() || undefined,
        description: description().trim() || undefined,
      });

      props.onSuccess();
      props.onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update watchlist');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    // Reset form
    setName('');
    setCategoryId(null);
    setDescription('');
    setNameError(null);
    setError(null);
    props.onClose();
  };

  return (
    <Show when={props.isOpen}>
      <div class="modal-backdrop" onClick={handleClose}>
        <div class="modal-content" onClick={(e) => e.stopPropagation()}>
          <header class="modal-header">
            <h2>Edit Watchlist</h2>
            <button
              class="close-button"
              aria-label="Close"
              onClick={handleClose}
            >
              ×
            </button>
          </header>

          <Show when={loadingData()}>
            <div class="loading">Loading watchlist...</div>
          </Show>

          <Show when={!loadingData()}>
            <form onSubmit={handleSubmit}>
              <div class="form-group">
                <label for="edit-watchlist-name">Name *</label>
                <input
                  id="edit-watchlist-name"
                  type="text"
                  value={name()}
                  onInput={(e) => {
                    setName(e.currentTarget.value);
                    setNameError(null);
                  }}
                  aria-invalid={nameError() !== null}
                  disabled={loading()}
                />
                <Show when={nameError()}>
                  <span class="error-message">{nameError()}</span>
                </Show>
              </div>

              <div class="form-group">
                <label for="edit-watchlist-category">Category</label>
                <select
                  id="edit-watchlist-category"
                  value={categoryId() ?? ''}
                  onChange={(e) => setCategoryId(e.currentTarget.value ? parseInt(e.currentTarget.value) : null)}
                  disabled={loading()}
                >
                  <option value="">None</option>
                  <For each={categories()}>
                    {(category) => (
                      <option value={category.id}>
                        {category.icon} {category.name}
                      </option>
                    )}
                  </For>
                </select>
              </div>

              <div class="form-group">
                <label for="edit-watchlist-description">Description</label>
                <textarea
                  id="edit-watchlist-description"
                  value={description()}
                  onInput={(e) => setDescription(e.currentTarget.value)}
                  disabled={loading()}
                  rows={3}
                />
              </div>

              <Show when={error()}>
                <div class="error-banner">{error()}</div>
              </Show>

              <div class="modal-actions">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={loading()}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={loading()}
                >
                  <Show when={loading()}>Saving...</Show>
                  <Show when={!loading()}>Save</Show>
                </button>
              </div>
            </form>
          </Show>
        </div>
      </div>
    </Show>
  );
}
