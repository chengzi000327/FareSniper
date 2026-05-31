from __future__ import annotations

from typing import Any

from backend.utils.airport_codes import city_to_code


def _key(row: dict[str, Any]) -> tuple:
    return (row.get("flight_number", ""), row.get("dep_time", ""), row.get("date", ""))


def normalize_raw_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把多平台原始抓取行聚合为业务航班结构（同航班按 flight_no+dep_time+date 聚合）。"""
    grouped: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        price = row.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            continue  # 丢弃异常价格，不影响同航班其它平台
        key = _key(row)
        flight = grouped.get(key)
        if flight is None:
            flight = {
                "flight_no": row.get("flight_number", ""),
                "airline": row.get("airline", ""),
                "origin_city": row.get("dep_city", ""),
                "destination_city": row.get("arr_city", ""),
                "origin_code": city_to_code(row.get("dep_city", "")),
                "destination_code": city_to_code(row.get("arr_city", "")),
                "depart_date": row.get("date", ""),
                "dep_time": row.get("dep_time", ""),
                "arr_time": row.get("arr_time", ""),
                "duration": row.get("duration", ""),
                "stops": int(row.get("transfer_count", 0) or 0),
                "prices": [],
                "history_avg_90d": None,
                "history_low_90d": None,
            }
            grouped[key] = flight
        flight["prices"].append(
            {"platform": row.get("platform", ""), "price": int(price), "url": row.get("url", "")}
        )

    out: list[dict[str, Any]] = []
    for flight in grouped.values():
        flight["prices"].sort(key=lambda p: p["price"])
        lowest = flight["prices"][0]["price"]
        flight["lowest_price"] = lowest
        for p in flight["prices"]:
            p["lowest"] = p["price"] == lowest
        out.append(flight)
    return out
