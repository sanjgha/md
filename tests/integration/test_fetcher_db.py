"""Integration tests for DataFetcher using testcontainers PostgreSQL."""

from unittest.mock import Mock
from datetime import datetime
from sqlalchemy.orm import Session
from src.data_fetcher.fetcher import DataFetcher
from src.db.models import Stock
from src.data_provider.base import DataProvider, Candle, Earning, NewsArticle


def test_fetcher_bulk_upsert_daily_candles(db_session: Session):
    """Inserting 5 candles for a stock creates 5 rows."""
    stock = Stock(symbol="AAPL", name="Apple")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, i + 1), 150.0, 152.0, 149.0, 151.0, 1000000) for i in range(5)
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["AAPL"])

    aapl = db_session.query(Stock).filter_by(symbol="AAPL").first()  # type: ignore[union-attr]
    assert len(aapl.daily_candles) == 5  # type: ignore[union-attr]


def test_fetcher_daily_no_duplicate_on_resync(db_session: Session):
    """Resyncing the same candle twice does not create duplicates."""
    stock = Stock(symbol="GOOGL", name="Google")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, 1), 150.0, 152.0, 149.0, 151.0, 1000000),
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["GOOGL"])
    fetcher.sync_daily(symbols=["GOOGL"])  # second sync — same data

    googl = db_session.query(Stock).filter_by(symbol="GOOGL").first()
    assert googl is not None, "Stock should exist after sync"
    assert len(googl.daily_candles) == 1  # no duplicate


def test_fetcher_sync_intraday(db_session: Session):
    """sync_intraday creates intraday candle rows."""
    stock = Stock(symbol="TSLA", name="Tesla")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_intraday_candles.return_value = [
        Candle(datetime(2024, 1, 1, 9, 30), 100.0, 101.0, 99.0, 100.5, 50000),
        Candle(datetime(2024, 1, 1, 9, 35), 100.5, 102.0, 100.0, 101.0, 60000),
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_intraday(symbols=["TSLA"], resolutions=["5m"], days_back=1)

    tsla = db_session.query(Stock).filter_by(symbol="TSLA").first()  # type: ignore[union-attr]
    assert len(tsla.intraday_candles) == 2  # type: ignore[union-attr]


def test_fetcher_sync_news(db_session: Session):
    """sync_news creates news rows."""
    stock = Stock(symbol="NVDA", name="Nvidia")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_news.return_value = [
        NewsArticle(
            symbol="NVDA",
            headline="Nvidia releases new GPU",
            content="Details here",
            source="Reuters",
            publication_date=datetime(2024, 1, 1),
        )
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_news(symbols=["NVDA"])

    nvda = db_session.query(Stock).filter_by(symbol="NVDA").first()  # type: ignore[union-attr]
    assert len(nvda.news) == 1  # type: ignore[union-attr]
    assert nvda.news[0].headline == "Nvidia releases new GPU"  # type: ignore[union-attr]


def test_resync_overwrites_stale_candle(db_session: Session):
    """Re-fetching a candle with different close (e.g. post-split adjusted) overwrites the existing row."""
    stock = Stock(symbol="SPLITCO", name="Split Corp")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)

    # First sync: unadjusted price $100
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, 2), 100.0, 102.0, 99.0, 100.0, 1_000_000),
    ]
    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["SPLITCO"])

    splitco = db_session.query(Stock).filter_by(symbol="SPLITCO").first()
    assert splitco is not None
    assert float(splitco.daily_candles[0].close) == 100.0

    # Second sync: adjusted price $50 (2:1 split applied retrospectively)
    mock_provider.get_daily_candles.return_value = [
        Candle(datetime(2024, 1, 2), 50.0, 51.0, 49.5, 50.0, 2_000_000),
    ]
    fetcher.sync_daily(symbols=["SPLITCO"])

    db_session.expire_all()
    splitco = db_session.query(Stock).filter_by(symbol="SPLITCO").first()
    assert splitco is not None
    assert len(splitco.daily_candles) == 1  # no duplicate
    assert float(splitco.daily_candles[0].close) == 50.0  # overwritten


def test_fetcher_sync_earnings(db_session: Session):
    """sync_earnings creates earnings rows without duplicates."""
    stock = Stock(symbol="MSFT", name="Microsoft")
    db_session.add(stock)
    db_session.commit()

    mock_provider = Mock(spec=DataProvider)
    mock_provider.get_earnings_history.return_value = [
        Earning(
            symbol="MSFT",
            fiscal_year=2024,
            fiscal_quarter=1,
            earnings_date=datetime(2024, 1, 25),
            report_date=datetime(2024, 1, 25),
            report_time="amc",
            currency="USD",
            reported_eps=2.93,
            estimated_eps=2.78,
        )
    ]

    fetcher = DataFetcher(provider=mock_provider, db=db_session, rate_limit_delay=0)
    fetcher.sync_earnings(symbols=["MSFT"])
    fetcher.sync_earnings(symbols=["MSFT"])  # idempotent — no duplicate

    msft = db_session.query(Stock).filter_by(symbol="MSFT").first()  # type: ignore[union-attr]
    assert len(msft.earnings) == 1  # type: ignore[union-attr]
    assert msft.earnings[0].fiscal_year == 2024  # type: ignore[union-attr]
