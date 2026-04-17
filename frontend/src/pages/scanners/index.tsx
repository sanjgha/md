import { createSignal, Show } from "solid-js";
import { EodTab } from "./eod-tab";
import { IntradayTab } from "./intraday-tab";

type Tab = "eod" | "intraday";

export default function ScannerPage() {
  const [tab, setTab] = createSignal<Tab>("eod");

  return (
    <div class="scanner-page">
      <div class="scanner-page__tabs">
        {(["eod", "intraday"] as Tab[]).map(t => (
          <button
            class="scanner-tab-btn"
            classList={{ active: tab() === t }}
            onClick={() => setTab(t)}
          >
            {t === "eod" ? "EOD" : "Intraday"}
          </button>
        ))}
      </div>
      <div class="scanner-page__body">
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
