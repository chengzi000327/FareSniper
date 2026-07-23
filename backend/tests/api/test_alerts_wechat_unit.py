from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import alerts
from backend.config import settings


@pytest.mark.asyncio
async def test_subscribe_wechat_binds_existing_active_alert(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "wechat_price_alert_template_id", "template-1")

    async def get_alert(alert_id, user_id):
        assert (alert_id, user_id) == ("alert-1", "user-1")
        return SimpleNamespace(status="active")

    async def get_account(user_id):
        assert user_id == "user-1"
        return SimpleNamespace(open_id="openid-1")

    async def upsert(**kwargs):
        calls.append(("upsert", kwargs))

    async def mark(alert_id, status):
        calls.append(("mark", alert_id, status))

    monkeypatch.setattr(alerts, "get_alert_for_user", get_alert)
    monkeypatch.setattr(alerts, "get_wechat_account_for_user", get_account)
    monkeypatch.setattr(alerts, "upsert_alert_subscription", upsert)
    monkeypatch.setattr(alerts, "mark_alert_notification_status", mark)

    result = await alerts.subscribe_wechat("alert-1", uid="user-1")

    assert result["wechat_notification"] == "subscribed"
    assert calls == [
        (
            "upsert",
            {
                "alert_id": "alert-1",
                "user_id": "user-1",
                "channel": "wechat",
                "template_id": "template-1",
            },
        ),
        ("mark", "alert-1", "subscribed"),
    ]


@pytest.mark.asyncio
async def test_subscribe_wechat_rejects_triggered_alert(monkeypatch):
    monkeypatch.setattr(settings, "wechat_price_alert_template_id", "template-1")

    async def get_alert(_alert_id, _user_id):
        return SimpleNamespace(status="triggered")

    monkeypatch.setattr(alerts, "get_alert_for_user", get_alert)

    with pytest.raises(HTTPException) as exc:
        await alerts.subscribe_wechat("alert-1", uid="user-1")

    assert exc.value.status_code == 409
