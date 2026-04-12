/**
 * Create Watchlist Modal Component
 *
 * Modal form for creating new watchlists with validation
 */

import { Show, For, createSignal, onMount, JSX } from 'solid-js';
import { watchlistsAPI } from '~/lib/watchlists-api';
import type { Category } from '~/pages/watchlists/types';

interface ShowCreateWatchlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function ShowCreateWatchlistModal(props: ShowCreateWatchlistModalProps) {
  const [categories, setCategories] = createSignal<Category[]>([]);
  const [loading, setLoading] = createSignal(false);
  const [loadingCategories, setLoadingCategories] = createSignal(true);
  const [error, setError] = createSignal<string | null>(null);
  const [name, setName] = createSignal('');
  const [categoryId, setCategoryId] = createSignal<number | null>(null);
  const [description, setDescription] = createSignal('');
  const [nameError, setNameError] = createSignal<string | null>(null);

  onMount(async () => {
    try {
      const cats = await watchlistsAPI.categories.list();
      setCategories(cats);
    } catch (err) {
      console.error('Failed to load categories:', err);
    } finally {
      setLoadingCategories(false);
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
      await watchlistsAPI.create({
        name: name().trim(),
        category_id: categoryId() || undefined,
        description: description().trim() || undefined,
      });

      // Reset form
      setName('');
      setCategoryId(null);
      setDescription('');

      props.onSuccess();
      props.onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create watchlist');
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
            <h2>Create Watchlist</h2>
            <button
              class="close-button"
              aria-label="Close"
              onClick={handleClose}
            >
              ×
            </button>
          </header>

          <Show when={loadingCategories()}>
            <div class="loading">Loading categories...</div>
          </Show>

          <Show when={!loadingCategories()}>
            <form onSubmit={handleSubmit}>
              <div class="form-group">
                <label for="watchlist-name">Name *</label>
                <input
                  id="watchlist-name"
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
                <label for="watchlist-category">Category</label>
                <select
                  id="watchlist-category"
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
                <label for="watchlist-description">Description</label>
                <textarea
                  id="watchlist-description"
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
                  disabled={loading() || loadingCategories()}
                >
                  <Show when={loading()}>Creating...</Show>
                  <Show when={!loading()}>Create</Show>
                </button>
              </div>
            </form>
          </Show>
        </div>
      </div>
    </Show>
  );
}
