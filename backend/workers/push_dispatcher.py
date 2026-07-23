from __future__ import annotations

from backend.config import settings


async def send_push(user_id: str, title: str, body: str, subscription: dict) -> None:
    from pywebpush import webpush

    webpush(
        subscription_info=subscription,
        data=f'{{"title":"{title}","body":"{body}"}}',
        vapid_private_key=settings.vapid_private_key,
        vapid_claims={"sub": settings.vapid_subject},
    )
