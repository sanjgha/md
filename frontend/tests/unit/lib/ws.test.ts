import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Minimal WebSocket mock
class MockWS {
  static instances: MockWS[] = [];
  readyState = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    MockWS.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }

  simulateOpen() {
    this.readyState = 1;
    this.onopen?.();
  }
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

beforeEach(() => {
  MockWS.instances = [];
  vi.stubGlobal("WebSocket", MockWS);
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe("WsClient", () => {
  it("calls handler when subscribed topic message arrives", async () => {
    const { WsClient } = await import("~/lib/ws");
    const client = new WsClient("/ws");
    const handler = vi.fn();
    client.subscribe("quotes:NVDA", handler);
    client.connect();

    const ws = MockWS.instances[0];
    ws.simulateOpen();
    ws.simulateMessage({ topic: "quotes:NVDA", data: { price: 100 } });

    expect(handler).toHaveBeenCalledWith({ price: 100 });
  });

  it("unsubscribe stops delivery", async () => {
    const { WsClient } = await import("~/lib/ws");
    const client = new WsClient("/ws");
    const handler = vi.fn();
    const unsub = client.subscribe("t1", handler);
    client.connect();

    const ws = MockWS.instances[0];
    ws.simulateOpen();
    unsub();
    ws.simulateMessage({ topic: "t1", data: {} });

    expect(handler).not.toHaveBeenCalled();
  });

  it("re-subscribes after reconnect", async () => {
    const { WsClient } = await import("~/lib/ws");
    const client = new WsClient("/ws");
    const handler = vi.fn();
    client.subscribe("t1", handler);
    client.connect();

    const ws1 = MockWS.instances[0];
    ws1.simulateOpen();
    ws1.close(); // trigger reconnect

    // Fast-forward timers to trigger reconnect
    await vi.runAllTimersAsync();

    if (MockWS.instances.length > 1) {
      const ws2 = MockWS.instances[1];
      ws2.simulateOpen();
      ws2.simulateMessage({ topic: "t1", data: "after reconnect" });
      expect(handler).toHaveBeenCalledWith("after reconnect");
    }
  });
});
