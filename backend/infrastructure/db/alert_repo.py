from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Integer, String, select, update
from sqlalchemy.sql import func

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
    status = Column(String, nullable=False, server_default="active")
    created_at = Column(DateTime, nullable=False, server_default=func.now())


async def create_alert(
    user_id: str,
    *,
    origin: str,
    destination: str,
    depart_date: str,
    target_price: int,
) -> str:
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
            )
        )
        await s.commit()
    return aid


async def list_alerts(user_id: str) -> list[PriceAlert]:
    async with get_session() as s:
        return list(
            (
                await s.execute(
                    select(PriceAlert).where(PriceAlert.user_id == user_id)
                )
            ).scalars().all()
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
        return [
            (row.origin, row.destination, row.depart_date)
            for row in rows
        ]


async def mark_triggered(alert_id: str) -> None:
    async with get_session() as s:
        await s.execute(
            update(PriceAlert)
            .where(PriceAlert.id == alert_id)
            .values(status="triggered")
        )
        await s.commit()
