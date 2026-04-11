from __future__ import annotations

from typing import Dict, List, Optional


def compare_prices(flights: List[Dict[str, object]]) -> Dict[str, Optional[float]]:
    prices = [int(flight["price"]) for flight in flights if flight.get("price") is not None]
    if not prices:
        return {
            "min_price": None,
            "max_price": None,
            "avg_price": None,
            "price_spread_pct": None,
        }

    min_price = min(prices)
    max_price = max(prices)
    avg_price = round(sum(prices) / len(prices))
    spread = round(((max_price - min_price) / min_price), 2) if min_price else None
    return {
        "min_price": min_price,
        "max_price": max_price,
        "avg_price": avg_price,
        "price_spread_pct": spread,
    }
