from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.infrastructure.db.base import Base, get_session


class FlightSearchDemandRow(Base):
    __tablename__ = "flight_search_demands"
    __table_args__ = (
        UniqueConstraint(
            "origin_code",
            "destination_code",
            "depart_date",
            name="uq_flight_search_demand_route_date",
        ),
        Index(
            "ix_flight_search_demands_due",
            "active",
            "next_run_at",
            "priority",
        ),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True)
    origin_code = Column(String, nullable=False)
    destination_code = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    priority = Column(Integer, nullable=False, default=10)
    source = Column(String, nullable=False)
    last_requested_at = Column(DateTime(timezone=True), nullable=False)
    next_run_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


@dataclass(frozen=True)
class FlightSearchDemand:
    id: str
    origin_code: str
    destination_code: str
    depart_date: str
    priority: int
    source: str
    last_requested_at: datetime
    next_run_at: datetime
    expires_at: datetime
    active: bool

    @classmethod
    def from_row(cls, row: FlightSearchDemandRow) -> FlightSearchDemand:
        return cls(
            id=row.id,
            origin_code=row.origin_code,
            destination_code=row.destination_code,
            depart_date=row.depart_date,
            priority=row.priority,
            source=row.source,
            last_requested_at=row.last_requested_at,
            next_run_at=row.next_run_at,
            expires_at=row.expires_at,
            active=row.active,
        )


async def enqueue_demand(
    *,
    origin_code: str,
    destination_code: str,
    depart_date: str,
    priority: int,
    source: str,
) -> None:
    now = datetime.now(timezone.utc)
    demand_id = hashlib.sha1(
        f"{origin_code}|{destination_code}|{depart_date}".encode()
    ).hexdigest()[:24]
    values = {
        "id": demand_id,
        "origin_code": origin_code,
        "destination_code": destination_code,
        "depart_date": depart_date,
        "priority": priority,
        "source": source,
        "last_requested_at": now,
        "next_run_at": now,
        "expires_at": now + timedelta(days=7),
        "active": True,
    }
    async with get_session() as session:
        stmt = pg_insert(FlightSearchDemandRow.__table__).values(**values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_flight_search_demand_route_date",
            set_={
                "priority": func.greatest(
                    FlightSearchDemandRow.priority, stmt.excluded.priority
                ),
                "source": stmt.excluded.source,
                "last_requested_at": now,
                "next_run_at": func.least(
                    FlightSearchDemandRow.next_run_at, now
                ),
                "expires_at": now + timedelta(days=7),
                "active": True,
            },
        )
        await session.execute(stmt)
        await session.commit()


async def claim_due_demands(limit: int) -> list[FlightSearchDemand]:
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        await session.execute(
            update(FlightSearchDemandRow)
            .where(
                FlightSearchDemandRow.depart_date <= now.date().isoformat()
            )
            .values(active=False)
        )
        rows = (
            await session.execute(
                select(FlightSearchDemandRow)
                .where(
                    FlightSearchDemandRow.active.is_(True),
                    FlightSearchDemandRow.expires_at > now,
                    FlightSearchDemandRow.next_run_at <= now,
                )
                .order_by(
                    FlightSearchDemandRow.priority.desc(),
                    FlightSearchDemandRow.last_requested_at.desc(),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for row in rows:
            row.next_run_at = now + timedelta(hours=1)
        await session.commit()
        return [FlightSearchDemand.from_row(row) for row in rows]
