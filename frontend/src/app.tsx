import { A, useNavigate } from "@solidjs/router";
import { JSX, Show } from "solid-js";
import { currentUser, logout } from "./lib/auth";
import { ws } from "./lib/ws";

function WsStatusDot() {
  const color = () => {
    switch (ws.status()) {
      case "open": return "var(--green-6, #16a34a)";
      case "connecting": return "var(--yellow-6, #ca8a04)";
      default: return "var(--red-6, #dc2626)";
    }
  };
  return (
    <span
      title={`WebSocket: ${ws.status()}`}
      style={{ display: "inline-block", width: "10px", height: "10px",
               "border-radius": "50%", background: color() }}
    />
  );
}

export default function App(props: { children?: JSX.Element }) {
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <>
      <nav class="app-nav">
        <span class="app-title">Market Data</span>
        <div class="nav-links">
          <A href="/dashboard">Dashboard</A>
          <A href="/settings">Settings</A>
        </div>
        <div class="nav-user">
          <WsStatusDot />
          <Show when={currentUser()}>
            <span>{currentUser()!.username}</span>
            <button onClick={handleLogout}>Logout</button>
          </Show>
        </div>
      </nav>
      {props.children}
    </>
  );
}
