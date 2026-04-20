"""APScheduler setup for EOD pipeline automation."""

import logging
import subprocess
from datetime import date

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
    return scheduler


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

    # Pull latest Dolt data
    subprocess.run(
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
