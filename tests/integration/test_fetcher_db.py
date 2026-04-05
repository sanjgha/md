"""Integration tests for DataFetcher using testcontainers PostgreSQL."""

from unittest.mock import Mock
from datetime import datetime
from sqlalchemy.orm import Session
from src.data_fetcher.fetcher import DataFetcher
from src.db.models import Stock
from src.data_provider.base import DataProvider, Candle, NewsArticle


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

    aapl = db_session.query(Stock).filter_by(symbol="AAPL").first()
    assert len(aapl.daily_candles) == 5


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

    tsla = db_session.query(Stock).filter_by(symbol="TSLA").first()
    assert len(tsla.intraday_candles) == 2


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

    nvda = db_session.query(Stock).filter_by(symbol="NVDA").first()
    assert len(nvda.news) == 1
    assert nvda.news[0].headline == "Nvidia releases new GPU"
