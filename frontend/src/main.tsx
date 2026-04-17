import { render } from "solid-js/web";
import { Navigate, Route, Router } from "@solidjs/router";
import { createResource, Show, Suspense } from "solid-js";
import "./index.css";
import App from "./app";
import LoginPage from "./pages/login";
import DashboardPage from "./pages/dashboard";
import SettingsPage from "./pages/settings/index";
import { ShowWatchlistsDashboard } from "./pages/watchlists/dashboard";
import ScannerPage from "./pages/scanners/index";
import SchedulePage from "./pages/schedule/index";
import { fetchCurrentUser } from "./lib/auth";

function RequireAuth(props: { children: any }) {
  const [user] = createResource(fetchCurrentUser);
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <Show when={!user.loading}>
        <Show when={user()} fallback={<Navigate href="/login" />}>
          {props.children}
        </Show>
      </Show>
    </Suspense>
  );
}

export function AppRoutes() {
  return (
    <Router root={App}>
      <Route path="/" component={() => <Navigate href="/dashboard" />} />
      <Route path="/login" component={LoginPage} />
      <Route
        path="/dashboard"
        component={() => (
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        )}
      />
      <Route
        path="/settings"
        component={() => (
          <RequireAuth>
            <Navigate href="/settings/appearance" />
          </RequireAuth>
        )}
      />
      <Route
        path="/settings/:panelId"
        component={() => (
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        )}
      />
      <Route
        path="/watchlists"
        component={() => (
          <RequireAuth>
            <ShowWatchlistsDashboard />
          </RequireAuth>
        )}
      />
      <Route
        path="/scanners"
        component={() => (
          <RequireAuth>
            <ScannerPage />
          </RequireAuth>
        )}
      />
      <Route
        path="/schedule"
        component={() => (
          <RequireAuth>
            <SchedulePage />
          </RequireAuth>
        )}
      />
    </Router>
  );
}

// Only render if we're in a browser environment with a root element
if (typeof document !== "undefined") {
  render(() => <AppRoutes />, document.getElementById("root")!);
}

export default AppRoutes;
