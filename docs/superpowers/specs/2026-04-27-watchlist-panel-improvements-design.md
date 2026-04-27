# Watchlist Panel Improvements — Design Spec

**Date:** 2026-04-27
**Status:** Approved

---

## Problem

Three issues with the current watchlist left panel:

1. **Ticker column too narrow** — 38px clips 5-character symbols (GOOGL, NVIDA)
2. **Keyboard navigation unreliable** — multiple expanded watchlist groups each call `onRegisterSymbolRefs`, overwriting a single shared signal in `WatchlistPanel`; only the last group to register is navigable
3. **No column headers or sort** — users cannot identify columns or reorder symbols

---

## Changes

### 1. Panel and ticker width

- `watchlist-layout__panel`: 260px → 300px
- `.symbol-ticker`: 38px → 56px
- All other column widths unchanged

**Budget check (300px panel, ~8px padding = 292px usable):**

```
dot(10) + ticker(56) + spark(48) + range(32) + last(40) + chg%(40) + remove(12) + gaps(24) = 262px
```

Fits with 30px to spare.

---

### 2. Keyboard navigation fix

**Root cause:** `WatchlistPanel` holds a single `symbolRefs` signal. Every expanded `CategoryGroup` calls `onRegisterSymbolRefs(refs)` which replaces the signal entirely. The last group to register wins; all others are unreachable via keyboard.

**Fix:** Remove the global keyboard handler from `WatchlistPanel` entirely. Each `CategoryGroup` attaches its own `keydown` listener on `window` and guards with:

```ts
if (!quotes().some(q => q.symbol === props.selectedSymbol)) return;
```

Only the group containing the selected symbol acts. Navigation stays within that group's quote list.

**ArrowLeft (delete) behaviour:**
- Remove the selected symbol
- If more symbols remain: select the next one down, or the one above if at the last position
- If no symbols remain: call `props.onSymbolSelect(null)`

**Cleanup from `WatchlistPanel`:**
- Remove `symbolRefs` signal
- Remove `focusedSymbol` signal
- Remove `onRegisterSymbolRefs` prop and handler
- Remove `handleKeyDown` and the `window.addEventListener('keydown', ...)` call

**`SymbolRow` change:**
- Remove `focused` prop — `selected` is sufficient (keyboard and mouse selection are now the same state)
- Remove `focused` CSS class and outline rule

**`CategoryGroup` change:**
- Remove `focusedSymbol` prop
- Add `keydown` listener in `onMount` (cleaned up in `onCleanup`)

---

### 3. Column headers with sort

A header row is added inside each `CategoryGroup`, rendered immediately above the symbol list when expanded.

**Header layout (mirrors symbol row columns):**

```
[·] [TICKER ▲] [——] [——] [LAST] [CHG%] [×]
 dot  sortable  spark range sortable sortable  remove
```

Dot, sparkline, range, and remove columns show no label — spacer `<div>` elements maintain alignment.

**Sort state (lives in `CategoryGroup`):**

```ts
const [sortCol, setSortCol] = createSignal<'ticker' | 'last' | 'chg_pct' | null>(null);
const [sortDir, setSortDir] = createSignal<'asc' | 'desc'>('asc');
```

**Double-click cycle:** none → asc → desc → none

**Sort indicator:** active column shows `▲` (asc) or `▼` (desc); inactive columns show no indicator.

**Sorted quotes:** a `createMemo` derives `sortedQuotes` from `quotes()` + `sortCol()` + `sortDir()`. Default (no sort) preserves original API order.

```ts
const sortedQuotes = createMemo(() => {
  const col = sortCol();
  if (!col) return quotes();
  const dir = sortDir() === 'asc' ? 1 : -1;
  return [...quotes()].sort((a, b) => {
    if (col === 'ticker') return dir * a.symbol.localeCompare(b.symbol);
    const av = col === 'last' ? (a.last ?? -Infinity) : (a.change_pct ?? -Infinity);
    const bv = col === 'last' ? (b.last ?? -Infinity) : (b.change_pct ?? -Infinity);
    return dir * (av - bv);
  });
});
```

**Header component:** inline in `CategoryGroup` — no separate file needed given its simplicity.

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/index.css` | Panel 260→300px; ticker 38→56px; add header row styles |
| `frontend/src/pages/watchlists/dashboard.tsx` | No change |
| `frontend/src/pages/watchlists/watchlist-panel.tsx` | Remove `symbolRefs`, `focusedSymbol`, `onRegisterSymbolRefs`, global keydown handler |
| `frontend/src/pages/watchlists/category-group.tsx` | Add keydown listener, sort state, `sortedQuotes` memo, header row; remove `focusedSymbol` prop |
| `frontend/src/pages/watchlists/symbol-row.tsx` | Remove `focused` prop |
| `frontend/src/pages/watchlists/types.ts` | Remove `WatchlistSymbolRef` type |

---

## Out of Scope

- Persist sort preference across sessions
- Sort within the chart pane or detail view
- Resizable panel width
