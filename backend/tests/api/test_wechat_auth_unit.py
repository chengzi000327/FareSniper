from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException

from backend.api import wechat_auth
from backend.infrastructure.notifications.wechat import WechatSession


@pytest.mark.asyncio
async def test_wechat_session_issues_existing_project_jwt(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "wechat_mini_app_id", "wx-test-app")
    monkeypatch.setattr(settings, "wechat_mini_app_secret", "secret")

    async def fake_exchange(code: str):
        assert code == "login-code"
        return WechatSession("openid-1", "session-key", "union-1")

    async def fake_find_or_create(**kwargs):
        assert kwargs == {
            "app_id": "wx-test-app",
            "open_id": "openid-1",
            "union_id": "union-1",
        }
        return "user-wechat-1"

    monkeypatch.setattr(wechat_auth, "exchange_login_code", fake_exchange)
    monkeypatch.setattr(wechat_auth, "find_or_create_wechat_user", fake_find_or_create)

    result = await wechat_auth.create_wechat_session(
        wechat_auth.WechatSessionReq(code="login-code"),
        authorization=None,
    )
    claims = jwt.decode(
        result.access_token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    assert result.user_id == "user-wechat-1"
    assert claims["sub"] == "user-wechat-1"
    assert claims["provider"] == "wechat"


@pytest.mark.asyncio
async def test_wechat_session_reports_missing_configuration(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "wechat_mini_app_id", "")
    monkeypatch.setattr(settings, "wechat_mini_app_secret", "")

    with pytest.raises(HTTPException) as exc:
        await wechat_auth.create_wechat_session(
            wechat_auth.WechatSessionReq(code="login-code"),
            authorization=None,
        )

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_wechat_status_reports_configuration(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "wechat_mini_app_id", "wx-test-app")
    monkeypatch.setattr(settings, "wechat_mini_app_secret", "secret")

    assert await wechat_auth.wechat_login_status() == {"configured": True}


@pytest.mark.asyncio
async def test_wechat_session_merges_existing_visitor(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "wechat_mini_app_id", "wx-test-app")
    monkeypatch.setattr(settings, "wechat_mini_app_secret", "secret")

    async def fake_exchange(_code: str):
        return WechatSession("openid-1", "session-key", None)

    async def fake_find_or_create(**_kwargs):
        return "wechat-user"

    merged: list[tuple[str, str]] = []

    async def fake_merge(*, anon_id: str, target_id: str):
        merged.append((anon_id, target_id))

    visitor_token = jwt.encode(
        {"sub": "visitor-user", "anon": True},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    monkeypatch.setattr(wechat_auth, "exchange_login_code", fake_exchange)
    monkeypatch.setattr(wechat_auth, "find_or_create_wechat_user", fake_find_or_create)
    monkeypatch.setattr(wechat_auth, "merge_anonymous_user", fake_merge)

    result = await wechat_auth.create_wechat_session(
        wechat_auth.WechatSessionReq(code="login-code"),
        authorization=f"Bearer {visitor_token}",
    )

    assert result.user_id == "wechat-user"
    assert merged == [("visitor-user", "wechat-user")]
