import { For, Show } from "solid-js";
import { A, useParams } from "@solidjs/router";
import { settingsPanels } from "./registry";

export default function SettingsPage() {
  const params = useParams<{ panelId: string }>();
  const panel = () => settingsPanels.find((p) => p.id === params.panelId);

  return (
    <div class="settings-layout">
      <aside class="settings-sidebar">
        <nav>
          <For each={settingsPanels.sort((a, b) => a.order - b.order)}>
            {(p) => (
              <A
                href={`/settings/${p.id}`}
                class="sidebar-link"
                activeClass="active"
                end
              >
                {p.label}
              </A>
            )}
          </For>
        </nav>
      </aside>
      <main class="settings-content">
        <Show
          when={panel()}
          fallback={<p>Panel not found.</p>}
        >
          {(p) => { const Panel = p().component; return <Panel />; }}
        </Show>
      </main>
    </div>
  );
}
