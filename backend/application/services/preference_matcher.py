from __future__ import annotations

from backend.application.contracts.preference import Memory


def _is_redeye(t: str) -> bool:
    h = int(t.split(":")[0])
    return h >= 23 or h < 7


def match(deals: list[dict], pref: Memory) -> dict:
    filtered = list(deals)
    if pref.budget_ceiling:
        filtered = [d for d in filtered if d.get("price", 0) <= pref.budget_ceiling]
    if "avoid_redeye" in pref.constraints:
        filtered = [
            d
            for d in filtered
            if "depart_time" not in d or not _is_redeye(d["depart_time"])
        ]
    boosted = sorted(
        filtered,
        key=lambda d: 0 if d.get("airline") in pref.preferred_airlines else 1,
    )
    return {"filtered": filtered, "boosted": boosted}
