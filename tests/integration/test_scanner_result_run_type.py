"""Unit tests for ScannerResult model run_type field."""


def test_scanner_result_run_type_default(db_session):
    """ScannerResult defaults run_type to 'eod'."""
    from datetime import datetime
    from src.db.models import ScannerResult, Stock

    stock = Stock(symbol="AAPL", name="Apple Inc.")
    db_session.add(stock)
    db_session.flush()

    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="momentum",
        result_metadata={"rsi": 72.0},
        matched_at=datetime.utcnow(),
    )
    db_session.add(result)
    db_session.commit()

    assert result.run_type == "eod"


def test_scanner_result_run_type_pre_close(db_session):
    """ScannerResult accepts run_type='pre_close'."""
    from datetime import datetime
    from src.db.models import ScannerResult, Stock

    stock = Stock(symbol="NVDA", name="Nvidia Corp")
    db_session.add(stock)
    db_session.flush()

    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="momentum",
        result_metadata={},
        matched_at=datetime.utcnow(),
        run_type="pre_close",
    )
    db_session.add(result)
    db_session.commit()

    assert result.run_type == "pre_close"
