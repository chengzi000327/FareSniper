from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, select, update
from sqlalchemy.sql import func

from backend.application.services.flight_dates import (
    validate_canonical_depart_date,
)
from backend.infrastructure.db.base import Base, get_session


class PriceAlert(Base):
    __tablename__ = "alerts"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    target_price = Column(Integer, nullable=False)
    current_price = Column(Integer, nullable=True)
    currency = Column(String, nullable=False, server_default="CNY")
    latest_price = Column(Integer, nullable=True)
    latest_provider = Column(String, nullable=True)
    latest_quote_at = Column(DateTime(timezone=True), nullable=True)
    notification_status = Column(String, nullable=False, server_default="not_requested")
    status = Column(String, nullable=False, server_default="active")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


async def create_alert(
    user_id: str,
    *,
    origin: str,
    destination: str,
    depart_date: str,
    target_price: int,
    current_price: int | None = None,
    currency: str = "CNY",
    notification_status: str = "not_requested",
) -> str:
    validate_canonical_depart_date(depart_date)
    aid = f"alert_{uuid.uuid4().hex[:12]}"
    async with get_session() as s:
        s.add(
            PriceAlert(
                id=aid,
                user_id=user_id,
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                target_price=target_price,
                current_price=current_price,
                currency=currency,
                latest_price=current_price,
                notification_status=notification_status,
            )
        )
        await s.commit()
    return aid


async def list_alerts(user_id: str) -> list[PriceAlert]:
    async with get_session() as s:
        return list(
            (await s.execute(select(PriceAlert).where(PriceAlert.user_id == user_id)))
            .scalars()
            .all()
        )


async def list_active_alert_routes() -> list[tuple[str, str, str]]:
    async with get_session() as session:
        rows = (
            await session.execute(
                select(
                    PriceAlert.origin,
                    PriceAlert.destination,
                    PriceAlert.depart_date,
                ).where(PriceAlert.status == "active")
            )
        ).all()
        return [(row.origin, row.destination, row.depart_date) for row in rows]


async def get_alert_for_user(alert_id: str, user_id: str) -> PriceAlert | None:
    async with get_session() as session:
        return (
            await session.execute(
                select(PriceAlert).where(
                    PriceAlert.id == alert_id,
                    PriceAlert.user_id == user_id,
                )
            )
        ).scalar_one_or_none()


async def update_alert_observation(
    alert_id: str,
    *,
    price: int,
    provider: str | None,
    quote_at: datetime | None = None,
) -> None:
    async with get_session() as session:
        await session.execute(
            update(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .values(
                latest_price=price,
                latest_provider=provider,
                latest_quote_at=quote_at or datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()


async def update_alert_status(alert_id: str, user_id: str, *, status: str) -> bool:
    async with get_session() as session:
        result = await session.execute(
            update(PriceAlert)
            .where(
                PriceAlert.id == alert_id,
                PriceAlert.user_id == user_id,
            )
            .values(status=status, updated_at=datetime.now(timezone.utc))
        )
        await session.commit()
        return bool(result.rowcount)


async def mark_triggered(
    alert_id: str, *, notification_status: str = "not_requested"
) -> None:
    async with get_session() as s:
        await s.execute(
            update(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .values(
                status="triggered",
                notification_status=notification_status,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await s.commit()


async def mark_alert_notification_status(
    alert_id: str, notification_status: str
) -> None:
    async with get_session() as session:
        await session.execute(
            update(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .values(
                notification_status=notification_status,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
