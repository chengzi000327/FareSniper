from __future__ import annotations


def compute_signals(
    *,
    price: int,
    hist_avg: int | None,
    user_band: dict | None,
    holiday: bool,
    frequent_route: bool,
) -> list[str]:
    sigs: list[str] = []
    if hist_avg and price <= hist_avg * 0.85:
        sigs.append("历史低价")
    if user_band and user_band["min"] <= price <= user_band["max"]:
        sigs.append("符合心理价位")
    if holiday:
        sigs.append("节假日热门")
    if frequent_route:
        sigs.append("符合出行习惯")
    return sigs
