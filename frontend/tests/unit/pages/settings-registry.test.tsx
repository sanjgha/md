import { describe, it, expect } from "vitest";

describe("settings panel registry", () => {
  it("contains appearance panel", async () => {
    const { settingsPanels } = await import("~/pages/settings/registry");
    const ids = settingsPanels.map((p) => p.id);
    expect(ids).toContain("appearance");
  });

  it("panels are sorted by order", async () => {
    const { settingsPanels } = await import("~/pages/settings/registry");
    const orders = settingsPanels.map((p) => p.order);
    const sorted = [...orders].sort((a, b) => a - b);
    expect(orders).toEqual(sorted);
  });
});
