import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => {
  vi.resetModules();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("auth store", () => {
  it("currentUser is null initially", async () => {
    const { currentUser } = await import("~/lib/auth");
    expect(currentUser()).toBeNull();
  });

  it("login calls POST /api/auth/login", async () => {
    const postMock = vi.fn().mockResolvedValue({ ok: true });
    const getMock = vi.fn().mockResolvedValue({ id: 1, username: "user" });
    vi.doMock("~/lib/api", () => ({ apiPost: postMock, apiGet: getMock, ApiError: class extends Error {} }));
    const { login } = await import("~/lib/auth");
    await login("user", "pass");
    expect(postMock).toHaveBeenCalledWith("/api/auth/login", { username: "user", password: "pass" });
  });

  it("logout calls POST /api/auth/logout and clears user", async () => {
    const postMock = vi.fn().mockResolvedValue(undefined);
    vi.doMock("~/lib/api", () => ({ apiPost: postMock, apiGet: vi.fn(), ApiError: class extends Error {} }));
    const { logout, currentUser } = await import("~/lib/auth");
    await logout();
    expect(postMock).toHaveBeenCalledWith("/api/auth/logout");
    expect(currentUser()).toBeNull();
  });

  it("fetchCurrentUser sets currentUser on success", async () => {
    const userData = { id: 1, username: "alice" };
    const getMock = vi.fn().mockResolvedValue(userData);
    vi.doMock("~/lib/api", () => ({ apiGet: getMock, apiPost: vi.fn(), ApiError: class extends Error {} }));
    const { fetchCurrentUser, currentUser } = await import("~/lib/auth");
    const result = await fetchCurrentUser();
    expect(result).toEqual(userData);
    expect(currentUser()).toEqual(userData);
  });

  it("fetchCurrentUser returns null on error", async () => {
    const getMock = vi.fn().mockRejectedValue(new Error("network error"));
    vi.doMock("~/lib/api", () => ({ apiGet: getMock, apiPost: vi.fn(), ApiError: class extends Error {} }));
    const { fetchCurrentUser, currentUser } = await import("~/lib/auth");
    const result = await fetchCurrentUser();
    expect(result).toBeNull();
    expect(currentUser()).toBeNull();
  });
});
