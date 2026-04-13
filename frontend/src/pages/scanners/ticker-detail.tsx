import { For } from "solid-js";
import type { ScannerResultItem } from "./types";

interface Props {
  result: ScannerResultItem;
}

export function TickerDetail(props: Props) {
  return (
    <div class="p-4 space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-bold">{props.result.symbol}</h2>
        <span class={`px-2 py-1 rounded text-sm font-medium ${
          props.result.signal === "BUY" ? "bg-green-100 text-green-800" :
          props.result.signal === "SELL" ? "bg-red-100 text-red-800" :
          "bg-gray-100 text-gray-800"
        }`}>{props.result.signal ?? "—"}</span>
      </div>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <div><span class="text-gray-500">Price</span><div class="font-medium">{props.result.price != null ? `$${props.result.price.toFixed(2)}` : "—"}</div></div>
        <div><span class="text-gray-500">Score</span><div class="font-medium">{props.result.score != null ? props.result.score.toFixed(1) : "—"}</div></div>
        <div><span class="text-gray-500">Volume</span><div class="font-medium">{props.result.volume != null ? `${(props.result.volume / 1_000_000).toFixed(1)}M` : "—"}</div></div>
        <div><span class="text-gray-500">Change</span><div class={`font-medium ${(props.result.change_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>{props.result.change_pct != null ? `${props.result.change_pct >= 0 ? "+" : ""}${props.result.change_pct.toFixed(2)}%` : "—"}</div></div>
      </div>
      <div>
        <p class="text-gray-500 text-sm mb-1">Scanner</p>
        <p class="text-sm font-medium">{props.result.scanner_name}</p>
      </div>
      {props.result.indicators_fired.length > 0 && (
        <div>
          <p class="text-gray-500 text-sm mb-1">Indicators triggered</p>
          <ul class="text-sm space-y-0.5">
            <For each={props.result.indicators_fired}>
              {(ind) => (
                <li class="flex items-center gap-1">
                  <span class="text-green-500">✓</span> {ind.replace(/_/g, " ")}
                </li>
              )}
            </For>
          </ul>
        </div>
      )}
    </div>
  );
}
