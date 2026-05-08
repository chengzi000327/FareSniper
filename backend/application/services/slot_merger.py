from __future__ import annotations

import copy

from backend.application.contracts.intent import SlotBundle


def merge_slots(accumulated: SlotBundle, new_slots: dict) -> SlotBundle:
    merged = copy.copy(accumulated)
    for k, v in new_slots.items():
        if v is not None and hasattr(merged, k):
            setattr(merged, k, v)
    return merged
