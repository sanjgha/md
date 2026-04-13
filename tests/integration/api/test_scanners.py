"""Integration tests for scanner API endpoints."""


def test_list_scanners_returns_registered_scanners(authenticated_client):
    """GET /api/scanners returns all registered scanners with metadata."""
    resp = authenticated_client.get("/api/scanners")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    names = {s["name"] for s in data}
    assert "momentum" in names
    assert "price_action" in names
    assert "volume" in names

    for scanner in data:
        assert "name" in scanner
        assert "timeframe" in scanner
        assert "description" in scanner
        assert scanner["timeframe"] == "daily"


def test_list_scanners_requires_auth(api_client):
    """GET /api/scanners returns 401 without authentication."""
    resp = api_client.get("/api/scanners")
    assert resp.status_code == 401


from datetime import datetime


def _seed_results(db_session, run_type="eod"):
    """Helper: seed one scanner result for AAPL."""
    from src.db.models import ScannerResult, Stock

    # Use get_or_create to avoid unique constraint violations on symbol
    stock = db_session.query(Stock).filter_by(symbol="AAPL").first()
    if stock is None:
        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.flush()
    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="momentum",
        result_metadata={"reason": "overbought", "rsi": 72.5},
        matched_at=datetime.utcnow(),
        run_type=run_type,
    )
    db_session.add(result)
    db_session.commit()
    return stock, result


def test_get_results_defaults_to_latest(authenticated_client, db_session):
    """GET /api/scanners/results returns latest results by default."""
    _seed_results(db_session)
    resp = authenticated_client.get("/api/scanners/results")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    assert data["results"][0]["symbol"] == "AAPL"
    assert data["results"][0]["scanner_name"] == "momentum"


def test_get_results_filter_by_run_type(authenticated_client, db_session):
    """GET /api/scanners/results?run_type=pre_close filters correctly."""
    _seed_results(db_session, run_type="eod")
    _seed_results(db_session, run_type="pre_close")
    resp = authenticated_client.get("/api/scanners/results?run_type=pre_close")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_type"] == "pre_close"
    assert all(r["scanner_name"] == "momentum" for r in data["results"])


def test_get_results_filter_by_scanner(authenticated_client, db_session):
    """GET /api/scanners/results?scanners=momentum returns only momentum results."""
    _seed_results(db_session)
    resp = authenticated_client.get("/api/scanners/results?scanners=momentum")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["scanner_name"] == "momentum" for r in data["results"])


def test_get_results_empty_returns_empty_list(authenticated_client, db_session):
    """GET /api/scanners/results with no data returns empty results, not 404."""
    resp = authenticated_client.get("/api/scanners/results")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def test_get_run_dates_returns_distinct_runs(authenticated_client, db_session):
    """GET /api/scanners/run-dates returns distinct date+run_type combos."""
    _seed_results(db_session, run_type="eod")
    _seed_results(db_session, run_type="pre_close")
    resp = authenticated_client.get("/api/scanners/run-dates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    run_types = {d["run_type"] for d in data}
    assert run_types == {"eod", "pre_close"}
