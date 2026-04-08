import { describe, it, expect, vi, afterEach } from "vitest";

describe("apiFetch", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends credentials: include on every request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("~/lib/api");
    await apiFetch("/api/health");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("returns parsed JSON on 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
    );
    const { apiFetch } = await import("~/lib/api");
    const result = await apiFetch("/api/health");
    expect(result).toEqual({ status: "ok" });
  });

  it("throws ApiError on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "bad" }), { status: 400 }))
    );
    const { apiFetch, ApiError } = await import("~/lib/api");
    await expect(apiFetch("/api/whatever")).rejects.toBeInstanceOf(ApiError);
  });
});
