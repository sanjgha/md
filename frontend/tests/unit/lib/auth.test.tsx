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
    vi.doMock("~/lib/api", () => ({ apiPost: postMock, apiGet: vi.fn(), ApiError: class extends Error {} }));
    const { login } = await import("~/lib/auth");
    await login("user", "pass");
    expect(postMock).toHaveBeenCalledWith("/api/auth/login", { username: "user", password: "pass" });
  });
});
