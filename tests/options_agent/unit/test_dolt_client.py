"""Unit tests for DoltOptionsClient with SQL pushdown optimization."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.options_agent.data.dolt_client import DoltOptionsClient, OptionsContract


@pytest.fixture
def client():
    """Create a DoltOptionsClient with mocked connection."""
    return DoltOptionsClient("mysql+pymysql://root@localhost:3306/options")


def test_fetch_chain_without_expiry_filter(client):
    """fetch_chain without expiries parameter builds SQL without IN clause."""
    symbol = "SPY"
    as_of = date(2026, 4, 20)

    # Mock the connection and cursor
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.object(client, "_connect", return_value=mock_conn):
        client.fetch_chain(symbol, as_of)

    # Verify SQL does not contain expiration IN
    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]
    params = call_args[0][1]

    assert "WHERE underlying = %s AND date = %s" in sql
    assert "expiration IN" not in sql
    assert params == ("SPY", "2026-04-20")


def test_fetch_chain_with_single_expiry_filter(client):
    """fetch_chain with expiries parameter pushes down expiration IN filter."""
    symbol = "SPY"
    as_of = date(2026, 4, 20)
    expiries = [date(2026, 4, 24)]

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.object(client, "_connect", return_value=mock_conn):
        client.fetch_chain(symbol, as_of, expiries=expiries)

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]
    params = call_args[0][1]

    assert "expiration IN (%s)" in sql
    assert params == ("SPY", "2026-04-20", "2026-04-24")


def test_fetch_chain_with_multiple_expiry_filters(client):
    """fetch_chain with multiple expiries builds correct IN clause."""
    symbol = "QQQ"
    as_of = date(2026, 4, 20)
    expiries = [date(2026, 4, 24), date(2026, 5, 16), date(2026, 6, 19)]

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.object(client, "_connect", return_value=mock_conn):
        client.fetch_chain(symbol, as_of, expiries=expiries)

    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]
    params = call_args[0][1]

    assert "expiration IN (%s, %s, %s)" in sql
    assert params == ("QQQ", "2026-04-20", "2026-04-24", "2026-05-16", "2026-06-19")


def test_fetch_chain_with_empty_expiry_list(client):
    """fetch_chain with empty expiries list still works (no rows expected)."""
    symbol = "SPY"
    as_of = date(2026, 4, 20)
    expiries = []

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.object(client, "_connect", return_value=mock_conn):
        result = client.fetch_chain(symbol, as_of, expiries=expiries)

    assert result == []


def test_fetch_chain_symbol_uppercase(client):
    """fetch_chain converts symbol to uppercase."""
    symbol = "spy"
    as_of = date(2026, 4, 20)

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.object(client, "_connect", return_value=mock_conn):
        client.fetch_chain(symbol, as_of)

    call_args = mock_cursor.execute.call_args
    params = call_args[0][1]

    assert params[0] == "SPY"


def test_fetch_chain_returns_contracts(client):
    """fetch_chain converts rows to OptionsContract objects."""
    symbol = "SPY"
    as_of = date(2026, 4, 20)

    mock_row = {
        "underlying": "SPY",
        "expiration": "2026-04-24",
        "type": "C",
        "strike": 185.0,
        "bid": 2.5,
        "ask": 2.7,
        "mid": 2.6,
        "last": 2.55,
        "volume": 1500,
        "open_interest": 3000,
        "iv": 0.28,
        "delta": 0.52,
        "gamma": 0.045,
        "theta": -0.08,
        "vega": 0.15,
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [mock_row]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch.object(client, "_connect", return_value=mock_conn):
        result = client.fetch_chain(symbol, as_of)

    assert len(result) == 1
    assert isinstance(result[0], OptionsContract)
    assert result[0].symbol == "SPY"
    assert result[0].strike == 185.0
    assert result[0].bid == 2.5
