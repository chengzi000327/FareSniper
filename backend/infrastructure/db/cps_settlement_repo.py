"""Persistence for CPS (affiliate) settlement reconciliation."""
from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, select

from backend.infrastructure.db.base import Base, get_session


class CpsSettlement(Base):
    __tablename__ = "cps_settlements"
    __table_args__ = {"extend_existing": True}

    order_id = Column(String, primary_key=True)
    platform = Column(String, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    price = Column(Integer, nullable=False)
    commission = Column(Float, nullable=False)
    status = Column(String, nullable=False, default="pending")


async def upsert_settlement(
    *,
    order_id: str,
    platform: str,
    user_id: str,
    price: int,
    commission: float,
    status: str,
) -> None:
    async with get_session() as session:
        existing = (
            await session.execute(
                select(CpsSettlement).where(CpsSettlement.order_id == order_id)
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                CpsSettlement(
                    order_id=order_id,
                    platform=platform,
                    user_id=user_id,
                    price=price,
                    commission=commission,
                    status=status,
                )
            )
        else:
            existing.platform = platform
            existing.user_id = user_id
            existing.price = price
            existing.commission = commission
            existing.status = status
        await session.commit()


async def get_settlement(order_id: str) -> CpsSettlement:
    async with get_session() as session:
        return (
            await session.execute(
                select(CpsSettlement).where(CpsSettlement.order_id == order_id)
            )
        ).scalar_one()
