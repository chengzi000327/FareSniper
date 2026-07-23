from __future__ import annotations

import httpx
import pytest

from backend.infrastructure.notifications import wechat


def configure_wechat(monkeypatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "wechat_mini_app_id", "wx-test-app")
    monkeypatch.setattr(settings, "wechat_mini_app_secret", "test-secret")
    monkeypatch.setattr(settings, "wechat_api_base_url", "https://wechat.test")
    monkeypatch.setattr(settings, "wechat_request_timeout_seconds", 1.0)
    monkeypatch.setattr(wechat, "_access_token", None)
    monkeypatch.setattr(wechat, "_access_token_expires_at", 0.0)


@pytest.mark.asyncio
async def test_exchange_login_code_returns_wechat_identity(monkeypatch):
    configure_wechat(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sns/jscode2session"
        assert request.url.params["js_code"] == "login-code"
        return httpx.Response(
            200,
            json={
                "openid": "openid-1",
                "session_key": "session-key",
                "unionid": "union-1",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await wechat.exchange_login_code("login-code", client=client)

    assert result.open_id == "openid-1"
    assert result.union_id == "union-1"


@pytest.mark.asyncio
async def test_subscription_message_fetches_token_and_sends(monkeypatch):
    configure_wechat(monkeypatch)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/cgi-bin/token":
            return httpx.Response(
                200, json={"access_token": "access-1", "expires_in": 7200}
            )
        assert request.url.params["access_token"] == "access-1"
        body = request.read().decode()
        assert "openid-1" in body
        assert "template-1" in body
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await wechat.send_subscription_message(
            open_id="openid-1",
            template_id="template-1",
            page="pages/alert-detail/index?alertId=a1",
            data={"thing1": {"value": "北京 → 三亚"}},
            client=client,
        )

    assert calls == ["/cgi-bin/token", "/cgi-bin/message/subscribe/send"]


@pytest.mark.asyncio
async def test_subscription_message_surfaces_refused_subscription(monkeypatch):
    configure_wechat(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/cgi-bin/token":
            return httpx.Response(
                200, json={"access_token": "access-1", "expires_in": 7200}
            )
        return httpx.Response(
            200,
            json={"errcode": 43101, "errmsg": "user refuse to accept"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(wechat.WechatApiError) as exc:
            await wechat.send_subscription_message(
                open_id="openid-1",
                template_id="template-1",
                page="pages/alerts/index",
                data={"thing1": {"value": "北京 → 三亚"}},
                client=client,
            )

    assert exc.value.errcode == 43101
