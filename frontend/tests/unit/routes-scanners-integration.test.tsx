import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@solidjs/testing-library";
import { AppRoutes } from "../../src/main";

vi.mock("../../src/lib/scanners-api", () => ({
  listScanners: vi.fn().mockResolvedValue([]),
  getResults: vi.fn().mockResolvedValue({ results: [], run_type: "eod", date: "" }),
  getRunDates: vi.fn().mockResolvedValue([]),
  runIntraday: vi.fn().mockResolvedValue({ results: [], run_type: "intraday", date: "" }),
}));

vi.mock("../../src/lib/watchlists-api", () => ({
  watchlistsAPI: { list: vi.fn().mockResolvedValue({ categories: [] }) },
}));

vi.mock("../../src/lib/auth", () => ({
  fetchCurrentUser: vi.fn().mockResolvedValue({ id: 1, username: "testuser" }),
  currentUser: vi.fn().mockReturnValue({ id: 1, username: "testuser" }),
  logout: vi.fn(),
}));

vi.mock("../../src/lib/ws", () => ({
  ws: { status: vi.fn().mockReturnValue("open") },
}));

describe("Scanners route", () => {
  it("renders scanners page at /scanners with EOD and Intraday tabs", async () => {
    window.history.pushState({}, "", "/scanners");
    render(() => <AppRoutes />);
    await waitFor(() => {
      expect(screen.getByText("EOD")).toBeTruthy();
      expect(screen.getByText("Intraday")).toBeTruthy();
    }, { timeout: 3000 });
  });
});
