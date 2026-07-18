from __future__ import annotations

import hashlib
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


class FlightSearchDemandRow(Base):
    __tablename__ = "flight_search_demands"
    __table_args__ = (
        UniqueConstraint(
            "origin_code",
            "destination_code",
            "depart_date",
            "demand_hour",
            name="uq_flight_search_demand_hour",
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
    destination_code = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    demand_hour = Column(DateTime(timezone=True), nullable=False)
    priority = Column(Integer, nullable=False, default=10)
    source = Column(String, nullable=False)
    last_requested_at = Column(DateTime(timezone=True), nullable=False)
    next_run_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False)
    lease_owner = Column(String, nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


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
    destination_code: str
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
            destination_code=row.destination_code,
            depart_date=row.depart_date,
            source=row.source,
            priority=row.priority,
            attempts=row.attempts,
            node_id=row.lease_owner,
            lease_expires_at=row.lease_expires_at,
        )


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
    demand_hour = now.replace(minute=0, second=0, microsecond=0)
    demand_id = hashlib.sha1(
        (
            f"{origin_code}|{destination_code}|{depart_date}|"
            f"{demand_hour.isoformat()}"
        ).encode()
    ).hexdigest()[:24]
    values = {
        "id": demand_id,
        "origin_code": origin_code,
        "destination_code": destination_code,
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
                    FlightSearchDemandRow.last_requested_at.desc(),
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
) -> bool:
    from backend.infrastructure.db import flight_snapshot_repo

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
        if offers:
            _verify_offer_scope(row, offers)
            _verify_ctrip_offer_identity(offers)
        if row.status == "completed" and row.lease_owner == node_id:
            return False
        _verify_live_lease(row, node_id, now)

        if offers:
            await flight_snapshot_repo._upsert_provider_offers_in_session(
                session,
                "ctrip_snapshot",
                offers,
                ttl_minutes=75,
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
        if row.status == "retry" and row.lease_owner == node_id:
            return False
        _verify_live_lease(row, node_id, now)

        row.status = "retry"
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
        destination_code = _offer_field(offer, "destination_code")
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


def _verify_ctrip_offer_identity(offers: list[object]) -> None:
    for offer in offers:
        if (
            _offer_field(offer, "data_provider") != "ctrip"
            or _offer_field(offer, "seller_name") != "携程"
        ):
            raise CollectorOfferValidationError(
                "collector offers must have Ctrip identity"
            )


def _offer_field(offer: object, name: str) -> object:
    if isinstance(offer, dict):
        return offer.get(name)
    return getattr(offer, name, None)
