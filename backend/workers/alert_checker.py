from __future__ import annotations

from sqlalchemy import select

from backend.application.services.flight_query import (
    FlightQueryValidationError,
    build_flight_query,
)
from backend.application.services.flight_search_aggregator import (
    FlightSearchAggregator,
)
from backend.config import settings
from backend.infrastructure.db.alert_repo import (
    PriceAlert,
    mark_triggered,
    update_alert_observation,
)
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_cache import (
    read_cached_deals,
    write_cached_deals,
)
from backend.infrastructure.db.notification_repo import (
    enqueue_notification,
    list_alert_subscriptions,
)
from backend.infrastructure.db.push_subscription_repo import list_user_subscriptions
from backend.infrastructure.db.wechat_repo import get_wechat_account_for_user
from backend.infrastructure.flight_data.providers.factory import (
    build_flight_providers,
)
from backend.workers.notification_dispatcher import dispatch_notifications_once


def _deal_price(deal: dict) -> int | None:
    value = deal.get("total_price")
    if value is None:
        value = deal.get("price")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _wechat_message_data(alert: PriceAlert, price: int, provider: str) -> dict:
    return {
        settings.wechat_price_alert_route_field: {
            "value": f"{alert.origin} → {alert.destination}"[:20]
        },
        settings.wechat_price_alert_date_field: {"value": alert.depart_date},
        settings.wechat_price_alert_price_field: {"value": f"{price}元"},
        settings.wechat_price_alert_remark_field: {
            "value": f"{provider or 'FareSniper'} 已达到目标价"[:20]
        },
    }


async def _refresh_route_deals(
    *, origin: str, destination: str, depart_date: str
) -> list[dict]:
    try:
        query = build_flight_query(origin, destination, depart_date)
    except FlightQueryValidationError:
        return []
    aggregator = FlightSearchAggregator(
        build_flight_providers(),
        timeout_seconds=settings.flight_provider_timeout_seconds,
    )
    result = await aggregator.collect(query)
    deals = list(result.get("deals") or [])
    if deals:
        await write_cached_deals(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            deals=deals,
        )
    return deals


async def check_alerts_once() -> None:
    async with get_session() as s:
        actives = list(
            (await s.execute(select(PriceAlert).where(PriceAlert.status == "active")))
            .scalars()
            .all()
        )
    route_deals: dict[tuple[str, str, str], list[dict]] = {}
    for a in actives:
        route_key = (a.origin, a.destination, a.depart_date)
        if route_key not in route_deals:
            try:
                deals = await _refresh_route_deals(
                    origin=a.origin,
                    destination=a.destination,
                    depart_date=a.depart_date,
                )
            except Exception:
                deals = []
            if not deals:
                deals = await read_cached_deals(
                    origin=a.origin,
                    destination=a.destination,
                    depart_date=a.depart_date,
                )
            route_deals[route_key] = deals
        deals = route_deals[route_key]
        priced_deals = [
            (price, deal) for deal in deals if (price := _deal_price(deal)) is not None
        ]
        if not priced_deals:
            continue
        best_price, best_deal = min(priced_deals, key=lambda item: item[0])
        provider = str(
            best_deal.get("platform") or best_deal.get("provider") or "FareSniper"
        )
        await update_alert_observation(
            a.id,
            price=best_price,
            provider=provider,
        )
        if best_price > a.target_price:
            continue

        queued = False
        body = (
            f"{a.origin}-{a.destination} 当前 {best_price} 元，"
            f"已达到目标价 {a.target_price} 元"
        )
        for index, subscription in enumerate(await list_user_subscriptions(a.user_id)):
            await enqueue_notification(
                event_key=f"alert:{a.id}:webpush:{index}",
                alert_id=a.id,
                user_id=a.user_id,
                channel="webpush",
                payload={
                    "title": "机票价格已触发",
                    "body": body,
                    "subscription": subscription,
                },
            )
            queued = True

        account = await get_wechat_account_for_user(a.user_id)
        if account is not None:
            for subscription in await list_alert_subscriptions(a.id):
                if subscription.channel != "wechat":
                    continue
                await enqueue_notification(
                    event_key=f"alert:{a.id}:wechat:{subscription.id}",
                    alert_id=a.id,
                    user_id=a.user_id,
                    channel="wechat",
                    payload={
                        "open_id": account.open_id,
                        "template_id": subscription.template_id,
                        "subscription_id": subscription.id,
                        "page": ("pages/alert-detail/index" f"?alertId={a.id}"),
                        "data": _wechat_message_data(a, best_price, provider),
                    },
                )
                queued = True

        await mark_triggered(
            a.id,
            notification_status="queued" if queued else "not_requested",
        )
    await dispatch_notifications_once()
