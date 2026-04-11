"""Unit tests for src/api/auth.py — no DB required."""

from datetime import datetime, timedelta


def test_hash_and_verify_password():
    from src.api.auth import hash_password, verify_password

    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert verify_password("mysecret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_session_returns_unique_tokens():
    from src.api.auth import SESSIONS, create_session

    SESSIONS.clear()
    t1 = create_session(1)
    t2 = create_session(1)
    assert t1 != t2
    assert len(t1) >= 32
    SESSIONS.clear()


def test_get_session_returns_data():
    from src.api.auth import SESSIONS, create_session, get_session

    SESSIONS.clear()
    token = create_session(1)
    session = get_session(token)
    assert session is not None
    assert session.user_id == 1
    SESSIONS.clear()


def test_get_session_returns_none_for_unknown_token():
    from src.api.auth import get_session

    assert get_session("nonexistent") is None


def test_get_session_removes_expired():
    from src.api.auth import SESSIONS, SessionData, get_session

    SESSIONS.clear()
    SESSIONS["expired"] = SessionData(
        user_id=1, expires_at=datetime.utcnow() - timedelta(seconds=1)
    )
    result = get_session("expired")
    assert result is None
    assert "expired" not in SESSIONS
    SESSIONS.clear()


def test_delete_session_removes_entry():
    from src.api.auth import SESSIONS, create_session, delete_session

    SESSIONS.clear()
    token = create_session(1)
    delete_session(token)
    assert token not in SESSIONS
    SESSIONS.clear()


def test_rate_limit_allows_under_threshold():
    from src.api.auth import _lockouts, _rate_failures, check_rate_limit

    _rate_failures.clear()
    _lockouts.clear()
    for _ in range(4):
        assert check_rate_limit("1.2.3.4") is True
        from src.api.auth import record_failure

        record_failure("1.2.3.4")
    _rate_failures.clear()
    _lockouts.clear()


def test_rate_limit_blocks_after_5_failures():
    from src.api.auth import _lockouts, _rate_failures, check_rate_limit, record_failure

    _rate_failures.clear()
    _lockouts.clear()
    for _ in range(5):
        record_failure("1.2.3.5")
    assert check_rate_limit("1.2.3.5") is False
    _rate_failures.clear()
    _lockouts.clear()
