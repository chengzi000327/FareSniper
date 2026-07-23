from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, UniqueConstraint, select
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session
from backend.infrastructure.db.user_repo import allocate_anonymous


class WechatAccount(Base):
    __tablename__ = "wechat_accounts"
    __table_args__ = (
        UniqueConstraint("app_id", "open_id", name="uq_wechat_app_openid"),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    app_id = Column(String, nullable=False)
    open_id = Column(String, nullable=False)
    union_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


async def get_wechat_account_for_user(user_id: str) -> WechatAccount | None:
    async with get_session() as session:
        return (
            await session.execute(
                select(WechatAccount).where(WechatAccount.user_id == user_id)
            )
        ).scalar_one_or_none()


async def find_wechat_user_id(*, app_id: str, open_id: str) -> str | None:
    async with get_session() as session:
        return (
            await session.execute(
                select(WechatAccount.user_id).where(
                    WechatAccount.app_id == app_id,
                    WechatAccount.open_id == open_id,
                )
            )
        ).scalar_one_or_none()


async def bind_wechat_account(
    user_id: str,
    *,
    app_id: str,
    open_id: str,
    union_id: str | None = None,
) -> WechatAccount:
    async with get_session() as session:
        existing = (
            await session.execute(
                select(WechatAccount).where(
                    WechatAccount.app_id == app_id,
                    WechatAccount.open_id == open_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            if union_id and not existing.union_id:
                existing.union_id = union_id
                await session.commit()
            return existing

        account = WechatAccount(
            id=f"wx_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            app_id=app_id,
            open_id=open_id,
            union_id=union_id,
        )
        session.add(account)
        await session.commit()
        return account


async def find_or_create_wechat_user(
    *,
    app_id: str,
    open_id: str,
    union_id: str | None = None,
) -> str:
    existing = await find_wechat_user_id(app_id=app_id, open_id=open_id)
    if existing is not None:
        return existing
    user_id = await allocate_anonymous()
    account = await bind_wechat_account(
        user_id,
        app_id=app_id,
        open_id=open_id,
        union_id=union_id,
    )
    return account.user_id
