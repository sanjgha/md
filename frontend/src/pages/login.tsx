import { createSignal, Show } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { login } from "../lib/auth";
import { ApiError } from "../lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [error, setError] = createSignal<string | null>(null);
  const [loading, setLoading] = createSignal(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username(), password());
      navigate("/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Invalid username or password.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError("Too many attempts. Please wait a minute and try again.");
      } else {
        setError("Login failed. Check your connection.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main class="login-page">
      <form onSubmit={handleSubmit} class="login-form">
        <h1>Market Data</h1>
        <Show when={error()}>
          <p class="error-msg" role="alert">{error()}</p>
        </Show>
        <label>
          Username
          <input
            type="text"
            autocomplete="username"
            value={username()}
            onInput={(e) => setUsername(e.currentTarget.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autocomplete="current-password"
            value={password()}
            onInput={(e) => setPassword(e.currentTarget.value)}
            required
          />
        </label>
        <button type="submit" disabled={loading()}>
          {loading() ? "Signing in\u2026" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
