"""APScheduler setup for EOD pipeline automation."""

import logging

import subprocess  # nosec: B404
from datetime import date
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


def create_eod_scheduler(eod_callback) -> BlockingScheduler:
    """Schedule EOD pipeline at 4:15 PM ET Monday–Friday."""
    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        eod_callback,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16,
            minute=15,
            timezone="America/New_York",
        ),
        id="eod_pipeline",
        name="EOD Scanner Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.add_job(
        _run_options_chain_ingest,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=3,
            minute=0,
            timezone="America/New_York",
        ),
        id="options_chain_ingest",
        name="Nightly Options Chain Ingestion",
        misfire_grace_time=600,
        coalesce=True,
    )
    scheduler.add_job(
        _run_options_ivr_compute,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=3,
            minute=30,
            timezone="America/New_York",
        ),
        id="options_ivr_compute",
        name="Nightly IVR Computation",
        misfire_grace_time=600,
        coalesce=True,
    )
    scheduler.add_job(
        _run_options_regime_detect,
        trigger=CronTrigger(day_of_week="mon-fri", hour=3, minute=45, timezone="America/New_York"),
        id="options_regime_detect",
        name="Nightly Regime Detection",
        misfire_grace_time=600,
        coalesce=True,
    )
    return scheduler


def _run_options_ivr_compute() -> None:
    """Nightly job: compute and store IVR for every watchlist symbol."""
    import pandas as pd
    from sqlalchemy.orm import sessionmaker

    from src.config import get_config
    from src.db.connection import get_engine
    from src.db.models import DailyCandle, Stock, WatchlistSymbol
    from src.options_agent.ivr import InsufficientHistoryError, compute_and_store_ivr

    cfg = get_config()
    engine = get_engine(cfg.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    computed = 0
    skipped = 0
    try:
        symbols = [
            symbol
            for (symbol,) in session.query(Stock.symbol)
            .join(WatchlistSymbol, WatchlistSymbol.stock_id == Stock.id)
            .distinct()
        ]
        today = date.today()
        for symbol in symbols:
            try:
                rows = (
                    session.query(DailyCandle.timestamp, DailyCandle.close)
                    .join(Stock, Stock.id == DailyCandle.stock_id)
                    .filter(Stock.symbol == symbol)
                    .order_by(DailyCandle.timestamp.asc())
                    .all()
                )
                bars = pd.DataFrame(rows, columns=["date", "close"])
                bars["date"] = pd.to_datetime(bars["date"]).dt.date
                bars["close"] = bars["close"].astype(float)
                compute_and_store_ivr(session, symbol, bars, as_of=today)
                computed += 1
            except InsufficientHistoryError as e:
                logger.info("IVR skipped for %s: %s", symbol, e)
                skipped += 1
        logger.info("IVR compute complete: %d computed, %d skipped", computed, skipped)
    except Exception:
        logger.exception("IVR compute job failed")
    finally:
        session.close()


def _run_options_regime_detect() -> None:
    """Nightly job: compute and store regime for every watchlist symbol."""
    import pandas as pd
    from sqlalchemy.orm import sessionmaker

    from src.config import get_config
    from src.db.connection import get_engine
    from src.db.models import DailyCandle, Stock, WatchlistSymbol
    from src.options_agent.signals.regime import compute_and_store_regime

    cfg = get_config()
    engine = get_engine(cfg.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    computed = 0
    skipped = 0
    try:
        today = date.today()

        # Load SPY bars unconditionally (last 30 candles)
        spy_rows = (
            session.query(DailyCandle.timestamp, DailyCandle.close)
            .join(Stock, Stock.id == DailyCandle.stock_id)
            .filter(Stock.symbol == "SPY")
            .order_by(DailyCandle.timestamp.asc())
            .limit(30)
            .all()
        )
        if not spy_rows:
            logger.warning("No SPY bars found — skipping regime detection for all symbols")
            return

        spy_bars = pd.DataFrame(spy_rows, columns=["date", "close"])
        spy_bars["close"] = spy_bars["close"].astype(float)

        symbols = [
            symbol
            for (symbol,) in session.query(Stock.symbol)
            .join(WatchlistSymbol, WatchlistSymbol.stock_id == Stock.id)
            .distinct()
        ]

        for symbol in symbols:
            try:
                rows = (
                    session.query(
                        DailyCandle.timestamp,
                        DailyCandle.open,
                        DailyCandle.high,
                        DailyCandle.low,
                        DailyCandle.close,
                    )
                    .join(Stock, Stock.id == DailyCandle.stock_id)
                    .filter(Stock.symbol == symbol)
                    .order_by(DailyCandle.timestamp.asc())
                    .all()
                )
                if len(rows) < 30:
                    logger.info("Regime skipped for %s: insufficient bars (%d)", symbol, len(rows))
                    skipped += 1
                    continue
                bars = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close"])
                for col in ("open", "high", "low", "close"):
                    bars[col] = bars[col].astype(float)
                compute_and_store_regime(session, symbol, bars, spy_bars, as_of=today)
                computed += 1
            except Exception:
                logger.exception("Regime detection failed for %s", symbol)
                skipped += 1

        logger.info("Regime detection complete: %d computed, %d skipped", computed, skipped)
    except Exception:
        logger.exception("Regime detection job failed")
    finally:
        session.close()


def _run_options_chain_ingest() -> None:
    """Nightly job: pull latest Dolt data and ingest options chains into PostgreSQL."""
    from src.config import get_config
    from src.db.connection import get_engine
    from src.db.models import Stock, WatchlistSymbol
    from src.options_agent.data.chain_ingester import ChainIngester
    from src.options_agent.data.dolt_client import DoltOptionsClient
    from src.options_agent.data.expiries import determine_target_expiries
    from sqlalchemy.orm import sessionmaker

    cfg = get_config()

    if not Path(cfg.DOLT_REPO_PATH).exists():
        logger.info(
            "options agent: dolt repo not configured at %s, skipping chain ingest",
            cfg.DOLT_REPO_PATH,
        )
        return

    # Pull latest Dolt data
    subprocess.run(  # nosec: B603, B607
        ["dolt", "pull"],
        cwd=cfg.DOLT_REPO_PATH,
        check=False,
        timeout=300,
    )

    engine = get_engine(cfg.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        symbols = [
            symbol
            for (symbol,) in session.query(Stock.symbol)
            .join(WatchlistSymbol, WatchlistSymbol.stock_id == Stock.id)
            .distinct()
        ]
        buckets = determine_target_expiries(date.today())
        dolt_client = DoltOptionsClient(cfg.DOLT_OPTIONS_URL)
        ingester = ChainIngester(dolt_client=dolt_client, session=session)
        total = ingester.ingest_for_symbols(symbols, as_of=date.today(), buckets=buckets)
        logger.info("Options chain ingestion complete: %d rows inserted", total)
    except Exception:
        logger.exception("Options chain ingestion failed")
    finally:
        session.close()
