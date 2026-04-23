# Continuous Intraday Data Updates Design

**Date:** 2026-04-23
**Status:** Approved
**Author:** Claude (with user)

## Problem Statement

The current intraday data update system is misconfigured:

- **Quote poller**: Documented as "runs every 30 seconds" but actually scheduled with CronTrigger at 9:30 AM ET once per day
- **Intraday candles**: Only updated during EOD fetch at 4:15 PM ET
- **Impact**: No continuous intraday updates during market hours despite system claiming to support it

## Requirements

Implement continuous intraday data updates during market hours:

1. **Quote polling**: Every 1 minute during regular market hours (9:30 AM - 4:00 PM ET)
2. **Intraday candles**: Every 5 minutes during market hours (9:30 AM - 4:00 PM ET)
3. **Support both trigger types**: CronTrigger (scheduled at specific time) and IntervalTrigger (recurring)

## Architecture Overview

```
Market Hours (9:30 AM - 4:00 PM ET, Mon-Fri)
├── Quote Poller (IntervalTrigger, 60 seconds)
│   └── QuoteWorker.poll()
│       ├── Fetch realtime quotes for all watchlist symbols
│       ├── Store in realtime_quotes table
│       └── Update cache for API clients
└── Intraday Candle Job (IntervalTrigger, 300 seconds)
    └── run_intraday_candle_job()
        └── DataFetcher.sync_intraday()
            └── Fetch 5m, 15m, 1h candles for last 1 day
```

## Components

### 1. Database Schema Changes

**Table: `schedule_config`**

Add columns to support both CronTrigger and IntervalTrigger:

```sql
ALTER TABLE schedule_config
ADD COLUMN trigger_type VARCHAR(10) NOT NULL DEFAULT 'cron',
ADD COLUMN interval_seconds INTEGER;

ALTER TABLE schedule_config
ADD CONSTRAINT check_trigger_config
CHECK (
  (trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR
  (trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)
);
```

**Migration behavior:**
- Existing rows default to `trigger_type='cron'`
- Cron jobs: `hour` and `minute` required, `interval_seconds` NULL
- Interval jobs: `interval_seconds` required, `hour` and `minute` NULL

### 2. ScheduleManager Enhancements

**File: `src/api/schedule/manager.py`**

Support both trigger types in `_add_job_to_scheduler()`:

```python
from apscheduler.triggers.interval import IntervalTrigger

def _add_job_to_scheduler(self, cfg: ScheduleConfig) -> None:
    if cfg.trigger_type == 'cron':
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=cfg.hour,
            minute=cfg.minute,
            timezone="America/New_York",
        )
    elif cfg.trigger_type == 'interval':
        trigger = IntervalTrigger(
            seconds=cfg.interval_seconds,
            timezone="America/New_York",
        )
    else:
        raise ValueError(f"Unknown trigger_type: {cfg.trigger_type}")

    self._scheduler.add_job(
        callback,
        trigger=trigger,
        id=cfg.job_id,
        name=JOB_DISPLAY_NAMES.get(cfg.job_id, cfg.job_id),
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
```

**Register new callbacks:**

```python
def start(self, db_session: Session) -> None:
    # ... existing code ...

    self._callbacks["quote_poller"] = run_quote_polling_job
    self._callbacks["intraday_candle_5m"] = run_intraday_candle_job
    self._locks["quote_poller"] = threading.Lock()
    self._locks["intraday_candle_5m"] = threading.Lock()

    # ... rest of existing code ...
```

### 3. Market Hours Extension

**File: `src/utils/market_hours.py`**

Extend to support pre-market trading:

```python
def is_market_open(dt: datetime | None = None, include_premarket: bool = False) -> bool:
    """Check if US market is open (Mon-Fri 9:30 AM - 4:00 PM ET).

    Args:
        dt: Datetime to check. If naive, treats as ET. Defaults to now.
        include_premarket: If True, includes pre-market (4:00 AM - 9:30 AM ET)

    Returns:
        True if market is open, False otherwise.
    """
    if dt is None:
        dt = datetime.now(ET)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=ET)
    else:
        dt = dt.astimezone(ET)

    # Weekends (0=Sunday, 6=Saturday)
    if dt.weekday() >= 5:
        return False

    # Regular hours: 9:30 AM - 4:00 PM
    if not include_premarket:
        if dt.hour < 9 or dt.hour >= 16:
            return False
        if dt.hour == 9 and dt.minute < 30:
            return False
        return True

    # Extended hours (including pre-market): 4:00 AM - 4:00 PM
    if dt.hour < 4 or dt.hour >= 16:
        return False

    return True
```

### 4. Quote Polling Job

**File: `src/workers/quote_worker.py`**

Update `QuoteWorker.poll()` to use existing market hours check:

```python
def poll(self) -> int:
    """Poll for quotes and update database/cache if market is open.

    Returns:
        Number of quotes fetched (0 if market closed or error)
    """
    if not is_market_open():
        logger.debug("Market closed, skipping quote poll")
        return 0

    # ... rest of existing logic ...
```

**Job callback:**

```python
def run_quote_polling_job(db: Session) -> int:
    """Run quote polling job every 1 minute. Returns count of quotes fetched."""
    from src.workers.quote_worker import QuoteWorker
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.config import get_config

    cfg = get_config()
    provider = MarketDataAppProvider(api_token=cfg.MARKETDATA_API_TOKEN)

    from src.api.schedule.manager import get_quote_cache_service
    cache_service = get_quote_cache_service()

    worker = QuoteWorker(db, cache_service, provider)
    return worker.poll()
```

### 5. Intraday Candle Job

**File: `src/api/schedule/jobs.py`**

Add new job callback:

```python
def run_intraday_candle_job(db: Session) -> int:
    """Sync intraday candles every 5 minutes. Returns count of symbols synced."""
    from src.data_fetcher.fetcher import DataFetcher
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.config import get_config
    from src.utils.market_hours import is_market_open
    from src.db.models import Stock

    # Skip if market closed
    if not is_market_open():
        logger.debug("Market closed, skipping intraday candle sync")
        return 0

    cfg = get_config()
    provider = MarketDataAppProvider(api_token=cfg.MARKETDATA_API_TOKEN)
    fetcher = DataFetcher(provider=provider, db=db, rate_limit_delay=cfg.API_RATE_LIMIT_DELAY)

    # Sync intraday candles for last 1 day
    fetcher.sync_intraday(symbols=None, resolutions=["5m", "15m", "1h"], days_back=1)

    # Return count of symbols synced
    return db.query(Stock).count()
```

**Register job display name:**

```python
JOB_DISPLAY_NAMES: Dict[str, str] = {
    "eod_scan": "EOD Scan",
    "pre_close_scan": "Pre-Close Scan",
    "quote_poller": "Quote Polling",
    "intraday_candle_5m": "Intraday Candle Sync",
}
```

## Data Flow

### Quote Polling (every 1 minute)

```
IntervalTrigger (60s)
  ↓
ScheduleManager callback
  ↓
run_quote_polling_job(db)
  ↓
QuoteWorker.poll()
  ↓
Check: is_market_open()
  ↓
If open:
  - Get all symbols from watchlists
  - Fetch realtime quotes (batch API call)
  - Store in realtime_quotes table (delete today's existing, insert new)
  - Update QuoteCacheService
  - Log "Polled X quotes"
```

### Intraday Candle Sync (every 5 minutes)

```
IntervalTrigger (300s)
  ↓
ScheduleManager callback
  ↓
run_intraday_candle_job(db)
  ↓
Check: is_market_open()
  ↓
If open:
  - DataFetcher.sync_intraday(resolutions=["5m", "15m", "1h"], days_back=1)
  - Bulk upsert to intraday_candles table (ON CONFLICT DO NOTHING)
  - Log "sync_intraday {symbol} {resolution}: X new rows"
```

## Error Handling

**Market hours check:**
- Jobs return 0 immediately if market closed
- Logged as "Market closed, skipping..."

**API failures:**
- QuoteWorker: Catches exceptions, logs error, returns 0, rolls back DB
- DataFetcher: Logs error per symbol, continues with next symbol, rolls back on failure

**Locking:**
- Both jobs use threading.Lock to prevent double-execution
- If job already running, logs warning and skips

**Database:**
- All DB operations in try/except with rollback on error
- Quotes: Delete today's entries before insert (no duplicates)
- Candles: ON CONFLICT DO NOTHING (no duplicates)

## Testing Strategy

### Manual Verification

1. **Start API server:**
   ```bash
   python3 -m uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8001
   ```

2. **Check logs for quote polling:**
   ```bash
   tail -f market_data.log | grep "Polled"
   # Should see: "Polled X quotes" every 1 minute
   ```

3. **Check logs for intraday candles:**
   ```bash
   tail -f market_data.log | grep "sync_intraday"
   # Should see: "sync_intraday {symbol} 5m: X new rows" every 5 minutes
   ```

4. **Verify database:**
   ```sql
   -- Realtime quotes (should have timestamps every 1 minute)
   SELECT symbol, timestamp FROM realtime_quotes
   WHERE timestamp >= NOW() - INTERVAL '10 minutes'
   ORDER BY timestamp DESC;

   -- Intraday candles (should have new data every 5 minutes)
   SELECT symbol, resolution, timestamp FROM intraday_candles
   WHERE resolution = '5m' AND timestamp >= NOW() - INTERVAL '30 minutes'
   ORDER BY timestamp DESC;
   ```

### Database Verification

```sql
-- Check job configs
SELECT job_id, enabled, trigger_type, hour, minute, interval_seconds
FROM schedule_config;

-- Should show:
-- quote_poller:         interval, 60
-- intraday_candle_5m:   interval, 300
-- pre_close_scan:       cron, 15, 45
-- eod_scan:             cron, 16, 15
```

## Migration Steps

### 1. Create Alembic Migration

```bash
alembic revision --autogenerate -m "add_interval_trigger_support"
```

**Edit migration file:**

```python
def upgrade():
    op.add_column('schedule_config', sa.Column('trigger_type', sa.String(10), nullable=False, server_default='cron'))
    op.add_column('schedule_config', sa.Column('interval_seconds', sa.Integer, nullable=True))

    op.create_check_constraint(
        'check_trigger_config',
        'schedule_config',
        "(trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR "
        "(trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)"
    )

def downgrade():
    op.drop_constraint('check_trigger_config', 'schedule_config')
    op.drop_column('schedule_config', 'interval_seconds')
    op.drop_column('schedule_config', 'trigger_type')
```

### 2. Run Migration

```bash
alembic upgrade head
```

### 3. Update Job Configurations

Via API or directly in database:

```sql
-- Update existing quote_poller to interval
UPDATE schedule_config
SET trigger_type = 'interval',
    interval_seconds = 60,
    hour = NULL,
    minute = NULL
WHERE job_id = 'quote_poller';

-- Insert new intraday candle job
INSERT INTO schedule_config (job_id, enabled, trigger_type, interval_seconds, auto_save)
VALUES ('intraday_candle_5m', true, 'interval', 300, false);
```

### 4. Restart API Server

```bash
# Stop existing server
pkill -f "uvicorn.*8001"

# Start new server
python3 -m uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8001
```

### 5. Verify

```bash
# Check logs
tail -f market_data.log

# Query database for recent quotes
python3 -c "
from src.db.connection import get_engine
from src.db.models import RealtimeQuote
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

engine = get_engine()
Session = sessionmaker(bind=engine)
db = Session()

recent = db.query(RealtimeQuote).filter(
    RealtimeQuote.timestamp >= datetime.utcnow() - timedelta(minutes=10)
).count()

print(f'Realtime quotes in last 10 minutes: {recent}')
"
```

## Rollback Strategy

If issues occur:

1. **Disable interval jobs:**
   ```sql
   UPDATE schedule_config SET enabled = false WHERE job_id IN ('quote_poller', 'intraday_candle_5m');
   ```

2. **Restore old quote_poller config:**
   ```sql
   UPDATE schedule_config
   SET trigger_type = 'cron',
       interval_seconds = NULL,
       hour = 9,
       minute = 30
   WHERE job_id = 'quote_poller';
   ```

3. **Restart API server**

4. **Revert migration if needed:**
   ```bash
   alembic downgrade -1
   ```

## Configuration

**New job configurations in `schedule_config` table:**

| job_id | enabled | trigger_type | hour | minute | interval_seconds | auto_save |
|--------|---------|--------------|------|--------|------------------|-----------|
| quote_poller | true | interval | NULL | NULL | 60 | false |
| intraday_candle_5m | true | interval | NULL | NULL | 300 | false |
| pre_close_scan | true | cron | 15 | 45 | NULL | false |
| eod_scan | true | cron | 16 | 15 | NULL | false |

## API Rate Limits

**Estimated API usage:**

- **Quote polling**: ~390 requests/day (1 req/min × 390 min during 6.5-hour market day)
- **Intraday candles**: ~78 requests/day (1 req/5min × 390 min / 60 symbols × 3 resolutions)
- **Total**: ~468 requests/day (within typical rate limits)

**Rate limiting:**
- `API_RATE_LIMIT_DELAY` config: 0.1 seconds between requests
- QuoteWorker uses batch API call: 1 request for all symbols
- Intraday sync uses existing `DataFetcher` rate limiting

## Future Considerations

**Potential enhancements:**
1. Add pre/post-market hours support
2. Make polling frequency configurable per job
3. Add metrics/monitoring for job execution times
4. Implement backfill logic for missed intervals
5. Add WebSocket push for real-time quote updates

**Monitoring:**
- Track job execution frequency
- Alert if jobs stop firing
- Monitor API rate limit usage
- Track database growth (realtime_quotes, intraday_candles tables)
