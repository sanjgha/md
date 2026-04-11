import { createSignal, onMount, For } from "solid-js";
import { settings, loadSettings, saveSettings } from "../../../lib/settings-store";

export default function AppearancePanel() {
  const [theme, setTheme] = createSignal<"light" | "dark">("dark");
  const [timezone, setTimezone] = createSignal("America/New_York");
  const [dirty, setDirty] = createSignal(false);
  const [saving, setSaving] = createSignal(false);

  const tzList = () => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (Intl as any).supportedValuesOf("timeZone") as string[];
    } catch {
      return ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "UTC"];
    }
  };

  onMount(async () => {
    await loadSettings();
    setTheme(settings.theme as "light" | "dark");
    setTimezone(settings.timezone);
  });

  function handleTimezoneChange(e: Event) {
    setTimezone((e.currentTarget as HTMLSelectElement).value);
    setDirty(true);
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    setSaving(true);
    try {
      await saveSettings({ theme: theme(), timezone: timezone() });
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form class="settings-panel" onSubmit={handleSave}>
      <h2>Appearance</h2>

      <fieldset>
        <legend>Theme</legend>
        <label for="theme-dark">
          <input
            id="theme-dark"
            type="radio"
            name="theme"
            value="dark"
            checked={theme() === "dark"}
            onClick={() => { setTheme("dark"); setDirty(true); }}
          />
          Dark
        </label>
        <label for="theme-light">
          <input
            id="theme-light"
            type="radio"
            name="theme"
            value="light"
            checked={theme() === "light"}
            onClick={() => { setTheme("light"); setDirty(true); }}
          />
          Light
        </label>
      </fieldset>

      <label for="timezone">
        Timezone
        <select id="timezone" value={timezone()} onChange={handleTimezoneChange}>
          <For each={tzList()}>{(tz) => <option value={tz}>{tz}</option>}</For>
        </select>
      </label>

      <button type="submit" disabled={!dirty() || saving()}>
        {saving() ? "Saving\u2026" : "Save"}
      </button>
    </form>
  );
}
