from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert

from backend.infrastructure.db.base import Base, get_session

CACHE_TTL = timedelta(hours=1)


class FlightSnapshot(Base):
    __tablename__ = "flight_snapshots"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    origin_code = Column(String, nullable=False)
    destination_code = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    flight_no = Column(String, nullable=False)
    airline = Column(String, nullable=False, default="")
    dep_time = Column(String, nullable=False, default="")
    arr_time = Column(String, nullable=False, default="")
    duration = Column(String, nullable=False, default="")
    stops = Column(Integer, nullable=False, default=0)
    lowest_price = Column(Integer, nullable=False, default=0)
    history_avg_90d = Column(Integer, nullable=True)
    history_low_90d = Column(Integer, nullable=True)
    crawled_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)


class PlatformPriceSnapshot(Base):
    __tablename__ = "platform_price_snapshots"
    __table_args__ = (
        Index(
            "ix_platform_price_provider_flight",
            "data_provider",
            "flight_snapshot_id",
        ),
        UniqueConstraint(
            "flight_snapshot_id",
            "data_provider",
            "platform",
            name="uq_platform_price_provider_seller",
        ),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True)
    flight_snapshot_id = Column(String, ForeignKey("flight_snapshots.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    url = Column(Text, nullable=False, default="")
    raw_payload = Column(JSONB, nullable=True)
    crawled_at = Column(DateTime(timezone=True), nullable=False)
    data_provider = Column(String, nullable=False, default="legacy")
    currency = Column(String, nullable=False, default="CNY")
    price_status = Column(String, nullable=False, default="priced")
    expires_at = Column(DateTime(timezone=True), nullable=True)


class ProviderInventoryObservation(Base):
    __tablename__ = "provider_inventory_observations"
    __table_args__ = {"extend_existing": True}

    provider = Column(String, primary_key=True)
    origin_code = Column(String, primary_key=True)
    destination_code = Column(String, primary_key=True)
    depart_date = Column(String, primary_key=True)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    item_count = Column(Integer, nullable=False)


def _snapshot_id(f: dict[str, Any]) -> str:
    raw = (
        f"{f['origin_code']}|{f['destination_code']}|{f['depart_date']}|"
        f"{f['flight_no']}|{f.get('dep_time', '')}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _advisory_lock_key(snapshot_id: str) -> int:
    return int(hashlib.sha1(snapshot_id.encode("utf-8")).hexdigest()[:15], 16)


def _provider_price_id(
    snapshot_id: str, provider: str, platform: str, currency: str
) -> str:
    raw = f"{snapshot_id}|{provider}|{platform}|{currency}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _lowest_price(flight: dict[str, Any]) -> int:
    if flight.get("lowest_price") is not None:
        return int(flight["lowest_price"])
    prices = flight.get("prices", [])
    currency = str(flight.get("currency") or "CNY")
    matching = [
        price
        for price in prices
        if str(price.get("currency") or currency) == currency
    ]
    return min((int(price["price"]) for price in matching), default=0)


def _provider_refresh_scope(
    flights: list[dict[str, Any]],
    *,
    origin_code: str | None,
    destination_code: str | None,
    depart_date: str | None,
) -> tuple[str, str, str]:
    explicit = (origin_code, destination_code, depart_date)
    inferred = {
        (
            str(flight["origin_code"]),
            str(flight["destination_code"]),
            str(flight["depart_date"]),
        )
        for flight in flights
    }
    if len(inferred) > 1:
        raise ValueError("provider refresh must cover one route and date")
    if inferred:
        inferred_scope = next(iter(inferred))
        resolved = tuple(
            supplied if supplied is not None else inferred_value
            for supplied, inferred_value in zip(explicit, inferred_scope)
        )
        if resolved != inferred_scope:
            raise ValueError("provider refresh rows do not match scope")
    else:
        resolved = explicit
    if not all(isinstance(value, str) and value for value in resolved):
        raise ValueError("provider refresh scope is required")
    return resolved  # type: ignore[return-value]


def _deduplicate_provider_prices(
    flight: dict[str, Any], default_currency: str
) -> list[dict[str, Any]]:
    by_seller: dict[str, dict[str, Any]] = {}
    for price in flight.get("prices", []):
        currency = str(price.get("currency") or default_currency).upper()
        seller = str(price["platform"])
        candidate = {**price, "currency": currency}
        existing = by_seller.get(seller)
        if existing is None:
            by_seller[seller] = candidate
        elif currency == default_currency and existing["currency"] != currency:
            by_seller[seller] = candidate
        elif currency == existing["currency"] and int(price["price"]) < int(
            existing["price"]
        ):
            by_seller[seller] = candidate
    return list(by_seller.values())


def _offer_to_provider_flight(offer: object) -> dict[str, Any]:
    if hasattr(offer, "model_dump"):
        values = offer.model_dump(mode="json")  # type: ignore[attr-defined]
    elif isinstance(offer, dict):
        values = dict(offer)
    else:
        raise TypeError("provider offer must be a FlightOffer or mapping")

    total_price = values.get("total_price", values.get("display_price"))
    if isinstance(total_price, bool) or not isinstance(total_price, int):
        raise ValueError("provider offers require an integer total_price")
    if total_price <= 0:
        raise ValueError("provider offers require a positive total_price")

    duration_minutes = values.get("duration_minutes")
    raw_reference = values.get("raw_reference")
    return {
        "flight_no": values["flight_no"],
        "airline": values.get("airline") or "",
        "origin_code": values["origin_code"],
        "destination_code": values["destination_code"],
        "depart_date": values["depart_date"],
        "dep_time": values.get("depart_time") or "",
        "arr_time": values.get("arrive_time") or "",
        "duration": (
            f"{duration_minutes}分钟"
            if duration_minutes is not None
            else ""
        ),
        "stops": int(values.get("stops") or 0),
        "currency": str(values.get("currency") or "CNY").upper(),
        "prices": [
            {
                "platform": values["seller_name"],
                "price": total_price,
                "currency": values.get("currency") or "CNY",
                "url": values.get("booking_url") or "",
                "raw_payload": (
                    {"raw_reference": raw_reference}
                    if raw_reference is not None
                    else None
                ),
                "price_status": values.get("price_status") or "priced",
            }
        ],
    }


def _display_currency(prices: list[PlatformPriceSnapshot]) -> str | None:
    currencies = sorted({price.currency for price in prices if price.currency})
    if not currencies:
        return None
    return "CNY" if "CNY" in currencies else currencies[0]


def _inventory_freshness(
    expires_at: datetime | None,
    *,
    price_status: str = "priced",
    now: datetime,
) -> str:
    if price_status == "stale":
        return "stale"
    if expires_at is None:
        return "unknown"
    expiry = expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return "stale" if expiry <= now else "fresh"


def _observation_age_seconds(observed_at: datetime, now: datetime) -> int:
    observed = observed_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return max(0, int((now - observed).total_seconds()))


def _deal_sort_key(deal: dict[str, Any]) -> tuple[int, str, int, str]:
    currency = str(deal.get("currency") or "").upper()
    currency_group = 0 if currency == "CNY" else 1 if currency else 2
    price = deal.get("lowest_price")
    numeric_price = int(price) if isinstance(price, int) else 0
    return (
        currency_group,
        currency,
        numeric_price,
        str(deal.get("flight_no") or ""),
    )


async def upsert_flights(flights: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc)
    async with get_session() as s:
        for f in flights:
            sid = _snapshot_id(f)
            await s.execute(select(func.pg_advisory_xact_lock(_advisory_lock_key(sid))))
            values = {
                "id": sid,
                "origin_code": f["origin_code"],
                "destination_code": f["destination_code"],
                "depart_date": f["depart_date"],
                "flight_no": f["flight_no"],
                "airline": f.get("airline", ""),
                "dep_time": f.get("dep_time", ""),
                "arr_time": f.get("arr_time", ""),
                "duration": f.get("duration", ""),
                "stops": int(f.get("stops", 0)),
                "lowest_price": int(f.get("lowest_price", 0)),
                "history_avg_90d": f.get("history_avg_90d"),
                "history_low_90d": f.get("history_low_90d"),
                "crawled_at": now,
                "expires_at": now + CACHE_TTL,
            }
            stmt = pg_insert(FlightSnapshot.__table__).values(**values)
            await s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[FlightSnapshot.id],
                    set_={k: v for k, v in values.items() if k != "id"},
                )
            )
            await s.execute(
                delete(PlatformPriceSnapshot).where(
                    PlatformPriceSnapshot.flight_snapshot_id == sid,
                    PlatformPriceSnapshot.data_provider == "legacy",
                )
            )
            default_currency = str(f.get("currency") or "CNY").upper()
            legacy_prices = _deduplicate_provider_prices(
                f, default_currency
            )
            price_rows = [
                {
                    "id": f"{sid}-{idx}",
                    "flight_snapshot_id": sid,
                    "platform": p["platform"],
                    "price": int(p["price"]),
                    "url": p.get("url", ""),
                    "raw_payload": p.get("raw_payload"),
                    "crawled_at": now,
                    "data_provider": "legacy",
                    "currency": p.get(
                        "currency", f.get("currency", "CNY")
                    ),
                    "price_status": p.get("price_status", "priced"),
                    "expires_at": now + CACHE_TTL,
                }
                for idx, p in enumerate(legacy_prices)
            ]
            if price_rows:
                await s.execute(
                    pg_insert(PlatformPriceSnapshot.__table__).values(price_rows)
                )
        await s.commit()


async def upsert_provider_flights(
    provider: str,
    flights: list[dict[str, Any]],
    ttl_minutes: int,
    *,
    origin_code: str | None = None,
    destination_code: str | None = None,
    depart_date: str | None = None,
    _session: Any = None,
) -> None:
    if _session is None:
        async with get_session() as session:
            await upsert_provider_flights(
                provider,
                flights,
                ttl_minutes,
                origin_code=origin_code,
                destination_code=destination_code,
                depart_date=depart_date,
                _session=session,
            )
            await session.commit()
        return

    scope = _provider_refresh_scope(
        flights,
        origin_code=origin_code,
        destination_code=destination_code,
        depart_date=depart_date,
    )
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ttl_minutes)
    s = _session
    route_lock = _advisory_lock_key("|".join((provider, *scope)))
    await s.execute(select(func.pg_advisory_xact_lock(route_lock)))
    scoped_snapshot_ids = select(FlightSnapshot.id).where(
        FlightSnapshot.origin_code == scope[0],
        FlightSnapshot.destination_code == scope[1],
        FlightSnapshot.depart_date == scope[2],
    )
    await s.execute(
        delete(PlatformPriceSnapshot).where(
            PlatformPriceSnapshot.data_provider == provider,
            PlatformPriceSnapshot.flight_snapshot_id.in_(
                scoped_snapshot_ids
            ),
        )
    )
    for f in flights:
        sid = _snapshot_id(f)
        values = {
            "id": sid,
            "origin_code": f["origin_code"],
            "destination_code": f["destination_code"],
            "depart_date": f["depart_date"],
            "flight_no": f["flight_no"],
            "airline": f.get("airline", ""),
            "dep_time": f.get("dep_time", ""),
            "arr_time": f.get("arr_time", ""),
            "duration": f.get("duration", ""),
            "stops": int(f.get("stops", 0)),
            "lowest_price": _lowest_price(f),
            "history_avg_90d": f.get("history_avg_90d"),
            "history_low_90d": f.get("history_low_90d"),
            "crawled_at": now,
            "expires_at": expires_at,
        }
        stmt = pg_insert(FlightSnapshot.__table__).values(**values)
        await s.execute(
            stmt.on_conflict_do_update(
                index_elements=[FlightSnapshot.id],
                set_={
                    "airline": values["airline"],
                    "arr_time": values["arr_time"],
                    "duration": values["duration"],
                    "stops": values["stops"],
                },
            )
        )
        default_currency = str(f.get("currency") or "CNY").upper()
        provider_prices = _deduplicate_provider_prices(f, default_currency)
        price_rows = [
            {
                "id": _provider_price_id(
                    sid, provider, p["platform"], p["currency"]
                ),
                "flight_snapshot_id": sid,
                "platform": p["platform"],
                "price": int(p["price"]),
                "url": p.get("url", ""),
                "raw_payload": p.get("raw_payload"),
                "crawled_at": now,
                "data_provider": provider,
                "currency": p["currency"],
                "price_status": p.get("price_status", "priced"),
                "expires_at": expires_at,
            }
            for p in provider_prices
        ]
        if price_rows:
            price_stmt = pg_insert(
                PlatformPriceSnapshot.__table__
            ).values(price_rows)
            await s.execute(
                price_stmt.on_conflict_do_update(
                    constraint="uq_platform_price_provider_seller",
                    set_={
                        "price": price_stmt.excluded.price,
                        "url": price_stmt.excluded.url,
                        "raw_payload": price_stmt.excluded.raw_payload,
                        "crawled_at": price_stmt.excluded.crawled_at,
                        "currency": price_stmt.excluded.currency,
                        "price_status": price_stmt.excluded.price_status,
                        "expires_at": price_stmt.excluded.expires_at,
                    },
                )
            )
    observation_values = {
        "provider": provider,
        "origin_code": scope[0],
        "destination_code": scope[1],
        "depart_date": scope[2],
        "observed_at": now,
        "expires_at": expires_at,
        "item_count": len(flights),
    }
    observation_stmt = pg_insert(
        ProviderInventoryObservation.__table__
    ).values(**observation_values)
    await s.execute(
        observation_stmt.on_conflict_do_update(
            index_elements=[
                ProviderInventoryObservation.provider,
                ProviderInventoryObservation.origin_code,
                ProviderInventoryObservation.destination_code,
                ProviderInventoryObservation.depart_date,
            ],
            set_={
                "observed_at": now,
                "expires_at": expires_at,
                "item_count": len(flights),
            },
        )
    )


async def upsert_provider_offers(
    provider: str,
    offers: list[object],
    ttl_minutes: int,
    *,
    _session: Any = None,
) -> None:
    if not offers:
        return
    flights = [_offer_to_provider_flight(offer) for offer in offers]
    await upsert_provider_flights(
        provider,
        flights,
        ttl_minutes,
        _session=_session,
    )


async def read_deals_latest(
    *,
    origin_code: str,
    destination_code: str,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Return only the latest future legacy inventory for a route."""
    cutoff = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    async with get_session() as s:
        latest = (await s.execute(
            select(func.max(FlightSnapshot.depart_date))
            .join(
                PlatformPriceSnapshot,
                PlatformPriceSnapshot.flight_snapshot_id == FlightSnapshot.id,
            )
            .where(
                FlightSnapshot.origin_code == origin_code,
                FlightSnapshot.destination_code == destination_code,
                FlightSnapshot.depart_date > cutoff.isoformat(),
                PlatformPriceSnapshot.data_provider == "legacy",
            )
        )).scalar_one_or_none()
    if not latest:
        return []
    return await read_deals(
        origin_code=origin_code, destination_code=destination_code, depart_date=latest
    )


async def read_deals(*, origin_code: str, destination_code: str, depart_date: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    async with get_session() as s:
        snaps = (await s.execute(
            select(FlightSnapshot)
            .join(
                PlatformPriceSnapshot,
                PlatformPriceSnapshot.flight_snapshot_id == FlightSnapshot.id,
            )
            .where(
                FlightSnapshot.origin_code == origin_code,
                FlightSnapshot.destination_code == destination_code,
                FlightSnapshot.depart_date == depart_date,
                PlatformPriceSnapshot.data_provider == "legacy",
            )
            .distinct()
        )).scalars().all()
        if not snaps:
            return []
        deals: list[dict[str, Any]] = []
        for snap in snaps:
            prices = (await s.execute(
                select(PlatformPriceSnapshot)
                .where(
                    PlatformPriceSnapshot.flight_snapshot_id == snap.id,
                    PlatformPriceSnapshot.data_provider == "legacy",
                )
                .order_by(PlatformPriceSnapshot.price.asc())
            )).scalars().all()
            currency = _display_currency(prices)
            display_prices = [
                price for price in prices if price.currency == currency
            ]
            freshness = {
                price.id: _inventory_freshness(
                    price.expires_at,
                    price_status=price.price_status,
                    now=now,
                )
                for price in prices
            }
            eligible_prices = [
                price
                for price in display_prices
                if freshness[price.id] == "fresh"
            ]
            winning_price = min(
                eligible_prices,
                key=lambda price: (price.price, price.platform, price.id),
                default=None,
            )
            reference_price = winning_price or min(
                display_prices,
                key=lambda price: (price.price, price.platform, price.id),
                default=None,
            )
            price_items = [
                {
                    "id": p.id,
                    "platform": p.platform,
                    "price": p.price,
                    "currency": p.currency,
                    "url": p.url,
                    "lowest": winning_price is not None and p.id == winning_price.id,
                    "price_status": p.price_status,
                    "data_provider": p.data_provider,
                    "data_freshness": freshness[p.id],
                    "expires_at": (
                        p.expires_at.isoformat()
                        if p.expires_at is not None
                        else None
                    ),
                }
                for p in prices
            ]
            deals.append({
                "flight_no": snap.flight_no, "airline": snap.airline,
                "origin_code": snap.origin_code, "destination_code": snap.destination_code,
                "depart_date": snap.depart_date, "dep_time": snap.dep_time, "arr_time": snap.arr_time,
                "duration": snap.duration, "stops": snap.stops,
                "lowest_price": reference_price.price if reference_price is not None else 0,
                "currency": currency,
                "history_avg_90d": snap.history_avg_90d, "history_low_90d": snap.history_low_90d,
                "prices": price_items,
                "winning_price_id": winning_price.id if winning_price is not None else None,
                "data_freshness": (
                    freshness[reference_price.id]
                    if reference_price is not None
                    else "unknown"
                ),
            })
        deals.sort(key=_deal_sort_key)
        return deals


async def read_provider_deals(
    provider: str,
    origin_code: str,
    destination_code: str,
    depart_date: str,
) -> tuple[list[dict[str, Any]], int | None, bool]:
    async with get_session() as s:
        observation = (
            await s.execute(
                select(ProviderInventoryObservation).where(
                    ProviderInventoryObservation.provider == provider,
                    ProviderInventoryObservation.origin_code == origin_code,
                    ProviderInventoryObservation.destination_code
                    == destination_code,
                    ProviderInventoryObservation.depart_date == depart_date,
                )
            )
        ).scalar_one_or_none()
        snaps = (
            await s.execute(
                select(FlightSnapshot)
                .join(
                    PlatformPriceSnapshot,
                    PlatformPriceSnapshot.flight_snapshot_id
                    == FlightSnapshot.id,
                )
                .where(
                    FlightSnapshot.origin_code == origin_code,
                    FlightSnapshot.destination_code == destination_code,
                    FlightSnapshot.depart_date == depart_date,
                    PlatformPriceSnapshot.data_provider == provider,
                )
                .distinct()
            )
        ).scalars().all()
        deals: list[dict[str, Any]] = []
        provider_rows: list[PlatformPriceSnapshot] = []
        for snap in snaps:
            prices = (
                await s.execute(
                    select(PlatformPriceSnapshot)
                    .where(
                        PlatformPriceSnapshot.flight_snapshot_id == snap.id,
                        PlatformPriceSnapshot.data_provider == provider,
                    )
                    .order_by(PlatformPriceSnapshot.price.asc())
                )
            ).scalars().all()
            provider_rows.extend(prices)
            currency = _display_currency(prices)
            display_prices = [
                price for price in prices if price.currency == currency
            ]
            price_items = [
                {
                    "id": price.id,
                    "platform": price.platform,
                    "price": price.price,
                    "url": price.url,
                    "currency": price.currency,
                    "price_status": price.price_status,
                    "crawled_at": price.crawled_at.isoformat(),
                    "expires_at": (
                        price.expires_at.isoformat()
                        if price.expires_at is not None
                        else None
                    ),
                }
                for price in prices
            ]
            deals.append(
                {
                    "flight_no": snap.flight_no,
                    "airline": snap.airline,
                    "origin_code": snap.origin_code,
                    "destination_code": snap.destination_code,
                    "depart_date": snap.depart_date,
                    "dep_time": snap.dep_time,
                    "arr_time": snap.arr_time,
                    "duration": snap.duration,
                    "stops": snap.stops,
                    "lowest_price": min(
                        (price.price for price in display_prices), default=0
                    ),
                    "currency": currency,
                    "history_avg_90d": snap.history_avg_90d,
                    "history_low_90d": snap.history_low_90d,
                    "prices": price_items,
                }
            )

    now = datetime.now(timezone.utc)
    if not snaps:
        if observation is None:
            return [], None, False
        return (
            [],
            _observation_age_seconds(observation.observed_at, now),
            observation.expires_at <= now,
        )

    if observation is not None:
        age = _observation_age_seconds(observation.observed_at, now)
        all_stale = observation.expires_at <= now
    else:
        newest_crawl = max(row.crawled_at for row in provider_rows)
        age = _observation_age_seconds(newest_crawl, now)
        all_stale = all(
            _inventory_freshness(
                row.expires_at,
                price_status=row.price_status,
                now=now,
            )
            != "fresh"
            for row in provider_rows
        )
    deals.sort(key=_deal_sort_key)
    return deals, age, all_stale
