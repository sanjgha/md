# Foundation: API + UI Shell — Design Spec

**Sub-project:** 1 of 6 (see `2026-04-08-frontend-roadmap.md`)
**Date:** 2026-04-08
**Status:** Design — pending user review

## 1. Purpose

Establish the foundational API and UI layers for a web frontend over the
existing market data backend. Everything needed to prove the full stack
works end-to-end — and nothing more. All domain features (watchlists,
scanners, charts, alerts) are deferred to later sub-projects.

The Foundation delivers:

- A FastAPI HTTP + WebSocket layer living alongside the existing Python
  package.
- A SolidJS + Vite frontend in a new `frontend/` directory.
- Session-based auth for a single user, forward-compatible with future
  multi-user support.
- A sectioned settings page with exactly one panel (Appearance), designed
  as an extension point for later sub-projects.
- A working WebSocket connection exercised by a heartbeat topic.
- An end-to-end test that drives the full login → change theme → reload
  flow.

## 2. Non-goals

Explicitly **out** of Foundation scope:

- Any charting library, canvas work, or quote streaming.
- Any scanner, watchlist, scheduler, or alert UI.
- User management UI (signup, password reset, profile editing).
- Log level via settings — deferred to a later observability sub-project.
- Internationalization.
- Component library adoption (Foundation uses hand-written components).
- Retroactive addition of `user_id` columns to existing tables. Foundation
  establishes the pattern; later sub-projects own their own tables.

## 3. Architectural decisions

| Axis | Decision | Rationale |
|---|---|---|
| Deployment context | Single-user, remote-accessible | User choice. Drives auth + HTTPS requirements. |
| Frontend framework | SolidJS + Vite + TypeScript (strict) | Fine-grained reactivity, ~10KB runtime, well-suited to realtime chart/quote updates in later sub-projects. |
| Styling | Open Props + hand-written CSS | No build complexity, no lock-in, small bundle. No Tailwind. |
| API transport | REST for CRUD, single `/ws` WebSocket for streaming | Single connection handles future quote streams + alert pushes. |
| Backend framework | FastAPI (new `src/api/` package) | Async, Pydantic-native, OpenAPI for free, WebSocket support built in. |
| Auth | App-level session login, in-memory session store | Simplest self-contained option. Single-user scale justifies in-memory. |
| HTTPS | Required for non-localhost deployments; assumed terminated by external proxy (Caddy / Cloudflare Tunnel / Tailscale). FastAPI speaks plain HTTP. | Keeps cert management out of the app. |
| Bind address default | `127.0.0.1:8000` | Remote exposure must be explicit opt-in via a proxy/tunnel. |
| Repo layout | Monorepo; frontend in `frontend/` subdirectory | Single PR for full-stack changes; FastAPI serves built static files in prod. |
| Multi-user forward-compat | `users` table + `user_id` FKs + `get_current_user` dependency from day one | Future multi-user migration becomes swapping the auth implementation, not refactoring every endpoint. |
| Type sharing | Generate TypeScript from FastAPI's OpenAPI schema | Pydantic is the single source of truth; drift becomes a compile error. |
| Frontend routing | `solid-router` | Minimal, idiomatic for SolidJS. |
| Settings extensibility | Panel registry (array of `{id, label, component, order}`) | Later sub-projects drop in panels without touching Foundation code. |

## 4. Repository layout

```
md/                              ← existing repo root
├── src/
│   ├── api/                     ← NEW: FastAPI app
│   │   ├── __init__.py
│   │   ├── main.py              ← app factory, middleware, static mount
│   │   ├── deps.py              ← get_current_user, get_db
│   │   ├── auth.py              ← session login/logout, password hashing, in-memory store
│   │   ├── ws.py                ← /ws endpoint + PubSubRegistry + heartbeat task
│   │   ├── schemas.py           ← Pydantic request/response models
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py          ← /api/auth/login, /api/auth/logout
│   │       ├── me.py            ← /api/me
│   │       ├── settings.py      ← /api/settings GET + PUT
│   │       └── health.py        ← /api/health
│   ├── db/
│   │   └── models.py            ← +User, +UiSetting
│   ├── config.py                ← +APP_USERNAME, +APP_PASSWORD, +APP_BIND_HOST
│   └── ...                      ← existing code untouched
├── alembic/versions/
│   └── 20260408_foundation.py   ← new migration
├── frontend/                    ← NEW
│   ├── index.html
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── tsconfig.json
│   ├── vite.config.ts           ← /api + /ws proxy to :8000 in dev
│   ├── src/
│   │   ├── main.tsx             ← SolidJS entry, router
│   │   ├── app.tsx              ← shell: nav, WS status dot, <Outlet>
│   │   ├── index.css            ← Open Props import + theme CSS vars
│   │   ├── lib/
│   │   │   ├── api.ts           ← typed fetch wrapper
│   │   │   ├── ws.ts            ← WsClient w/ reconnect + pub/sub
│   │   │   ├── auth.ts          ← currentUser store, login/logout
│   │   │   └── settings-store.ts ← global settings signal
│   │   ├── pages/
│   │   │   ├── login.tsx
│   │   │   ├── dashboard.tsx    ← "Hello, {username}" placeholder
│   │   │   └── settings/
│   │   │       ├── index.tsx    ← two-pane shell reading registry
│   │   │       ├── registry.ts  ← panel registry
│   │   │       └── panels/
│   │   │           └── appearance.tsx
│   │   └── types/
│   │       └── api.ts           ← generated from /openapi.json
│   └── tests/
│       └── ...                  ← Vitest + @solidjs/testing-library
├── tests/
│   ├── unit/
│   │   └── api/                 ← new unit tests for src/api
│   └── integration/
│       └── api/                 ← new integration tests (testcontainers)
└── pyproject.toml               ← +fastapi, +uvicorn[standard], +passlib[bcrypt]
```

## 5. Backend design

### 5.1 Data model

Two new tables. Migration: `alembic/versions/20260408_foundation.py`.

```python
class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True)
    username      = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

class UiSetting(Base):
    __tablename__ = "ui_settings"
    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, server_default="1")
    key     = Column(String(64), nullable=False)
    value   = Column(JSONB, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_ui_settings_user_key"),)
```

The `user_id` default of `1` is the forward-compat crutch. It is
explicitly documented as debt to be removed by the multi-user sub-project
via `ALTER TABLE ui_settings ALTER COLUMN user_id DROP DEFAULT`.

Foundation does **not** touch existing tables (`stocks`, `daily_candles`,
`scanner_results`, etc.). Those are either global or owned by later
sub-projects that will add `user_id` as appropriate when they're reworked.

### 5.2 Migration seed

The migration's `upgrade()`:

1. Creates `users` and `ui_settings`.
2. Reads `APP_USERNAME` and `APP_PASSWORD` from the environment; raises
   `RuntimeError` if either is missing.
3. Hashes the password with `passlib[bcrypt]` (12 rounds).
4. Inserts the single user with `id=1`.
5. Seeds `ui_settings` for user 1:
   - `theme` → `"dark"`
   - `timezone` → `"America/New_York"`

`downgrade()` drops both tables.

`src/config.py` adds `APP_USERNAME` and `APP_PASSWORD` as required settings
and documents that they are read only by the migration. The running app
reads auth data from the `users` table.

### 5.3 Auth

**Password hashing:** `passlib[bcrypt]`, 12 rounds. Constant-time verify.

**Session store:** module-level dict in `src/api/auth.py`:

```python
SESSIONS: dict[str, SessionData] = {}  # token → {user_id, expires_at}
SESSION_TTL = timedelta(hours=12)
```

Tokens are 256-bit random values from `secrets.token_urlsafe(32)`. Sessions
are lost on process restart — documented tradeoff, escape hatch described
in §11.

**Login** (`POST /api/auth/login`, body `{username, password}`):
- Fetch user by username. If missing or password mismatches, return 401.
- Generate token, store `{user_id, expires_at}`, return
  `Set-Cookie: session=<token>; HttpOnly; Secure; SameSite=Lax; Path=/`.
- Rate limit: 5 failed attempts per IP in a rolling 60-second window
  triggers a 60-second lockout (in-memory).

**Logout** (`POST /api/auth/logout`): delete the session, clear cookie.

**Middleware** (`SessionMiddleware`, custom, in `src/api/auth.py`): on
every request, read the `session` cookie, validate against `SESSIONS`,
attach `request.state.user_id` on success. Expired sessions are removed
lazily on access.

### 5.4 `get_current_user` dependency

The forward-compat centerpiece. Every user-scoped endpoint uses it:

```python
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(401, "not authenticated")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "user not found")
    return user
```

**No endpoint anywhere in the codebase may hardcode `user_id=1`.** Multi-user
conversion later changes only the middleware that populates
`request.state.user_id` — the dependency and every consumer stay the same.

### 5.5 Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | No | Liveness probe; returns `{status: "ok"}` |
| POST | `/api/auth/login` | No | Authenticate, set session cookie |
| POST | `/api/auth/logout` | Yes | Invalidate session |
| GET | `/api/me` | Yes | Return current user `{id, username}` |
| GET | `/api/settings` | Yes | Return all `ui_settings` rows for current user as `{key: value, ...}` |
| PUT | `/api/settings` | Yes | Upsert provided keys; return full settings |

`PUT /api/settings` uses Postgres `INSERT ... ON CONFLICT (user_id, key)
DO UPDATE` to avoid read-modify-write races.

### 5.6 WebSocket

Single endpoint: `/ws`.

**Handshake:** the browser sends the session cookie automatically on same-
origin WS connections. The endpoint reads `websocket.cookies["session"]`,
validates via the same session store. Invalid/missing cookie → close with
code 1008 (policy violation).

**Protocol (JSON messages, text frames):**

- Client → server: `{"op": "subscribe", "topic": "<topic>"}`
- Client → server: `{"op": "unsubscribe", "topic": "<topic>"}`
- Client → server: `{"op": "ping"}` → server replies `{"op": "pong"}`
- Server → client: `{"topic": "<topic>", "data": <any>}`

**PubSubRegistry** (in `src/api/ws.py`): maps `topic: str → set[WebSocket]`.
Methods: `subscribe(ws, topic)`, `unsubscribe(ws, topic)`, `publish(topic,
data)`, `disconnect(ws)` (removes from all topics). All operations are
guarded by an `asyncio.Lock`.

**Heartbeat task:** a lifespan-managed background task publishes
`{"topic": "system:heartbeat", "data": {"ts": <iso>}}` every 5 seconds.
This is the only publisher Foundation ships. Real topics (`quotes:*`,
`alerts:*`) are wired in by later sub-projects.

### 5.7 App factory and lifespan

```python
# src/api/main.py
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: begin heartbeat task
    task = asyncio.create_task(heartbeat_loop(pubsub))
    yield
    # shutdown: cancel heartbeat, close all sockets
    task.cancel()
    await pubsub.close_all()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="market-data")
    app.add_middleware(SessionMiddleware)
    app.include_router(auth_router,     prefix="/api/auth")
    app.include_router(me_router,       prefix="/api")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(health_router,   prefix="/api")
    app.add_api_websocket_route("/ws", ws_endpoint)
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
```

Launch command (documented in README):

```bash
uvicorn src.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

## 6. Frontend design

### 6.1 API client

`src/lib/api.ts` is a typed `fetch` wrapper that uses TypeScript types
generated from FastAPI's `/openapi.json` schema:

```bash
pnpm generate:types
# runs: openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts
```

Codegen is a dev-time step. The generated `src/types/api.ts` is checked
in. A CI job runs the codegen and fails the build if the file changes,
catching drift.

The wrapper:
- Sets `credentials: "include"` on every request so the session cookie is
  sent.
- Parses JSON responses.
- On 401, clears the `currentUser` store and redirects to `/login`.
- Throws on non-2xx with a typed error.

### 6.2 WebSocket client

`src/lib/ws.ts` exposes a singleton `WsClient`:

- **Single connection** for the entire app.
- `ws.subscribe(topic, handler)` → returns an unsubscribe function.
- **Auto-reconnect** on close: exponential backoff 1s → 30s cap.
- **Re-subscribe on reconnect:** remembers active topics and re-issues
  `subscribe` ops after the new connection opens.
- **Status signal** (`ws.status: "connecting" | "open" | "closed"`) is a
  Solid signal consumed by the nav bar's status dot.
- Foundation subscribes to exactly one topic: `"system:heartbeat"`.

### 6.3 Auth state

`src/lib/auth.ts` exposes a Solid store:

```ts
const [currentUser, setCurrentUser] =
    createStore<{ id: number; username: string } | null>(null);
```

On app boot, `main.tsx` calls `GET /api/me`. Success populates the store;
401 redirects to `/login`. The router uses a `<RequireAuth>` guard.
`POST /api/auth/logout` clears the store and navigates to `/login`.

### 6.4 Routing

| Path | Component | Guard |
|---|---|---|
| `/` | redirect to `/dashboard` | — |
| `/login` | `LoginPage` | none |
| `/dashboard` | `DashboardPage` (placeholder) | `RequireAuth` |
| `/settings` | redirect to `/settings/appearance` | `RequireAuth` |
| `/settings/:panelId` | `SettingsPage` → renders panel by id | `RequireAuth` |

### 6.5 App shell

`app.tsx` is a top nav bar with: app title, nav links (Dashboard,
Settings), user menu (username + Logout), WebSocket status dot (green =
open, yellow = connecting, red = closed). The main area is a
`<Outlet />` for the current route.

### 6.6 Settings panel registry

The key extensibility primitive. `src/pages/settings/registry.ts`:

```ts
export interface SettingsPanel {
    id: string;
    label: string;
    component: Component;
    order: number;
}

export const settingsPanels: SettingsPanel[] = [
    { id: "appearance", label: "Appearance", component: AppearancePanel, order: 0 },
    // Future sub-projects append here.
];
```

`SettingsPage` renders a two-pane layout: left sidebar lists panels sorted
by `order`; right pane renders the selected panel based on `panelId`. An
unknown `panelId` renders a 404 within the settings page.

Adding a new panel in a future sub-project is: create a component file,
append to the array, done. Zero Foundation changes.

### 6.7 Appearance panel

Foundation's single panel. Fields:

- **Theme**: radio — `light` / `dark` (default `dark`).
- **Timezone**: select, populated from an IANA tz list
  (`Intl.supportedValuesOf("timeZone")`).

On mount: `GET /api/settings` → populate form. On save: `PUT /api/settings`
with changed keys → update global `settingsStore` → apply theme via
`document.documentElement.dataset.theme = "dark"`, which flips CSS custom
properties defined in `index.css`.

### 6.8 Dev workflow

```bash
# terminal 1: backend
uvicorn src.api.main:create_app --factory --reload --port 8000

# terminal 2: frontend
cd frontend && pnpm dev    # Vite on :5173, proxies /api + /ws → :8000
```

Vite config proxies both HTTP and WebSocket. In production, `pnpm build`
emits `frontend/dist/`, which FastAPI's `StaticFiles` mount serves.

## 7. Data flow: end-to-end walkthrough

**Scenario:** user toggles theme from light to dark.

1. User is on `/settings/appearance`. The panel mounted and called
   `GET /api/settings`. Middleware validated the session cookie and
   attached `request.state.user_id = 1`.
   `get_current_user` fetched user 1. The endpoint queried
   `SELECT key, value FROM ui_settings WHERE user_id = 1` and returned
   the dict. The panel's form is populated.
2. User clicks the "dark" radio. A local Solid signal updates. The save
   button becomes enabled. Nothing has left the browser yet.
3. User clicks Save. `api.put("/api/settings", { body: { theme: "dark" }})`
   fires. The typed client ensures the body shape matches the generated
   TypeScript type derived from the Pydantic model.
4. FastAPI handler runs: `get_current_user` returns user 1; an upsert
   `INSERT INTO ui_settings ... ON CONFLICT (user_id, key) DO UPDATE`
   persists the change; the handler re-reads all settings for user 1 and
   returns them.
5. Client receives response, replaces the global `settingsStore`, and sets
   `document.documentElement.dataset.theme = "dark"`. CSS custom properties
   re-resolve; the UI repaints dark instantly.
6. In the background, the WebSocket connection has been receiving
   `system:heartbeat` messages throughout. The nav bar status dot stays
   green. The REST round-trip did not disturb it.

If this flow works end-to-end in a test, Foundation has exercised every
layer: auth middleware, `get_current_user`, typed API client, Pydantic
contract, `user_id`-scoped query, upsert pattern, panel registry, global
settings propagation, and WebSocket independence.

## 8. Error handling

| Layer | Failure | Behavior |
|---|---|---|
| Auth middleware | Missing/expired cookie | 401 for `/api/*` except `/api/health` and `/api/auth/login`; no redirect (client handles) |
| Login rate limit | >5 failures / IP / 60s | 429 for 60s |
| `get_current_user` | `user_id` valid but user row missing | 401 + server-side warning log |
| Settings PUT | Unknown key | 400 with list of allowed keys; nothing persisted |
| Settings PUT | Invalid value shape | 422 from Pydantic validation |
| WebSocket | Missing/invalid cookie at handshake | Close 1008 |
| WebSocket | Client sends invalid JSON | Send `{op: "error", message: ...}`; do not close |
| WebSocket | Client disconnects | `disconnect()` on registry; background heartbeat keeps running |
| Frontend | `fetch` network error | User-visible toast "Connection lost"; retry manual |
| Frontend | 401 on any request | Clear `currentUser`; redirect to `/login` |
| Frontend | WS disconnect | Auto-reconnect w/ backoff; status dot goes yellow → red |

## 9. Testing strategy

### 9.1 Backend unit tests (no DB)

- `test_auth.py`: password hash round-trip; session token uniqueness; rate
  limiter counter logic.
- `test_ws_registry.py`: subscribe/unsubscribe; publish reaches subscribers;
  disconnect removes from all topics; concurrent subscribe safety.
- `test_deps.py`: `get_current_user` raises 401 when `request.state.user_id`
  is missing; raises 401 when user row absent.

### 9.2 Backend integration tests (testcontainers Postgres)

Follows existing `tests/conftest.py` pattern.

- `test_migration.py`: applies to fresh DB; `users` row seeded from env;
  `ui_settings` seeded with theme=dark, timezone; migration reversible.
- `test_auth_flow.py`: correct login → 200 + cookie; wrong password → 401;
  logout invalidates session; expired session → 401; rate limit triggers
  after 5 failures.
- `test_me_endpoint.py`: authenticated → 200; unauthenticated → 401.
- `test_settings_endpoint.py`: GET returns seeded defaults; PUT upserts new
  value; second PUT updates in place; unauthenticated → 401; unknown key
  → 400.
- `test_ws_endpoint.py`: connect without cookie → close 1008; connect with
  cookie → receive heartbeat within 6s; subscribe + unsubscribe behavior;
  client disconnect cleans up.

Coverage target for backend Foundation code: ≥ 85% (existing repo convention
from `pyproject.toml` enforces `--cov=src`).

### 9.3 Frontend tests (Vitest + @solidjs/testing-library)

- `api.test.ts`: wrapper attaches credentials; 401 clears currentUser;
  typed errors thrown on non-2xx.
- `ws.test.ts`: subscribe returns working unsubscribe; reconnect
  re-subscribes; backoff escalates on repeated failures.
- `auth.test.tsx`: login posts credentials; `RequireAuth` redirects
  unauthenticated; `currentUser` populated from `/me`.
- `appearance-panel.test.tsx`: renders seeded values; changing radio marks
  dirty; save calls PUT; global store updates.
- `settings-registry.test.tsx`: renders all registered panels; unknown
  `panelId` shows 404.

Coverage target: ≥ 80% for `src/lib/*`, ≥ 70% overall frontend.

### 9.4 End-to-end smoke test (Playwright, one test)

Fresh DB → run migration → start FastAPI → start Vite → open `/login` →
submit credentials → navigate to `/settings/appearance` → toggle theme to
light → save → reload → assert theme is light (persisted). This is the
walkthrough in §7 as automation.

## 10. Security

- Session cookies: `HttpOnly; Secure; SameSite=Lax; Path=/`.
- TLS: **required** for any non-localhost deployment; must be terminated by
  an external proxy (Caddy / Cloudflare Tunnel / Tailscale Funnel / nginx).
  FastAPI speaks plain HTTP. README documents this explicitly.
- Default bind: `127.0.0.1:8000`. Remote exposure is opt-in via the
  tunnel/proxy.
- Password hashing: `passlib[bcrypt]`, 12 rounds.
- Session tokens: 256-bit random via `secrets.token_urlsafe(32)`.
- Login rate limit: 5 failures / IP / 60s, in-memory.
- WebSocket handshake auth uses the same session cookie.
- No secrets in generated TypeScript: the OpenAPI schema excludes
  environment variables.

## 11. Known debts and escape hatches

1. **In-memory session store loses sessions on restart.** Escape hatch: a
   `sessions` table + ~30 lines to swap the dict for DB queries. The
   `get_current_user` dependency and all consumers are unaffected.
2. **`ui_settings.user_id` defaults to 1.** Must be removed by the
   multi-user sub-project via
   `ALTER TABLE ui_settings ALTER COLUMN user_id DROP DEFAULT` plus a
   backfill step.
3. **OpenAPI codegen drift.** Mitigated by a CI job that regenerates
   `frontend/src/types/api.ts` and fails on diff. Local `make generate-types`
   target provided.
4. **WebSocket cookie auth assumes same-origin.** Future deployment with a
   different frontend origin will require token-based WS auth. Documented
   in `src/api/ws.py`.
5. **Migration reads env vars** (`APP_USERNAME`, `APP_PASSWORD`). Unusual
   for Alembic migrations but justified by the one-user-forever invariant.
   Multi-user sub-project will replace this with a proper bootstrap flow.

## 12. Dependencies added

**Python** (`pyproject.toml`):
- `fastapi`
- `uvicorn[standard]`
- `passlib[bcrypt]`
- (existing: sqlalchemy, alembic, pydantic, click, apscheduler)

**Node** (`frontend/package.json`):
- `solid-js`
- `@solidjs/router`
- `@solid-primitives/storage`
- `open-props`
- Dev: `vite`, `vite-plugin-solid`, `typescript`, `vitest`,
  `@solidjs/testing-library`, `@playwright/test`, `openapi-typescript`

## 13. Acceptance criteria

Foundation is complete when **all** of the following are true:

1. `alembic upgrade head` on a fresh DB creates `users` + `ui_settings`,
   seeds user 1 from `APP_USERNAME`/`APP_PASSWORD`, and seeds default
   appearance settings.
2. `uvicorn src.api.main:create_app --factory` starts cleanly on
   `127.0.0.1:8000`.
3. `cd frontend && pnpm dev` starts Vite and proxies `/api` and `/ws` to
   FastAPI.
4. Navigating to the dev URL redirects to `/login` when unauthenticated.
5. Submitting correct credentials sets a session cookie and redirects to
   `/dashboard`, showing `"Hello, <username>"`.
6. Navigating to `/settings/appearance` shows the seeded theme (dark) and
   timezone.
7. Toggling theme to light and saving persists: reloading the page shows
   light theme.
8. The nav bar WebSocket status dot is green; disconnecting the backend
   turns it red; reconnecting turns it green with no manual intervention.
9. All backend unit + integration tests pass.
10. All frontend unit tests pass.
11. The Playwright end-to-end smoke test passes.
12. `make ci` (lint + type-check + tests) passes for both backend and
    frontend.
13. Backend coverage ≥ 85% on Foundation code.
14. Frontend coverage ≥ 80% on `src/lib/*`, ≥ 70% overall.
