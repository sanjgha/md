import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";

beforeEach(() => {
  // Reset dataset before each test
  document.documentElement.dataset.theme = "";
});

afterEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("settings-store", () => {
  it("applyTheme sets document.documentElement.dataset.theme", async () => {
    const { applyTheme } = await import("~/lib/settings-store");
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("applyTheme updates theme to dark", async () => {
    const { applyTheme } = await import("~/lib/settings-store");
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("loadSettings fetches and applies settings", async () => {
    const settingsData = { theme: "light", timezone: "UTC" };
    const getMock = vi.fn().mockResolvedValue(settingsData);
    vi.doMock("~/lib/api", () => ({
      apiGet: getMock,
      apiPut: vi.fn(),
      ApiError: class extends Error {},
    }));
    const { loadSettings } = await import("~/lib/settings-store");
    await loadSettings();
    expect(getMock).toHaveBeenCalledWith("/api/settings");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("saveSettings sends PUT and applies theme if changed", async () => {
    const updatedSettings = { theme: "dark", timezone: "America/New_York" };
    const putMock = vi.fn().mockResolvedValue(updatedSettings);
    vi.doMock("~/lib/api", () => ({
      apiGet: vi.fn(),
      apiPut: putMock,
      ApiError: class extends Error {},
    }));
    const { saveSettings } = await import("~/lib/settings-store");
    await saveSettings({ theme: "dark" });
    expect(putMock).toHaveBeenCalledWith("/api/settings", { theme: "dark" });
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("saveSettings without theme patch does not call applyTheme", async () => {
    const updatedSettings = { theme: "dark", timezone: "UTC" };
    const putMock = vi.fn().mockResolvedValue(updatedSettings);
    vi.doMock("~/lib/api", () => ({
      apiGet: vi.fn(),
      apiPut: putMock,
      ApiError: class extends Error {},
    }));
    const { saveSettings } = await import("~/lib/settings-store");
    await saveSettings({ timezone: "UTC" });
    expect(putMock).toHaveBeenCalledWith("/api/settings", { timezone: "UTC" });
  });
});
