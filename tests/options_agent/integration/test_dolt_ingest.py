"""Integration tests for ChainIngester against a real PostgreSQL container."""

from datetime import date
from unittest.mock import MagicMock


def _mock_contracts(symbol: str, expiry: date) -> list:
    """Return two mock OptionsContract rows for testing."""
    from src.options_agent.data.dolt_client import OptionsContract

    return [
        OptionsContract(
            symbol=symbol,
            expiry_date=expiry,
            contract_type="C",
            strike=185.0,
            bid=2.5,
            ask=2.7,
            mid=2.6,
            last=2.55,
            volume=1500,
            open_interest=3000,
            iv=0.28,
            delta=0.52,
            gamma=0.045,
            theta=-0.08,
            vega=0.15,
        ),
        OptionsContract(
            symbol=symbol,
            expiry_date=expiry,
            contract_type="P",
            strike=180.0,
            bid=1.8,
            ask=2.0,
            mid=1.9,
            last=1.85,
            volume=800,
            open_interest=2000,
            iv=0.31,
            delta=-0.45,
            gamma=0.040,
            theta=-0.07,
            vega=0.12,
        ),
    ]


def test_ingest_persists_contracts(db_session):
    """ChainIngester writes contracts to options_eod_chains."""
    from src.options_agent.data.chain_ingester import ChainIngester
    from src.db.models import OptionsEodChain, Stock
    from src.options_agent.data.expiries import ExpiryBucket

    # Seed AAPL stock row — FK on stocks.symbol
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    mock_client = MagicMock()
    as_of = date(2026, 4, 18)
    expiry = date(2026, 4, 24)
    mock_client.fetch_chain.return_value = _mock_contracts("AAPL", expiry)

    ingester = ChainIngester(dolt_client=mock_client, session=db_session)
    bucket = ExpiryBucket(label="current_week", expiry=expiry)
    count = ingester.ingest_for_symbol("AAPL", as_of=as_of, buckets=[bucket])

    assert count == 2
    rows = db_session.query(OptionsEodChain).filter_by(symbol="AAPL").all()
    assert len(rows) == 2


def test_ingest_idempotent(db_session):
    """Ingesting the same contracts twice produces no duplicates."""
    from src.options_agent.data.chain_ingester import ChainIngester
    from src.db.models import OptionsEodChain, Stock
    from src.options_agent.data.expiries import ExpiryBucket

    # Seed AAPL stock row — FK on stocks.symbol
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    mock_client = MagicMock()
    as_of = date(2026, 4, 18)
    expiry = date(2026, 4, 24)
    mock_client.fetch_chain.return_value = _mock_contracts("AAPL", expiry)
    bucket = ExpiryBucket(label="current_week", expiry=expiry)
    ingester = ChainIngester(dolt_client=mock_client, session=db_session)

    ingester.ingest_for_symbol("AAPL", as_of=as_of, buckets=[bucket])
    ingester.ingest_for_symbol("AAPL", as_of=as_of, buckets=[bucket])

    count = db_session.query(OptionsEodChain).filter_by(symbol="AAPL").count()
    assert count == 2  # no duplicates
