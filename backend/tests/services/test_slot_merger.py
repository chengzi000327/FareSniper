from __future__ import annotations

from backend.application.contracts.intent import SlotBundle
from backend.application.services.slot_merger import merge_slots


def test_null_does_not_overwrite():
    acc = SlotBundle(origin="BJS", destination="SHA")
    merged = merge_slots(acc, {"origin": None, "depart_date": "2026-05-08"})
    assert merged.origin == "BJS"
    assert merged.depart_date == "2026-05-08"


def test_non_null_overwrites():
    acc = SlotBundle(origin="BJS")
    merged = merge_slots(acc, {"origin": "PEK"})
    assert merged.origin == "PEK"
