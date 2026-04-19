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
def fetch_data(symbols):
    """Fetch and sync market data (daily candles, earnings, cleanup)."""
    from src.config import get_config
    from src.data_provider.marketdata_app import MarketDataAppProvider
    from src.data_fetcher.fetcher import DataFetcher

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting data fetch...")

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

        logger.info("Fetching intraday candles...")
        fetcher.sync_intraday(symbols=list(symbols) if symbols else None)

        logger.info("Cleaning up old data...")
        fetcher.cleanup_old_intraday()
        fetcher.cleanup_old_quotes()

        logger.info("Data fetch complete.")
        click.echo("Data fetch complete.")

    except Exception as e:
        logger.error(f"Data fetch failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command()
def scan():
    """Run scanners on existing data."""
    from src.config import get_config
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
    logger.info("Starting scanner...")

    db = _get_db_session()
    try:
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

        click.echo(f"Scan complete. {len(results)} matches found.")

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command()
@click.option("--symbols", multiple=True, help="Stock symbols to sync (default: all)")
def eod(symbols):
    """Run EOD scanner pipeline (fetch + scan combined)."""
    from click.testing import CliRunner
    from src.config import get_config

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting EOD pipeline...")

    try:
        # Run fetch-data
        runner = CliRunner()
        result = runner.invoke(fetch_data, list(symbols))
        if result.exit_code != 0:
            logger.error(f"Data fetch failed: {result.output}")
            click.echo(f"Error: {result.output}", err=True)
            return

        # Run scan
        result = runner.invoke(scan, [])
        if result.exit_code != 0:
            logger.error(f"Scan failed: {result.output}")
            click.echo(f"Error: {result.output}", err=True)
            return

        click.echo("EOD pipeline complete.")
    except Exception as e:
        logger.error(f"EOD pipeline failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)


@app.command()
@click.option("--scanner", default="price_action", help="Scanner to monitor results from")
@click.option(
    "--interval", default=300, type=int, help="Poll interval in seconds (default: 5 minutes)"
)
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


@app.command("status")
def status_cmd():
    """Show daily run status and scanner results."""
    from src.config import get_config
    from src.db.models import ScannerResult
    from datetime import datetime
    from sqlalchemy.orm import joinedload

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)

    db = _get_db_session()
    try:
        # Get today's date in ET
        now = datetime.utcnow()
        today = now.date()

        # Get latest scanner results
        results = (
            db.query(ScannerResult)
            .options(joinedload(ScannerResult.stock))
            .filter(ScannerResult.matched_at >= today)
            .order_by(ScannerResult.matched_at.desc())
            .all()
        )

        # Group by scanner
        scanner_counts = {}
        for r in results:
            scanner_counts[r.scanner_name] = scanner_counts.get(r.scanner_name, 0) + 1

        # Display status
        click.echo(f"\n{'=' * 60}")
        click.echo("Market Data Infrastructure Status")
        click.echo(f"{'=' * 60}")
        click.echo(f"Date: {today.strftime('%Y-%m-%d')}")
        click.echo(f"Time: {now.strftime('%H:%M:%S')} UTC")
        click.echo(f"Total Matches: {len(results)}")
        click.echo(f"{'=' * 60}\n")

        # Scanner summary
        if scanner_counts:
            click.echo("Scanner Results:")
            for scanner, count in sorted(scanner_counts.items()):
                click.echo(f"  {scanner}: {count} matches")
            click.echo()

        # Recent matches (top 20)
        if results:
            click.echo(f"Recent Matches (showing {min(20, len(results))}):")
            click.echo(f"{'Symbol':<10} {'Scanner':<15} {'Reason':<30} {'Time'}")
            click.echo("-" * 80)
            for r in results[:20]:
                symbol = r.stock.symbol if r.stock else "Unknown"
                metadata = r.result_metadata or {}
                reason = metadata.get("reason", "N/A")
                time_str = r.matched_at.strftime("%H:%M:%S")
                click.echo(f"{symbol:<10} {r.scanner_name:<15} {reason:<30} {time_str}")
        else:
            click.echo("No matches found today.")

        click.echo(f"\n{'=' * 60}\n")

        # Check for recent errors in logs
        import os

        log_file = cfg.LOG_FILE
        if os.path.exists(log_file):
            # Get last 50 lines from log
            with open(log_file, "r") as f:
                lines = f.readlines()[-50:]
            error_count = sum(1 for line in lines if "ERROR" in line)
            if error_count > 0:
                click.echo(f"⚠️  Found {error_count} errors in recent logs")
            else:
                click.echo("✅ No errors in recent logs")

    except Exception as e:
        logger.error(f"Status command failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command("schedule-analyze")
def schedule_analyze_cmd():
    """Start scheduler for analysis (runs at 9:00 AM ET Mon-Fri)."""
    from src.config import get_config
    from click.testing import CliRunner

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting analysis scheduler...")

    def run_analyze():
        """Invoke the analysis callback."""
        runner = CliRunner()
        result = runner.invoke(analyze_cmd, ["--days", "1"])
        if result.exit_code != 0:
            logger.error(f"Scheduled analysis failed: {result.output}")

    # Create scheduler for 9:00 AM ET
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_analyze,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=9,
            minute=0,
            timezone="America/New_York",
        ),
        id="analyze",
        name="Trading Analysis Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )

    try:
        click.echo("Analysis scheduler started. Runs at 9:00 AM ET Mon-Fri. Press Ctrl+C to stop.")
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Analysis scheduler stopped.")


@app.command("analyze")
@click.option("--scanner", default=None, help="Filter by scanner name")
@click.option("--days", default=1, type=int, help="Number of days to analyze")
@click.option("--api-key", default=None, help="GLM API key (overrides GLM_API_KEY env var)")
def analyze_cmd(scanner, days, api_key):
    """Analyze scanner results with technical analysis (no AI required)."""
    from src.config import get_config
    from src.db.models import ScannerResult, DailyCandle
    from datetime import datetime, timedelta
    from sqlalchemy.orm import joinedload
    from collections import defaultdict

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)

    db = _get_db_session()
    try:
        # Get results for the specified period
        since_date = datetime.utcnow() - timedelta(days=days)
        query = (
            db.query(ScannerResult)
            .options(joinedload(ScannerResult.stock))
            .filter(ScannerResult.matched_at >= since_date)
        )

        if scanner:
            query = query.filter(ScannerResult.scanner_name == scanner)

        results = query.order_by(ScannerResult.matched_at.desc()).all()

        if not results:
            click.echo("No scanner results found for the specified period.")
            return

        # Prepare analysis data
        analysis_data = []
        for r in results:
            stock = r.stock
            if not stock:
                continue

            # Get recent price data
            recent_candles = (
                db.query(DailyCandle)
                .filter_by(stock_id=stock.id)
                .order_by(DailyCandle.timestamp.desc())
                .limit(20)
                .all()
            )

            if len(recent_candles) < 10:
                continue

            candles = sorted(recent_candles, key=lambda c: c.timestamp)
            latest = candles[-1]

            # Calculate basic metrics
            highs = [c.high for c in candles[-10:]]
            lows = [c.low for c in candles[-10:]]

            analysis_data.append(
                {
                    "symbol": stock.symbol,
                    "scanner": r.scanner_name,
                    "signal": (
                        r.result_metadata.get("reason", "N/A") if r.result_metadata else "N/A"
                    ),
                    "current_price": latest.close,
                    "volume": latest.volume,
                    "avg_volume_20d": sum(c.volume for c in candles[-20:]) / min(20, len(candles)),
                    "price_range_10d": max(highs) - min(lows),
                    "price_change_10d": ((latest.close - candles[-10].close) / candles[-10].close)
                    * 100,
                    "high_10d": max(highs),
                    "low_10d": min(lows),
                    "rsi": r.result_metadata.get("rsi") if r.result_metadata else None,
                    "support_level": (
                        r.result_metadata.get("support_level") if r.result_metadata else None
                    ),
                    "date": r.matched_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        if not analysis_data:
            click.echo("No sufficient data for analysis.")
            return

        click.echo("=" * 80)
        click.echo("TECHNICAL ANALYSIS SUMMARY")
        click.echo("=" * 80)
        click.echo()

        # 1. Overall Market Sentiment
        scanner_counts = defaultdict(list)
        for item in analysis_data:
            scanner_counts[item["scanner"]].append(item)

        overbought_count = sum(
            1 for item in analysis_data if "overbought" in item["signal"].lower()
        )
        oversold_count = sum(1 for item in analysis_data if "oversold" in item["signal"].lower())
        volume_spike_up = sum(
            1 for item in analysis_data if "volume_spike_up" in item["signal"].lower()
        )

        total_signals = len(analysis_data)
        bullish_ratio = (
            (overbought_count + volume_spike_up) / total_signals if total_signals > 0 else 0
        )

        click.echo("📊 MARKET SENTIMENT")
        click.echo("-" * 40)
        if bullish_ratio > 0.6:
            sentiment = "🟢 BULLISH"
            explanation = f"Strong buying pressure with {overbought_count} overbought signals"
        elif bullish_ratio < 0.4:
            sentiment = "🔴 BEARISH"
            explanation = f"Selling pressure with {oversold_count} oversold signals"
        else:
            sentiment = "🟡 NEUTRAL"
            explanation = "Mixed signals, wait for confirmation"

        click.echo(f"Sentiment: {sentiment}")
        click.echo(f"Explanation: {explanation}")
        click.echo(
            f"Total Signals: {total_signals} (Bullish: {overbought_count + volume_spike_up}, Bearish: {oversold_count})"
        )
        click.echo()

        # 2. Top 5 High-Conviction Setups
        click.echo("🎯 TOP 5 HIGH-CONVICTION SETUPS")
        click.echo("-" * 40)

        # Score stocks by conviction
        scored_stocks = []
        for item in analysis_data:
            score = 0
            reasons = []

            # Momentum signals
            if item["rsi"]:
                if item["rsi"] < 30:
                    score += 3
                    reasons.append("Deeply oversold RSI")
                elif item["rsi"] > 70:
                    score += 2
                    reasons.append("Overbought RSI")

            # Volume signals
            if "volume_spike_up" in item["signal"].lower():
                score += 3
                reasons.append("Strong volume breakout")
            elif "volume_spike_down" in item["signal"].lower():
                score += 1
                reasons.append("High volume decline")

            # Price action signals
            if item["support_level"]:
                score += 2
                reasons.append(f"Bounce off support at ${item['support_level']:.2f}")

            # Price momentum
            if item["price_change_10d"] > 5:
                score += 1
                reasons.append(f"Strong {item['price_change_10d']:.1f}% 10-day gain")

            scored_stocks.append(
                {
                    "symbol": item["symbol"],
                    "score": score,
                    "reasons": reasons,
                    "price": item["current_price"],
                    "signal": item["signal"],
                    "scanner": item["scanner"],
                }
            )

        # Sort by score and get top 5
        scored_stocks.sort(key=lambda x: x["score"], reverse=True)
        top_5 = scored_stocks[:5]

        for i, stock in enumerate(top_5, 1):
            click.echo(
                f"\n{i}. {stock['symbol']} @ ${stock['price']:.2f} (Score: {stock['score']})"
            )
            click.echo(f"   Signal: {stock['signal']}")
            click.echo(f"   Scanner: {stock['scanner']}")
            click.echo(f"   Reasons: {', '.join(stock['reasons'])}")

        click.echo()

        # 3. Risk Assessment
        click.echo("⚠️  RISK ASSESSMENT")
        click.echo("-" * 40)

        # Calculate risk levels
        prices = [item["current_price"] for item in analysis_data]
        avg_price = sum(prices) / len(prices)

        high_risk_stocks = [item for item in analysis_data if item["price_change_10d"] > 10]
        moderate_risk_stocks = [
            item for item in analysis_data if 5 < item["price_change_10d"] <= 10
        ]

        click.echo(f"High Volatility Stocks (10d change > 10%): {len(high_risk_stocks)}")
        for stock in high_risk_stocks[:3]:
            click.echo(f"  - {stock['symbol']}: {stock['price_change_10d']:.1f}% move")

        click.echo(f"\nModerate Volatility Stocks (10d change 5-10%): {len(moderate_risk_stocks)}")

        # Support/Resistance levels
        support_stocks = [item for item in analysis_data if item["support_level"]]
        click.echo(f"\nStocks Near Support Levels: {len(support_stocks)}")
        for stock in support_stocks[:5]:
            current_price = float(stock["current_price"])
            support_level = float(stock["support_level"])
            distance = ((current_price - support_level) / support_level) * 100
            click.echo(f"  - {stock['symbol']}: Support @ ${support_level:.2f} ({distance:+.1f}%)")

        click.echo()

        # 4. Trading Strategy
        click.echo("💡 TRADING STRATEGY")
        click.echo("-" * 40)

        if oversold_count > 5:
            click.echo("Strategy: Consider long positions on deeply oversold stocks")
            click.echo("Entry: Wait for confirmation (volume spike + price reversal)")
            click.echo("Stop Loss: 2-3% below entry")
            click.echo("Target: 5-8% gains or next resistance level")
        elif overbought_count > 5:
            click.echo("Strategy: Consider taking profits on overbought positions")
            click.echo("Entry: Wait for pullback to support levels")
            click.echo("Stop Loss: 3-5% below entry for swing trades")
            click.echo("Target: Quick 3-5% gains, avoid chasing")
        else:
            click.echo("Strategy: Wait for confirmation before entering new positions")
            click.echo("Entry: Look for stocks with multiple signal confirmation")
            click.echo("Stop Loss: 2-3% below support levels")
            click.echo("Target: 5-10% gains based on volatility")

        click.echo()
        click.echo("Position Sizing Guidelines:")
        click.echo("  - High conviction (score 8+): 2-3% of portfolio")
        click.echo("  - Medium conviction (score 5-7): 1-2% of portfolio")
        click.echo("  - Low conviction (score < 5): 0.5-1% or skip")

        click.echo()

        # 5. Sector/Scanner Themes
        click.echo("📈 SCANNER THEME ANALYSIS")
        click.echo("-" * 40)

        # Create symbol to score mapping
        symbol_scores = {stock["symbol"]: stock["score"] for stock in scored_stocks}

        for scanner_name, items in scanner_counts.items():
            if items:
                avg_price = sum(item["current_price"] for item in items) / len(items)
                avg_volume = sum(item["volume"] for item in items) / len(items)

                # Get top picks by score
                scanner_top_picks = sorted(
                    [item for item in items if item["symbol"] in symbol_scores],
                    key=lambda x: symbol_scores.get(x["symbol"], 0),
                    reverse=True,
                )[:3]

                click.echo(f"\n{scanner_name.upper()} Scanner ({len(items)} stocks):")
                click.echo(f"  Avg Price: ${avg_price:.2f}")
                click.echo(f"  Avg Volume: {avg_volume:,.0f}")
                if scanner_top_picks:
                    click.echo(
                        f"  Top Picks: {', '.join([item['symbol'] for item in scanner_top_picks])}"
                    )
                else:
                    click.echo(f"  Top Picks: {', '.join([item['symbol'] for item in items[:3]])}")

        click.echo()
        click.echo("=" * 80)
        click.echo(
            "⏰ Analysis generated at: " + datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        )
        click.echo("=" * 80)

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()


@app.command("schedule-fetch")
def schedule_fetch_cmd():
    """Start scheduler for data fetching (runs at 4:15 PM ET Mon-Fri)."""
    from src.config import get_config
    from click.testing import CliRunner

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting data fetch scheduler...")

    def run_fetch():
        """Invoke the fetch callback."""
        runner = CliRunner()
        result = runner.invoke(fetch_data, [])
        if result.exit_code != 0:
            logger.error(f"Scheduled data fetch failed: {result.output}")

    # Create scheduler for 4:15 PM ET
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_fetch,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=16,
            minute=15,
            timezone="America/New_York",
        ),
        id="data_fetch",
        name="Data Fetch Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )

    try:
        click.echo(
            "Data fetch scheduler started. Runs at 4:15 PM ET Mon-Fri. Press Ctrl+C to stop."
        )
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Data fetch scheduler stopped.")


@app.command("schedule-scan")
def schedule_scan_cmd():
    """Start scheduler for scanning (runs at 5:00 PM ET Mon-Fri)."""
    from src.config import get_config
    from click.testing import CliRunner

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting scan scheduler...")

    def run_scan():
        """Invoke the scan callback."""
        runner = CliRunner()
        result = runner.invoke(scan, [])
        if result.exit_code != 0:
            logger.error(f"Scheduled scan failed: {result.output}")

    # Create scheduler for 5:00 PM ET
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_scan,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=17,
            minute=0,
            timezone="America/New_York",
        ),
        id="scan",
        name="Scanner Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )

    try:
        click.echo("Scan scheduler started. Runs at 5:00 PM ET Mon-Fri. Press Ctrl+C to stop.")
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Scan scheduler stopped.")


@app.command("schedule-pre-close")
def schedule_pre_close_cmd():
    """Start scheduler for pre-close scanning (runs at 3:45 PM ET Mon-Fri)."""
    from src.config import get_config

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting pre-close scan scheduler...")

    def run_pre_close_scan():
        """Instantiate PreCloseExecutor and run pre-close scans."""
        from src.scanner.pre_close_executor import PreCloseExecutor
        from src.scanner.registry import ScannerRegistry
        from src.scanner.indicators.moving_averages import SMA, EMA, WMA
        from src.scanner.indicators.momentum import RSI, MACD
        from src.scanner.indicators.volatility import BollingerBands, ATR
        from src.scanner.indicators.support_resistance import SupportResistance
        from src.scanner.indicators.patterns.breakouts import BreakoutDetector
        from src.scanner.scanners import PriceActionScanner, MomentumScanner, VolumeScanner
        from src.output.cli import CLIOutputHandler
        from src.output.logger import LogFileOutputHandler
        from src.output.composite import CompositeOutputHandler

        db = _get_db_session()
        try:
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

            executor = PreCloseExecutor(
                registry=scanner_registry,
                indicators_registry=indicators,
                output_handler=output,
                db=db,
            )
            results = executor.run()
            logger.info(f"Pre-close scan complete. Found {len(results)} matches.")
        except Exception as e:
            logger.error(f"Pre-close scan job failed: {e}", exc_info=True)
        finally:
            db.close()

    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler(timezone="America/New_York")
    scheduler.add_job(
        run_pre_close_scan,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=15,
            minute=45,
            timezone="America/New_York",
        ),
        id="pre_close_scan",
        name="Pre-Close Scanner Pipeline",
        misfire_grace_time=300,
        coalesce=True,
    )

    try:
        click.echo(
            "Pre-close scan scheduler started. Runs at 3:45 PM ET Mon-Fri. Press Ctrl+C to stop."
        )
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
        click.echo("Pre-close scan scheduler stopped.")


@app.command("schedule")
def schedule_cmd():
    """Start the blocking APScheduler (runs EOD pipeline at 4:15 PM ET Mon-Fri)."""
    from src.data_fetcher.scheduler import create_eod_scheduler
    from src.config import get_config

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting APScheduler...")

    def run_eod():
        """Invoke the EOD callback."""
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
