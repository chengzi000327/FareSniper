from __future__ import annotations

from backend.infrastructure.db.alert_repo import (
    mark_alert_notification_status,
)
from backend.infrastructure.db.notification_repo import (
    claim_due_notifications,
    mark_notification_failed,
    mark_notification_retry,
    mark_notification_sent,
    mark_subscription_consumed,
    mark_subscription_invalid,
)
from backend.infrastructure.notifications.wechat import (
    WechatApiError,
    send_subscription_message,
)
from backend.workers.push_dispatcher import send_push

_PERMANENT_WECHAT_ERRORS = {40003, 40037, 43101}


async def dispatch_notifications_once(*, limit: int = 50) -> None:
    notifications = await claim_due_notifications(limit=limit)
    for notification in notifications:
        payload = dict(notification.payload or {})
        try:
            if notification.channel == "webpush":
                await send_push(
                    notification.user_id,
                    title=str(payload["title"]),
                    body=str(payload["body"]),
                    subscription=dict(payload["subscription"]),
                )
            elif notification.channel == "wechat":
                await send_subscription_message(
                    open_id=str(payload["open_id"]),
                    template_id=str(payload["template_id"]),
                    page=str(payload["page"]),
                    data=dict(payload["data"]),
                )
                subscription_id = str(payload.get("subscription_id") or "")
                if subscription_id:
                    await mark_subscription_consumed(subscription_id)
            else:
                raise RuntimeError(
                    f"unsupported notification channel: {notification.channel}"
                )
        except WechatApiError as exc:
            subscription_id = str(payload.get("subscription_id") or "")
            if exc.errcode in _PERMANENT_WECHAT_ERRORS:
                await mark_notification_failed(notification.id, str(exc))
                if subscription_id:
                    await mark_subscription_invalid(subscription_id)
                await mark_alert_notification_status(notification.alert_id, "failed")
            else:
                await mark_notification_retry(notification.id, str(exc))
                await mark_alert_notification_status(notification.alert_id, "retrying")
        except Exception as exc:
            await mark_notification_retry(notification.id, str(exc))
            await mark_alert_notification_status(notification.alert_id, "retrying")
        else:
            await mark_notification_sent(notification.id)
            await mark_alert_notification_status(notification.alert_id, "sent")
