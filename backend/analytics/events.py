"""Frontend / backend telemetry contract for the 8 launch-plan events.

The required-field lists are the single source of truth used by both the
frontend ``analytics`` helper (TG-13) and the backend ``track()`` channel
(TG-03 · Task 2). New optional fields can be added to a payload without
schema changes; new required fields require updating this module and any
producer at the same time.
"""
from __future__ import annotations

from enum import Enum
from typing import TypedDict


class EventName(str, Enum):
    SEARCH_SUBMITTED = "search_submitted"
    INTENT_PARSED = "intent_parsed"
    RESULT_VIEWED = "result_viewed"
    TICKET_CLICKED = "ticket_clicked"
    PURCHASE_JUMPED = "purchase_jumped"
    MEMORY_EDITED = "memory_edited"
    MEMORY_CLEARED = "memory_cleared"
    FALLBACK_TRIGGERED = "fallback_triggered"


class EventSchema(TypedDict):
    required: list[str]


EVENT_SCHEMAS: dict[EventName, EventSchema] = {
    EventName.SEARCH_SUBMITTED: {"required": ["query_text", "user_id", "clarify_count"]},
    EventName.INTENT_PARSED: {"required": ["intent_complete", "parse_failed"]},
    EventName.RESULT_VIEWED: {"required": ["result_count", "has_signals", "has_preference"]},
    EventName.TICKET_CLICKED: {"required": ["flight_no", "platform", "price", "signals"]},
    EventName.PURCHASE_JUMPED: {"required": ["flight_no", "platform", "price"]},
    EventName.MEMORY_EDITED: {"required": ["field_name"]},
    EventName.MEMORY_CLEARED: {"required": []},
    EventName.FALLBACK_TRIGGERED: {"required": ["reason"]},
}
