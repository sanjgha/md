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
    <div class="flex h-full">
      <div class="w-64 border-r overflow-y-auto flex-shrink-0">
        <Show when={!hasResults()}>
          <p class="p-4 text-gray-400 text-sm">No results</p>
        </Show>
        <Show when={overlap().length > 0}>
          <div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b">
            Overlap ({overlap().length})
          </div>
          <For each={overlap()}>
            {(item) => (
              <button
                class={`w-full text-left px-3 py-2 hover:bg-gray-50 ${selected()?.symbol === item.symbol && selected()?.scanner_name === item.scanner_name ? "bg-blue-50" : ""}`}
                onClick={() => setSelected(item)}
              >
                <span class="font-medium text-sm">{item.symbol}</span>
              </button>
            )}
          </For>
        </Show>
        <For each={props.groups}>
          {(group) => (
            <>
              <div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-t mt-1">
                {group.scanner_name} ({group.results.length})
              </div>
              <For each={group.results}>
                {(item) => (
                  <button
                    class={`w-full text-left px-3 py-2 hover:bg-gray-50 ${selected()?.symbol === item.symbol && selected()?.scanner_name === item.scanner_name ? "bg-blue-50" : ""}`}
                    onClick={() => setSelected(item)}
                  >
                    <span class="font-medium text-sm">{item.symbol}</span>
                  </button>
                )}
              </For>
            </>
          )}
        </For>
      </div>
      <div class="flex-1 overflow-y-auto">
        <Show when={selected()} fallback={<p class="p-4 text-gray-400 text-sm">Select a ticker</p>}>
          <TickerDetail result={selected()!} />
        </Show>
      </div>
    </div>
  );
}
