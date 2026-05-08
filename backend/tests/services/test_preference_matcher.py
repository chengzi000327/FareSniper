from __future__ import annotations

from backend.application.contracts.preference import Memory
from backend.application.services.preference_matcher import match


def test_budget_filter():
    deals = [{"price": 380}, {"price": 720}]
    pref = Memory(budget_ceiling=500)
    out = match(deals, pref)
    assert [d["price"] for d in out["filtered"]] == [380]


def test_airline_boost():
    deals = [{"price": 480, "airline": "MU"}, {"price": 480, "airline": "CA"}]
    pref = Memory(preferred_airlines=["CA"])
    out = match(deals, pref)
    assert out["boosted"][0]["airline"] == "CA"


def test_avoid_redeye():
    deals = [{"depart_time": "06:00"}, {"depart_time": "23:50"}]
    pref = Memory(constraints=["avoid_redeye"])
    out = match(deals, pref)
    assert all(d["depart_time"] != "23:50" for d in out["filtered"])
