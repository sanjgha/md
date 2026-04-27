# Watchlist Panel Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the ticker column, fix keyboard navigation so it works reliably within the active watchlist, and add sortable column headers to each watchlist group.

**Architecture:** Extract pure navigation and sort helpers into `watchlist-utils.ts` (tested in isolation), then wire them into `CategoryGroup` (which takes over keyboard handling from `WatchlistPanel`). Column headers live inside each `CategoryGroup` with local sort state.

**Tech Stack:** SolidJS, TypeScript, Vitest, `@solidjs/testing-library`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/pages/watchlists/watchlist-utils.ts` | **Create** | Pure helpers: `navigateQuotes`, `sortQuotes` |
| `frontend/src/pages/watchlists/watchlist-utils.test.ts` | **Create** | Unit tests for helpers |
| `frontend/src/pages/watchlists/symbol-row.tsx` | **Modify** | Remove `focused` prop |
| `frontend/src/pages/watchlists/symbol-row.test.tsx` | **Modify** | Remove `focused={false}` from all renders |
| `frontend/src/pages/watchlists/watchlist-panel.tsx` | **Modify** | Remove keyboard handler, `symbolRefs`, `focusedSymbol`, `onRegisterSymbolRefs` |
| `frontend/src/pages/watchlists/category-group.tsx` | **Modify** | Add keyboard handler, sort state, `sortedQuotes` memo, header row |
| `frontend/src/pages/watchlists/types.ts` | **Modify** | Remove `WatchlistSymbolRef` interface |
| `frontend/src/index.css` | **Modify** | Panel 260→300px, ticker 38→56px, remove `.symbol-row.focused`, add header styles |

---

## Task 1: Create `navigateQuotes` helper with tests

**Files:**
- Create: `frontend/src/pages/watchlists/watchlist-utils.ts`
- Create: `frontend/src/pages/watchlists/watchlist-utils.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/pages/watchlists/watchlist-utils.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { navigateQuotes } from "./watchlist-utils";
import type { QuoteResponse } from "./types";

const q = (symbol: string): QuoteResponse => ({
  symbol,
  last: 100,
  low: 90,
  high: 110,
  change: 1,
  change_pct: 1,
  source: "realtime",
  date: null,
  intraday: [],
});

describe("navigateQuotes", () => {
  const quotes = [q("AAPL"), q("TSLA"), q("MSFT")];

  it("moves down to next symbol", () => {
    expect(navigateQuotes(quotes, "AAPL", "down")).toBe("TSLA");
  });

  it("wraps from last to first on ArrowDown", () => {
    expect(navigateQuotes(quotes, "MSFT", "down")).toBe("AAPL");
  });

  it("moves up to previous symbol", () => {
    expect(navigateQuotes(quotes, "TSLA", "up")).toBe("AAPL");
  });

  it("wraps from first to last on ArrowUp", () => {
    expect(navigateQuotes(quotes, "AAPL", "up")).toBe("MSFT");
  });

  it("returns first symbol when current is null", () => {
    expect(navigateQuotes(quotes, null, "down")).toBe("AAPL");
  });

  it("returns null for empty quotes", () => {
    expect(navigateQuotes([], "AAPL", "down")).toBeNull();
  });

  it("returns first symbol when current is unknown", () => {
    expect(navigateQuotes(quotes, "GOOG", "down")).toBe("AAPL");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/pages/watchlists/watchlist-utils.test.ts
```

Expected: FAIL — `Cannot find module './watchlist-utils'`

- [ ] **Step 3: Create the helper**

Create `frontend/src/pages/watchlists/watchlist-utils.ts`:

```ts
import type { QuoteResponse } from "./types";

export function navigateQuotes(
  quotes: QuoteResponse[],
  currentSymbol: string | null,
  direction: "up" | "down"
): string | null {
  if (quotes.length === 0) return null;
  if (currentSymbol === null) return quotes[0].symbol;
  const idx = quotes.findIndex((q) => q.symbol === currentSymbol);
  if (idx === -1) return quotes[0].symbol;
  if (direction === "down") return quotes[(idx + 1) % quotes.length].symbol;
  return quotes[idx <= 0 ? quotes.length - 1 : idx - 1].symbol;
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run src/pages/watchlists/watchlist-utils.test.ts
```

Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/watchlists/watchlist-utils.ts \
        frontend/src/pages/watchlists/watchlist-utils.test.ts
git commit -m "feat: add navigateQuotes helper for watchlist keyboard nav"
```

---

## Task 2: Add `sortQuotes` helper with tests

**Files:**
- Modify: `frontend/src/pages/watchlists/watchlist-utils.ts`
- Modify: `frontend/src/pages/watchlists/watchlist-utils.test.ts`

- [ ] **Step 1: Add failing tests**

Append to `frontend/src/pages/watchlists/watchlist-utils.test.ts`:

```ts
import { sortQuotes } from "./watchlist-utils";

describe("sortQuotes", () => {
  const quotes: QuoteResponse[] = [
    { ...q("TSLA"), last: 250, change_pct: 3.5 },
    { ...q("AAPL"), last: 186, change_pct: -1.2 },
    { ...q("MSFT"), last: 415, change_pct: 0.8 },
  ];

  it("sorts by ticker asc", () => {
    expect(sortQuotes(quotes, "ticker", "asc").map((r) => r.symbol)).toEqual([
      "AAPL",
      "MSFT",
      "TSLA",
    ]);
  });

  it("sorts by ticker desc", () => {
    expect(sortQuotes(quotes, "ticker", "desc").map((r) => r.symbol)).toEqual([
      "TSLA",
      "MSFT",
      "AAPL",
    ]);
  });

  it("sorts by last price asc", () => {
    expect(sortQuotes(quotes, "last", "asc").map((r) => r.symbol)).toEqual([
      "AAPL",
      "TSLA",
      "MSFT",
    ]);
  });

  it("sorts by chg_pct desc", () => {
    expect(sortQuotes(quotes, "chg_pct", "desc").map((r) => r.symbol)).toEqual([
      "TSLA",
      "MSFT",
      "AAPL",
    ]);
  });

  it("returns original order when col is null", () => {
    expect(sortQuotes(quotes, null, "asc").map((r) => r.symbol)).toEqual([
      "TSLA",
      "AAPL",
      "MSFT",
    ]);
  });

  it("does not mutate the original array", () => {
    const original = quotes.map((r) => r.symbol);
    sortQuotes(quotes, "ticker", "asc");
    expect(quotes.map((r) => r.symbol)).toEqual(original);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run src/pages/watchlists/watchlist-utils.test.ts
```

Expected: FAIL — `sortQuotes is not a function`

- [ ] **Step 3: Add `sortQuotes` to the helper file**

Append to `frontend/src/pages/watchlists/watchlist-utils.ts`:

```ts
export function sortQuotes(
  quotes: QuoteResponse[],
  col: "ticker" | "last" | "chg_pct" | null,
  dir: "asc" | "desc"
): QuoteResponse[] {
  if (!col) return quotes;
  const d = dir === "asc" ? 1 : -1;
  return [...quotes].sort((a, b) => {
    if (col === "ticker") return d * a.symbol.localeCompare(b.symbol);
    const av = col === "last" ? (a.last ?? -Infinity) : (a.change_pct ?? -Infinity);
    const bv = col === "last" ? (b.last ?? -Infinity) : (b.change_pct ?? -Infinity);
    return d * (av - bv);
  });
}
```

- [ ] **Step 4: Run all helper tests**

```bash
cd frontend && npx vitest run src/pages/watchlists/watchlist-utils.test.ts
```

Expected: 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/watchlists/watchlist-utils.ts \
        frontend/src/pages/watchlists/watchlist-utils.test.ts
git commit -m "feat: add sortQuotes helper for watchlist column sort"
```

---

## Task 3: Remove `focused` prop from `SymbolRow`

**Files:**
- Modify: `frontend/src/pages/watchlists/symbol-row.tsx`
- Modify: `frontend/src/pages/watchlists/symbol-row.test.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Write a failing test that renders without `focused`**

Add this test to `frontend/src/pages/watchlists/symbol-row.test.tsx` (after the existing tests):

```ts
it("renders without focused prop", () => {
  const { container } = render(() => (
    <SymbolRow
      quote={baseQuote}
      selected={false}
      onSelect={() => {}}
      onRemove={() => {}}
    />
  ));
  expect(container.querySelector(".symbol-row")).not.toBeNull();
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npx vitest run src/pages/watchlists/symbol-row.test.tsx
```

Expected: FAIL — TypeScript error: Property `focused` is missing

- [ ] **Step 3: Remove `focused` from `SymbolRow`**

In `frontend/src/pages/watchlists/symbol-row.tsx`, update the interface and component:

```ts
// Remove from interface:
interface SymbolRowProps {
  quote: QuoteResponse;
  selected: boolean;
  // focused: boolean;  <-- DELETE THIS LINE
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}
```

In the JSX, change:
```tsx
// FROM:
classList={{ selected: props.selected, focused: props.focused }}
// TO:
classList={{ selected: props.selected }}
```

- [ ] **Step 4: Remove `focused` from `CategoryGroup`'s JSX** (prevents a TypeScript error before Task 4 completes)

In `frontend/src/pages/watchlists/category-group.tsx`, find the `<SymbolRow` call inside the `<For each={quotes()}>` block and remove the `focused` prop:

```tsx
<SymbolRow
  quote={quote}
  selected={props.selectedSymbol === quote.symbol}
  onSelect={(sym) => props.onSymbolSelect(sym)}
  onRemove={handleRemove}
/>
```

- [ ] **Step 5: Remove the `.symbol-row.focused` CSS rule from `frontend/src/index.css`**

Find and delete:
```css
.symbol-row.focused {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
```

- [ ] **Step 6: Update all existing tests in `symbol-row.test.tsx` to remove `focused={false}`**

Remove `focused={false}` from every `render()` call in the test file. There are 6 render calls (in the 5 existing tests plus the 2 renders inside "determines sparkline color from change"). After editing, every `<SymbolRow ...>` call should have only `quote`, `selected`, `onSelect`, `onRemove`.

- [ ] **Step 7: Run all symbol-row tests**

```bash
cd frontend && npx vitest run src/pages/watchlists/symbol-row.test.tsx
```

Expected: 6 tests PASS (5 original + 1 new)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/watchlists/symbol-row.tsx \
        frontend/src/pages/watchlists/symbol-row.test.tsx \
        frontend/src/pages/watchlists/category-group.tsx \
        frontend/src/index.css
git commit -m "refactor: remove focused prop from SymbolRow"
```

---

## Task 4: Move keyboard nav into `CategoryGroup`, simplify `WatchlistPanel`

This task is a coordinated multi-file change. TypeScript won't compile cleanly until both files and types are updated together — do all steps before running tests.

**Files:**
- Modify: `frontend/src/pages/watchlists/types.ts`
- Modify: `frontend/src/pages/watchlists/watchlist-panel.tsx`
- Modify: `frontend/src/pages/watchlists/category-group.tsx`

- [ ] **Step 1: Remove `WatchlistSymbolRef` from `types.ts`**

In `frontend/src/pages/watchlists/types.ts`, delete:

```ts
export interface WatchlistSymbolRef {
  symbol: string;
  onRemove: () => void;
}
```

- [ ] **Step 2: Rewrite `watchlist-panel.tsx`**

Replace the entire file content with:

```tsx
import { Component, For, Show, createSignal, onMount, onCleanup } from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
import { pollingManager } from "~/lib/polling-manager";
import { CategoryGroup } from "./category-group";
import type { CategoryWatchlists } from "./types";

const LS_KEY = "watchlist-expanded-ids";

function loadExpandedIds(): Set<number> {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return new Set();
    return new Set(JSON.parse(raw) as number[]);
  } catch {
    return new Set();
  }
}

function saveExpandedIds(ids: Set<number>) {
  localStorage.setItem(LS_KEY, JSON.stringify([...ids]));
}

interface WatchlistPanelProps {
  selectedSymbol: string | null;
  onSymbolSelect: (symbol: string | null) => void;
}

export const WatchlistPanel: Component<WatchlistPanelProps> = (props) => {
  const [categories, setCategories] = createSignal<CategoryWatchlists[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal(false);
  const [expandedIds, setExpandedIds] = createSignal<Set<number>>(loadExpandedIds());
  const [refreshCounter, setRefreshCounter] = createSignal(0);

  onMount(async () => {
    try {
      const data = await watchlistsAPI.list();
      setCategories(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }

    pollingManager.start(() => {
      setRefreshCounter((c) => c + 1);
    });

    onCleanup(() => {
      pollingManager.stop();
    });
  });

  function handleExpandChange(watchlistId: number, expanded: boolean) {
    const next = new Set(expandedIds());
    if (expanded) {
      next.add(watchlistId);
    } else {
      next.delete(watchlistId);
    }
    setExpandedIds(next);
    saveExpandedIds(next);
  }

  return (
    <div class="watchlist-panel">
      <Show when={loading()}>
        <div class="watchlist-panel__loading">Loading…</div>
      </Show>

      <Show when={error()}>
        <div class="watchlist-panel__error">Failed to load watchlists</div>
      </Show>

      <Show when={!loading() && !error()}>
        <For each={categories()}>
          {(group) => (
            <>
              <div class="watchlist-panel__category-label">{group.category.name}</div>
              <For each={group.watchlists}>
                {(wl) => (
                  <CategoryGroup
                    watchlist={wl}
                    initiallyExpanded={expandedIds().has(wl.id)}
                    selectedSymbol={props.selectedSymbol}
                    refreshSignal={refreshCounter()}
                    onSymbolSelect={props.onSymbolSelect}
                    onExpandChange={handleExpandChange}
                  />
                )}
              </For>
            </>
          )}
        </For>

        <Show when={categories().length === 0}>
          <div class="watchlist-panel__empty">No watchlists yet.</div>
        </Show>
      </Show>
    </div>
  );
};
```

- [ ] **Step 3: Update `category-group.tsx` — remove ref machinery, add keyboard handler**

**3a.** Update the import block at the top of `frontend/src/pages/watchlists/category-group.tsx`:

```tsx
import {
  Component,
  Show,
  For,
  createSignal,
  onMount,
  onCleanup,
  createEffect,
  untrack,
} from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
import { SymbolRow } from "./symbol-row";
import { navigateQuotes } from "./watchlist-utils";
import type { QuoteResponse, WatchlistSummary } from "./types";
```

**3b.** Update the `CategoryGroupProps` interface — remove `focusedSymbol` and `onRegisterSymbolRefs`:

```ts
interface CategoryGroupProps {
  watchlist: WatchlistSummary;
  initiallyExpanded: boolean;
  selectedSymbol: string | null;
  refreshSignal: number;
  onSymbolSelect: (symbol: string | null) => void;
  onExpandChange: (watchlistId: number, expanded: boolean) => void;
}
```

**3c.** Replace the `onMount` body. The existing `onMount` only calls `fetchQuotes` when initially expanded. Replace it with:

```ts
onMount(() => {
  if (props.initiallyExpanded) {
    fetchQuotes();
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement) return;
    const currentQuotes = quotes();
    if (!currentQuotes.some((q) => q.symbol === props.selectedSymbol)) return;

    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next = navigateQuotes(
        currentQuotes,
        props.selectedSymbol,
        e.key === "ArrowDown" ? "down" : "up"
      );
      if (next !== null) props.onSymbolSelect(next);
    } else if (e.key === "ArrowLeft" && props.selectedSymbol !== null) {
      e.preventDefault();
      const remaining = currentQuotes.filter((q) => q.symbol !== props.selectedSymbol);
      const currentIdx = currentQuotes.findIndex((q) => q.symbol === props.selectedSymbol);
      const nextSymbol =
        remaining.length === 0
          ? null
          : remaining[Math.min(currentIdx, remaining.length - 1)].symbol;
      handleRemove(props.selectedSymbol);
      if (nextSymbol !== null) props.onSymbolSelect(nextSymbol);
    }
  };

  window.addEventListener("keydown", handleKeyDown);
  onCleanup(() => window.removeEventListener("keydown", handleKeyDown));
});
```

**3d.** Delete the entire `createEffect` block that registers symbol refs (the one with the comment "Register symbol refs with parent when quotes change"). Keep only the polling `createEffect`.

The polling effect to keep:
```ts
createEffect(() => {
  props.refreshSignal;
  if (untrack(expanded) && untrack(loaded)) {
    fetchQuotes();
  }
});
```

**3e.** The `SymbolRow` call in the JSX no longer has a `focused` prop — this was already removed in Task 3. Confirm the call looks like:

```tsx
<SymbolRow
  quote={quote}
  selected={props.selectedSymbol === quote.symbol}
  onSelect={(sym) => props.onSymbolSelect(sym)}
  onRemove={handleRemove}
/>
```

- [ ] **Step 4: Run the full test suite**

```bash
cd frontend && npx vitest run
```

Expected: all tests PASS (no TS errors, no test failures)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/watchlists/types.ts \
        frontend/src/pages/watchlists/watchlist-panel.tsx \
        frontend/src/pages/watchlists/category-group.tsx
git commit -m "fix: move keyboard nav into CategoryGroup, remove broken symbolRefs mechanism"
```

---

## Task 5: Add sort state and `sortedQuotes` memo to `CategoryGroup`

**Files:**
- Modify: `frontend/src/pages/watchlists/category-group.tsx`

- [ ] **Step 1: Add `createMemo` to the solid-js import**

Update the import block in `category-group.tsx`:

```tsx
import {
  Component,
  Show,
  For,
  createSignal,
  createMemo,
  onMount,
  onCleanup,
  createEffect,
  untrack,
} from "solid-js";
```

- [ ] **Step 2: Add `sortQuotes` to the utils import**

```ts
import { navigateQuotes, sortQuotes } from "./watchlist-utils";
```

- [ ] **Step 3: Add sort signals and memo inside the component function**

Add after the existing signal declarations (after `const [removeError, setRemoveError] = createSignal...`):

```ts
const [sortCol, setSortCol] = createSignal<"ticker" | "last" | "chg_pct" | null>(null);
const [sortDir, setSortDir] = createSignal<"asc" | "desc">("asc");

const sortedQuotes = createMemo(() => sortQuotes(quotes(), sortCol(), sortDir()));

function handleHeaderDblClick(col: "ticker" | "last" | "chg_pct") {
  if (sortCol() !== col) {
    setSortCol(col);
    setSortDir("asc");
  } else if (sortDir() === "asc") {
    setSortDir("desc");
  } else {
    setSortCol(null);
  }
}
```

- [ ] **Step 4: Update the `For` loop in JSX to use `sortedQuotes()`**

Find:
```tsx
<For each={quotes()}>
```
Replace with:
```tsx
<For each={sortedQuotes()}>
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npx vitest run
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/watchlists/category-group.tsx
git commit -m "feat: add sort state and sortedQuotes memo to CategoryGroup"
```

---

## Task 6: Add column header row to `CategoryGroup`

**Files:**
- Modify: `frontend/src/pages/watchlists/category-group.tsx`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add the header row JSX inside the expanded section**

In `category-group.tsx`, inside `<Show when={expanded()}>`, add the header row immediately before `<div class="category-group__symbols">`:

```tsx
<Show when={expanded()}>
  {/* Column header */}
  <div class="symbol-header">
    <span class="symbol-header__dot" />
    <button
      class="symbol-header__cell symbol-header__ticker"
      onDblClick={() => handleHeaderDblClick("ticker")}
      title="Double-click to sort"
    >
      {`Ticker${sortCol() === "ticker" ? (sortDir() === "asc" ? " ▲" : " ▼") : ""}`}
    </button>
    <span class="symbol-header__spark" />
    <span class="symbol-header__range" />
    <button
      class="symbol-header__cell symbol-header__last"
      onDblClick={() => handleHeaderDblClick("last")}
      title="Double-click to sort"
    >
      {`Last${sortCol() === "last" ? (sortDir() === "asc" ? " ▲" : " ▼") : ""}`}
    </button>
    <button
      class="symbol-header__cell symbol-header__change"
      onDblClick={() => handleHeaderDblClick("chg_pct")}
      title="Double-click to sort"
    >
      {`Chg%${sortCol() === "chg_pct" ? (sortDir() === "asc" ? " ▲" : " ▼") : ""}`}
    </button>
    <span class="symbol-header__remove" />
  </div>

  {/* Symbol list — insert the header div above this line; do not modify this div or its children */}
  <div class="category-group__symbols">
</Show>
```

- [ ] **Step 2: Add header CSS to `frontend/src/index.css`**

Add after the `.symbol-row--skeleton` rule block:

```css
/* ===================================================
   SYMBOL HEADER — column labels above symbol rows
   =================================================== */

.symbol-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 0.5rem;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.symbol-header__dot {
  width: 10px;
  flex-shrink: 0;
}

.symbol-header__spark {
  width: 48px;
  flex-shrink: 0;
}

.symbol-header__range {
  width: 32px;
  flex-shrink: 0;
}

.symbol-header__remove {
  width: 12px;
  flex-shrink: 0;
}

.symbol-header__cell {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-size: 0.62rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-2);
  text-align: right;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.symbol-header__cell:hover {
  color: var(--text-1);
}

.symbol-header__ticker {
  width: 56px;
  text-align: left;
}

.symbol-header__last {
  width: 40px;
}

.symbol-header__change {
  width: 40px;
}
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && npx vitest run
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/watchlists/category-group.tsx \
        frontend/src/index.css
git commit -m "feat: add sortable column headers to watchlist group"
```

---

## Task 7: Widen panel and ticker column

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Update panel width**

In `frontend/src/index.css`, find `.watchlist-layout__panel` and change `width`:

```css
/* FROM: */
width: 260px;
/* TO: */
width: 300px;
```

- [ ] **Step 2: Update ticker column width**

Find `.symbol-ticker` and change `width`:

```css
/* FROM: */
width: 38px;
/* TO: */
width: 56px;
```

- [ ] **Step 3: Start the dev server and verify visually**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173/watchlists` and verify:
- Left panel is wider (300px)
- 5-character symbols (GOOGL, MSFT) are fully visible without clipping
- Column header row appears under each expanded watchlist name
- Double-clicking a header label cycles: asc ▲ → desc ▼ → unsorted
- ArrowDown/Up moves selection within the active watchlist, wrapping at edges
- ArrowLeft removes the symbol and moves focus to the next one

- [ ] **Step 4: Run final test suite**

```bash
cd frontend && npx vitest run
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "feat: widen watchlist panel to 300px and ticker column to 56px"
```
