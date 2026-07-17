from __future__ import annotations

import re

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


def ctrip_rows_to_offers(
    rows: list[dict], query: FlightQuery, *, stale: bool
) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    for row in rows:
        prices = row.get("prices") or []
        if not prices:
            continue
        price = min(prices, key=lambda item: int(item["price"]))
        offers.append(
            FlightOffer(
                data_provider="ctrip_snapshot",
                seller_name="携程",
                flight_no=row["flight_no"],
                airline=row.get("airline", ""),
                origin_city=query.origin_city,
                origin_code=query.origin_code,
                destination_city=query.destination_city,
                destination_code=query.destination_code,
                depart_date=query.depart_date,
                depart_time=row.get("dep_time", ""),
                arrive_time=row.get("arr_time", ""),
                duration_minutes=_duration_minutes(row.get("duration")),
                stops=int(row.get("stops", 0)),
                currency=price.get("currency", query.currency),
                base_price=None,
                tax=None,
                baggage_fee=None,
                total_price=int(price["price"]),
                has_baggage=None,
                price_status=(
                    PriceStatus.stale if stale else PriceStatus.priced
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
        rows, age, stale = await read_provider_deals(
            provider="ctrip_snapshot",
            origin_code=query.origin_code,
            destination_code=query.destination_code,
            depart_date=query.depart_date,
        )
        if not rows:
            await enqueue_demand(
                origin_code=query.origin_code,
                destination_code=query.destination_code,
                depart_date=query.depart_date,
                priority=50,
                source="recent_search",
            )
            return ProviderResult(
                provider=self.name,
                status=ProviderStatus.queued,
                message="等待下次刷新",
            )
        offers = ctrip_rows_to_offers(rows, query, stale=stale)
        return ProviderResult(
            provider=self.name,
            status=(
                ProviderStatus.stale if stale else ProviderStatus.success
            ),
            offers=offers,
            cache_age_seconds=age,
        )
