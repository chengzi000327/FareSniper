"""TG-12 Task 0: current_user_id JWT dependency regression."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.api._deps import current_user_id


def test_current_user_id_accepts_bearer(jwt_for):
    token = jwt_for("u1")
    assert current_user_id(f"Bearer {token}") == "u1"


def test_current_user_id_rejects_missing_token():
    with pytest.raises(HTTPException) as e:
        current_user_id(None)
    assert e.value.status_code == 401
