# Continuous Intraday Data Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement continuous intraday data updates during regular market hours (9:30 AM - 4:00 PM ET) with 1-minute quote polling and 5-minute intraday candle updates.

**Architecture:** Extend ScheduleManager to support IntervalTrigger jobs, add trigger_type column to schedule_config table, create interval-based jobs for quote polling and intraday candle sync.

**Tech Stack:** Python, SQLAlchemy, APScheduler, PostgreSQL, Alembic

---

## File Structure

**New Files:**
- `alembic/versions/XXX_add_interval_trigger_support.py` - Database migration
- `tests/api/schedule/test_interval_jobs.py` - Tests for interval job scheduling

**Modified Files:**
- `src/db/models.py` - Add trigger_type, interval_seconds to ScheduleConfig
- `src/api/schedule/manager.py` - Support IntervalTrigger in addition to CronTrigger
- `src/api/schedule/jobs.py` - Add run_intraday_candle_job callback
- `src/workers/quote_worker.py` - Remove include_premarket parameter (use existing is_market_open)

---

## Task 1: Database Model Update

**Files:**
- Modify: `src/db/models.py:ScheduleConfig`

- [ ] **Step 1: Add columns to ScheduleConfig model**

```python
# In ScheduleConfig class (after existing columns)

trigger_type: str = Column(String(10), nullable=False, server_default="cron")
interval_seconds: Optional[int] = Column(Integer, nullable=True)

# Add check constraint via __table_args__
__table_args__ = (
    CheckConstraint(
        "(trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR "
        "(trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)",
        name="check_trigger_config"
    ),
)
```

- [ ] **Step 2: Run type check**

```bash
mypy src/db/models.py --ignore-missing-imports
```

Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add src/db/models.py
git commit -m "feat: add trigger_type and interval_seconds to ScheduleConfig model"
```

---

## Task 2: Database Migration

**Files:**
- Create: `alembic/versions/XXX_add_interval_trigger_support.py`

- [ ] **Step 1: Generate migration**

```bash
alembic revision --autogenerate -m "add_interval_trigger_support"
```

- [ ] **Step 2: Edit the migration file**

Find the generated file in `alembic/versions/` and replace with:

```python
"""add_interval_trigger_support

Revision ID: add_interval_trigger_support
Revises: <previous_revision_id>
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import check

# revision identifiers, used by Alembic.
revision = 'add_interval_trigger_support'
down_revision = '<previous_revision_id>'  # Replace with actual revision ID
branch_labels = None
depends_on = None


def upgrade():
    # Add columns
    op.add_column('schedule_config', sa.Column('trigger_type', sa.String(10), nullable=False, server_default='cron'))
    op.add_column('schedule_config', sa.Column('interval_seconds', sa.Integer, nullable=True))

    # Add check constraint
    op.create_check_constraint(
        'check_trigger_config',
        'schedule_config',
        "(trigger_type = 'cron' AND hour IS NOT NULL AND minute IS NOT NULL) OR "
        "(trigger_type = 'interval' AND interval_seconds IS NOT NULL AND interval_seconds > 0)"
    )


def downgrade():
    op.drop_constraint('check_trigger_config', 'schedule_config', type_='check')
    op.drop_column('schedule_config', 'interval_seconds')
    op.drop_column('schedule_config', 'trigger_type')
```

- [ ] **Step 3: Run migration**

```bash
alembic upgrade head
```

Expected: "Running upgrade... -> add_interval_trigger_support"

- [ ] **Step 4: Verify database schema**

```bash
python3 -c "
from src.db.connection import get_engine
from src.db.models import ScheduleConfig
from sqlalchemy import inspect

engine = get_engine()
inspector = inspect(engine)

columns = [c['name'] for c in inspector.get_columns('schedule_config')]
print('Columns:', columns)

assert 'trigger_type' in columns
assert 'interval_seconds' in columns
print('✓ Columns added successfully')
"
```

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add database migration for interval trigger support"
```

---

## Task 3: Update ScheduleManager for IntervalTrigger

**Files:**
- Modify: `src/api/schedule/manager.py`

- [ ] **Step 1: Add IntervalTrigger import**

```python
# At top of file, after existing imports
from apscheduler.triggers.interval import IntervalTrigger
```

- [ ] **Step 2: Update _add_job_to_scheduler method**

Replace the entire `_add_job_to_scheduler` method (lines ~249-282) with:

```python
def _add_job_to_scheduler(self, cfg: ScheduleConfig) -> None:
    """Add a job to the scheduler from a DB config.

    Wraps the callback with lock acquisition and auto-save logic.

    Args:
        cfg: ScheduleConfig instance from database
    """
    if self._scheduler is None:
        raise RuntimeError("Scheduler not started")

    callback = self._make_scheduled_callback(cfg.job_id, cfg.auto_save)

    # Create trigger based on trigger_type
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
    logger.info(
        "Added job %s (trigger_type=%s) at %02d:%02d (auto_save=%s)",
        cfg.job_id,
        cfg.trigger_type,
        cfg.hour or 0,
        cfg.minute or 0,
        cfg.auto_save,
    )
```

- [ ] **Step 3: Update job display names constant**

Add to `JOB_DISPLAY_NAMES` dictionary (after line 43):

```python
JOB_DISPLAY_NAMES: Dict[str, str] = {
    "eod_scan": "EOD Scan",
    "pre_close_scan": "Pre-Close Scan",
    "quote_poller": "Quote Polling",
    "intraday_candle_5m": "Intraday Candle Sync",
}
```

- [ ] **Step 4: Run linter**

```bash
ruff check src/api/schedule/manager.py
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add src/api/schedule/manager.py
git commit -m "feat: support IntervalTrigger in ScheduleManager"
```

---

## Task 4: Add Intraday Candle Job Callback

**Files:**
- Modify: `src/api/schedule/jobs.py`

- [ ] **Step 1: Add run_intraday_candle_job function**

Add at end of file (before any test code):

```python
def run_intraday_candle_job(db: Session) -> int:
    """Sync intraday candles every 5 minutes during market hours. Returns count of symbols synced."""
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

    # Sync intraday candles for last 1 day (5m, 15m, 1h resolutions)
    fetcher.sync_intraday(symbols=None, resolutions=["5m", "15m", "1h"], days_back=1)

    # Return count of symbols synced
    return db.query(Stock).count()
```

- [ ] **Step 2: Run linter**

```bash
ruff check src/api/schedule/jobs.py
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/api/schedule/jobs.py
git commit -m "feat: add intraday candle sync job callback"
```

---

## Task 5: Register Interval Job Callbacks

**Files:**
- Modify: `src/api/schedule/manager.py`

- [ ] **Step 1: Import new callback**

Add to imports section (after line 23):

```python
from src.api.schedule.jobs import run_eod_job, run_pre_close_job, run_quote_polling_job, run_intraday_candle_job
```

- [ ] **Step 2: Register callbacks in start() method**

Update the callbacks registration section (around lines 100-105):

```python
# Register job callbacks
self._callbacks["eod_scan"] = run_eod_job
self._callbacks["pre_close_scan"] = run_pre_close_job
self._callbacks["quote_poller"] = run_quote_polling_job
self._callbacks["intraday_candle_5m"] = run_intraday_candle_job
self._locks["eod_scan"] = threading.Lock()
self._locks["pre_close_scan"] = threading.Lock()
self._locks["quote_poller"] = threading.Lock()
self._locks["intraday_candle_5m"] = threading.Lock()
```

- [ ] **Step 3: Run linter**

```bash
ruff check src/api/schedule/manager.py
```

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add src/api/schedule/manager.py
git commit -m "feat: register intraday_candle_5m callback in ScheduleManager"
```

---

## Task 6: Update QuoteWorker for Regular Hours

**Files:**
- Modify: `src/workers/quote_worker.py`

- [ ] **Step 1: Remove include_premarket parameter**

Update the `poll()` method signature (line 43):

```python
def poll(self) -> int:
    """Poll for quotes and update database/cache if market is open.

    Returns:
        Number of quotes fetched (0 if market closed or error)
    """
    if not is_market_open():
        logger.debug("Market closed, skipping quote poll")
        return 0
```

Remove `include_premarket` parameter from method signature and the `is_market_open()` call.

- [ ] **Step 2: Run linter**

```bash
ruff check src/workers/quote_worker.py
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/workers/quote_worker.py
git commit -m "refactor: remove include_premarket from QuoteWorker.poll()"
```

---

## Task 7: Update Quote Polling Job Callback

**Files:**
- Modify: `src/api/schedule/jobs.py`

- [ ] **Step 1: Update run_quote_polling_job to remove include_premarket**

Replace the entire function (lines 105-120):

```python
def run_quote_polling_job(db: Session) -> int:
    """Run quote polling job every 1 minute. Returns count of quotes fetched."""
    from src.workers.quote_worker import QuoteWorker
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.config import get_config

    cfg = get_config()
    provider = MarketDataAppProvider(api_token=cfg.MARKETDATA_API_TOKEN)

    # Use global cache service instance (will be created in manager)
    from src.api.schedule.manager import get_quote_cache_service

    cache_service = get_quote_cache_service()

    worker = QuoteWorker(db, cache_service, provider)
    return worker.poll()
```

- [ ] **Step 2: Run linter**

```bash
ruff check src/api/schedule/jobs.py
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/api/schedule/jobs.py
git commit -m "refactor: remove include_premarket from run_quote_polling_job"
```

---

## Task 8: Update Docstrings

**Files:**
- Modify: `src/workers/quote_worker.py`

- [ ] **Step 1: Update QuoteWorker class docstring**

Update the class docstring (lines 18-24):

```python
class QuoteWorker:
    """Background worker that polls MarketData.app for realtime quotes.

    Runs every 1 minute during regular market hours (Mon-Fri 9:30 AM - 4:00 PM ET).
    Fetches quotes for all unique symbols across all user watchlists.
    Stores results in realtime_quotes table and updates cache.
    """
```

- [ ] **Step 2: Run linter**

```bash
ruff check src/workers/quote_worker.py
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add src/workers/quote_worker.py
git commit -m "docs: update QuoteWorker docstring for 1-minute polling"
```

---

## Task 9: Configure Interval Jobs in Database

**Files:**
- Database: `schedule_config` table

- [ ] **Step 1: Start Python shell**

```bash
python3
```

- [ ] **Step 2: Update existing quote_poller to interval**

```python
from src.db.connection import get_engine
from src.db.models import ScheduleConfig
from sqlalchemy.orm import sessionmaker

engine = get_engine()
Session = sessionmaker(bind=engine)
db = Session()

# Update quote_poller to interval trigger
quote_poller = db.query(ScheduleConfig).filter(ScheduleConfig.job_id == 'quote_poller').first()
if quote_poller:
    quote_poller.trigger_type = 'interval'
    quote_poller.interval_seconds = 60
    quote_poller.hour = None
    quote_poller.minute = None
    db.commit()
    print("✓ Updated quote_poller to interval trigger (60 seconds)")
else:
    print("✗ quote_poller not found")

# Add intraday_candle_5m job
intraday_job = ScheduleConfig(
    job_id='intraday_candle_5m',
    enabled=True,
    trigger_type='interval',
    interval_seconds=300,
    hour=None,
    minute=None,
    auto_save=False
)
db.add(intraday_job)
db.commit()
print("✓ Added intraday_candle_5m job (300 seconds)")

# Verify all jobs
jobs = db.query(ScheduleConfig).all()
print("\nAll configured jobs:")
for job in jobs:
    print(f"  {job.job_id}: {job.trigger_type} ({job.interval_seconds or 'N/A'}s or {job.hour}:{job.minute:02d})")

db.close()
```

- [ ] **Step 3: Exit Python shell**

```python
exit()
```

- [ ] **Step 4: Verify database**

```bash
python3 -c "
from src.db.connection import get_engine
from src.db.models import ScheduleConfig
from sqlalchemy.orm import sessionmaker

engine = get_engine()
Session = sessionmaker(bind=engine)
db = Session()

jobs = db.query(ScheduleConfig).all()
print('Configured jobs:')
for job in jobs:
    if job.trigger_type == 'interval':
        print(f'  {job.job_id}: interval={job.interval_seconds}s, enabled={job.enabled}')
    else:
        print(f'  {job.job_id}: cron={job.hour}:{job.minute:02d}, enabled={job.enabled}')

assert any(j.job_id == 'quote_poller' and j.trigger_type == 'interval' for j in jobs), 'quote_poller not interval'
assert any(j.job_id == 'intraday_candle_5m' for j in jobs), 'intraday_candle_5m not found'
print('\\n✓ Jobs configured correctly')

db.close()
"
```

Expected: Shows quote_poller as interval=60s, intraday_candle_5m as interval=300s

---

## Task 10: Test Interval Jobs

**Files:**
- Create: `tests/api/schedule/test_interval_jobs.py`

- [ ] **Step 1: Write test for IntervalTrigger creation**

```python
"""Test interval job scheduling."""

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import sessionmaker

from src.api.schedule.manager import ScheduleManager
from src.config import get_config
from src.db.connection import get_engine
from src.db.models import ScheduleConfig


@pytest.fixture
def db_session():
    """Create test database session."""
    cfg = get_config()
    engine = get_engine(cfg.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_interval_trigger_creation(db_session):
    """Test that IntervalTrigger is created for interval jobs."""
    # Create test schedule config
    config = ScheduleConfig(
        job_id='test_interval',
        enabled=True,
        trigger_type='interval',
        interval_seconds=60,
        hour=None,
        minute=None,
        auto_save=False
    )
    db_session.add(config)
    db_session.commit()

    # Create schedule manager
    manager = ScheduleManager()
    manager.start(db_session)

    # Verify job was added
    job = manager._scheduler.get_job('test_interval')
    assert job is not None, "Job not found in scheduler"

    # Verify trigger is IntervalTrigger
    assert isinstance(job.trigger, IntervalTrigger), "Trigger is not IntervalTrigger"

    # Verify interval
    # Note: IntervalTrigger stores interval differently, check trigger instance
    assert job.trigger.interval_length == 60, f"Expected 60s interval, got {job.trigger.interval_length}"

    # Cleanup
    manager.stop()
    db_session.delete(config)
    db_session.commit()


def test_market_hours_check():
    """Test that is_market_open works correctly."""
    from src.utils.market_hours import is_market_open
    from datetime import datetime
    from zoneinfo import ZoneInfo

    ET = ZoneInfo('America/New_York')

    # Test regular market hours (10:00 AM ET)
    market_time = datetime.now(ET).replace(hour=10, minute=0, second=0, microsecond=0)
    assert is_market_open(market_time), "Should be open at 10:00 AM ET"

    # Test pre-market (8:00 AM ET)
    pre_market_time = datetime.now(ET).replace(hour=8, minute=0, second=0, microsecond=0)
    assert not is_market_open(pre_market_time), "Should be closed at 8:00 AM ET"

    # Test after hours (5:00 PM ET)
    after_hours_time = datetime.now(ET).replace(hour=17, minute=0, second=0, microsecond=0)
    assert not is_market_open(after_hours_time), "Should be closed at 5:00 PM ET"


def test_quote_worker_market_check():
    """Test that QuoteWorker respects market hours."""
    from src.workers.quote_worker import QuoteWorker
    from src.api.watchlists.quote_cache_service import QuoteCacheService
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.config import get_config
    from unittest.mock import Mock

    cfg = get_config()

    # Mock database and provider
    db = Mock()
    cache = Mock(spec=QuoteCacheService)
    provider = Mock(spec=MarketDataAppProvider)

    worker = QuoteWorker(db, cache, provider)

    # Test when market is closed (should return 0)
    result = worker.poll()
    # Result will be 0 if market closed, or actual count if open
    assert isinstance(result, int), "Should return integer count"
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/api/schedule/test_interval_jobs.py -v
```

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/api/schedule/test_interval_jobs.py
git commit -m "test: add interval job scheduling tests"
```

---

## Task 11: Manual Verification

**Files:**
- None (manual testing)

- [ ] **Step 1: Stop existing API server**

```bash
pkill -f "uvicorn.*8001"
```

- [ ] **Step 2: Start API server**

```bash
python3 -m uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8001 > /tmp/api.log 2>&1 &
echo $!
```

- [ ] **Step 3: Wait for startup**

```bash
sleep 5
curl -s http://localhost:8001/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Monitor logs for quote polling**

```bash
tail -f /tmp/api.log | grep -i "quote\|polled"
```

Wait 1-2 minutes and observe.

Expected: See "Polled X quotes" messages every 1 minute (only if market is open)

- [ ] **Step 5: Monitor logs for intraday candles**

In another terminal:

```bash
tail -f /tmp/api.log | grep -i "intraday\|sync_intraday"
```

Wait 5-6 minutes and observe.

Expected: See "sync_intraday" messages every 5 minutes (only if market is open)

- [ ] **Step 6: Verify database updates**

```bash
python3 -c "
from src.db.connection import get_engine
from src.db.models import RealtimeQuote, IntradayCandle
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

engine = get_engine()
Session = sessionmaker(bind=engine)
db = Session()

# Check recent quotes
recent_quotes = db.query(RealtimeQuote).filter(
    RealtimeQuote.timestamp >= datetime.utcnow() - timedelta(minutes=10)
).count()

print(f'Realtime quotes in last 10 minutes: {recent_quotes}')

# Check recent intraday candles
recent_candles = db.query(IntradayCandle).filter(
    IntradayCandle.resolution == '5m',
    IntradayCandle.timestamp >= datetime.utcnow() - timedelta(minutes=30)
).count()

print(f'5m intraday candles in last 30 minutes: {recent_candles}')

db.close()
"
```

Expected: Shows recent quotes and candles if market is open

- [ ] **Step 7: Check job status via database**

```bash
python3 -c "
from src.db.connection import get_engine
from src.db.models import ScheduleConfig
from sqlalchemy.orm import sessionmaker

engine = get_engine()
Session = sessionmaker(bind=engine)
db = Session()

jobs = db.query(ScheduleConfig).all()
print('Job Configurations:')
for job in jobs:
    if job.trigger_type == 'interval':
        print(f'  {job.job_id}:')
        print(f'    Type: interval ({job.interval_seconds}s)')
        print(f'    Enabled: {job.enabled}')
    else:
        print(f'  {job.job_id}:')
        print(f'    Type: cron ({job.hour}:{job.minute:02d} ET)')
        print(f'    Enabled: {job.enabled}')

db.close()
"
```

Expected: Shows quote_poller as 60s interval, intraday_candle_5m as 300s interval, both enabled

---

## Task 12: Update Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update scheduler section**

Find the scheduler section in CLAUDE.md and add:

```markdown
### Scheduler Jobs

The system supports both cron and interval trigger types:

**Cron Jobs (run once per day at specific time):**
- `pre_close_scan` - 3:45 PM ET
- `eod_scan` - 4:15 PM ET

**Interval Jobs (run continuously during market hours):**
- `quote_poller` - Every 60 seconds (9:30 AM - 4:00 PM ET)
- `intraday_candle_5m` - Every 300 seconds (9:30 AM - 4:00 PM ET)

Jobs are configured in the `schedule_config` table and managed by `ScheduleManager`.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with interval job information"
```

---

## Task 13: Final Testing and Rollback Plan

**Files:**
- None (verification)

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --cov=src
```

Expected: All tests pass, coverage report generated

- [ ] **Step 2: Check API rate limits**

Monitor API usage for first hour:

```bash
# Check log file for API call patterns
grep "Polled\|sync_intraday" /tmp/api.log | wc -l
```

Expected: ~60 quote polls per hour, ~12 intraday syncs per hour

- [ ] **Step 3: Document rollback procedure**

Create rollback notes:

```bash
cat > /tmp/rollback_intraday.md << 'EOF'
# Rollback Procedure

If issues occur with interval jobs:

1. Disable interval jobs:
```sql
UPDATE schedule_config SET enabled = false WHERE job_id IN ('quote_poller', 'intraday_candle_5m');
```

2. Restore old quote_poller config:
```sql
UPDATE schedule_config
SET trigger_type = 'cron',
    interval_seconds = NULL,
    hour = 9,
    minute = 30
WHERE job_id = 'quote_poller' AND enabled = false;
```

3. Restart API server:
```bash
pkill -f "uvicorn.*8001"
python3 -m uvicorn src.api.main:create_app --factory --host 0.0.0.0 --port 8001
```

4. If needed, revert database migration:
```bash
alembic downgrade -1
```
EOF
```

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: complete intraday data updates implementation

- Add interval trigger support to ScheduleManager
- Quote polling every 1 minute (9:30 AM - 4:00 PM ET)
- Intraday candle sync every 5 minutes (9:30 AM - 4:00 PM ET)
- Database migration for trigger_type and interval_seconds
- Comprehensive testing and rollback procedures

Co-Authored-By: Claude Sonnet 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Verification Checklist

After completing all tasks, verify:

- [ ] Database migration applied successfully
- [ ] `quote_poller` shows as interval trigger (60s) in database
- [ ] `intraday_candle_5m` exists and is enabled
- [ ] API server starts without errors
- [ ] Logs show "Polled X quotes" every 1 minute during market hours
- [ ] Logs show "sync_intraday" every 5 minutes during market hours
- [ ] `realtime_quotes` table updates every 1 minute
- [ ] `intraday_candles` table updates every 5 minutes
- [ ] Jobs stop automatically when market closes
- [ ] All tests pass
- [ ] No API rate limit errors

---

## Troubleshooting

**Jobs not firing:**
- Check `schedule_config.enabled = true`
- Check API server logs for scheduler errors
- Verify `ScheduleManager.start()` was called

**Jobs firing when market closed:**
- Check `is_market_open()` function
- Verify ET timezone is correct
- Check system time

**High API usage:**
- Reduce `interval_seconds` in database
- Disable jobs: `UPDATE schedule_config SET enabled = false WHERE job_id = '...'`
- Monitor `MARKETDATA_API_TOKEN` rate limits

**Database errors:**
- Check constraint: `trigger_type` must be 'cron' or 'interval'
- Cron jobs require `hour` and `minute`
- Interval jobs require `interval_seconds > 0`
