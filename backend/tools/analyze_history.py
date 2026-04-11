from __future__ import annotations

from typing import Dict, List, Optional


def analyze_history(history_prices: List[Dict[str, object]], current_price: Optional[int]) -> Dict[str, Optional[float]]:
    prices = [int(item["price"]) for item in history_prices if item.get("price") is not None]
    if not prices or current_price is None:
        return {
            "avg_90d": None,
            "lower_than_avg": None,
            "percentile": None,
        }

    avg_price = round(sum(prices) / len(prices))
    sorted_prices = sorted(prices)
    smaller_or_equal = len([price for price in sorted_prices if price <= current_price])
    percentile = round(smaller_or_equal / len(sorted_prices), 2)

    if avg_price == 0:
        lower_than_avg = None
    else:
        lower_than_avg = round((avg_price - current_price) / avg_price, 2)

    return {
        "avg_90d": avg_price,
        "lower_than_avg": lower_than_avg,
        "percentile": percentile,
    }
