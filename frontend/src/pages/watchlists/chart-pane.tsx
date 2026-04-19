/**
 * Chart pane shell.
 * Manages split state (1 or 2 panels) and renders chart-panel instances.
 */

import { createSignal, Show } from "solid-js";
import { ChartPanel } from "./chart-panel";

interface QuoteData {
  last: number;
  change: number;
  change_pct: number;
}

interface Props {
  selectedSymbol: () => string | null;
  quote: QuoteData | null;
}

export function ChartPane(props: Props) {
  const [panelCount, setPanelCount] = createSignal<1 | 2>(1);

  const handleSplitToggle = () => {
    setPanelCount(panelCount() === 1 ? 2 : 1);
  };

  return (
    <div class="chart-pane">
      <div class="chart-pane-header">
        <button
          class="split-toggle"
          onClick={handleSplitToggle}
        >
          {panelCount() === 1 ? "⊞ Split" : "⊟ Unsplit"}
        </button>
      </div>

      <Show when={props.selectedSymbol()}>
        <div class="chart-panels" classList={{ "split": panelCount() === 2 }}>
          <ChartPanel
            symbol={props.selectedSymbol()!}
            quote={props.quote}
            selectedSymbol={props.selectedSymbol}
          />

          <Show when={panelCount() === 2}>
            <ChartPanel
              symbol={props.selectedSymbol()!}
              quote={props.quote}
              selectedSymbol={props.selectedSymbol}
              defaultResolution="1h"
            />
          </Show>
        </div>
      </Show>

      <Show when={!props.selectedSymbol()}>
        <div class="empty-state">
          Select a stock from the watchlist to view its chart.
        </div>
      </Show>
    </div>
  );
}
