from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.infrastructure.notifications.wechat import WechatApiError
from backend.workers import notification_dispatcher


def notification(channel: str, payload: dict):
    return SimpleNamespace(
        id="notification-1",
        alert_id="alert-1",
        user_id="user-1",
        channel=channel,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_wechat_delivery_marks_outbox_and_subscription_sent(monkeypatch):
    calls: list[tuple[str, str]] = []
    item = notification(
        "wechat",
        {
            "open_id": "openid-1",
            "template_id": "template-1",
            "subscription_id": "subscription-1",
            "page": "pages/alerts/index",
            "data": {"thing1": {"value": "北京 → 三亚"}},
        },
    )

    async def claim(**_kwargs):
        return [item]

    async def send(**_kwargs):
        calls.append(("send", "wechat"))

    async def record(identifier, *args):
        value = args[0] if args else ""
        calls.append((str(identifier), str(value)))

    monkeypatch.setattr(notification_dispatcher, "claim_due_notifications", claim)
    monkeypatch.setattr(notification_dispatcher, "send_subscription_message", send)
    monkeypatch.setattr(notification_dispatcher, "mark_notification_sent", record)
    monkeypatch.setattr(notification_dispatcher, "mark_subscription_consumed", record)
    monkeypatch.setattr(
        notification_dispatcher, "mark_alert_notification_status", record
    )

    await notification_dispatcher.dispatch_notifications_once()

    assert ("send", "wechat") in calls
    assert ("subscription-1", "") in calls
    assert ("notification-1", "") in calls
    assert ("alert-1", "sent") in calls


@pytest.mark.asyncio
async def test_refused_subscription_is_permanent_failure(monkeypatch):
    calls: list[tuple[str, str]] = []
    item = notification(
        "wechat",
        {
            "open_id": "openid-1",
            "template_id": "template-1",
            "subscription_id": "subscription-1",
            "page": "pages/alerts/index",
            "data": {},
        },
    )

    async def claim(**_kwargs):
        return [item]

    async def send(**_kwargs):
        raise WechatApiError("refused", errcode=43101)

    async def record(identifier, *args):
        value = args[0] if args else ""
        calls.append((str(identifier), str(value)))

    monkeypatch.setattr(notification_dispatcher, "claim_due_notifications", claim)
    monkeypatch.setattr(notification_dispatcher, "send_subscription_message", send)
    monkeypatch.setattr(notification_dispatcher, "mark_notification_failed", record)
    monkeypatch.setattr(notification_dispatcher, "mark_subscription_invalid", record)
    monkeypatch.setattr(
        notification_dispatcher, "mark_alert_notification_status", record
    )

    await notification_dispatcher.dispatch_notifications_once()

    assert ("notification-1", "refused") in calls
    assert ("subscription-1", "") in calls
    assert ("alert-1", "failed") in calls
