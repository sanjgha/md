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
