import { render } from "solid-js/web";
import { Navigate, Route, Router } from "@solidjs/router";
import { createResource, Show, Suspense } from "solid-js";
import "./index.css";
import App from "./app";
import LoginPage from "./pages/login";
import DashboardPage from "./pages/dashboard";
import SettingsPage from "./pages/settings/index";
import { fetchCurrentUser } from "./lib/auth";

function RequireAuth(props: { children: any }) {
  const [user] = createResource(fetchCurrentUser);
  return (
    <Suspense fallback={<p>Loading\u2026</p>}>
      <Show when={!user.loading}>
        <Show when={user()} fallback={<Navigate href="/login" />}>
          {props.children}
        </Show>
      </Show>
    </Suspense>
  );
}

render(
  () => (
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
    </Router>
  ),
  document.getElementById("root")!
);
