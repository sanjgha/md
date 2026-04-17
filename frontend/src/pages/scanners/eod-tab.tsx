import { createEffect, createMemo, createResource, createSignal, For, Show } from "solid-js";
import { listScanners, getResults, getRunDates } from "../../lib/scanners-api";
import type { RunDateEntry } from "../../lib/scanners-api";
import { watchlistsAPI } from "../../lib/watchlists-api";
import { ResultsPanel } from "./results-panel";
import type { ScannerMeta, ScannerResultItem, ScannerResultsResponse } from "./types";

export function EodTab() {
  const [scanners] = createResource(listScanners);
  const [runDates] = createResource(getRunDates);
  const [selectedScanners, setSelectedScanners] = createSignal<Set<string>>(new Set());
  const [selectedRunIdx, setSelectedRunIdx] = createSignal<number>(0);
  const [results, setResults] = createSignal<ScannerResultsResponse | null>(null);
  const [saving, setSaving] = createSignal(false);

  const selectedRun = createMemo((): RunDateEntry | null => runDates()?.[selectedRunIdx()] ?? null);

  // Load results when selected run changes
  createEffect(() => {
    const run = selectedRun();
    if (!run) return;
    getResults({
      run_type: run.run_type as "eod" | "pre_close",
      date: run.date,
    }).then(data => {
      setResults(data);
      setSelectedScanners(new Set(data.results.map((r: ScannerResultItem) => r.scanner_name)));
    });
  });

  const toggleScanner = (name: string) => {
    setSelectedScanners(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const filteredGroups = createMemo(() => {
    if (!results()) return [];
    const grouped = new Map<string, ScannerResultItem[]>();
    for (const r of results()!.results) {
      if (!selectedScanners().has(r.scanner_name)) continue;
      if (!grouped.has(r.scanner_name)) grouped.set(r.scanner_name, []);
      grouped.get(r.scanner_name)!.push(r);
    }
    return [...grouped.entries()].map(([scanner_name, items]) => ({ scanner_name, results: items }));
  });

  const saveAsWatchlist = async () => {
    if (!results() || saving()) return;
    setSaving(true);
    try {
      const scannerNames = [...selectedScanners()].join(" + ");
      const runType = results()!.run_type;
      const runLabel = runType === "pre_close" ? "Pre-close" : "EOD";
      const name = `${scannerNames} — ${runLabel} ${results()!.date}`;
      await watchlistsAPI.create({ name, description: "Auto-generated from scanner run", category_id: null });
    } finally {
      setSaving(false);
    }
  };

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
        <Show when={runDates()?.length}>
          <select
            class="run-date-select"
            onChange={e => setSelectedRunIdx(parseInt(e.currentTarget.value))}
          >
            <For each={runDates()}>
              {(entry: RunDateEntry, i) => (
                <option value={i()}>
                  {entry.date} — {entry.run_type === "pre_close" ? "Pre-close" : "EOD"} {entry.time}
                </option>
              )}
            </For>
          </select>
        </Show>
        <Show when={results() && filteredGroups().some(g => g.results.length > 0)}>
          <button
            class="save-watchlist-btn"
            onClick={saveAsWatchlist}
            disabled={saving()}
          >
            {saving() ? "Saving..." : "Save as Watchlist"}
          </button>
        </Show>
      </div>
      <div class="eod-tab__body">
        <ResultsPanel groups={filteredGroups()} />
      </div>
    </div>
  );
}
