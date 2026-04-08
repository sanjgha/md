import { createEffect } from "solid-js";
import { currentUser } from "../lib/auth";
import { ws } from "../lib/ws";

export default function DashboardPage() {
  createEffect(() => {
    ws.connect();
  });

  return (
    <main class="dashboard-page">
      <h1>Dashboard</h1>
      <p>Hello, {currentUser()?.username ?? "\u2026"}!</p>
      <p class="ws-note">WebSocket: {ws.status()}</p>
    </main>
  );
}
