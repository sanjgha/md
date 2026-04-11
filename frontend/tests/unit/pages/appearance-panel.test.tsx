import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@solidjs/testing-library";

afterEach(() => {
  vi.resetModules();
  vi.restoreAllMocks();
});

describe("AppearancePanel", () => {
  it("renders theme radio buttons", async () => {
    vi.doMock("~/lib/settings-store", () => ({
      settings: { theme: "dark", timezone: "America/New_York" },
      loadSettings: vi.fn().mockResolvedValue(undefined),
      saveSettings: vi.fn().mockResolvedValue(undefined),
      applyTheme: vi.fn(),
    }));
    const { default: AppearancePanel } = await import(
      "~/pages/settings/panels/appearance"
    );
    const { unmount } = render(() => <AppearancePanel />);
    expect(screen.getByLabelText(/dark/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/light/i)).toBeInTheDocument();
    unmount();
  });

  it("save button calls saveSettings with changed theme", async () => {
    const saveSettings = vi.fn().mockResolvedValue(undefined);
    vi.doMock("~/lib/settings-store", () => ({
      settings: { theme: "dark", timezone: "America/New_York" },
      loadSettings: vi.fn().mockResolvedValue(undefined),
      saveSettings,
      applyTheme: vi.fn(),
    }));
    const { default: AppearancePanel } = await import(
      "~/pages/settings/panels/appearance"
    );
    const { unmount } = render(() => <AppearancePanel />);
    fireEvent.click(screen.getByLabelText(/light/i));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ theme: "light" }));
    unmount();
  });
});
