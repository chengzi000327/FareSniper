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
        wechat_auth.WechatSessionReq(code="login-code")
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
            wechat_auth.WechatSessionReq(code="login-code")
        )

    assert exc.value.status_code == 503
