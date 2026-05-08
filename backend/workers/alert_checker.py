from __future__ import annotations

from sqlalchemy import select

from backend.infrastructure.db.alert_repo import PriceAlert, mark_triggered
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_cache import read_cached_deals
from backend.infrastructure.db.push_subscription_repo import list_user_subscriptions
from backend.workers.push_dispatcher import send_push


async def check_alerts_once() -> None:
    async with get_session() as s:
        actives = list(
            (
                await s.execute(
                    select(PriceAlert).where(PriceAlert.status == "active")
                )
            ).scalars().all()
        )
    for a in actives:
        deals = await read_cached_deals(
            origin=a.origin,
            destination=a.destination,
            depart_date=a.depart_date,
        )
        if deals and min(d["price"] for d in deals) <= a.target_price:
            await mark_triggered(a.id)
            for sub in await list_user_subscriptions(a.user_id):
                await send_push(
                    a.user_id,
                    title="价格已触发",
                    body=f"{a.origin}-{a.destination} 已 ≤ {a.target_price} 元",
                    subscription=sub,
                )
