import { createEffect } from "solid-js";
import { A } from "@solidjs/router";
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

      {/* Quick navigation links */}
      <div class="quick-nav" style={{ "margin-top": "2rem" }}>
        <h2>Quick Navigation</h2>
        <div class="quick-nav-links" style={{ display: "flex", gap: "1rem", "flex-wrap": "wrap" }}>
          <A href="/schedule" style={{
            padding: "0.75rem 1.5rem",
            background: "var(--accent)",
            color: "white",
            "text-decoration": "none",
            "border-radius": "0.375rem",
            "font-weight": "500"
          }}>
            📅 Schedule
          </A>
          <A href="/scanners" style={{
            padding: "0.75rem 1.5rem",
            background: "var(--surface-2)",
            color: "var(--text-1)",
            "text-decoration": "none",
            "border-radius": "0.375rem",
            border: "1px solid var(--border)"
          }}>
            🔍 Scanners
          </A>
          <A href="/watchlists" style={{
            padding: "0.75rem 1.5rem",
            background: "var(--surface-2)",
            color: "var(--text-1)",
            "text-decoration": "none",
            "border-radius": "0.375rem",
            border: "1px solid var(--border)"
          }}>
            📊 Watchlists
          </A>
          <A href="/settings" style={{
            padding: "0.75rem 1.5rem",
            background: "var(--surface-2)",
            color: "var(--text-1)",
            "text-decoration": "none",
            "border-radius": "0.375rem",
            border: "1px solid var(--border)"
          }}>
            ⚙️ Settings
          </A>
        </div>
      </div>
    </main>
  );
}
