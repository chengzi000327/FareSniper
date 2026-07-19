from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Boolean,
    case,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.application.services.flight_dates import (
    validate_canonical_depart_date,
)
from backend.infrastructure.db.base import Base, get_session

APPROVED_DEMAND_SOURCES = frozenset(
    {"recent_search", "price_alert", "hot_route"}
)
MAX_DEMAND_ATTEMPTS = 3


class FlightSearchDemandRow(Base):
    __tablename__ = "flight_search_demands"
    __table_args__ = (
        UniqueConstraint(
            "origin_code",
            "origin_airport_code",
            "destination_code",
            "destination_airport_code",
            "depart_date",
            "demand_hour",
            name="uq_flight_search_demand_hour",
        ),
        UniqueConstraint(
            "origin_code",
            "origin_airport_code",
            "destination_code",
            "destination_airport_code",
            "depart_date",
            "demand_hour",
            name="uq_flight_search_demand_route_date",
        ),
        Index(
            "ix_flight_search_demands_due",
            "active",
            "status",
            "next_attempt_at",
            "priority",
        ),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True)
    origin_code = Column(String, nullable=False)
    origin_airport_code = Column(
        String, nullable=False, default="", server_default=""
    )
    destination_code = Column(String, nullable=False)
    destination_airport_code = Column(
        String, nullable=False, default="", server_default=""
    )
    depart_date = Column(String, nullable=False)
    demand_hour = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default="1970-01-01 00:00:00+00",
    )
    priority = Column(Integer, nullable=False, default=10)
    source = Column(String, nullable=False)
    last_requested_at = Column(DateTime(timezone=True), nullable=False)
    next_run_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    status = Column(
        String, nullable=False, default="pending", server_default="pending"
    )
    attempts = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_attempt_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_owner = Column(String, nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectorNodeRow(Base):
    __tablename__ = "collector_nodes"
    __table_args__ = {"extend_existing": True}

    node_id = Column(String, primary_key=True)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    last_heartbeat = Column(DateTime(timezone=True), nullable=False)
    last_success = Column(DateTime(timezone=True), nullable=True)


@dataclass(frozen=True)
class CollectorJob:
    job_id: str
    origin_code: str
    origin_airport_code: str | None
    destination_code: str
    destination_airport_code: str | None
    depart_date: str
    source: str
    priority: int
    attempts: int
    node_id: str
    lease_expires_at: datetime

    @classmethod
    def from_row(cls, row: FlightSearchDemandRow) -> CollectorJob:
        assert row.lease_owner is not None
        assert row.lease_expires_at is not None
        return cls(
            job_id=row.id,
            origin_code=row.origin_code,
            origin_airport_code=row.origin_airport_code or None,
            destination_code=row.destination_code,
            destination_airport_code=row.destination_airport_code or None,
            depart_date=row.depart_date,
            source=row.source,
            priority=row.priority,
            attempts=row.attempts,
            node_id=row.lease_owner,
            lease_expires_at=row.lease_expires_at,
        )


@dataclass(frozen=True)
class CollectorVerificationStatus:
    collector_online: bool
    last_heartbeat_at: datetime | None
    last_success_at: datetime | None
    job_status: str
    job_attempts: int
    job_updated_at: datetime | None
    snapshot_observed_at: datetime | None


class LeaseOwnershipError(RuntimeError):
    pass


class CollectorJobNotFoundError(LookupError):
    pass


class CollectorOfferValidationError(ValueError):
    pass


async def enqueue_demand(
    origin_code: str,
    destination_code: str,
    depart_date: str,
    source: str,
    priority: int,
    origin_airport_code: str | None = None,
    destination_airport_code: str | None = None,
    *,
    reactivate_completed: bool = True,
) -> str:
    validate_canonical_depart_date(depart_date)
    if source not in APPROVED_DEMAND_SOURCES:
        raise ValueError("source must be an approved demand source")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    if depart_date <= today:
        raise ValueError(
            "collector demand requires a future depart_date in Asia/Shanghai"
        )

    now = datetime.now(timezone.utc)
    origin_airport_scope = _normalize_airport_scope(origin_airport_code)
    destination_airport_scope = _normalize_airport_scope(
        destination_airport_code
    )
    demand_hour = now.replace(minute=0, second=0, microsecond=0)
    demand_id = hashlib.sha1(
        (
            f"{origin_code}|{origin_airport_scope}|"
            f"{destination_code}|{destination_airport_scope}|{depart_date}|"
            f"{demand_hour.isoformat()}"
        ).encode()
    ).hexdigest()[:24]
    values = {
        "id": demand_id,
        "origin_code": origin_code,
        "origin_airport_code": origin_airport_scope,
        "destination_code": destination_code,
        "destination_airport_code": destination_airport_scope,
        "depart_date": depart_date,
        "demand_hour": demand_hour,
        "priority": priority,
        "source": source,
        "last_requested_at": now,
        "next_run_at": now,
        "expires_at": now + timedelta(days=7),
        "active": True,
        "status": "pending",
        "attempts": 0,
        "next_attempt_at": now,
        "lease_owner": None,
        "lease_expires_at": None,
        "last_error": None,
        "created_at": now,
        "updated_at": now,
    }
    async with get_session() as session:
        await session.execute(
            update(FlightSearchDemandRow)
            .where(
                FlightSearchDemandRow.origin_code == origin_code,
                FlightSearchDemandRow.origin_airport_code
                == origin_airport_scope,
                FlightSearchDemandRow.destination_code == destination_code,
                FlightSearchDemandRow.destination_airport_code
                == destination_airport_scope,
                FlightSearchDemandRow.depart_date == depart_date,
                FlightSearchDemandRow.demand_hour < demand_hour,
                FlightSearchDemandRow.priority <= priority,
                FlightSearchDemandRow.status != "leased",
            )
            .values(active=False, updated_at=now)
        )
        stmt = pg_insert(FlightSearchDemandRow.__table__).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_flight_search_demand_hour",
            set_={
                "priority": func.greatest(
                    FlightSearchDemandRow.priority, stmt.excluded.priority
                ),
                "source": case(
                    (
                        stmt.excluded.priority
                        > FlightSearchDemandRow.priority,
                        stmt.excluded.source,
                    ),
                    else_=FlightSearchDemandRow.source,
                ),
                "last_requested_at": now,
                "next_run_at": func.least(
                    FlightSearchDemandRow.next_run_at, now
                ),
                "next_attempt_at": func.least(
                    FlightSearchDemandRow.next_attempt_at, now
                ),
                "expires_at": now + timedelta(days=7),
                "active": True,
                "status": (
                    case(
                        (
                            FlightSearchDemandRow.status == "completed",
                            "pending",
                        ),
                        else_=FlightSearchDemandRow.status,
                    )
                    if reactivate_completed
                    else FlightSearchDemandRow.status
                ),
                "updated_at": now,
            },
        )
        await session.execute(stmt)
        await session.commit()
    return demand_id


async def claim_next(
    node_id: str, lease_seconds: int
) -> CollectorJob | None:
    if lease_seconds <= 0:
        raise ValueError("lease_seconds must be positive")

    now = datetime.now(timezone.utc)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    async with get_session() as session:
        await session.execute(
            update(FlightSearchDemandRow)
            .where(FlightSearchDemandRow.depart_date <= today)
            .values(active=False, updated_at=now)
        )
        row = (
            await session.execute(
                select(FlightSearchDemandRow)
                .where(
                    FlightSearchDemandRow.active.is_(True),
                    FlightSearchDemandRow.expires_at > now,
                    FlightSearchDemandRow.next_attempt_at <= now,
                    or_(
                        FlightSearchDemandRow.status.in_(
                            ("pending", "retry")
                        ),
                        (
                            (FlightSearchDemandRow.status == "leased")
                            & (
                                FlightSearchDemandRow.lease_expires_at
                                <= now
                            )
                        ),
                    ),
                )
                .order_by(
                    FlightSearchDemandRow.priority.desc(),
                    FlightSearchDemandRow.last_requested_at.asc(),
                    FlightSearchDemandRow.id.asc(),
                )
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if row is None:
            await session.commit()
            return None

        row.status = "leased"
        row.attempts += 1
        row.lease_owner = node_id
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.updated_at = now
        await session.commit()
        return CollectorJob.from_row(row)


async def complete_job(
    job_id: str,
    node_id: str,
    offers: list[object],
    *,
    ttl_minutes: int = 75,
) -> bool:
    from backend.infrastructure.db import flight_snapshot_repo

    if not offers:
        raise CollectorOfferValidationError(
            "collector completion requires at least one offer"
        )
    if ttl_minutes <= 0:
        raise ValueError("snapshot TTL must be positive")
    _verify_offer_scope_values(offers)

    now = datetime.now(timezone.utc)
    async with get_session() as session:
        row = (
            await session.execute(
                select(FlightSearchDemandRow)
                .where(FlightSearchDemandRow.id == job_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise CollectorJobNotFoundError(job_id)
        _verify_offer_scope(row, offers)
        _verify_ctrip_offer_identity(offers)
        _verify_booking_urls_match_lease(row, offers)
        if row.status == "completed" and row.lease_owner == node_id:
            return False
        _verify_live_lease(row, node_id, now)

        await flight_snapshot_repo._upsert_provider_offers_in_session(
            session,
            "ctrip_snapshot",
            offers,
            ttl_minutes=ttl_minutes,
            origin_airport_code=row.origin_airport_code or None,
            destination_airport_code=(
                row.destination_airport_code or None
            ),
        )

        row.status = "completed"
        row.lease_expires_at = None
        row.last_error = None
        row.updated_at = now
        await session.execute(
            update(CollectorNodeRow)
            .where(CollectorNodeRow.node_id == node_id)
            .values(last_success=now)
        )
        await session.commit()
        return True


async def fail_job(
    job_id: str,
    node_id: str,
    error_code: str,
    retry_at: datetime,
) -> bool:
    if retry_at.tzinfo is None:
        raise ValueError("retry_at must be timezone-aware")

    now = datetime.now(timezone.utc)
    async with get_session() as session:
        row = (
            await session.execute(
                select(FlightSearchDemandRow)
                .where(FlightSearchDemandRow.id == job_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise CollectorJobNotFoundError(job_id)
        if row.status in {"retry", "failed"} and row.lease_owner == node_id:
            return False
        _verify_live_lease(row, node_id, now)

        exhausted = row.attempts >= MAX_DEMAND_ATTEMPTS
        row.status = "failed" if exhausted else "retry"
        row.active = not exhausted
        row.next_attempt_at = retry_at.astimezone(timezone.utc)
        row.lease_expires_at = None
        row.last_error = error_code
        row.updated_at = now
        await session.commit()
        return True


async def record_heartbeat(
    node_id: str,
    version: str,
    status: str,
) -> None:
    now = datetime.now(timezone.utc)
    values = {
        "node_id": node_id,
        "version": version,
        "status": status,
        "last_heartbeat": now,
        "last_success": now if status == "success" else None,
    }
    async with get_session() as session:
        stmt = pg_insert(CollectorNodeRow.__table__).values(**values)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[CollectorNodeRow.node_id],
                set_={
                    "version": version,
                    "status": status,
                    "last_heartbeat": now,
                    "last_success": (
                        now
                        if status == "success"
                        else CollectorNodeRow.last_success
                    ),
                },
            )
        )
        await session.commit()


async def read_collector_verification_status(
    *,
    origin_code: str,
    origin_airport_code: str | None = None,
    destination_code: str,
    destination_airport_code: str | None = None,
    depart_date: str,
    heartbeat_timeout_seconds: int,
) -> CollectorVerificationStatus:
    from backend.infrastructure.db.flight_snapshot_repo import (
        FlightSnapshot,
        PlatformPriceSnapshot,
    )

    validate_canonical_depart_date(depart_date)
    if heartbeat_timeout_seconds <= 0:
        raise ValueError("heartbeat timeout must be positive")

    now = datetime.now(timezone.utc)
    origin_airport_scope = _normalize_airport_scope(origin_airport_code)
    destination_airport_scope = _normalize_airport_scope(
        destination_airport_code
    )
    async with get_session() as session:
        node = (
            await session.execute(
                select(CollectorNodeRow).order_by(
                    CollectorNodeRow.last_heartbeat.desc()
                ).limit(1)
            )
        ).scalar_one_or_none()
        job = (
            await session.execute(
                select(FlightSearchDemandRow)
                .where(
                    FlightSearchDemandRow.origin_code == origin_code,
                    FlightSearchDemandRow.origin_airport_code
                    == origin_airport_scope,
                    FlightSearchDemandRow.destination_code == destination_code,
                    FlightSearchDemandRow.destination_airport_code
                    == destination_airport_scope,
                    FlightSearchDemandRow.depart_date == depart_date,
                )
                .order_by(
                    FlightSearchDemandRow.demand_hour.desc(),
                    FlightSearchDemandRow.updated_at.desc(),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        snapshot_filters = [
            PlatformPriceSnapshot.data_provider == "ctrip_snapshot",
            FlightSnapshot.origin_code == origin_code,
            FlightSnapshot.destination_code == destination_code,
            FlightSnapshot.depart_date == depart_date,
        ]
        if origin_airport_scope:
            snapshot_filters.append(
                FlightSnapshot.origin_airport_code == origin_airport_scope
            )
        if destination_airport_scope:
            snapshot_filters.append(
                FlightSnapshot.destination_airport_code
                == destination_airport_scope
            )
        snapshot_observed_at = (
            await session.execute(
                select(func.max(PlatformPriceSnapshot.crawled_at))
                .join(
                    FlightSnapshot,
                    FlightSnapshot.id
                    == PlatformPriceSnapshot.flight_snapshot_id,
                )
                .where(*snapshot_filters)
            )
        ).scalar_one_or_none()

    heartbeat = _as_utc(node.last_heartbeat) if node is not None else None
    last_success = _as_utc(node.last_success) if node is not None else None
    job_updated_at = _as_utc(job.updated_at) if job is not None else None
    online = bool(
        heartbeat is not None
        and heartbeat
        >= now - timedelta(seconds=heartbeat_timeout_seconds)
    )
    status = str(job.status) if job is not None else "missing"
    if status not in {
        "pending",
        "leased",
        "retry",
        "completed",
        "failed",
    }:
        status = "missing"
    return CollectorVerificationStatus(
        collector_online=online,
        last_heartbeat_at=heartbeat,
        last_success_at=last_success,
        job_status=status,
        job_attempts=int(job.attempts) if job is not None else 0,
        job_updated_at=job_updated_at,
        snapshot_observed_at=_as_utc(snapshot_observed_at),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _verify_live_lease(
    row: FlightSearchDemandRow,
    node_id: str,
    now: datetime,
) -> None:
    lease_expires_at = row.lease_expires_at
    if lease_expires_at is not None and lease_expires_at.tzinfo is None:
        lease_expires_at = lease_expires_at.replace(tzinfo=timezone.utc)
    if (
        row.status != "leased"
        or row.lease_owner != node_id
        or lease_expires_at is None
        or lease_expires_at <= now
    ):
        raise LeaseOwnershipError(
            f"job {row.id} is not leased by node {node_id}"
        )


def _verify_offer_scope(
    row: FlightSearchDemandRow,
    offers: list[object],
) -> None:
    for offer in offers:
        origin_code = _offer_field(offer, "origin_code")
        origin_airport_code = _offer_field(offer, "origin_airport_code")
        destination_code = _offer_field(offer, "destination_code")
        destination_airport_code = _offer_field(
            offer, "destination_airport_code"
        )
        depart_date = _offer_field(offer, "depart_date")
        if (
            origin_code,
            destination_code,
            depart_date,
        ) != (
            row.origin_code,
            row.destination_code,
            row.depart_date,
        ):
            raise CollectorOfferValidationError(
                "collector offers do not match the leased job"
            )
        if not isinstance(origin_airport_code, str) or not isinstance(
            destination_airport_code, str
        ):
            raise CollectorOfferValidationError(
                "collector offers require airport evidence"
            )
        if (
            row.origin_airport_code
            and origin_airport_code != row.origin_airport_code
        ) or (
            row.destination_airport_code
            and destination_airport_code != row.destination_airport_code
        ):
            raise CollectorOfferValidationError(
                "collector offers do not match the leased airport scope"
            )


def _verify_ctrip_offer_identity(offers: list[object]) -> None:
    for offer in offers:
        if (
            _offer_field(offer, "data_provider") != "ctrip"
            or _offer_field(offer, "seller_name") != "携程"
        ):
            raise CollectorOfferValidationError(
                "collector offers must have Ctrip identity"
            )


def _verify_offer_scope_values(offers: list[object]) -> None:
    from backend.schemas.collector import normalize_ctrip_booking_url

    for offer in offers:
        booking_url = _offer_field(offer, "booking_url")
        depart_date = _offer_field(offer, "depart_date")
        origin_code = _offer_field(offer, "origin_code")
        origin_airport_code = _offer_field(offer, "origin_airport_code")
        destination_code = _offer_field(offer, "destination_code")
        destination_airport_code = _offer_field(
            offer, "destination_airport_code"
        )
        if not isinstance(booking_url, str) or not isinstance(depart_date, str):
            raise CollectorOfferValidationError(
                "collector offers require a Ctrip booking URL"
            )
        try:
            normalized = normalize_ctrip_booking_url(
                booking_url,
                depart_date=depart_date,
                origin_codes=(origin_code, origin_airport_code),
                destination_codes=(
                    destination_code,
                    destination_airport_code,
                ),
            )
        except ValueError as exc:
            raise CollectorOfferValidationError(
                "collector offers require a Ctrip booking URL"
            ) from exc
        if normalized != booking_url:
            raise CollectorOfferValidationError(
                "collector offers require a normalized Ctrip booking URL"
            )


def _verify_booking_urls_match_lease(
    row: FlightSearchDemandRow,
    offers: list[object],
) -> None:
    from backend.schemas.collector import normalize_ctrip_booking_url

    expected_origin = row.origin_airport_code or row.origin_code
    expected_destination = (
        row.destination_airport_code or row.destination_code
    )
    for offer in offers:
        booking_url = _offer_field(offer, "booking_url")
        if not isinstance(booking_url, str):
            raise CollectorOfferValidationError(
                "collector offers require a Ctrip booking URL"
            )
        try:
            normalize_ctrip_booking_url(
                booking_url,
                depart_date=row.depart_date,
                origin_codes=(expected_origin,),
                destination_codes=(expected_destination,),
            )
        except ValueError as exc:
            raise CollectorOfferValidationError(
                "collector offers require a Ctrip booking URL"
            ) from exc


def _offer_field(offer: object, name: str) -> object:
    if isinstance(offer, dict):
        return offer.get(name)
    return getattr(offer, name, None)


def _normalize_airport_scope(value: str | None) -> str:
    if value is None or not value.strip():
        return ""
    normalized = value.strip().upper()
    if re.fullmatch(r"[A-Z]{3}", normalized) is None:
        raise ValueError("airport scope must be a three-letter IATA code")
    return normalized
