# Corporate Action Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the data pipeline so daily/intraday candles are stored as split-adjusted prices, existing unadjusted data is corrected on re-fetch, and probable corporate actions are logged as warnings.

**Architecture:** Three-layer fix — (1) pass `adjusted=true` to MarketData.app so the API returns adjusted OHLCV, (2) change `ON CONFLICT DO NOTHING` → `DO UPDATE` on candle upserts so re-fetches overwrite stale rows, (3) add a threshold-based detector that logs a warning whenever a >35% overnight gap is seen in incoming candles. After deploying, a one-time re-fetch corrects the historical data already in the DB. A separate N+1 DB lookup fix is included because it reduces sync time and is trivially safe.

**Tech Stack:** Python, SQLAlchemy `pg_insert`, PostgreSQL, pytest, requests mock

---

## File Map

| File | Change |
|------|--------|
| `src/data_provider/marketdata_app.py` | Add `adjusted=true` param to `get_daily_candles` and `get_intraday_candles` |
| `src/data_fetcher/fetcher.py` | `DO UPDATE` on candle upserts; add `_detect_corporate_action`; preload stock_map |
| `tests/unit/test_marketdata_provider.py` | New test: `adjusted=true` param is sent |
| `tests/unit/test_fetcher_unit.py` | New file: unit tests for `_detect_corporate_action` and stock_map preload |
| `tests/integration/test_fetcher_db.py` | New test: re-fetch with different close overwrites existing row |

---

## Task 1: Add `adjusted=true` to candle API calls

**Files:**
- Modify: `src/data_provider/marketdata_app.py:88,104`
- Test: `tests/unit/test_marketdata_provider.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_marketdata_provider.py`:

```python
@patch("src.data_provider.marketdata_app.requests.Session")
def test_get_daily_candles_sends_adjusted_param(mock_session_class):
    """get_daily_candles sends adjusted=true to the API."""
    mock_session = Mock()
    mock_session_class.return_value = mock_session
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        "s": "ok", "t": [1704067200],
        "o": [150.0], "h": [152.0], "l": [149.0], "c": [151.0], "v": [1000000],
    }
    mock_session.get.return_value = mock_response

    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    provider.get_daily_candles("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 31))

    call_kwargs = mock_session.get.call_args
    params = call_kwargs[1].get("params", {})
    assert params.get("adjusted") == "true"


@patch("src.data_provider.marketdata_app.requests.Session")
def test_get_intraday_candles_sends_adjusted_param(mock_session_class):
    """get_intraday_candles sends adjusted=true to the API."""
    mock_session = Mock()
    mock_session_class.return_value = mock_session
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {
        "s": "ok", "t": [1704067200],
        "o": [150.0], "h": [152.0], "l": [149.0], "c": [151.0], "v": [500000],
    }
    mock_session.get.return_value = mock_response

    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    provider.get_intraday_candles("AAPL", "5m", datetime(2024, 1, 1), datetime(2024, 1, 31))

    call_kwargs = mock_session.get.call_args
    params = call_kwargs[1].get("params", {})
    assert params.get("adjusted") == "true"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_marketdata_provider.py::test_get_daily_candles_sends_adjusted_param tests/unit/test_marketdata_provider.py::test_get_intraday_candles_sends_adjusted_param -v
```

Expected: FAIL — `AssertionError: assert None == 'true'`

- [ ] **Step 3: Add `adjusted=true` to both candle methods**

In `src/data_provider/marketdata_app.py`, update `get_daily_candles` (line ~88):

```python
def get_daily_candles(
    self,
    symbol: str,
    from_date: datetime,
    to_date: datetime,
) -> List[Candle]:
    """Fetch daily OHLCV candles (split-adjusted)."""
    validate_symbol(symbol)
    url = f"{self.base_url}/stocks/candles/1d/{symbol}"
    params = {
        "from": from_date.strftime("%Y-%m-%d"),
        "to": to_date.strftime("%Y-%m-%d"),
        "adjusted": "true",
    }
    data = self._request_with_retry(url, params=params)
    return self._parse_candles(data)
```

And `get_intraday_candles` (line ~100):

```python
def get_intraday_candles(
    self,
    symbol: str,
    resolution: str,
    from_date: datetime,
    to_date: datetime,
) -> List[Candle]:
    """Fetch intraday bars at specified resolution (split-adjusted)."""
    validate_symbol(symbol)
    validate_resolution(resolution)
    url = f"{self.base_url}/stocks/candles/{resolution}/{symbol}"
    params = {
        "from": from_date.strftime("%Y-%m-%d"),
        "to": to_date.strftime("%Y-%m-%d"),
        "adjusted": "true",
    }
    data = self._request_with_retry(url, params=params)
    return self._parse_candles(data)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_marketdata_provider.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_provider/marketdata_app.py tests/unit/test_marketdata_provider.py
git commit -m "feat: pass adjusted=true to MarketData.app candle endpoints"
```

---

## Task 2: `ON CONFLICT DO UPDATE` for candle upserts

**Files:**
- Modify: `src/data_fetcher/fetcher.py:38-61,63-87`
- Test: `tests/integration/test_fetcher_db.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_fetcher_db.py`:

```python
def test_resync_overwrites_stale_candle(db_session: Session):
    """Re-fetching a candle with different close (e.g. post-split adjusted) overwrites the existing row."""
    stock = Stock(symbol="SPLITCO", name="Split Corp")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)

    # First sync: unadjusted price $100
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, 2), 100.0, 102.0, 99.0, 100.0, 1_000_000),
    ]
    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["SPLITCO"])

    splitco = db_session.query(Stock).filter_by(symbol="SPLITCO").first()
    assert float(splitco.daily_candles[0].close) == 100.0

    # Second sync: adjusted price $50 (2:1 split applied retrospectively)
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, 2), 50.0, 51.0, 49.5, 50.0, 2_000_000),
    ]
    fetcher.sync_daily(symbols=["SPLITCO"])

    db_session.expire_all()
    splitco = db_session.query(Stock).filter_by(symbol="SPLITCO").first()
    assert len(splitco.daily_candles) == 1  # no duplicate
    assert float(splitco.daily_candles[0].close) == 50.0  # overwritten
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/integration/test_fetcher_db.py::test_resync_overwrites_stale_candle -v
```

Expected: FAIL — `AssertionError: assert 100.0 == 50.0` (DO NOTHING silently ignores the update)

- [ ] **Step 3: Change `_bulk_upsert_daily_candles` to `DO UPDATE`**

In `src/data_fetcher/fetcher.py`, replace `_bulk_upsert_daily_candles` (lines 38-61):

```python
def _bulk_upsert_daily_candles(self, stock_id: int, candles) -> int:
    """Bulk upsert daily candles; re-fetches overwrite existing rows (e.g. post-split adjustment)."""
    if not candles:
        return 0
    rows = [
        {
            "stock_id": stock_id,
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]
    insert_stmt = pg_insert(DailyCandle).values(rows)
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["stock_id", "timestamp"],
        set_={
            "open": insert_stmt.excluded.open,
            "high": insert_stmt.excluded.high,
            "low": insert_stmt.excluded.low,
            "close": insert_stmt.excluded.close,
            "volume": insert_stmt.excluded.volume,
        },
    )
    result = self.db.execute(stmt)
    self.db.commit()
    return result.rowcount  # type: ignore[attr-defined]
```

And replace `_bulk_upsert_intraday_candles` (lines 63-87):

```python
def _bulk_upsert_intraday_candles(self, stock_id: int, resolution: str, candles) -> int:
    """Bulk upsert intraday candles; re-fetches overwrite existing rows."""
    if not candles:
        return 0
    rows = [
        {
            "stock_id": stock_id,
            "resolution": resolution,
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]
    insert_stmt = pg_insert(IntradayCandle).values(rows)
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["stock_id", "resolution", "timestamp"],
        set_={
            "open": insert_stmt.excluded.open,
            "high": insert_stmt.excluded.high,
            "low": insert_stmt.excluded.low,
            "close": insert_stmt.excluded.close,
            "volume": insert_stmt.excluded.volume,
        },
    )
    result = self.db.execute(stmt)
    self.db.commit()
    return result.rowcount  # type: ignore[attr-defined]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/integration/test_fetcher_db.py -v
```

Expected: all PASS including `test_fetcher_daily_no_duplicate_on_resync` (still no duplicate when values are the same) and the new overwrite test.

- [ ] **Step 5: Commit**

```bash
git add src/data_fetcher/fetcher.py tests/integration/test_fetcher_db.py
git commit -m "fix: upsert candles with DO UPDATE so re-fetches correct stale adjusted prices"
```

---

## Task 3: Add `_detect_corporate_action` safety-net detector

**Files:**
- Modify: `src/data_fetcher/fetcher.py` (add method + call in `sync_daily`)
- Create: `tests/unit/test_fetcher_unit.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_fetcher_unit.py`:

```python
"""Unit tests for DataFetcher helper methods."""

from datetime import datetime
from unittest.mock import Mock, MagicMock

import pytest

from src.data_fetcher.fetcher import DataFetcher
from src.data_provider.base import Candle


def _make_fetcher():
    return DataFetcher(provider=Mock(), db=MagicMock(), rate_limit_delay=0)


def test_detect_corporate_action_forward_split():
    """2:1 forward split (50% price drop overnight) is flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 50.0, 51.0, 49.5, 50.0, 2_000_000),   # post-split open
    ]
    assert fetcher._detect_corporate_action("AAPL", candles) is True


def test_detect_corporate_action_reverse_split_1_for_10():
    """1:10 reverse split (900% price jump overnight) is flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 1.0, 1.1, 0.9, 1.0, 5_000_000),
        Candle(datetime(2024, 1, 2), 10.0, 10.5, 9.8, 10.0, 500_000),   # post-reverse-split open
    ]
    assert fetcher._detect_corporate_action("LOWP", candles) is True


def test_detect_corporate_action_reverse_split_1_for_20():
    """1:20 reverse split (1900% price jump overnight) is flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 0.5, 0.55, 0.45, 0.5, 10_000_000),
        Candle(datetime(2024, 1, 2), 10.0, 10.2, 9.8, 10.0, 500_000),
    ]
    assert fetcher._detect_corporate_action("PENNY", candles) is True


def test_detect_corporate_action_normal_move():
    """Normal 2% daily move is not flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 150.0, 152.0, 149.0, 151.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 151.5, 153.0, 150.5, 152.0, 900_000),
    ]
    assert fetcher._detect_corporate_action("AAPL", candles) is False


def test_detect_corporate_action_earnings_gap_under_threshold():
    """30% earnings gap (just under threshold) is not flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 130.0, 132.0, 129.0, 131.0, 3_000_000),  # +30% gap
    ]
    assert fetcher._detect_corporate_action("EARN", candles) is False


def test_detect_corporate_action_single_candle():
    """Single candle returns False — nothing to compare."""
    fetcher = _make_fetcher()
    candles = [Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000)]
    assert fetcher._detect_corporate_action("AAPL", candles) is False


def test_detect_corporate_action_empty():
    """Empty candle list returns False."""
    fetcher = _make_fetcher()
    assert fetcher._detect_corporate_action("AAPL", []) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_fetcher_unit.py -v
```

Expected: FAIL — `AttributeError: 'DataFetcher' object has no attribute '_detect_corporate_action'`

- [ ] **Step 3: Add `_detect_corporate_action` to DataFetcher and call it in `sync_daily`**

In `src/data_fetcher/fetcher.py`, add method after `_bulk_upsert_intraday_candles`:

```python
def _detect_corporate_action(self, symbol: str, candles) -> bool:
    """Return True if any overnight open/close gap exceeds 35%, logging a warning.

    Threshold catches 2:1 forward splits (50% drop), 1:10 reverse splits (900% rise),
    and anything in between. Genuine earnings gaps rarely exceed 35% on daily data.
    """
    sorted_c = sorted(candles, key=lambda c: c.timestamp)
    for prev, curr in zip(sorted_c, sorted_c[1:]):
        if prev.close <= 0:
            continue
        gap = abs(curr.open / prev.close - 1)
        if gap > 0.35:
            logger.warning(
                "Possible corporate action %s: prev_close=%.2f curr_open=%.2f gap=%.1f%%",
                symbol,
                prev.close,
                curr.open,
                gap * 100,
            )
            return True
    return False
```

In `sync_daily`, call it after fetching candles (inside the try block, before `_bulk_upsert_daily_candles`):

```python
candles = self.provider.get_daily_candles(
    symbol=symbol, from_date=from_date, to_date=to_date
)
self._detect_corporate_action(symbol, candles)
inserted = self._bulk_upsert_daily_candles(int(stock.id), candles)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_fetcher_unit.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Run full unit suite to check for regressions**

```bash
pytest tests/unit/ -v --tb=short
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/data_fetcher/fetcher.py tests/unit/test_fetcher_unit.py
git commit -m "feat: add corporate action detector — log warning on >35% overnight gap"
```

---

## Task 4: Fix N+1 DB lookups (preload stock_map)

**Files:**
- Modify: `src/data_fetcher/fetcher.py` — `sync_daily`, `sync_intraday`, `sync_news`, `sync_earnings`
- Test: `tests/unit/test_fetcher_unit.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_fetcher_unit.py`:

```python
def test_sync_daily_preloads_stock_map_with_one_query():
    """sync_daily issues exactly one DB query to load the stock map, not one per symbol."""
    mock_db = MagicMock()
    # Mock the stock_map query (query(Stock.symbol, Stock.id).all())
    mock_db.query.return_value.all.return_value = []

    fetcher = DataFetcher(provider=Mock(), db=mock_db, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["AAPL", "MSFT", "GOOGL"])

    # query() should be called once for the preload, not 3 times for symbol lookups
    assert mock_db.query.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_fetcher_unit.py::test_sync_daily_preloads_stock_map_with_one_query -v
```

Expected: FAIL — `AssertionError: assert 3 == 1` (currently queries once per symbol)

- [ ] **Step 3: Replace per-symbol lookups with a preloaded map in all four sync methods**

Replace the top of `sync_daily` in `src/data_fetcher/fetcher.py`:

```python
def sync_daily(
    self,
    symbols: Optional[List[str]] = None,
    days_back: int = 365,
) -> None:
    """Sync daily candles for all (or specified) stocks."""
    stock_map = {s.symbol: int(s.id) for s in self.db.query(Stock).all()}
    if symbols is None:
        symbols = list(stock_map.keys())

    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=days_back)

    for symbol in symbols:
        stock_id = stock_map.get(str(symbol))
        if not stock_id:
            logger.warning(f"Stock {symbol} not found in DB — skipping")
            continue
        try:
            candles = self.provider.get_daily_candles(
                symbol=symbol, from_date=from_date, to_date=to_date
            )
            self._detect_corporate_action(symbol, candles)
            inserted = self._bulk_upsert_daily_candles(stock_id, candles)
            logger.info(f"sync_daily {symbol}: {inserted} new rows")
            time.sleep(self.rate_limit_delay)
        except Exception as e:
            logger.error(f"Failed to sync daily {symbol}: {e}")
            self.db.rollback()
```

Replace `sync_intraday`:

```python
def sync_intraday(
    self,
    symbols: Optional[List[str]] = None,
    resolutions: Optional[List[str]] = None,
    days_back: int = 7,
) -> None:
    """Sync intraday candles for 5m, 15m, 1h resolutions."""
    if resolutions is None:
        resolutions = ["5m", "15m", "1h"]
    stock_map = {s.symbol: int(s.id) for s in self.db.query(Stock).all()}
    if symbols is None:
        symbols = list(stock_map.keys())

    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=days_back)

    for symbol in symbols:
        stock_id = stock_map.get(str(symbol))
        if not stock_id:
            continue
        for resolution in resolutions:
            try:
                candles = self.provider.get_intraday_candles(
                    symbol=symbol,
                    resolution=resolution,
                    from_date=from_date,
                    to_date=to_date,
                )
                inserted = self._bulk_upsert_intraday_candles(stock_id, resolution, candles)
                logger.info(f"sync_intraday {symbol} {resolution}: {inserted} new rows")
            except Exception as e:
                logger.error(f"Failed to sync intraday {symbol} {resolution}: {e}")
                self.db.rollback()
        time.sleep(self.rate_limit_delay)
```

Replace `sync_news`:

```python
def sync_news(
    self,
    symbols: Optional[List[str]] = None,
    countback: int = 50,
) -> None:
    """Sync news articles for all stocks."""
    stock_map = {s.symbol: int(s.id) for s in self.db.query(Stock).all()}
    if symbols is None:
        symbols = list(stock_map.keys())

    for symbol in symbols:
        stock_id = stock_map.get(str(symbol))
        if not stock_id:
            continue
        try:
            articles = self.provider.get_news(symbol=symbol, countback=countback)
            for article in articles:
                stmt = (
                    pg_insert(StockNews)
                    .values(
                        stock_id=stock_id,
                        headline=article.headline,
                        content=article.content,
                        source=article.source,
                        publication_date=article.publication_date,
                    )
                    .on_conflict_do_nothing(
                        index_elements=["stock_id", "source", "publication_date"]
                    )
                )
                self.db.execute(stmt)
            self.db.commit()
            time.sleep(self.rate_limit_delay)
        except Exception as e:
            logger.error(f"Failed to sync news {symbol}: {e}")
            self.db.rollback()
```

Replace `sync_earnings`:

```python
def sync_earnings(self, symbols: Optional[List[str]] = None) -> None:
    """Sync earnings calendar."""
    stock_map = {s.symbol: int(s.id) for s in self.db.query(Stock).all()}
    if symbols is None:
        symbols = list(stock_map.keys())

    for symbol in symbols:
        stock_id = stock_map.get(str(symbol))
        if not stock_id:
            continue
        try:
            earnings = self.provider.get_earnings_history(symbol=symbol)
            rows = [
                {
                    "stock_id": stock_id,
                    "fiscal_year": e.fiscal_year,
                    "fiscal_quarter": e.fiscal_quarter,
                    "earnings_date": e.earnings_date,
                    "report_date": e.report_date,
                    "report_time": e.report_time,
                    "currency": e.currency,
                    "reported_eps": e.reported_eps,
                    "estimated_eps": e.estimated_eps,
                }
                for e in earnings
            ]
            if rows:
                stmt = (
                    pg_insert(EarningsCalendar)
                    .values(rows)
                    .on_conflict_do_nothing(index_elements=["stock_id", "earnings_date"])
                )
                self.db.execute(stmt)
                self.db.commit()
            time.sleep(self.rate_limit_delay)
        except Exception as e:
            logger.error(f"Failed to sync earnings {symbol}: {e}")
            self.db.rollback()
```

- [ ] **Step 4: Run all fetcher tests**

```bash
pytest tests/unit/test_fetcher_unit.py tests/integration/test_fetcher_db.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_fetcher/fetcher.py tests/unit/test_fetcher_unit.py
git commit -m "perf: preload stock_map to eliminate N+1 DB lookups in sync methods"
```

---

## Task 5: Data Cleanup — Re-fetch Historical Data with Adjusted Prices

> This task has no code changes. It is a manual operational step run once after Tasks 1–4 are deployed.

**Context:** All `daily_candles` rows currently in the DB were fetched without `adjusted=true`. Some of them may be unadjusted (wrong) prices for stocks that had splits. Since Task 2 changed the upsert to `DO UPDATE`, running `sync_daily` again will overwrite every existing row with the API's adjusted values.

- [ ] **Step 1: Identify suspect rows (run against live DB)**

Connect to the DB and run this SQL to find large overnight gaps in existing data. These are the rows most likely to be wrong:

```sql
WITH ordered AS (
    SELECT
        s.symbol,
        d.timestamp,
        d.close,
        LAG(d.close) OVER (PARTITION BY d.stock_id ORDER BY d.timestamp) AS prev_close
    FROM daily_candles d
    JOIN stocks s ON s.id = d.stock_id
)
SELECT
    symbol,
    timestamp,
    ROUND(prev_close::numeric, 2)  AS prev_close,
    ROUND(close::numeric, 2)       AS curr_close,
    ROUND(ABS(close::float / NULLIF(prev_close::float, 0) - 1) * 100, 1) AS gap_pct
FROM ordered
WHERE ABS(close::float / NULLIF(prev_close::float, 0) - 1) > 0.35
ORDER BY gap_pct DESC
LIMIT 50;
```

Log the output. Any symbol appearing here had a corporate action in the stored history.

- [ ] **Step 2: Check current data coverage**

```sql
SELECT
    MIN(timestamp) AS oldest,
    MAX(timestamp) AS newest,
    COUNT(*)       AS total_rows,
    COUNT(DISTINCT stock_id) AS stocks
FROM daily_candles;
```

Verify coverage includes at least the last 365 days.

- [ ] **Step 3: Re-fetch all daily candles with adjusted prices**

Run with `days_back=400` to cover a full year plus buffer, ensuring any split in the past year is corrected:

```bash
python -m src.main fetch-data
```

> `fetch_data` already calls `sync_daily` with default `days_back=365`. If you want to extend coverage run directly:
> ```bash
> python -c "
> from src.config import get_config
> from src.data_provider.marketdata_app import MarketDataAppProvider
> from src.data_fetcher.fetcher import DataFetcher
> from src.db.connection import get_engine
> from sqlalchemy.orm import sessionmaker
>
> cfg = get_config()
> engine = get_engine(cfg.DATABASE_URL)
> db = sessionmaker(bind=engine)()
> provider = MarketDataAppProvider(api_token=cfg.MARKETDATA_API_TOKEN)
> fetcher = DataFetcher(provider=provider, db=db, rate_limit_delay=cfg.API_RATE_LIMIT_DELAY)
> fetcher.sync_daily(days_back=400)
> db.close()
> print('Done')
> "
> ```

This will take approximately 8–9 minutes for 500 stocks.

- [ ] **Step 4: Verify no gaps remain**

Re-run the gap detection query from Step 1. With adjusted prices from the API, large overnight gaps should be gone (or dramatically reduced to only genuine extreme earnings moves):

```sql
WITH ordered AS (
    SELECT
        s.symbol,
        d.timestamp,
        d.close,
        LAG(d.close) OVER (PARTITION BY d.stock_id ORDER BY d.timestamp) AS prev_close
    FROM daily_candles d
    JOIN stocks s ON s.id = d.stock_id
)
SELECT COUNT(*) AS suspect_rows
FROM ordered
WHERE ABS(close::float / NULLIF(prev_close::float, 0) - 1) > 0.35;
```

Expected: count drops significantly (ideally to 0, or very few genuine earnings/news gaps).

---

## Retest Summary

Run after all tasks are complete:

```bash
# Full unit suite
pytest tests/unit/ -v --tb=short

# Full integration suite (requires Docker)
pytest tests/integration/ -v --tb=short

# Coverage report
pytest tests/ --cov=src --cov-report=term-missing
```

**Key tests that directly validate the fix:**

| Test | File | What it proves |
|------|------|----------------|
| `test_get_daily_candles_sends_adjusted_param` | `test_marketdata_provider.py` | API call includes `adjusted=true` |
| `test_get_intraday_candles_sends_adjusted_param` | `test_marketdata_provider.py` | Intraday API call includes `adjusted=true` |
| `test_resync_overwrites_stale_candle` | `test_fetcher_db.py` | Re-fetch with different price overwrites old row |
| `test_fetcher_daily_no_duplicate_on_resync` | `test_fetcher_db.py` | Idempotent re-fetch with same data still = 1 row |
| `test_detect_corporate_action_forward_split` | `test_fetcher_unit.py` | 2:1 split flagged |
| `test_detect_corporate_action_reverse_split_1_for_10` | `test_fetcher_unit.py` | 1:10 reverse split flagged |
| `test_detect_corporate_action_reverse_split_1_for_20` | `test_fetcher_unit.py` | 1:20 reverse split flagged |
| `test_detect_corporate_action_normal_move` | `test_fetcher_unit.py` | Normal 2% move not flagged |
| `test_sync_daily_preloads_stock_map_with_one_query` | `test_fetcher_unit.py` | N+1 eliminated |
