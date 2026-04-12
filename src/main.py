"""Market Data Infrastructure CLI entry point."""

import csv
import logging

import click

logger = logging.getLogger(__name__)


@click.group()
def app():
    """Market Data Infrastructure CLI."""
    pass


def _get_db_session():
    """Lazy DB session factory — called at runtime, never at import time."""
    from src.config import get_config
    from src.db.connection import get_engine
    from sqlalchemy.orm import sessionmaker

    cfg = get_config()
    engine = get_engine(cfg.DATABASE_URL)
    return sessionmaker(bind=engine)()


@app.command()
@click.option("--symbols", multiple=True, help="Stock symbols to sync (default: all)")
def eod(symbols):
    """Run EOD scanner pipeline."""
    from src.config import get_config
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.data_fetcher.fetcher import DataFetcher
    from src.scanner.registry import ScannerRegistry
    from src.scanner.executor import ScannerExecutor
    from src.scanner.indicators.moving_averages import SMA, EMA, WMA
    from src.scanner.indicators.momentum import RSI, MACD
    from src.scanner.indicators.volatility import BollingerBands, ATR
    from src.scanner.indicators.support_resistance import SupportResistance
    from src.scanner.indicators.patterns.breakouts import BreakoutDetector
    from src.scanner.scanners import PriceActionScanner, MomentumScanner, VolumeScanner
    from src.output.cli import CLIOutputHandler
    from src.output.logger import LogFileOutputHandler
    from src.output.composite import CompositeOutputHandler
    from src.db.models import Stock
    from sqlalchemy.orm import joinedload
    from datetime import date

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting EOD pipeline...")

    db = _get_db_session()
    try:
        provider = MarketDataAppProvider(
            api_token=cfg.MARKETDATA_API_TOKEN,
            max_retries=cfg.MAX_RETRIES,
            retry_backoff_base=cfg.RETRY_BACKOFF_BASE,
        )
        fetcher = DataFetcher(provider=provider, db=db, rate_limit_delay=cfg.API_RATE_LIMIT_DELAY)

        logger.info("Fetching daily candles...")
        fetcher.sync_daily(symbols=list(symbols) if symbols else None)

        logger.info("Fetching earnings...")
        fetcher.sync_earnings(symbols=list(symbols) if symbols else None)

        logger.info("Cleaning up old data...")
        fetcher.cleanup_old_intraday()
        fetcher.cleanup_old_quotes()

        indicators = {
            "sma": SMA(),
            "ema": EMA(),
            "wma": WMA(),
            "rsi": RSI(),
            "macd": MACD(),
            "bollinger": BollingerBands(),
            "atr": ATR(),
            "support_resistance": SupportResistance(),
            "breakout": BreakoutDetector(),
        }

        scanner_registry = ScannerRegistry()
        scanner_registry.register("price_action", PriceActionScanner())
        scanner_registry.register("momentum", MomentumScanner())
        scanner_registry.register("volume", VolumeScanner())

        output = CompositeOutputHandler(
            [
                CLIOutputHandler(),
                LogFileOutputHandler(log_file=cfg.LOG_FILE, log_level=cfg.LOG_LEVEL),
            ]
        )

        stocks = db.query(Stock).options(joinedload(Stock.daily_candles)).all()
        executor = ScannerExecutor(
            registry=scanner_registry,
            indicators_registry=indicators,
            output_handler=output,
            db=db,
        )
        stocks_with_candles = {
            s.id: (
                s.symbol,
                executor._to_candles(sorted(s.daily_candles, key=lambda c: c.timestamp)),
            )
            for s in stocks
            if s.daily_candles
        }

        results = executor.run_eod(stocks_with_candles)
        logger.info(f"Scan complete. Found {len(results)} matches.")

        # Auto-generate watchlists from scanner results
        try:
            from src.api.watchlists.service import WatchlistGenerationService
            from src.db.models import User

            # Get first user (single-user deployment)
            user = db.query(User).first()
            if user:
                watchlist_service = WatchlistGenerationService(db)

                # Group results by scanner
                scanner_names = set(r.scanner_name for r in results)

                for scanner_name in scanner_names:
                    watchlist = watchlist_service.generate_from_scanner_results(
                        scanner_name=scanner_name,
                        scan_date=date.today(),
                        user_id=user.id,
                    )
                    if watchlist:
                        logger.info(f"Created watchlist: {watchlist.name}")

                logger.info("Watchlist generation complete.")
        except Exception as e:
            logger.error(f"Watchlist generation failed: {e}", exc_info=True)
            # Don't fail the scan if watchlist generation fails

        logger.info(f"EOD complete. Found {len(results)} matches.")
        click.echo(f"EOD pipeline complete. {len(results)} matches found.")

    except Exception as e:
        logger.error(f"EOD pipeline failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command()
@click.option("--scanner", default="price_action", help="Scanner to monitor results from")
@click.option("--interval", default=5, type=int, help="Poll interval in seconds")
def monitor(scanner, interval):
    """Run realtime monitor for scanner matches."""
    from src.config import get_config
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.output.cli import CLIOutputHandler
    from src.output.logger import LogFileOutputHandler
    from src.output.composite import CompositeOutputHandler
    from src.realtime_monitor.monitor import RealtimeMonitor
    from src.realtime_monitor.alert_engine import AlertEngine

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info(f"Starting realtime monitor for {scanner} scanner...")

    db = _get_db_session()
    try:
        provider = MarketDataAppProvider(
            api_token=cfg.MARKETDATA_API_TOKEN,
            max_retries=cfg.MAX_RETRIES,
            retry_backoff_base=cfg.RETRY_BACKOFF_BASE,
        )
        output = CompositeOutputHandler(
            [
                CLIOutputHandler(),
                LogFileOutputHandler(log_file=cfg.LOG_FILE, log_level=cfg.LOG_LEVEL),
            ]
        )
        alert_engine = AlertEngine()
        mon = RealtimeMonitor(
            provider=provider,
            db=db,
            output_handler=output,
            alert_engine=alert_engine,
        )
        mon.load_scanner_results(scanner)

        if not mon.watched_tickers:
            logger.warning(f"No matches found for {scanner}")
            click.echo(f"No matches found for scanner '{scanner}'.")
            return

        logger.info(f"Monitoring {len(mon.watched_tickers)} tickers")
        mon.poll_quotes(interval_seconds=interval)

    except KeyboardInterrupt:
        logger.info("Monitor stopped by user")
        click.echo("Monitor stopped.")
    except Exception as e:
        logger.error(f"Monitor failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command("init-db")
def init_db_cmd():
    """Initialize database schema."""
    from src.config import get_config
    from src.db.connection import get_engine, init_db

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Initializing database...")
    try:
        engine = get_engine(cfg.DATABASE_URL)
        init_db(engine)
        logger.info("Database initialized successfully")
        click.echo("Database initialized.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        click.echo(f"Error: {e}", err=True)


@app.command("seed-universe")
@click.option(
    "--file",
    "universe_file",
    type=click.Path(exists=True),
    help="CSV with symbol,name,sector columns",
)
@click.option("--symbols", multiple=True, help="Stock symbols to add")
def seed_universe(universe_file, symbols):
    """Seed stock universe from CSV or symbol list."""
    from src.db.models import Stock

    db = _get_db_session()
    try:
        added = 0
        if universe_file:
            with open(universe_file) as f:
                for row in csv.DictReader(f):
                    sym = row["symbol"].strip().upper()
                    if not db.query(Stock).filter_by(symbol=sym).first():
                        db.add(
                            Stock(
                                symbol=sym,
                                name=row.get("name", ""),
                                sector=row.get("sector", ""),
                            )
                        )
                        added += 1
        for sym in symbols:
            sym = sym.strip().upper()
            if not db.query(Stock).filter_by(symbol=sym).first():
                db.add(Stock(symbol=sym))
                added += 1
        db.commit()
        total = db.query(Stock).count()
        click.echo(f"Added {added} stocks. Universe total: {total}")
    except Exception as e:
        logger.error(f"seed-universe failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command("schedule")
def schedule_cmd():
    """Start the blocking APScheduler (runs EOD pipeline at 4:15 PM ET Mon-Fri)."""
    from src.data_fetcher.scheduler import create_eod_scheduler
    from src.config import get_config

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting APScheduler...")

    def run_eod():
        """Callback invoked by scheduler."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(eod, [])
        if result.exit_code != 0:
            logger.error(f"Scheduled EOD failed: {result.output}")

    scheduler = create_eod_scheduler(run_eod)
    try:
        click.echo("Scheduler started. Press Ctrl+C to stop.")
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Scheduler stopped.")


if __name__ == "__main__":
    app()
