# Realtime Watchlist & Charts

## Overview

Watchlist quotes auto-refresh every 30 seconds during market hours (Mon-Fri 9:30 AM - 4:00 PM ET). Daily charts show current-day candle with realtime price overlay.

## Features

### Auto-Refreshing Watchlist

- **Automatic Updates**: Quotes update automatically every 30s during market hours
- **Visual Indicators**: Green dot (●) for realtime data, gray dot for EOD fallback
- **Smart Polling**: Only fetches quotes for expanded watchlists
- **Market Hours Aware**: Stops polling after market close and on weekends
- **Fallback**: Uses EOD data when market is closed

### Current Day Candle on Charts

- **Daily Resolution Only**: Current day candle overlay appears only on daily (D) timeframe
- **Realtime Updates**: Updates every 30s during market hours
- **Accurate OHL**: Open, high, low from 1-hour intraday bars
- **Realtime Close**: Close price from latest realtime quote
- **Smart Display**: Automatically hides after market close or on intraday resolutions

## Architecture

### Backend Components

#### Quote Polling Worker

- **Schedule**: Runs every 30s during market hours (Mon-Fri 9:30 AM - 4:00 PM ET)
- **Scope**: Fetches all unique symbols across all user watchlists
- **Efficiency**: Batch API calls to MarketData.app (comma-separated, fallback to parallel)
- **Storage**: Stores in `realtime_quotes` table with DELETE+INSERT for today
- **Cache**: Updates in-memory QuoteCacheService after each successful fetch

#### Quote Cache Service

- **TTL**: 30-second cache expiration
- **Scope**: Shared across all watchlist quote requests
- **Thread-Safe**: Uses `threading.Lock` for concurrent access
- **Key Pattern**: `quote:{symbol}`
- **Hit Strategy**: Returns cached if all requested symbols in cache, otherwise falls back to DB

#### Data Provider

- **Batch Fetch**: `get_realtime_quotes_batch()` tries comma-separated symbols first
- **Fallback**: Async parallel individual requests with semaphore(10) for rate limiting
- **Event Loop Safe**: Uses `asyncio.to_thread()` to avoid blocking

#### API Endpoints

- **`GET /api/watchlists/{id}/quotes`**: Returns quotes for watchlist symbols, uses cache first
- **`GET /api/stocks/{symbol}/candles/intraday?resolution=1h`**: Returns today's intraday candles + latest realtime quote

### Frontend Components

#### PollingManager

- **Pattern**: Singleton instance exported from `~/lib/polling-manager`
- **Timer**: 30-second interval via `window.setInterval`
- **Market Hours**: Delegates to `isMarketOpen()` from `~/lib/market-hours`
- **Lifecycle**: `start(callback)` / `stop()` with proper cleanup
- **Smart**: Only executes callback during market hours

#### Market Hours Utility

- **Timezone**: Converts input dates to US/Eastern
- **Schedule**: Mon-Fri 9:30 AM - 4:00 PM ET
- **Boundaries**: 9:30:00 inclusive, 16:00:00 exclusive
- **Weekends**: Returns false on Saturday/Sunday

#### Component Integration

- **WatchlistPanel**: Manages PollingManager lifecycle, passes refresh signal to CategoryGroups
- **CategoryGroup**: Watches refresh signal, fetches quotes when expanded and loaded
- **ChartPanel**: Fetches current day candle on mount, polls every 30s for daily resolution

## Data Flow

### Watchlist Quotes Flow

```
1. Background Worker (every 30s, market hours only)
   ├─ Check: is_market_open()? → Skip if closed
   ├─ Query: SELECT DISTINCT symbol FROM all watchlists
   ├─ Fetch: MarketData.app batch quotes
   │  ├─ Try: /stocks/quotes/AAPL,MSFT,TSLA/ (single request)
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

## Configuration

### Environment Variables

```bash
# MarketData.app API token (required)
MARKETDATA_API_TOKEN=your_token_here

# Database URL (required)
DATABASE_URL=postgresql://user:pass@host:port/db
```

### Scheduler Configuration

The quote polling job is registered in the `schedule_config` table:

- **Job ID**: `quote_poller`
- **Cron Expression**: `*/30 9-15 * * 1-5` (every 30s, 9:30 AM - 4:00 PM ET, Mon-Fri)
- **Enabled**: Can be toggled via `/api/schedule/jobs/{job_id}` endpoint

## Troubleshooting

### Quotes Not Updating

1. **Check Market Hours**: Verify current time is within Mon-Fri 9:30 AM - 4:00 PM ET
2. **Check Scheduler**: Query `/api/schedule/jobs` to verify `quote_poller` is enabled
3. **Check Worker Logs**: Look for "Polled X quotes" messages in application logs
4. **Check API Token**: Verify `MARKETDATA_API_TOKEN` is valid and not rate-limited

### Current Day Candle Not Showing

1. **Check Resolution**: Only shows on daily (D) timeframe
2. **Check Market Hours**: Only shows during market hours
3. **Check Browser Console**: Look for fetch errors in developer tools
4. **Check API Endpoint**: Verify `/api/stocks/{symbol}/candles/intraday` returns data

### Performance Issues

1. **Cache Hit Rate**: Monitor cache metrics - should be >80% during market hours
2. **Database Load**: realtime_quotes table has DELETE+INSERT pattern - ensure indexes on timestamp
3. **API Rate Limits**: MarketData.app has rate limits - batch requests help stay within limits
4. **Browser Memory**: PollingManager singleton prevents duplicate timers

## Future Enhancements

- WebSocket push for true real-time updates (when MarketData.app adds support)
- Configurable poll interval per user preference
- Historical quote tracking (keep 7-day history for charts)
- Pre-market (4:00 AM - 9:30 AM ET) and after-hours (4:00 PM - 8:00 PM ET) support
- Holiday calendar integration for market hours
- User-configurable refresh intervals (15s, 30s, 60s)
