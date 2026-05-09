"""Persistence layer for dynamic intent definitions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB

from backend.application.contracts.intent_registry import IntentDefinition
from backend.infrastructure.db.base import Base, get_session


class IntentRegistry(Base):
    __tablename__ = "intent_registry"
    __table_args__ = {"extend_existing": True}

    name = Column(String, primary_key=True)
    description = Column(Text, nullable=False, default="")
    required_slots = Column(JSONB, nullable=False, default=list)
    optional_slots = Column(JSONB, nullable=False, default=list)
    slot_schema = Column(JSONB, nullable=False, default=dict)
    handler_name = Column(String, nullable=False, default="")
    keywords = Column(JSONB, nullable=False, default=list)
    is_active = Column(Boolean, nullable=False, default=True)
    priority = Column(Integer, nullable=False, default=100)


class IntentExample(Base):
    __tablename__ = "intent_examples"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    intent_name = Column(
        String,
        ForeignKey("intent_registry.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    example_text = Column(Text, nullable=False)
    embedding = Column(JSONB, nullable=True)


async def list_active_intents() -> list[IntentDefinition]:
    async with get_session() as session:
        rows = (
            await session.execute(
                select(IntentRegistry)
                .where(IntentRegistry.is_active.is_(True))
                .order_by(IntentRegistry.priority.desc(), IntentRegistry.name.asc())
            )
        ).scalars().all()
        if not rows:
            return []

        examples_by_intent = {row.name: [] for row in rows}
        example_rows = (
            await session.execute(
                select(IntentExample).where(
                    IntentExample.intent_name.in_(examples_by_intent.keys())
                )
            )
        ).scalars().all()
        for example in example_rows:
            examples_by_intent.setdefault(example.intent_name, []).append(
                example.example_text
            )

        return [_to_definition(row, examples_by_intent.get(row.name, [])) for row in rows]


async def list_intents() -> list[IntentDefinition]:
    async with get_session() as session:
        rows = (
            await session.execute(
                select(IntentRegistry).order_by(
                    IntentRegistry.priority.desc(), IntentRegistry.name.asc()
                )
            )
        ).scalars().all()
        if not rows:
            return []

        examples_by_intent = {row.name: [] for row in rows}
        example_rows = (
            await session.execute(
                select(IntentExample).where(
                    IntentExample.intent_name.in_(examples_by_intent.keys())
                )
            )
        ).scalars().all()
        for example in example_rows:
            examples_by_intent.setdefault(example.intent_name, []).append(
                example.example_text
            )

        return [_to_definition(row, examples_by_intent.get(row.name, [])) for row in rows]


async def upsert_intent(definition: IntentDefinition) -> IntentDefinition:
    async with get_session() as session:
        row = (
            await session.execute(
                select(IntentRegistry).where(IntentRegistry.name == definition.name)
            )
        ).scalar_one_or_none()
        if row is None:
            row = IntentRegistry(name=definition.name)
            session.add(row)

        row.description = definition.description
        row.required_slots = definition.required_slots
        row.optional_slots = definition.optional_slots
        row.slot_schema = definition.slot_schema
        row.handler_name = definition.handler_name
        row.keywords = definition.keywords
        row.is_active = definition.is_active
        row.priority = definition.priority

        await session.commit()
        return definition


async def replace_examples(intent_name: str, examples: list[str]) -> None:
    from sqlalchemy import delete

    async with get_session() as session:
        await session.execute(
            delete(IntentExample).where(IntentExample.intent_name == intent_name)
        )
        for text in examples:
            session.add(IntentExample(intent_name=intent_name, example_text=text))
        await session.commit()


def _to_definition(row: IntentRegistry, examples: list[str]) -> IntentDefinition:
    return IntentDefinition(
        name=row.name,
        description=row.description or "",
        required_slots=_list(row.required_slots),
        optional_slots=_list(row.optional_slots),
        slot_schema=row.slot_schema or {},
        handler_name=row.handler_name or "",
        keywords=_list(row.keywords),
        examples=examples,
        is_active=bool(row.is_active),
        priority=row.priority or 100,
    )


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []
