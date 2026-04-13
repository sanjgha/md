import { createSignal, Show } from "solid-js";
import { EodTab } from "./eod-tab";
import { IntradayTab } from "./intraday-tab";

type Tab = "eod" | "intraday";

export default function ScannerPage() {
  const [tab, setTab] = createSignal<Tab>("eod");

  return (
    <div class="flex flex-col h-full">
      <div class="border-b px-4 flex gap-0">
        {(["eod", "intraday"] as Tab[]).map(t => (
          <button
            class={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab() === t
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            onClick={() => setTab(t)}
          >
            {t === "eod" ? "EOD" : "Intraday"}
          </button>
        ))}
      </div>
      <div class="flex-1 overflow-hidden">
        <Show when={tab() === "eod"}>
          <EodTab />
        </Show>
        <Show when={tab() === "intraday"}>
          <IntradayTab />
        </Show>
      </div>
    </div>
  );
}
