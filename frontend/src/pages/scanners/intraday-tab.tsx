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
    <div class="flex flex-col h-full">
      <div class="p-3 border-b flex items-center gap-3 flex-wrap">
        {/* Scanner pills */}
        <Show when={scanners()}>
          <div class="flex gap-2">
            <For each={scanners()}>
              {(s: ScannerMeta) => (
                <button
                  class={`px-3 py-1 rounded-full text-sm border transition-colors ${
                    selectedScanners().has(s.name)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                  }`}
                  onClick={() => toggleScanner(s.name)}
                >
                  {s.name}
                </button>
              )}
            </For>
          </div>
        </Show>
        {/* Timeframe */}
        <select
          class="border rounded px-2 py-1 text-sm"
          value={timeframe()}
          onChange={(e) => setTimeframe(e.currentTarget.value as "15m" | "1h")}
        >
          <option value="15m">15m</option>
          <option value="1h">1h</option>
        </select>
        {/* Input scope */}
        <select
          class="border rounded px-2 py-1 text-sm"
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
        {/* Run button */}
        <button
          class="px-4 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          onClick={handleRun}
          disabled={running()}
        >
          {running() ? "Running..." : "Run"}
        </button>
        {/* Save as Watchlist — only after results */}
        <Show when={results() && filteredGroups().some((g) => g.results.length > 0)}>
          <button
            class="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            onClick={saveAsWatchlist}
            disabled={saving()}
          >
            {saving() ? "Saving..." : "Save as Watchlist"}
          </button>
        </Show>
      </div>
      <div class="flex-1 overflow-hidden">
        <Show
          when={results()}
          fallback={<p class="p-4 text-gray-400 text-sm">Select scanners and click Run</p>}
        >
          <ResultsPanel groups={filteredGroups()} />
        </Show>
      </div>
    </div>
  );
}
