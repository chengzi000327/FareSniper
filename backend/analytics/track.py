"""Backend telemetry channel: validate payload and persist to PG."""
from __future__ import annotations

from backend.analytics.events import EVENT_SCHEMAS, EventName
from backend.infrastructure.db.event_repo import insert_event


async def track(event: EventName, *, user_id: str, payload: dict) -> None:
    required = EVENT_SCHEMAS[event]["required"]
    for field in required:
        if field not in payload:
            raise ValueError(f"missing required field: {field}")
    await insert_event(event.value, user_id, payload)
