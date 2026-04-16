# Watchlist Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inert watchlist UI with a TradingView-style panel — collapsible groups, realtime/EOD prices per row, inline add/remove, no page navigation.

**Architecture:** Backend adds a `GET /api/watchlists/{id}/quotes` endpoint that batch-queries `realtime_quotes` (today, window fn) then falls back to `daily_candles` (latest 2 rows for change calc) for missing stocks. Frontend replaces the two existing watchlist components with four new SolidJS components: `watchlist-panel` → `category-group` → `symbol-row`, all mounted in a rewritten `dashboard.tsx` split-layout shell.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), SolidJS/TypeScript/Vitest (frontend), pytest + testcontainers (backend tests), @solidjs/testing-library + vitest (frontend tests)

**Spec:** `docs/superpowers/specs/2026-04-16-watchlist-redesign.md`

---

## File Map

**Backend (create/modify):**
- Modify: `src/api/watchlists/schemas.py` — add `QuoteResponse`
- Modify: `src/api/watchlists/service.py` — add `get_quotes()`
- Modify: `src/api/watchlists/routes.py` — add `GET /{id}/quotes`
- Create: `tests/unit/api/test_watchlist_quotes_service.py`
- Create: `tests/integration/api/test_watchlist_quotes_route.py`

**Frontend (create/modify/delete):**
- Modify: `frontend/vite.config.ts` — add vitest config
- Create: `frontend/src/test-setup.ts`
- Modify: `frontend/src/pages/watchlists/types.ts` — add `QuoteResponse`
- Modify: `frontend/src/lib/watchlists-api.ts` — add `getQuotes()`
- Create: `frontend/src/pages/watchlists/symbol-row.tsx`
- Create: `frontend/src/pages/watchlists/symbol-row.test.tsx`
- Create: `frontend/src/pages/watchlists/category-group.tsx`
- Create: `frontend/src/pages/watchlists/watchlist-panel.tsx`
- Rewrite: `frontend/src/pages/watchlists/dashboard.tsx`
- Delete: `frontend/src/pages/watchlists/watchlist-view.tsx`
- Modify: `frontend/src/main.tsx` — remove `/watchlists/:id` route

---

### Task 1: Add `QuoteResponse` Pydantic schema

**Files:**
- Modify: `src/api/watchlists/schemas.py`

- [ ] **Step 1: Add the schema**

At the end of `src/api/watchlists/schemas.py`, append:

```python
class QuoteResponse(BaseModel):
    """Quote data for a single watchlist symbol."""

    symbol: str
    last: Optional[float]
    change: Optional[float]
    change_pct: Optional[float]
    source: str  # "realtime" or "eod"
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
cd /home/ubuntu/projects/md
python -c "from src.api.watchlists.schemas import QuoteResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/api/watchlists/schemas.py
git commit -m "feat: add QuoteResponse schema for watchlist quotes endpoint"
```

---

### Task 2: Add `get_quotes()` to `WatchlistService` (TDD)

**Files:**
- Create: `tests/unit/api/test_watchlist_quotes_service.py`
- Modify: `src/api/watchlists/service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/api/test_watchlist_quotes_service.py`:

```python
"""Unit tests for WatchlistService.get_quotes()."""

from datetime import datetime, date
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.orm import Session

from src.api.watchlists.schemas import QuoteResponse
from src.api.watchlists.service import WatchlistService
from src.db.models import (
    DailyCandle,
    RealtimeQuote,
    Stock,
    User,
    Watchlist,
    WatchlistCategory,
    WatchlistSymbol,
)


def _make_user(db: Session, username: str = "testuser") -> User:
    user = User(username=username, password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_stock(db: Session, symbol: str) -> Stock:
    stock = Stock(symbol=symbol, name=f"{symbol} Inc")
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _make_watchlist(db: Session, user_id: int) -> Watchlist:
    wl = Watchlist(
        user_id=user_id,
        name="Test WL",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


def _add_symbol(db: Session, watchlist_id: int, stock_id: int, priority: int = 0) -> WatchlistSymbol:
    ws = WatchlistSymbol(watchlist_id=watchlist_id, stock_id=stock_id, priority=priority)
    db.add(ws)
    db.commit()
    return ws


class TestGetQuotesOwnership:
    def test_returns_none_for_wrong_owner(self, db_session: Session):
        user1 = _make_user(db_session, "u1")
        user2 = _make_user(db_session, "u2")
        wl = _make_watchlist(db_session, cast(int, user1.id))

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user2.id))
        assert result is None

    def test_returns_empty_list_for_empty_watchlist(self, db_session: Session):
        user = _make_user(db_session)
        wl = _make_watchlist(db_session, cast(int, user.id))

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))
        assert result == []


class TestGetQuotesRealtimePriority:
    def test_realtime_quote_returned_when_present_today(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "AAPL")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        rq = RealtimeQuote(
            stock_id=cast(int, stock.id),
            last=Decimal("186.59"),
            change=Decimal("9.31"),
            change_pct=Decimal("5.25"),
            timestamp=datetime.combine(date.today(), datetime.min.time()),
        )
        db_session.add(rq)
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].last == pytest.approx(186.59)
        assert result[0].change == pytest.approx(9.31)
        assert result[0].change_pct == pytest.approx(5.25)
        assert result[0].source == "realtime"

    def test_old_realtime_quote_falls_back_to_eod(self, db_session: Session):
        """Realtime quote from yesterday should not be used."""
        user = _make_user(db_session)
        stock = _make_stock(db_session, "GSAT")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        from datetime import timedelta
        yesterday = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
        rq = RealtimeQuote(
            stock_id=cast(int, stock.id),
            last=Decimal("79.00"),
            change=Decimal("-1.00"),
            change_pct=Decimal("-1.25"),
            timestamp=yesterday,
        )
        db_session.add(rq)
        # Two daily candles
        dc1 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 15),
            open=Decimal("79.50"), high=Decimal("80.00"),
            low=Decimal("79.00"), close=Decimal("79.85"), volume=10000,
        )
        dc2 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 14),
            open=Decimal("79.00"), high=Decimal("79.90"),
            low=Decimal("78.80"), close=Decimal("79.89"), volume=9000,
        )
        db_session.add_all([dc1, dc2])
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert result[0].source == "eod"
        assert result[0].last == pytest.approx(79.85)


class TestGetQuotesEodFallback:
    def test_eod_change_computed_from_two_candles(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "TSLA")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        dc1 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 15),
            open=Decimal("200.00"), high=Decimal("210.00"),
            low=Decimal("199.00"), close=Decimal("205.00"), volume=50000,
        )
        dc2 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 14),
            open=Decimal("195.00"), high=Decimal("201.00"),
            low=Decimal("194.00"), close=Decimal("200.00"), volume=45000,
        )
        db_session.add_all([dc1, dc2])
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert result[0].source == "eod"
        assert result[0].last == pytest.approx(205.00)
        assert result[0].change == pytest.approx(5.00)
        assert result[0].change_pct == pytest.approx(2.50)

    def test_eod_change_is_null_with_only_one_candle(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "NEWCO")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        dc = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 15),
            open=Decimal("10.00"), high=Decimal("11.00"),
            low=Decimal("9.50"), close=Decimal("10.50"), volume=1000,
        )
        db_session.add(dc)
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert result[0].last == pytest.approx(10.50)
        assert result[0].change is None
        assert result[0].change_pct is None

    def test_symbol_with_no_data_excluded(self, db_session: Session):
        """Symbol with no realtime or EOD data is excluded from results."""
        user = _make_user(db_session)
        stock = _make_stock(db_session, "GHOST")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result == []

    def test_results_ordered_by_symbol_priority(self, db_session: Session):
        user = _make_user(db_session)
        stock_a = _make_stock(db_session, "AAA")
        stock_b = _make_stock(db_session, "BBB")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock_a.id), priority=1)
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock_b.id), priority=0)

        for stock in [stock_a, stock_b]:
            dc = DailyCandle(
                stock_id=cast(int, stock.id),
                timestamp=datetime(2026, 4, 15),
                open=Decimal("10.00"), high=Decimal("11.00"),
                low=Decimal("9.50"), close=Decimal("10.50"), volume=1000,
            )
            db_session.add(dc)
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert len(result) == 2
        assert result[0].symbol == "BBB"  # priority=0 first
        assert result[1].symbol == "AAA"  # priority=1 second
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/ubuntu/projects/md
pytest tests/unit/api/test_watchlist_quotes_service.py -v
```

Expected: `ERRORS` or `AttributeError: type object 'WatchlistService' has no attribute 'get_quotes'`

- [ ] **Step 3: Implement `get_quotes()` in `service.py`**

Add these imports at the top of `src/api/watchlists/service.py` (after existing imports):

```python
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select

from src.db.models import DailyCandle, RealtimeQuote
from src.api.watchlists.schemas import QuoteResponse
```

Add the method to `WatchlistService` (after `get_watchlist_symbols`):

```python
def get_quotes(self, watchlist_id: int, user_id: int) -> Optional[list[QuoteResponse]]:
    """Get price quotes for all symbols in a watchlist.

    Uses realtime_quotes (today only) with EOD daily_candles fallback.
    Batch queries — no per-symbol round-trips.

    Args:
        watchlist_id: ID of the watchlist
        user_id: ID of the authenticated user

    Returns:
        List of QuoteResponse in watchlist priority order,
        None if watchlist not found or not owned by user.
        Symbols with no data in either table are excluded.
    """
    # Ownership check
    watchlist = self.get_watchlist(watchlist_id, user_id)
    if not watchlist:
        return None

    # Get symbols in priority order (reuses existing method with eager stock join)
    symbol_rows = self.get_watchlist_symbols(watchlist_id, user_id)
    if not symbol_rows:
        return []

    stock_ids = [int(ws.stock_id) for ws in symbol_rows]
    stock_id_to_symbol: dict[int, str] = {
        int(ws.stock_id): ws.stock.symbol for ws in symbol_rows
    }

    # --- Batch 1: realtime quotes (today only, latest per stock) ---
    rq_rn = (
        func.row_number()
        .over(
            partition_by=RealtimeQuote.stock_id,
            order_by=RealtimeQuote.timestamp.desc(),
        )
        .label("rn")
    )
    rq_subq = (
        select(
            RealtimeQuote.stock_id,
            RealtimeQuote.last,
            RealtimeQuote.change,
            RealtimeQuote.change_pct,
            rq_rn,
        )
        .where(
            RealtimeQuote.stock_id.in_(stock_ids),
            func.date(RealtimeQuote.timestamp) == date.today(),
        )
        .subquery()
    )
    realtime_rows = self.db_session.execute(
        select(rq_subq).where(rq_subq.c.rn == 1)
    ).all()

    covered_ids: set[int] = {int(row.stock_id) for row in realtime_rows}
    missing_ids: list[int] = [sid for sid in stock_ids if sid not in covered_ids]

    result: dict[int, QuoteResponse] = {}
    for row in realtime_rows:
        result[int(row.stock_id)] = QuoteResponse(
            symbol=stock_id_to_symbol[int(row.stock_id)],
            last=float(row.last) if row.last is not None else None,
            change=float(row.change) if row.change is not None else None,
            change_pct=float(row.change_pct) if row.change_pct is not None else None,
            source="realtime",
        )

    # --- Batch 2: EOD fallback (latest 2 candles per missing stock) ---
    if missing_ids:
        dc_rn = (
            func.row_number()
            .over(
                partition_by=DailyCandle.stock_id,
                order_by=DailyCandle.timestamp.desc(),
            )
            .label("rn")
        )
        dc_subq = (
            select(
                DailyCandle.stock_id,
                DailyCandle.close,
                dc_rn,
            )
            .where(DailyCandle.stock_id.in_(missing_ids))
            .subquery()
        )
        eod_rows = self.db_session.execute(
            select(dc_subq)
            .where(dc_subq.c.rn <= 2)
            .order_by(dc_subq.c.stock_id, dc_subq.c.rn)
        ).all()

        candles_by_stock: dict[int, list] = defaultdict(list)
        for row in eod_rows:
            candles_by_stock[int(row.stock_id)].append(row)

        for stock_id, candles in candles_by_stock.items():
            latest_close = float(candles[0].close) if candles[0].close is not None else None
            if (
                len(candles) >= 2
                and candles[0].close is not None
                and candles[1].close is not None
            ):
                change = float(candles[0].close - candles[1].close)
                prev = float(candles[1].close)
                change_pct = (change / prev * 100) if prev != 0 else None
            else:
                change = None
                change_pct = None

            result[stock_id] = QuoteResponse(
                symbol=stock_id_to_symbol[stock_id],
                last=latest_close,
                change=change,
                change_pct=change_pct,
                source="eod",
            )

    # Return in watchlist priority order; symbols with no data are excluded
    return [result[int(ws.stock_id)] for ws in symbol_rows if int(ws.stock_id) in result]
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/ubuntu/projects/md
pytest tests/unit/api/test_watchlist_quotes_service.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Run mypy**

```bash
mypy src/api/watchlists/service.py --ignore-missing-imports
```

Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_quotes_service.py
git commit -m "feat: add WatchlistService.get_quotes() with batch realtime/EOD fallback"
```

---

### Task 3: Add `GET /api/watchlists/{id}/quotes` route (TDD)

**Files:**
- Create: `tests/integration/api/test_watchlist_quotes_route.py`
- Modify: `src/api/watchlists/routes.py`
- Modify: `src/api/watchlists/schemas.py` (import in routes)

- [ ] **Step 1: Write failing integration tests**

Create `tests/integration/api/test_watchlist_quotes_route.py`:

```python
"""Integration tests for GET /api/watchlists/{id}/quotes."""

from datetime import datetime, date
from decimal import Decimal

from src.db.models import (
    DailyCandle,
    RealtimeQuote,
    Stock,
    Watchlist,
    WatchlistCategory,
    WatchlistSymbol,
)


def _setup_watchlist(db_session, user):
    """Helper: create a watchlist with AAPL (realtime) and GSAT (EOD)."""
    cat = WatchlistCategory(
        user_id=user.id, name="Test", is_system=False, sort_order=0
    )
    db_session.add(cat)
    db_session.commit()

    wl = Watchlist(
        user_id=user.id,
        name="My WL",
        category_id=cat.id,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)

    aapl = Stock(symbol="AAPL", name="Apple Inc")
    gsat = Stock(symbol="GSAT", name="Globalstar")
    db_session.add_all([aapl, gsat])
    db_session.commit()

    ws_aapl = WatchlistSymbol(watchlist_id=wl.id, stock_id=aapl.id, priority=0)
    ws_gsat = WatchlistSymbol(watchlist_id=wl.id, stock_id=gsat.id, priority=1)
    db_session.add_all([ws_aapl, ws_gsat])

    # Realtime for AAPL (today)
    rq = RealtimeQuote(
        stock_id=aapl.id,
        last=Decimal("186.59"),
        change=Decimal("9.31"),
        change_pct=Decimal("5.25"),
        timestamp=datetime.combine(date.today(), datetime.min.time()),
    )
    # EOD for GSAT
    dc1 = DailyCandle(
        stock_id=gsat.id,
        timestamp=datetime(2026, 4, 15),
        open=Decimal("79.50"), high=Decimal("80.00"),
        low=Decimal("79.00"), close=Decimal("79.85"), volume=10000,
    )
    dc2 = DailyCandle(
        stock_id=gsat.id,
        timestamp=datetime(2026, 4, 14),
        open=Decimal("79.00"), high=Decimal("79.90"),
        low=Decimal("78.80"), close=Decimal("79.89"), volume=9000,
    )
    db_session.add_all([rq, dc1, dc2])
    db_session.commit()

    return wl, aapl, gsat


def test_quotes_happy_path(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id}/quotes returns quotes for all symbols."""
    user, _ = seeded_user
    wl, aapl, gsat = _setup_watchlist(db_session, user)

    resp = authenticated_client.get(f"/api/watchlists/{wl.id}/quotes")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 2

    aapl_row = next(r for r in data if r["symbol"] == "AAPL")
    assert aapl_row["last"] == 186.59
    assert aapl_row["change"] == 9.31
    assert aapl_row["source"] == "realtime"

    gsat_row = next(r for r in data if r["symbol"] == "GSAT")
    assert gsat_row["source"] == "eod"
    assert gsat_row["last"] == 79.85


def test_quotes_requires_auth(api_client, db_session):
    """GET /api/watchlists/{id}/quotes returns 401 without session."""
    resp = api_client.get("/api/watchlists/999/quotes")
    assert resp.status_code == 401


def test_quotes_404_wrong_owner(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id}/quotes returns 404 for another user's watchlist."""
    from src.db.models import User
    from src.api.auth import hash_password

    other = User(username="other", password_hash=hash_password("pw"))
    db_session.add(other)
    db_session.commit()

    wl = Watchlist(
        user_id=other.id,
        name="Their WL",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    resp = authenticated_client.get(f"/api/watchlists/{wl.id}/quotes")
    assert resp.status_code == 404


def test_quotes_empty_watchlist(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id}/quotes returns [] for a watchlist with no symbols."""
    user, _ = seeded_user
    wl = Watchlist(
        user_id=user.id,
        name="Empty",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    resp = authenticated_client.get(f"/api/watchlists/{wl.id}/quotes")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/ubuntu/projects/md
pytest tests/integration/api/test_watchlist_quotes_route.py -v
```

Expected: `ERRORS` — route doesn't exist yet

- [ ] **Step 3: Add the route to `routes.py`**

Add this import at the top of `src/api/watchlists/routes.py` (with other schema imports):

```python
from src.api.watchlists.schemas import (
    ...existing imports...,
    QuoteResponse,
)
```

Add the route after the `list_symbols` route (around line 325):

```python
@router.get("/{watchlist_id}/quotes", response_model=list[QuoteResponse])
def get_quotes(
    watchlist_id: int,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[QuoteResponse]:
    """Get price quotes for all symbols in a watchlist.

    Returns realtime quotes where available today, falling back to latest
    EOD candle data. Results are in watchlist priority order.

    Returns 404 if watchlist doesn't exist or isn't owned by the user.
    """
    service = WatchlistService(db)
    quotes = service.get_quotes(watchlist_id, cast(int, user.id))

    if quotes is None:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found",
        )

    return quotes
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/ubuntu/projects/md
pytest tests/integration/api/test_watchlist_quotes_route.py -v
```

Expected: all 4 tests `PASSED`

- [ ] **Step 5: Run full CI**

```bash
make ci
```

Expected: all checks pass

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/routes.py tests/integration/api/test_watchlist_quotes_route.py
git commit -m "feat: add GET /api/watchlists/{id}/quotes endpoint"
```

---

### Task 4: Frontend types + API client

**Files:**
- Modify: `frontend/src/pages/watchlists/types.ts`
- Modify: `frontend/src/lib/watchlists-api.ts`

- [ ] **Step 1: Add `QuoteResponse` to `types.ts`**

Append to `frontend/src/pages/watchlists/types.ts`:

```typescript
/**
 * Price quote for a single watchlist symbol.
 * source: "realtime" = from realtime_quotes (today), "eod" = from daily_candles.
 */
export interface QuoteResponse {
  symbol: string;
  last: number | null;
  change: number | null;
  change_pct: number | null;
  source: 'realtime' | 'eod';
}
```

- [ ] **Step 2: Add `getQuotes()` to `watchlists-api.ts`**

In `frontend/src/lib/watchlists-api.ts`, add to the `watchlistsAPI` object (after `clone`):

```typescript
  /**
   * Get price quotes for all symbols in a watchlist.
   * Returns realtime quotes where available today, EOD fallback otherwise.
   */
  getQuotes: (watchlistId: number): Promise<QuoteResponse[]> =>
    apiFetch(`/api/watchlists/${watchlistId}/quotes`),
```

Also add `QuoteResponse` to the import at the top of the file:

```typescript
import type {
  Watchlist,
  WatchlistCreate,
  Category,
  CategoryCreate,
  WatchlistUpdate,
  CategoryWatchlists,
  QuoteResponse,
} from "../pages/watchlists/types";
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /home/ubuntu/projects/md/frontend
npm run build 2>&1 | head -30
```

Expected: build succeeds (or only pre-existing errors, none from watchlist files)

- [ ] **Step 4: Commit**

```bash
cd /home/ubuntu/projects/md
git add frontend/src/pages/watchlists/types.ts frontend/src/lib/watchlists-api.ts
git commit -m "feat: add QuoteResponse type and getQuotes() API client"
```

---

### Task 5: Configure Vitest + build `symbol-row.tsx` (TDD)

**Files:**
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/test-setup.ts`
- Create: `frontend/src/pages/watchlists/symbol-row.tsx`
- Create: `frontend/src/pages/watchlists/symbol-row.test.tsx`

- [ ] **Step 1: Add Vitest config to `vite.config.ts`**

Replace the full contents of `frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import solidPlugin from "vite-plugin-solid";
import path from "path";

export default defineConfig({
  plugins: [solidPlugin()],
  resolve: {
    alias: {
      "~": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8001",
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    target: "es2020",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    transformMode: { web: [/\.[jt]sx?$/] },
  },
});
```

- [ ] **Step 2: Create test setup file**

Create `frontend/src/test-setup.ts`:

```typescript
import "@testing-library/jest-dom";
```

- [ ] **Step 3: Write failing tests for `symbol-row.tsx`**

Create `frontend/src/pages/watchlists/symbol-row.test.tsx`:

```typescript
import { render, fireEvent } from "@solidjs/testing-library";
import { describe, it, expect, vi } from "vitest";
import { SymbolRow } from "./symbol-row";
import type { QuoteResponse } from "./types";

const realtimeQuote: QuoteResponse = {
  symbol: "AAPL",
  last: 186.59,
  change: 9.31,
  change_pct: 5.25,
  source: "realtime",
};

const eodQuote: QuoteResponse = {
  symbol: "GSAT",
  last: 79.85,
  change: -0.04,
  change_pct: -0.05,
  source: "eod",
};

describe("SymbolRow", () => {
  it("renders symbol ticker", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(getByText("AAPL")).toBeInTheDocument();
  });

  it("renders last price", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(getByText("186.59")).toBeInTheDocument();
  });

  it("renders positive change in green", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    const changeEl = getByText("+9.31");
    expect(changeEl.className).toContain("positive");
  });

  it("renders negative change in red", () => {
    const { getByText } = render(() => (
      <SymbolRow
        quote={eodQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    const changeEl = getByText("-0.04");
    expect(changeEl.className).toContain("negative");
  });

  it("calls onSelect when row is clicked", () => {
    const onSelect = vi.fn();
    const { getByText } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={onSelect}
        onRemove={vi.fn()}
      />
    ));
    fireEvent.click(getByText("AAPL"));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("calls onRemove when remove button is clicked", () => {
    const onRemove = vi.fn();
    const { getByRole } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={onRemove}
      />
    ));
    fireEvent.click(getByRole("button", { name: /remove aapl/i }));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
  });

  it("renders — for null change", () => {
    const nullQuote: QuoteResponse = { ...eodQuote, change: null, change_pct: null };
    const { getAllByText } = render(() => (
      <SymbolRow
        quote={nullQuote}
        selected={false}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("adds selected class when selected=true", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={realtimeQuote}
        selected={true}
        onSelect={vi.fn()}
        onRemove={vi.fn()}
      />
    ));
    expect(container.firstChild).toHaveClass("selected");
  });
});
```

- [ ] **Step 4: Run tests — verify they fail**

```bash
cd /home/ubuntu/projects/md/frontend
npm test 2>&1 | tail -20
```

Expected: `FAIL` — `symbol-row.tsx` doesn't exist

- [ ] **Step 5: Create `symbol-row.tsx`**

Create `frontend/src/pages/watchlists/symbol-row.tsx`:

```typescript
/**
 * SymbolRow — a single stock row in the watchlist panel.
 * Shows: source dot, ticker, last price, change, change%, remove button on hover.
 */

import { Component, Show } from "solid-js";
import type { QuoteResponse } from "./types";

interface SymbolRowProps {
  quote: QuoteResponse;
  selected: boolean;
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}

function fmt(n: number | null, decimals = 2): string {
  if (n === null) return "—";
  return n.toFixed(decimals);
}

function fmtChange(n: number | null): string {
  if (n === null) return "—";
  return n >= 0 ? `+${n.toFixed(2)}` : `${n.toFixed(2)}`;
}

export const SymbolRow: Component<SymbolRowProps> = (props) => {
  const isPositive = () => props.quote.change !== null && props.quote.change >= 0;
  const changeClass = () =>
    props.quote.change === null ? "neutral" : isPositive() ? "positive" : "negative";

  return (
    <div
      class="symbol-row"
      classList={{ selected: props.selected }}
      onClick={() => props.onSelect(props.quote.symbol)}
    >
      <span
        class="source-dot"
        classList={{
          "source-dot--realtime": props.quote.source === "realtime",
          "source-dot--eod": props.quote.source === "eod",
        }}
        title={
          props.quote.source === "realtime"
            ? "Realtime"
            : "End of day"
        }
      />
      <span class="symbol-ticker">{props.quote.symbol}</span>
      <span class="symbol-last">{fmt(props.quote.last)}</span>
      <span class={`symbol-change ${changeClass()}`}>{fmtChange(props.quote.change)}</span>
      <span class={`symbol-change-pct ${changeClass()}`}>
        {props.quote.change_pct !== null ? `${fmtChange(props.quote.change_pct)}%` : "—"}
      </span>
      <button
        class="symbol-remove"
        aria-label={`Remove ${props.quote.symbol}`}
        onClick={(e) => {
          e.stopPropagation();
          props.onRemove(props.quote.symbol);
        }}
      >
        ✕
      </button>
    </div>
  );
};
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
cd /home/ubuntu/projects/md/frontend
npm test 2>&1 | tail -20
```

Expected: all `SymbolRow` tests `PASSED`

- [ ] **Step 7: Commit**

```bash
cd /home/ubuntu/projects/md
git add frontend/vite.config.ts frontend/src/test-setup.ts \
  frontend/src/pages/watchlists/symbol-row.tsx \
  frontend/src/pages/watchlists/symbol-row.test.tsx
git commit -m "feat: add SymbolRow component with vitest config"
```

---

### Task 6: Build `category-group.tsx`

**Files:**
- Create: `frontend/src/pages/watchlists/category-group.tsx`

This component owns: expand state, symbol+quote fetch, add-input visibility, add/remove mutations.

- [ ] **Step 1: Create `category-group.tsx`**

Create `frontend/src/pages/watchlists/category-group.tsx`:

```typescript
/**
 * CategoryGroup — collapsible watchlist group in the left panel.
 *
 * Owns: expanded state, quote data, add-input visibility.
 * Fires: onSymbolSelect(symbol) upward to dashboard.
 */

import {
  Component,
  Show,
  For,
  createSignal,
  onMount,
} from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
import { SymbolRow } from "./symbol-row";
import type { QuoteResponse, WatchlistSummary } from "./types";

interface CategoryGroupProps {
  watchlist: WatchlistSummary;
  initiallyExpanded: boolean;
  selectedSymbol: string | null;
  onSymbolSelect: (symbol: string) => void;
  onExpandChange: (watchlistId: number, expanded: boolean) => void;
}

export const CategoryGroup: Component<CategoryGroupProps> = (props) => {
  const [expanded, setExpanded] = createSignal(props.initiallyExpanded);
  const [quotes, setQuotes] = createSignal<QuoteResponse[]>([]);
  const [quotesLoading, setQuotesLoading] = createSignal(false);
  const [quotesError, setQuotesError] = createSignal(false);
  const [loaded, setLoaded] = createSignal(false);

  const [showAddInput, setShowAddInput] = createSignal(false);
  const [addValue, setAddValue] = createSignal("");
  const [addError, setAddError] = createSignal<string | null>(null);
  const [addLoading, setAddLoading] = createSignal(false);

  const [refreshing, setRefreshing] = createSignal(false);

  async function fetchQuotes() {
    setQuotesLoading(true);
    setQuotesError(false);
    try {
      const data = await watchlistsAPI.getQuotes(props.watchlist.id);
      setQuotes(data);
      setLoaded(true);
    } catch {
      setQuotesError(true);
    } finally {
      setQuotesLoading(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    await fetchQuotes();
    setRefreshing(false);
  }

  function toggleExpand() {
    const next = !expanded();
    setExpanded(next);
    props.onExpandChange(props.watchlist.id, next);
    if (next && !loaded()) {
      fetchQuotes();
    }
  }

  onMount(() => {
    if (props.initiallyExpanded) {
      fetchQuotes();
    }
  });

  async function handleAdd() {
    const symbol = addValue().trim().toUpperCase();
    if (!symbol) return;
    setAddLoading(true);
    setAddError(null);
    try {
      await watchlistsAPI.symbols.add(props.watchlist.id, symbol);
      setAddValue("");
      setShowAddInput(false);
      await fetchQuotes(); // re-fetch to get price for new symbol
    } catch (err: any) {
      const msg: string = err?.message ?? "";
      if (msg.includes("not found")) {
        setAddError(`"${symbol}" not found`);
      } else if (msg.includes("already exists")) {
        setAddError(`"${symbol}" already in this list`);
      } else {
        setAddError("Failed to add — try again");
      }
    } finally {
      setAddLoading(false);
    }
  }

  async function handleRemove(symbol: string) {
    const original = quotes();
    const idx = original.findIndex((q) => q.symbol === symbol);
    // Optimistic remove
    setQuotes(original.filter((q) => q.symbol !== symbol));
    try {
      await watchlistsAPI.symbols.remove(props.watchlist.id, symbol);
    } catch {
      // Restore at original index
      const restored = [...quotes()];
      restored.splice(idx, 0, original[idx]);
      setQuotes(restored);
    }
  }

  return (
    <div class="category-group">
      {/* Header */}
      <div class="category-group__header" onClick={toggleExpand}>
        <span class="category-group__chevron">{expanded() ? "▼" : "▶"}</span>
        <span class="category-group__name">{props.watchlist.name}</span>
        <Show when={expanded()}>
          <button
            class="category-group__refresh"
            classList={{ spinning: refreshing() }}
            aria-label="Refresh quotes"
            onClick={(e) => { e.stopPropagation(); handleRefresh(); }}
          >
            ↻
          </button>
          <button
            class="category-group__add-btn"
            aria-label="Add symbol"
            onClick={(e) => { e.stopPropagation(); setShowAddInput(true); setAddError(null); }}
          >
            +
          </button>
        </Show>
      </div>

      {/* Symbol list */}
      <Show when={expanded()}>
        <div class="category-group__symbols">
          <Show when={quotesLoading() && !loaded()}>
            <For each={Array(Math.max(props.watchlist.symbol_count, 1)).fill(0)}>
              {() => <div class="symbol-row symbol-row--skeleton" />}
            </For>
          </Show>

          <Show when={!quotesLoading() || loaded()}>
            <For each={quotes()}>
              {(quote) => (
                <SymbolRow
                  quote={quote}
                  selected={props.selectedSymbol === quote.symbol}
                  onSelect={props.onSymbolSelect}
                  onRemove={handleRemove}
                />
              )}
            </For>
          </Show>

          <Show when={quotesError()}>
            <div class="category-group__error">
              Prices unavailable —{" "}
              <button onClick={handleRefresh}>↻ retry</button>
            </div>
          </Show>

          {/* Add symbol input */}
          <Show when={showAddInput()}>
            <div class="category-group__add-row">
              <input
                type="text"
                class="category-group__add-input"
                placeholder="Symbol (e.g. TSLA)"
                value={addValue()}
                onInput={(e) => setAddValue(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAdd();
                  if (e.key === "Escape") { setShowAddInput(false); setAddValue(""); }
                }}
                ref={(el) => setTimeout(() => el?.focus(), 0)}
              />
              <button
                class="category-group__add-confirm"
                disabled={addLoading()}
                onClick={handleAdd}
              >
                Add
              </button>
              <button
                class="category-group__add-cancel"
                onClick={() => { setShowAddInput(false); setAddValue(""); setAddError(null); }}
              >
                ✕
              </button>
            </div>
            <Show when={addError()}>
              <div class="category-group__add-error">{addError()}</div>
            </Show>
          </Show>
        </div>
      </Show>
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/ubuntu/projects/md/frontend
npm run build 2>&1 | grep -E "error|Error" | head -10
```

Expected: no errors from `category-group.tsx`

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/projects/md
git add frontend/src/pages/watchlists/category-group.tsx
git commit -m "feat: add CategoryGroup component with expand, quotes, add/remove"
```

---

### Task 7: Build `watchlist-panel.tsx`

**Files:**
- Create: `frontend/src/pages/watchlists/watchlist-panel.tsx`

Owns: category list (from `GET /api/watchlists`), localStorage expansion state.

- [ ] **Step 1: Create `watchlist-panel.tsx`**

Create `frontend/src/pages/watchlists/watchlist-panel.tsx`:

```typescript
/**
 * WatchlistPanel — left pane of the watchlist page.
 *
 * Fetches all categories+watchlists on mount.
 * Persists expansion set in localStorage under "watchlist-expanded-ids".
 * Renders one CategoryGroup per watchlist (not per category header).
 * Category names appear as non-interactive section dividers.
 */

import { Component, For, Show, createSignal, onMount } from "solid-js";
import { watchlistsAPI } from "~/lib/watchlists-api";
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
  onSymbolSelect: (symbol: string) => void;
}

export const WatchlistPanel: Component<WatchlistPanelProps> = (props) => {
  const [categories, setCategories] = createSignal<CategoryWatchlists[]>([]);
  const [loading, setLoading] = createSignal(true);
  const [error, setError] = createSignal(false);
  const [expandedIds, setExpandedIds] = createSignal<Set<number>>(loadExpandedIds());

  onMount(async () => {
    try {
      const data = await watchlistsAPI.list();
      setCategories(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
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
                    onSymbolSelect={props.onSymbolSelect}
                    onExpandChange={handleExpandChange}
                  />
                )}
              </For>
            </>
          )}
        </For>

        <Show when={categories().length === 0}>
          <div class="watchlist-panel__empty">
            No watchlists yet.
          </div>
        </Show>
      </Show>
    </div>
  );
};
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/ubuntu/projects/md/frontend
npm run build 2>&1 | grep -E "error|Error" | head -10
```

Expected: no new errors

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/projects/md
git add frontend/src/pages/watchlists/watchlist-panel.tsx
git commit -m "feat: add WatchlistPanel with localStorage expansion persistence"
```

---

### Task 8: Rewrite `dashboard.tsx`

**Files:**
- Rewrite: `frontend/src/pages/watchlists/dashboard.tsx`

Route shell — owns `selectedSymbol`, renders split layout.

- [ ] **Step 1: Replace `dashboard.tsx`**

Replace the full contents of `frontend/src/pages/watchlists/dashboard.tsx`:

```typescript
/**
 * Watchlist Dashboard — route shell for /watchlists.
 *
 * Split layout: WatchlistPanel (left 260px) | detail pane (right, flex).
 * Owns selectedSymbol; passes it down to panel and up from panel.
 * Detail pane is a placeholder until the charting sub-project.
 */

import { createSignal } from "solid-js";
import { WatchlistPanel } from "./watchlist-panel";
import { ShowCreateWatchlistModal } from "./create-modal";
import { watchlistsAPI } from "~/lib/watchlists-api";

export function ShowWatchlistsDashboard() {
  const [selectedSymbol, setSelectedSymbol] = createSignal<string | null>(null);
  const [showCreateModal, setShowCreateModal] = createSignal(false);

  function handleSymbolSelect(symbol: string) {
    setSelectedSymbol(symbol);
  }

  return (
    <div class="watchlist-page">
      <ShowCreateWatchlistModal
        isOpen={showCreateModal()}
        onClose={() => setShowCreateModal(false)}
        onSuccess={() => {
          // Panel re-fetches on next mount/navigation; close modal is enough
          setShowCreateModal(false);
        }}
      />

      <div class="watchlist-layout">
        {/* Left pane */}
        <aside class="watchlist-layout__panel">
          <div class="watchlist-layout__panel-header">
            <span class="watchlist-layout__title">Watchlists</span>
            <button
              class="watchlist-layout__new-btn"
              onClick={() => setShowCreateModal(true)}
              title="New watchlist"
            >
              +
            </button>
          </div>
          <WatchlistPanel
            selectedSymbol={selectedSymbol()}
            onSymbolSelect={handleSymbolSelect}
          />
        </aside>

        {/* Right pane */}
        <main class="watchlist-layout__detail">
          {selectedSymbol() ? (
            <div class="watchlist-detail-placeholder">
              <h2>{selectedSymbol()}</h2>
              <p class="watchlist-detail-placeholder__note">
                Chart and detail view coming in the charting sub-project.
              </p>
            </div>
          ) : (
            <div class="watchlist-detail-placeholder watchlist-detail-placeholder--empty">
              <p>Select a stock to view detail</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /home/ubuntu/projects/md/frontend
npm run build 2>&1 | grep -E "error|Error" | head -10
```

Expected: no new errors

- [ ] **Step 3: Commit**

```bash
cd /home/ubuntu/projects/md
git add frontend/src/pages/watchlists/dashboard.tsx
git commit -m "feat: rewrite watchlist dashboard as split-layout shell"
```

---

### Task 9: Router cleanup

**Files:**
- Delete: `frontend/src/pages/watchlists/watchlist-view.tsx`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Remove `/watchlists/:id` route from `main.tsx`**

In `frontend/src/main.tsx`:

Remove the import line:
```typescript
import { ShowWatchlistView } from "./pages/watchlists/watchlist-view";
```

Remove the entire route block:
```typescript
      <Route
        path="/watchlists/:id"
        component={() => (
          <RequireAuth>
            <ShowWatchlistView />
          </RequireAuth>
        )}
      />
```

- [ ] **Step 2: Delete `watchlist-view.tsx`**

```bash
rm /home/ubuntu/projects/md/frontend/src/pages/watchlists/watchlist-view.tsx
```

- [ ] **Step 3: Verify build passes**

```bash
cd /home/ubuntu/projects/md/frontend
npm run build 2>&1 | tail -10
```

Expected: `✓ built in ...ms` with no errors

- [ ] **Step 4: Run all frontend tests**

```bash
cd /home/ubuntu/projects/md/frontend
npm test
```

Expected: all tests pass

- [ ] **Step 5: Run backend CI**

```bash
cd /home/ubuntu/projects/md
make ci
```

Expected: all checks pass

- [ ] **Step 6: Commit**

```bash
cd /home/ubuntu/projects/md
git add frontend/src/main.tsx
git rm frontend/src/pages/watchlists/watchlist-view.tsx
git commit -m "feat: remove /watchlists/:id route and watchlist-view.tsx"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Two-pane layout (260px left / flex right) | Task 8 |
| Collapsible groups | Task 6 |
| Multi-expand, localStorage persistence | Tasks 6, 7 |
| Realtime quote → EOD fallback | Task 2 |
| Batch queries (no N+1) | Task 2 |
| `GET /api/watchlists/{id}/quotes` | Task 3 |
| Ownership 404 guard | Task 3 |
| Source dot (green=realtime, grey=eod) + tooltip | Task 5 |
| Price fields: `change`/`change_pct` (not abbreviated) | Tasks 1, 2, 4, 5 |
| EOD null change when only 1 candle | Task 2 |
| Hover reveals ✕ remove | Task 5 |
| Optimistic remove, restore at original index | Task 6 |
| Add symbol via [+] → inline input → POST → re-fetch quotes | Task 6 |
| Add error messages (not found / already exists / network) | Task 6 |
| Skeleton placeholders while quotes load | Task 6 |
| Quotes error banner + retry | Task 6 |
| ↻ refresh button per group | Task 6 |
| Select symbol → right pane placeholder | Task 8 |
| Delete selected symbol → clear selection | Task 6 (onRemove clears via parent state) |
| Collapse with selected symbol → keep selection | Task 8 (selectedSymbol in dashboard, not group) |
| Remove `/watchlists/:id` route | Task 9 |
| Delete `watchlist-view.tsx` | Task 9 |
| `QuoteResponse` TS type | Task 4 |
| `getQuotes()` API client | Task 4 |
| Vitest config | Task 5 |

**Note on "delete selected clears selection":** When `onRemove` is called in `CategoryGroup`, it removes the quote from local state. But `selectedSymbol` lives in `dashboard.tsx`. The component needs to call `props.onSymbolSelect` with `null` when removing the selected symbol. Add this to `handleRemove` in `category-group.tsx`:

```typescript
async function handleRemove(symbol: string) {
  const original = quotes();
  const idx = original.findIndex((q) => q.symbol === symbol);
  setQuotes(original.filter((q) => q.symbol !== symbol));
  // Clear selection if we just removed the selected symbol
  if (props.selectedSymbol === symbol) {
    props.onSymbolSelect("__CLEAR__");
  }
  try {
    await watchlistsAPI.symbols.remove(props.watchlist.id, symbol);
  } catch {
    const restored = [...quotes()];
    restored.splice(idx, 0, original[idx]);
    setQuotes(restored);
  }
}
```

And in `dashboard.tsx`, handle the sentinel:

```typescript
function handleSymbolSelect(symbol: string) {
  setSelectedSymbol(symbol === "__CLEAR__" ? null : symbol);
}
```

**Fix:** Add these two snippets to Task 6 Step 1 (category-group `handleRemove`) and Task 8 Step 1 (dashboard `handleSymbolSelect`) respectively. The plan above already includes the Task 8 handler; update Task 6's `handleRemove` before executing.
