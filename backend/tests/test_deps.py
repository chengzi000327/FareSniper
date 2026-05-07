"""Smoke tests for backend.api._deps.current_user_id."""
from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException

from backend.api._deps import current_user_id
from backend.config import settings


def _mint(sub: str | None) -> str:
    payload = {"sub": sub} if sub is not None else {}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def test_returns_sub_for_valid_bearer():
    token = _mint("u-42")
    assert current_user_id(authorization=f"Bearer {token}") == "u-42"


def test_lowercase_bearer_accepted():
    token = _mint("u-42")
    assert current_user_id(authorization=f"bearer {token}") == "u-42"


def test_missing_header_raises_401():
    with pytest.raises(HTTPException) as exc:
        current_user_id(authorization=None)
    assert exc.value.status_code == 401
    assert "missing bearer" in exc.value.detail.lower()


def test_non_bearer_scheme_raises_401():
    with pytest.raises(HTTPException) as exc:
        current_user_id(authorization="Basic abc")
    assert exc.value.status_code == 401


def test_garbage_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        current_user_id(authorization="Bearer not-a-jwt")
    assert exc.value.status_code == 401
    assert "invalid token" in exc.value.detail.lower()


def test_token_without_sub_raises_401():
    token = _mint(sub=None)
    with pytest.raises(HTTPException) as exc:
        current_user_id(authorization=f"Bearer {token}")
    assert exc.value.status_code == 401
    assert "missing sub" in exc.value.detail.lower()
