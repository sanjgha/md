# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"     # Install with dev dependencies
pytest tests/               # Run all tests
pytest tests/unit/test_foo.py::test_bar  # Run a single test
pytest tests/ --cov=src --cov-report=term-missing  # Run with coverage
ruff check src/ tests/      # Lint
black src/ tests/           # Format (100-char line length)
mypy src/ --ignore-missing-imports  # Type check
make ci                     # Run full CI pipeline locally (lint + type-check + tests)
```

## Architecture

This is a **hybrid market data infrastructure** for a 500-stock universe. Data flows:

```
MarketData.app API → DataProvider → DataFetcher → PostgreSQL → Scanner → OutputHandler
```

**Key layers:**

- `src/data_provider/` — Abstract `DataProvider` interface (`base.py`) + `MarketDataAppProvider` implementation. Add new providers by subclassing `DataProvider`.
- `src/data_fetcher/fetcher.py` — Orchestrates bulk ingestion (daily candles, earnings, cleanup) using a `DataProvider`. `scheduler.py` wraps this with APScheduler (runs EOD at 4:15 PM ET Mon-Fri).
- `src/db/` — SQLAlchemy models (`models.py`) + connection/engine factory. Migrations via Alembic (`alembic.ini`). PostgreSQL-specific: uses JSONB for `scanner_results.result_metadata`.
- `src/scanner/` — `Scanner` abstract base → concrete scanners in `scanners/` (price action, momentum, volume). `ScannerRegistry` + `ScannerExecutor` wire indicators to scanners. Indicators live in `scanner/indicators/` (moving averages, momentum, volatility, support/resistance, breakout patterns).
- `src/output/` — `CompositeOutputHandler` fans out to CLI + log file handlers.
- `src/realtime_monitor/` — Polls quotes for tickers that matched a scanner; `AlertEngine` + `Rules` evaluate alert conditions.
- `src/config.py` — `get_config()` is `@lru_cache`; requires `DATABASE_URL` and `MARKETDATA_API_TOKEN` env vars. Use `.env` at repo root for local dev. **Call `get_config.cache_clear()` in tests that set env vars.**
- `src/main.py` — Click CLI entry point with commands: `eod`, `monitor`, `init-db`, `seed-universe`, `schedule`.

## Database Migrations

```bash
alembic upgrade head                          # Apply all pending migrations
alembic revision --autogenerate -m "message"  # Generate migration from model changes
alembic downgrade -1                          # Roll back one migration
```

After editing `src/db/models.py`, generate + review a migration before running tests.

## Testing

- Integration tests use **testcontainers** to spin up a real PostgreSQL 16 container (`tests/conftest.py`). Docker must be running.
- `db_session` fixture truncates all tables after each test — safe to commit inside tests.
- Unit tests mock the DB and provider; do not use testcontainers.
- `pytest` is configured in `pyproject.toml` with `--cov=src` by default, so coverage is always reported.

## Workflow

- **Before starting any feature or fix**, create a Linear issue using the prescribed template in `docs/linear/templates/` (`new-issue.md`, `bug-report.md`, or `enhancement.md`). Pick up one issue at a time.
- **Follow TDD**: write a failing test first, then implement to make it pass.
- **Commit messages** must follow Conventional Commits (`feat:`, `fix:`, `test:`, `refactor:`, `chore:`) — enforced by pre-commit hooks.
