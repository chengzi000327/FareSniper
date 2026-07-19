from __future__ import annotations

import re
from datetime import datetime, timezone

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)
from backend.infrastructure.db.flight_demand_repo import enqueue_demand
from backend.infrastructure.db.flight_snapshot_repo import read_provider_deals


def _duration_minutes(value: object) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    hours = re.search(r"(\d+)\s*(?:h|小时)", text)
    minutes = re.search(r"(\d+)\s*(?:m|分钟)", text)
    if hours or minutes:
        return (int(hours.group(1)) * 60 if hours else 0) + (
            int(minutes.group(1)) if minutes else 0
        )
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


def _price_status(expires_at: object, *, now: datetime) -> PriceStatus:
    if not isinstance(expires_at, str) or not expires_at:
        return PriceStatus.stale
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return PriceStatus.stale
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return (
        PriceStatus.stale
        if expiry <= now
        else PriceStatus.priced
    )


def ctrip_rows_to_offers(
    rows: list[dict],
    query: FlightQuery,
    *,
    stale: bool,
    now: datetime | None = None,
) -> list[FlightOffer]:
    pass_now = now or datetime.now(timezone.utc)
    if pass_now.tzinfo is None:
        pass_now = pass_now.replace(tzinfo=timezone.utc)
    else:
        pass_now = pass_now.astimezone(timezone.utc)
    offers: list[FlightOffer] = []
    for row in rows:
        prices = row.get("prices") or []
        if not prices:
            continue
        preferred_prices = [
            price
            for price in prices
            if str(price.get("currency") or "").upper() == query.currency
        ]
        if preferred_prices:
            comparable_prices = preferred_prices
        else:
            selected_currency = sorted(
                {
                    str(price.get("currency") or query.currency).upper()
                    for price in prices
                }
            )[0]
            comparable_prices = [
                price
                for price in prices
                if str(price.get("currency") or query.currency).upper()
                == selected_currency
            ]
        price = min(comparable_prices, key=lambda item: int(item["price"]))
        offers.append(
            FlightOffer(
                data_provider="ctrip_snapshot",
                seller_name="携程",
                flight_no=row["flight_no"],
                airline=row.get("airline", ""),
                origin_city=query.origin_city,
                origin_code=query.origin_code,
                origin_airport_code=row.get("origin_airport_code"),
                destination_city=query.destination_city,
                destination_code=query.destination_code,
                destination_airport_code=row.get(
                    "destination_airport_code"
                ),
                depart_date=query.depart_date,
                depart_time=row.get("dep_time", ""),
                arrive_time=row.get("arr_time", ""),
                duration_minutes=_duration_minutes(row.get("duration")),
                stops=int(row.get("stops", 0)),
                currency=price.get("currency", query.currency),
                base_price=price.get("base_price"),
                tax=price.get("tax"),
                tax_source=price.get("tax_source"),
                baggage_fee=price.get("baggage_fee"),
                baggage_allowance=price.get("baggage_allowance"),
                total_price=int(price["price"]),
                has_baggage=price.get("has_baggage"),
                price_status=(
                    PriceStatus.stale
                    if stale
                    else _price_status(
                        price.get("expires_at"), now=pass_now
                    )
                ),
                booking_url=price.get("url") or None,
                fetched_at=price.get("crawled_at"),
                expires_at=price.get("expires_at"),
                is_realtime=False,
                raw_reference=price.get("id"),
            )
        )
    return offers


class CtripSnapshotProvider:
    name = "ctrip"

    def supports(self, query: FlightQuery) -> bool:
        return True

    async def search(self, query: FlightQuery) -> ProviderResult:
        scope = {
            "origin_code": query.origin_code,
            "origin_airport_code": query.origin_airport_scope,
            "destination_code": query.destination_code,
            "destination_airport_code": query.destination_airport_scope,
            "depart_date": query.depart_date,
        }
        rows, age, stale = await read_provider_deals(
            provider="ctrip_snapshot",
            **scope,
        )
        if not rows:
            if age is not None and not stale:
                return ProviderResult(
                    provider=self.name,
                    status=ProviderStatus.empty,
                    message="本次刷新暂无结果",
                    cache_age_seconds=age,
                )
            await enqueue_demand(
                **scope,
                priority=50,
                source="recent_search",
            )
            return ProviderResult(
                provider=self.name,
                status=(
                    ProviderStatus.stale
                    if age is not None and stale
                    else ProviderStatus.queued
                ),
                message=(
                    "空结果已过期，等待刷新"
                    if age is not None and stale
                    else "等待下次刷新"
                ),
                cache_age_seconds=age,
            )
        now = datetime.now(timezone.utc)
        offers = ctrip_rows_to_offers(
            rows, query, stale=stale, now=now
        )
        effective_stale = stale or bool(offers) and all(
            offer.price_status is PriceStatus.stale for offer in offers
        )
        if effective_stale:
            await enqueue_demand(
                **scope,
                priority=50,
                source="recent_search",
            )
        return ProviderResult(
            provider=self.name,
            status=(
                ProviderStatus.stale
                if effective_stale
                else ProviderStatus.success
            ),
            offers=offers,
            cache_age_seconds=age,
        )
