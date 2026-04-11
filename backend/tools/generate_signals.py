from __future__ import annotations

from typing import Dict, List


def generate_signals(
    comparison: Dict[str, object],
    history: Dict[str, object],
    preference: Dict[str, object],
) -> List[str]:
    signals: List[str] = []

    lower_than_avg = history.get("lower_than_avg")
    percentile = history.get("percentile")
    within_budget = preference.get("within_budget")

    if isinstance(lower_than_avg, float) and lower_than_avg >= 0.15:
        signals.append("低于近90天均价")
    if isinstance(percentile, float) and percentile <= 0.25:
        signals.append("近90天低位")
    if within_budget:
        signals.append("符合心理价位")
    if comparison.get("price_spread_pct") is not None and comparison["price_spread_pct"] <= 0.1:
        signals.append("同批次价差较小")

    if not signals:
        signals.append("建议继续观察")

    return signals
