import { createMemo, createResource, createSignal, For, onCleanup, Show } from "solid-js";
import { listScanners, runIntraday } from "../../lib/scanners-api";
import { watchlistsAPI } from "../../lib/watchlists-api";
import { ResultsPanel } from "./results-panel";
import type { ScannerMeta, ScannerResultItem, ScannerResultsResponse } from "./types";
import type { Watchlist } from "../watchlists/types";

/** Shape returned by watchlistsAPI.list() */
interface CategoryWatchlistsEntry {
  category_id: number | null;
  category_name: string;
  category_icon: string | null;
  is_system: boolean;
  watchlists: Watchlist[];
}

export function IntradayTab() {
  const [scanners] = createResource(listScanners);
  const [selectedScanners, setSelectedScanners] = createSignal<Set<string>>(new Set(["momentum"]));
  const [timeframe, setTimeframe] = createSignal<"15m" | "1h">("15m");
  const [inputScope, setInputScope] = createSignal<"universe" | number>("universe");
  const [running, setRunning] = createSignal(false);
  const [results, setResults] = createSignal<ScannerResultsResponse | null>(null);
  const [saving, setSaving] = createSignal(false);

  const [watchlistData] = createResource(() => watchlistsAPI.list());

  // Clear results on unmount (ephemeral)
  onCleanup(() => setResults(null));

  const toggleScanner = (name: string) => {
    setSelectedScanners((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const handleRun = async () => {
    if (running()) return;
    setRunning(true);
    try {
      const data = await runIntraday({
        scanners: [...selectedScanners()],
        timeframe: timeframe(),
        input_scope: inputScope(),
      });
      setResults(data);
    } finally {
      setRunning(false);
    }
  };

  const filteredGroups = createMemo(() => {
    if (!results()) return [];
    const grouped = new Map<string, ScannerResultItem[]>();
    for (const r of results()!.results) {
      if (!grouped.has(r.scanner_name)) grouped.set(r.scanner_name, []);
      grouped.get(r.scanner_name)!.push(r);
    }
    return [...grouped.entries()].map(([scanner_name, items]) => ({ scanner_name, results: items }));
  });

  const saveAsWatchlist = async () => {
    if (!results() || saving()) return;
    setSaving(true);
    try {
      const name = `Intraday ${timeframe()} — ${results()!.date}`;
      await watchlistsAPI.create({ name, description: "Auto-generated from intraday scan", category_id: null });
    } finally {
      setSaving(false);
    }
  };

  const categories = createMemo<CategoryWatchlistsEntry[]>(
    () => (watchlistData()?.categories as CategoryWatchlistsEntry[] | undefined) ?? []
  );

  return (
    <div class="eod-tab">
      <div class="eod-tab__toolbar">
        <Show when={scanners()}>
          <div class="scanner-filter-group">
            <For each={scanners()}>
              {(s: ScannerMeta) => (
                <button
                  class="scanner-filter-btn"
                  classList={{ active: selectedScanners().has(s.name) }}
                  onClick={() => toggleScanner(s.name)}
                >
                  {s.name}
                </button>
              )}
            </For>
          </div>
        </Show>
        <select
          class="run-date-select"
          value={timeframe()}
          onChange={(e) => setTimeframe(e.currentTarget.value as "15m" | "1h")}
        >
          <option value="15m">15m</option>
          <option value="1h">1h</option>
        </select>
        <select
          class="run-date-select"
          value={inputScope() === "universe" ? "universe" : String(inputScope())}
          onChange={(e) => {
            const v = e.currentTarget.value;
            setInputScope(v === "universe" ? "universe" : parseInt(v));
          }}
        >
          <option value="universe">Full Universe</option>
          <For each={categories()}>
            {(cat) => (
              <For each={cat.watchlists ?? []}>
                {(wl) => <option value={wl.id}>{wl.name}</option>}
              </For>
            )}
          </For>
        </select>
        <button
          class="scanner-filter-btn active"
          onClick={handleRun}
          disabled={running()}
          style="border-radius: 4px;"
        >
          {running() ? "Running…" : "Run"}
        </button>
        <Show when={results() && filteredGroups().some((g) => g.results.length > 0)}>
          <button
            class="save-watchlist-btn"
            onClick={saveAsWatchlist}
            disabled={saving()}
          >
            {saving() ? "Saving…" : "Save as Watchlist"}
          </button>
        </Show>
      </div>
      <div class="eod-tab__body">
        <Show
          when={results()}
          fallback={<p class="scanner-results__no-selection">Select scanners and click Run</p>}
        >
          <ResultsPanel groups={filteredGroups()} />
        </Show>
      </div>
    </div>
  );
}
