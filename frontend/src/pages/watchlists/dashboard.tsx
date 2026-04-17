/**
 * Watchlist Dashboard — route shell for /watchlists.
 *
 * Split layout: WatchlistPanel (left 260px) | detail pane (right, flex).
 * Owns selectedSymbol; passes it down to panel and up from panel.
 * Handles null selection (symbol deleted) by clearing selectedSymbol.
 * Detail pane is a placeholder until the charting sub-project.
 */

import { createSignal } from "solid-js";
import { WatchlistPanel } from "./watchlist-panel";
import { ShowCreateWatchlistModal } from "./create-modal";

export function ShowWatchlistsDashboard() {
  const [selectedSymbol, setSelectedSymbol] = createSignal<string | null>(null);
  const [showCreateModal, setShowCreateModal] = createSignal(false);

  function handleSymbolSelect(symbol: string | null) {
    setSelectedSymbol(symbol);
  }

  return (
    <div class="watchlist-page">
      <ShowCreateWatchlistModal
        isOpen={showCreateModal()}
        onClose={() => setShowCreateModal(false)}
        onSuccess={() => setShowCreateModal(false)}
      />

      <div class="watchlist-layout">
        {/* Left pane */}
        <aside class="watchlist-layout__panel">
          <div class="watchlist-layout__panel-header">
            <span class="watchlist-layout__title">Watchlists</span>
            <button
              class="watchlist-layout__new-btn"
              onClick={() => setShowCreateModal(true)}
              title="New watchlist"
            >
              +
            </button>
          </div>
          <WatchlistPanel
            selectedSymbol={selectedSymbol()}
            onSymbolSelect={handleSymbolSelect}
          />
        </aside>

        {/* Right pane */}
        <main class="watchlist-layout__detail">
          {selectedSymbol() ? (
            <div class="watchlist-detail-placeholder">
              <h2>{selectedSymbol()}</h2>
              <p class="watchlist-detail-placeholder__note">
                Chart and detail view coming in the charting sub-project.
              </p>
            </div>
          ) : (
            <div class="watchlist-detail-placeholder watchlist-detail-placeholder--empty">
              <p>Select a stock to view detail</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
