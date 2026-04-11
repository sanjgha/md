"""Unit tests for FastAPI dependencies."""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from starlette.requests import Request


def _make_request(user_id=None):
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"", "headers": []}
    req = Request(scope)
    if user_id is not None:
        req.state.user_id = user_id
    return req


def test_get_current_user_raises_401_when_no_user_id():
    from src.api.deps import get_current_user

    req = _make_request()  # no user_id on state
    db = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(req, db)
    assert exc_info.value.status_code == 401


def test_get_current_user_raises_401_when_user_row_missing():
    from src.api.deps import get_current_user

    req = _make_request(user_id=99)
    db = MagicMock()
    db.get.return_value = None  # simulate user not in DB
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(req, db)
    assert exc_info.value.status_code == 401


def test_get_current_user_returns_user():
    from src.api.deps import get_current_user
    from src.db.models import User

    req = _make_request(user_id=1)
    fake_user = MagicMock(spec=User)
    fake_user.id = 1
    db = MagicMock()
    db.get.return_value = fake_user
    result = get_current_user(req, db)
    assert result is fake_user
