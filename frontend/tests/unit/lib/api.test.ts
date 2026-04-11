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

  it("returns undefined on 204 No Content", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    );
    const { apiFetch } = await import("~/lib/api");
    const result = await apiFetch("/api/resource");
    expect(result).toBeUndefined();
  });

  it("apiGet calls apiFetch with GET", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: 1 }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { apiGet } = await import("~/lib/api");
    const result = await apiGet("/api/data");
    expect(result).toEqual({ data: 1 });
    expect(fetchMock).toHaveBeenCalledWith("/api/data", expect.objectContaining({ credentials: "include" }));
  });

  it("apiPost sends POST with JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ created: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { apiPost } = await import("~/lib/api");
    await apiPost("/api/items", { name: "test" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/items",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ name: "test" }) })
    );
  });

  it("apiPost without body sends no body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { apiPost } = await import("~/lib/api");
    await apiPost("/api/action");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/action",
      expect.objectContaining({ method: "POST", body: undefined })
    );
  });

  it("apiPut sends PUT with JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ updated: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);
    const { apiPut } = await import("~/lib/api");
    await apiPut("/api/items/1", { name: "updated" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/items/1",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ name: "updated" }) })
    );
  });
});
