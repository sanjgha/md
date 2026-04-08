import { createStore } from "solid-js/store";
import { apiGet, apiPut } from "./api";
import type { SettingsOut, SettingsPatch } from "../types/api";

const [settings, setSettings] = createStore<SettingsOut>({
  theme: "dark",
  timezone: "America/New_York",
});

export { settings };

export function applyTheme(theme: string): void {
  document.documentElement.dataset.theme = theme;
}

export async function loadSettings(): Promise<void> {
  const data = await apiGet<SettingsOut>("/api/settings");
  setSettings(data);
  applyTheme(data.theme);
}

export async function saveSettings(patch: SettingsPatch): Promise<void> {
  const updated = await apiPut<SettingsOut>("/api/settings", patch);
  setSettings(updated);
  if (patch.theme) applyTheme(patch.theme);
}
