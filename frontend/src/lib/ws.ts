import { createSignal } from "solid-js";

export type WsStatus = "connecting" | "open" | "closed";

export class WsClient {
  private sock: WebSocket | null = null;
  private readonly subscribers = new Map<string, Set<(data: unknown) => void>>();
  private backoffMs = 1000;
  private readonly maxBackoffMs = 30_000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // SolidJS reactive status: consumers call ws.status() in JSX
  private readonly _sig = createSignal<WsStatus>("closed");
  readonly status = this._sig[0];
  private readonly setStatus = this._sig[1];

  constructor(private readonly url: string) {}

  connect(): void {
    if (this.sock && this.sock.readyState <= 1) return; // already connecting/open
    this.setStatus("connecting");
    this.sock = new WebSocket(this.url);

    this.sock.onopen = () => {
      this.backoffMs = 1000;
      this.setStatus("open");
      // Re-subscribe all active topics after reconnect
      for (const topic of this.subscribers.keys()) {
        this.sock?.send(JSON.stringify({ op: "subscribe", topic }));
      }
    };

    this.sock.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { topic?: string; data?: unknown };
        if (msg.topic) {
          this.subscribers.get(msg.topic)?.forEach((h) => h(msg.data));
        }
      } catch {
        // ignore parse errors
      }
    };

    this.sock.onclose = () => {
      this.setStatus("closed");
      this.scheduleReconnect();
    };
  }

  subscribe(topic: string, handler: (data: unknown) => void): () => void {
    if (!this.subscribers.has(topic)) {
      this.subscribers.set(topic, new Set());
      if (this.sock?.readyState === 1) {
        this.sock.send(JSON.stringify({ op: "subscribe", topic }));
      }
    }
    this.subscribers.get(topic)!.add(handler);
    return () => {
      const handlers = this.subscribers.get(topic);
      if (!handlers) return;
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.subscribers.delete(topic);
        if (this.sock?.readyState === 1) {
          this.sock.send(JSON.stringify({ op: "unsubscribe", topic }));
        }
      }
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.sock?.close();
    this.sock = null;
  }

  private scheduleReconnect(): void {
    this.reconnectTimer = setTimeout(() => {
      this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);
      this.connect();
    }, this.backoffMs);
  }
}

// App-wide singleton
export const ws = new WsClient("/ws");
