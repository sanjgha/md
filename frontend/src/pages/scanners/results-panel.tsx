import { createEffect, createMemo, createSignal, For, Show } from "solid-js";
import type { ScannerResultItem } from "./types";
import { TickerDetail } from "./ticker-detail";

interface ResultGroup {
  scanner_name: string;
  results: ScannerResultItem[];
}

interface Props {
  groups: ResultGroup[];
}

function computeOverlap(groups: ResultGroup[]): ScannerResultItem[] {
  if (groups.length < 2) return [];
  const sets = groups.map(g => new Set(g.results.map(r => r.symbol)));
  const intersection = [...sets[0]].filter(sym => sets.slice(1).every(s => s.has(sym)));
  return intersection.map(sym => groups[0].results.find(r => r.symbol === sym)!);
}

export function ResultsPanel(props: Props) {
  const [selected, setSelected] = createSignal<ScannerResultItem | null>(null);

  const overlap = createMemo(() => computeOverlap(props.groups));
  const hasResults = () => props.groups.some(g => g.results.length > 0);

  createEffect(() => {
    props.groups; // track
    setSelected(null);
  });

  return (
    <div class="scanner-results">
      <div class="scanner-results__list">
        <Show when={!hasResults()}>
          <p class="scanner-results__empty">No results</p>
        </Show>
        <Show when={overlap().length > 0}>
          <div class="scanner-results__section-header">
            Overlap ({overlap().length})
          </div>
          <For each={overlap()}>
            {(item) => (
              <button
                class="scanner-results__item"
                classList={{ selected: selected()?.symbol === item.symbol && selected()?.scanner_name === item.scanner_name }}
                onClick={() => setSelected(item)}
              >
                {item.symbol}
              </button>
            )}
          </For>
        </Show>
        <For each={props.groups}>
          {(group) => (
            <>
              <div class="scanner-results__section-header">
                {group.scanner_name} ({group.results.length})
              </div>
              <For each={group.results}>
                {(item) => (
                  <button
                    class="scanner-results__item"
                    classList={{ selected: selected()?.symbol === item.symbol && selected()?.scanner_name === item.scanner_name }}
                    onClick={() => setSelected(item)}
                  >
                    {item.symbol}
                  </button>
                )}
              </For>
            </>
          )}
        </For>
      </div>
      <div class="scanner-results__detail">
        <Show when={selected()} fallback={<p class="scanner-results__no-selection">Select a ticker</p>}>
          <TickerDetail result={selected()!} />
        </Show>
      </div>
    </div>
  );
}
