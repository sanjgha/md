import type { Component } from "solid-js";
import AppearancePanel from "./panels/appearance";

export interface SettingsPanel {
  id: string;
  label: string;
  component: Component;
  order: number;
}

export const settingsPanels: SettingsPanel[] = [
  { id: "appearance", label: "Appearance", component: AppearancePanel, order: 0 },
  // Future sub-projects append here — no Foundation files need changing.
];
