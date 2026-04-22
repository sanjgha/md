# Realtime Watchlist & Charts Design

**Date:** 2026-04-22
**Author:** Claude Code + User
**Status:** Design Approved

## Overview

Add automatic realtime quote updates to watchlists and current-day candle overlay to daily charts. System polls MarketData.app every 30 seconds during market hours (Mon-Fri 9:30 AM - 4:00 PM ET), caches results server-side, and pushes updates to frontend.

## Requirements

1. **Auto-refresh watchlist quotes** every 30s during market hours (no manual refresh)
2. **Add current-day candle** to daily chart view showing realtime price
3. **Market hours detection** using simple fixed schedule (Mon-Fri 9:30 AM - 4:00 PM ET)
4. **Visual indicators**: Green dot for realtime, gray for EOD (already implemented)
5. **Efficient polling**: Batch quotes with server-side caching, 30s TTL shared across all watchlists
6. **Handle periods < Day**: Use existing `intraday_candles` table for chart current-day candle OHL data

## Constraints

- **MarketData.app does NOT support WebSocket** - HTTP REST polling only
- **Batch support unknown** - Must test comma-separated symbols, fallback to async parallel
- **500-stock universe** - Need efficient batching to minimize API calls
- **15-min delayed data** - Per MarketData.app UTP entitlement requirements

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (SolidJS)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ WatchlistPanel  │  │  ChartPanel     │  │ PollingManager  │ │
│  │ (auto-refresh)  │  │ (daily overlay) │  │ (30s timer)     │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │           │
│           └────────────────────┴────────────────────┘           │
│                              │                                  │
│                        REST API (HTTP)                          │
└──────────────────────────────┼──────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────┐
│                    Backend (FastAPI)                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ /quotes endpoint│  │ /candles endpoint│  │ QuoteCache      │ │
│  │ (cache + DB)    │  │ (intraday merge) │  │ (30s TTL)       │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │           │
│  ┌────────▼────────────────────▼────────────────────▼─────────┐ │
│  │         PostgreSQL (realtime_quotes, daily_candles)        │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────┐
│              MarketData.app API (HTTP REST)                     │
│         /stocks/quotes/{symbol/} or /stocks/candles/            │
└─────────────────────────────────────────────────────────────────┘
```

## Backend Components

### 1. QuoteCacheService (New)

**File:** `src/api/watchlists/quote_cache_service.py`

**Responsibilities:**
- In-memory cache with 30s TTL
- `get_quotes(symbols: List[str]) -> List[QuoteResponse]`
- `refresh_cache()` called by background worker
- `is_market_open()` for ET timezone check

**Cache Structure:**
- Key: `quote:{symbol}`
- Value: QuoteResponse object
- TTL: 30 seconds

**Interface:**
```python
class QuoteCacheService:
    def get_quotes(self, symbols: List[str]) -> List[QuoteResponse]
    def refresh_cache(self, quotes: List[Quote]) -> None
    def is_market_open(self) -> bool
```

### 2. Background Quote Worker (New)

**File:** `src/workers/quote_worker.py`

**Responsibilities:**
- APScheduler job every 30s during market hours
- Get all unique symbols from all user watchlists
- Batch fetch from MarketData.app (comma-separated → async fallback)
- Update `realtime_quotes` table (DELETE + INSERT for today)
- Update QuoteCacheService

**Market Hours Logic:**
```python
def is_market_open() -> bool:
    now = datetime.now(pytz.timezone('US/Eastern'))
    if now.weekday() >= 5:  # Sat/Sun
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
```

**Scheduler Integration:**
- Add to existing `src/api/schedule/manager.py`
- Job ID: `quote_poller`
- Trigger: CronTrigger (`cron="*/30 9-15 * * 1-5"` for 9:30-16:00 ET)

### 3. Enhanced DataProvider

**File:** `src/data_provider/marketdata_app.py`

**New Method:**
```python
async def get_realtime_quotes_batch(self, symbols: List[str]) -> List[Quote]:
    """Fetch multiple quotes efficiently.

    1. Try comma-separated: /stocks/quotes/AAPL,MSFT,TSLA/
    2. Fallback: Async parallel individual requests
    """
```

**Batch Strategy:**
- Try single request with comma-separated symbols (max 50 per request)
- If 400 Bad Request, fall back to `asyncio.gather()` with 10 concurrent
- Parse columnar response format: `{last: [...], change: [...], ...}`

### 4. Enhanced Quote Endpoint

**File:** `src/api/watchlists/routes.py`

**Changes to `GET /api/watchlists/{id}/quotes`:**
- Use QuoteCacheService.get_quotes() first
- Return cached if available (< 30s old)
- Fallback to database query if cache miss
- No schema changes (already has `source: "realtime" | "eod"`)

### 5. New Intraday Endpoint

**File:** `src/api/stocks/routes.py`

**New Endpoint:**
```
GET /api/stocks/{symbol}/candles/intraday?resolution=1h
```

**Response Schema:**
```python
{
  "intraday": [CandleResponse],  # Today's 1h candles
  "realtime": QuoteResponse       # Latest quote
}
```

**Logic:**
1. Query `intraday_candles` WHERE `timestamp::date = today` AND `resolution = '1h'`
2. Query `realtime_quotes` WHERE `timestamp::date = today`
3. Return both merged

## Frontend Components

### 1. PollingManager (New)

**File:** `frontend/src/lib/polling-manager.ts`

**Responsibilities:**
- Singleton pattern for shared 30s timer
- Market hours detection (ET timezone)
- Start/stop with cleanup
- Shared by WatchlistPanel and ChartPanel

**Interface:**
```typescript
class PollingManager {
  private interval: number | null = null;

  start(callback: () => void): void
  stop(): void
  isMarketOpen(): boolean
  isPolling(): boolean
}

export const pollingManager = new PollingManager();
```

### 2. Enhanced WatchlistPanel

**File:** `frontend/src/pages/watchlists/watchlist-panel.tsx`

**Changes:**
- Use PollingManager for auto-refresh
- Remove auto-refresh button (keep manual as fallback)
- Fetch quotes for all expanded watchlists every 30s
- Respect market hours (no polling at night/weekends)

**Implementation:**
```typescript
onMount(() => {
  pollingManager.start(() => {
    expandedIds().forEach(id => fetchQuotes(id));
  });
});

onCleanup(() => {
  pollingManager.stop();
});
```

### 3. Enhanced ChartPanel

**File:** `frontend/src/pages/watchlists/chart-panel.tsx`

**Changes:**
- New method `fetchCurrentDayCandle()` for daily resolution only
- Call new `/api/stocks/{symbol}/candles/intraday` endpoint
- Merge latest intraday OHL with realtime LAST
- Update chart every 30s via PollingManager

**Current Day Candle Logic:**
```typescript
// Only when resolution === "D" and market is open
if (resolution() === "D" && isMarketOpen()) {
  const { intraday, realtime } = await fetchIntradayAndRealtime(symbol);

  const currentCandle = {
    time: intraday[intraday.length - 1].timestamp,
    open: intraday[intraday.length - 1].open,
    high: Math.max(...intraday.map(c => c.high), realtime.high),
    low: Math.min(...intraday.map(c => c.low), realtime.low),
    close: realtime.last
  };

  // Update or append to candles
  updateCurrentDayCandle(currentCandle);
}
```

### 4. Market Hours Utility

**File:** `frontend/src/lib/market-hours.ts`

**Function:**
```typescript
export function isMarketOpen(): boolean {
  const now = new Date();
  const et = toET(now);  // Convert to US/Eastern

  if (et.getDay() === 0 || et.getDay() === 6) return false;
  const hour = et.getHours();
  const minute = et.getMinutes();

  if (hour < 9 || hour > 16) return false;
  if (hour === 9 && minute < 30) return false;
  if (hour === 16 && minute > 0) return false;

  return true;
}
```

## Data Flow Details

### Watchlist Quotes Flow

```
1. Background Worker (every 30s, market hours only)
   ├─ Check: is_market_open()? → Skip if closed
   ├─ Query: SELECT DISTINCT symbol FROM all watchlists
   ├─ Fetch: MarketData.app batch quotes
   │  ├─ Try: /stocks/quotes/AAPL,MSPT,TSLA/ (single request)
   │  └─ Fallback: Async parallel individual requests
   ├─ Store: DELETE realtime_quotes WHERE timestamp::date = today
   │         INSERT new quotes (batch)
   └─ Update: QuoteCacheService (in-memory cache)

2. Frontend (WatchlistPanel, every 30s)
   ├─ Check: is_market_open()? → Skip if closed
   ├─ Call: GET /api/watchlists/{id}/quotes
   │  ├─ Check: QuoteCacheService.get_quotes(symbols)
   │  │  └─ Return if cached < 30s ago
   │  └─ Fallback: Query realtime_quotes table
   └─ Display: Update symbol rows
      ├─ Green dot (source="realtime")
      └─ Gray dot (source="eod")
```

### Chart Current Day Candle Flow

```
User loads chart for AAPL (daily resolution):

1. Initial Load
   ├─ Fetch: GET /api/stocks/AAPL/candles?resolution=D&range=3M
   └─ Display: Historical candles

2. If Market Open AND Resolution === "D"
   ├─ Fetch: GET /api/stocks/AAPL/candles/intraday?resolution=1h
   │  ├─ Query: intraday_candles (today's 1h bars)
   │  └─ Fetch: realtime_quotes (latest quote)
   ├─ Merge: Combine into current day candle
   │  ├─ OHL: From latest intraday candle
   │  └─ Close: From realtime.last
   └─ Display: Append/update current day candle

3. Polling Updates (every 30s)
   ├─ Fetch: Latest intraday + realtime
   ├─ Update: Modify existing current day candle
   └─ Chart: lightweight-charts updateData() API
```

## Error Handling

### Background Worker
- **API rate limit (429)** → Log warning, retry after 60s
- **Network error** → Log error, skip this cycle
- **Invalid symbols** → Skip, log warning
- **Empty response** → Log warning, continue

### Frontend Polling
- **Network error** → Show "Prices unavailable" toast, continue polling
- **5xx error** → Stop polling, show retry button
- **Empty response** → Keep last known prices
- **Timeout** → Continue with next poll cycle

### Chart Updates
- **Missing intraday data** → Don't show current day candle
- **Missing realtime quote** → Use intraday close only
- **Stale data (> 5 min)** → Show warning indicator on chart

## Testing Strategy

### Backend Unit Tests
- `tests/unit/test_quote_cache_service.py` - Cache TTL, hit/miss logic
- `tests/unit/test_marketdata_app_provider.py` - Batch quote fetching
- `tests/unit/workers/test_quote_worker.py` - Market hours, aggregation logic

### Backend Integration Tests
- `tests/integration/test_realtime_quotes_flow.py` - Full flow: API → DB → Cache → Endpoint
- `tests/integration/test_intraday_chart_endpoint.py` - Intraday + realtime merge

### Frontend Unit Tests
- `frontend/tests/unit/lib/polling-manager.test.ts` - Market hours, start/stop logic
- `frontend/tests/unit/lib/market-hours.test.ts` - ET timezone, DST transitions

### Frontend E2E Tests
- `frontend/tests/e2e/realtime-updates.spec.ts` - Auto-refresh, error handling

### Manual Testing Checklist
- [ ] Quotes update every 30s during market hours
- [ ] Polling stops at 4:00 PM ET
- [ ] Polling resumes at 9:30 AM ET next day
- [ ] No polling on weekends
- [ ] Green dot for realtime, gray for EOD
- [ ] Current day candle appears on daily view
- [ ] Candle updates every 30s
- [ ] No current day candle on intraday resolutions
- [ ] Network failure handling
- [ ] API rate limit handling
- [ ] DST transition (March/November)

## Database Schema Changes

No schema changes required. Existing tables:
- `realtime_quotes` - Already has OHL fields (open, high, low, close)
- `intraday_candles` - Already has 1h resolution support
- `daily_candles` - Historical daily data

## API Changes

### New Endpoints
```
GET /api/stocks/{symbol}/candles/intraday?resolution=1h
```

### Modified Endpoints
```
GET /api/watchlists/{id}/quotes  # Now uses cache
```

## Performance Considerations

- **API Calls**: 1 batch request per 30s (or ~50 parallel for 500 symbols)
- **Database**: 1 DELETE + 1 INSERT per 30s (bulk operation)
- **Cache**: In-memory, ~500 quotes × ~200 bytes = ~100 KB
- **Frontend**: 1 REST call per 30s per expanded watchlist

## Future Enhancements

- WebSocket push for true real-time updates
- Configurable poll interval per user
- Historical quote tracking (keep 7-day history)
- Pre-market / after-hours support
- Holiday calendar for market hours

## Implementation Order

1. Backend: QuoteCacheService + market hours utility
2. Backend: Background worker with scheduler integration
3. Backend: Enhanced DataProvider batch quotes
4. Backend: New intraday endpoint
5. Frontend: PollingManager + market hours utility
6. Frontend: Enhanced WatchlistPanel with auto-refresh
7. Frontend: Enhanced ChartPanel with current day candle
8. Tests: Unit + integration for all components
9. Manual testing: Market hours simulation, error scenarios
