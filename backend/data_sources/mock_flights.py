"""静态 Mock 航班数据，覆盖 5 条高频航线 × 3 平台。

history_avg_90d = lowest_price × random(1.2, 1.5)  —— 模拟历史高于当前
history_low_90d = lowest_price × random(0.8, 0.95) —— 历史最低偶尔更便宜
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any


CITY_CODE: dict[str, str] = {
    "北京": "BJS",
    "成都": "CTU",
    "三亚": "SYX",
    "上海": "SHA",
    "广州": "CAN",
    "杭州": "HGH",
}

CODE_CITY: dict[str, str] = {v: k for k, v in CITY_CODE.items()}

# 平台深链模板
_DEEP_LINK_TPL = {
    "携程": "ctrip://flight/search?from={from_code}&to={to_code}&date={date}",
    "去哪儿": "qunar://flight?from={from_code}&to={to_code}&date={date}",
    "飞猪": "alitrip://flight?from={from_code}&to={to_code}&date={date}",
}

_H5_LINK_TPL = {
    "携程": "https://flights.ctrip.com/online/list/oneway-{from_code_l}-{to_code_l}?depdate={date}",
    "去哪儿": "https://flight.qunar.com/site/oneway.htm?searchDepartureAirport={from_code}&searchArrivalAirport={to_code}&searchDepartureTime={date}",
    "飞猪": "https://www.alitrip.com/flights/oneway/{from_code_l}-{to_code_l}/?date={date}",
}

# 5 条航线的基础数据（出发城市、目的地、航班列表）
_ROUTES: list[dict[str, Any]] = [
    {
        "origin": "北京", "dest": "成都",
        "flights": [
            {"flight_no": "CA4105", "airline": "中国国航", "dep": "07:20", "arr": "10:00", "duration": "2h40m", "stops": 0, "base": 420},
            {"flight_no": "MU5419", "airline": "东方航空", "dep": "12:30", "arr": "15:10", "duration": "2h40m", "stops": 0, "base": 380},
            {"flight_no": "3U8501", "airline": "四川航空", "dep": "18:50", "arr": "21:30", "duration": "2h40m", "stops": 0, "base": 350},
        ],
    },
    {
        "origin": "北京", "dest": "三亚",
        "flights": [
            {"flight_no": "HU7833", "airline": "海南航空", "dep": "09:30", "arr": "14:20", "duration": "4h50m", "stops": 0, "base": 389},
            {"flight_no": "CA1839", "airline": "中国国航", "dep": "06:55", "arr": "12:00", "duration": "5h05m", "stops": 0, "base": 450},
            {"flight_no": "MU2303", "airline": "东方航空", "dep": "15:40", "arr": "20:30", "duration": "4h50m", "stops": 0, "base": 410},
        ],
    },
    {
        "origin": "北京", "dest": "上海",
        "flights": [
            {"flight_no": "MU5106", "airline": "东方航空", "dep": "08:00", "arr": "10:00", "duration": "2h00m", "stops": 0, "base": 280},
            {"flight_no": "CA1801", "airline": "中国国航", "dep": "14:00", "arr": "16:05", "duration": "2h05m", "stops": 0, "base": 260},
        ],
    },
    {
        "origin": "北京", "dest": "广州",
        "flights": [
            {"flight_no": "CZ3101", "airline": "南方航空", "dep": "08:30", "arr": "12:00", "duration": "3h30m", "stops": 0, "base": 510},
            {"flight_no": "CA1301", "airline": "中国国航", "dep": "13:10", "arr": "16:50", "duration": "3h40m", "stops": 0, "base": 480},
            {"flight_no": "MU2175", "airline": "东方航空", "dep": "19:00", "arr": "22:45", "duration": "3h45m", "stops": 0, "base": 440},
        ],
    },
    {
        "origin": "北京", "dest": "杭州",
        "flights": [
            {"flight_no": "CA1713", "airline": "中国国航", "dep": "09:00", "arr": "11:05", "duration": "2h05m", "stops": 0, "base": 310},
            {"flight_no": "HU7307", "airline": "海南航空", "dep": "16:20", "arr": "18:25", "duration": "2h05m", "stops": 0, "base": 290},
        ],
    },
]

_PLATFORMS = ["携程", "去哪儿", "飞猪"]


def _price_spread(base: int, platform_idx: int) -> int:
    """平台间价差模拟：通常 ±5%-15%。"""
    spreads = [0, int(base * 0.08), int(base * 0.13)]
    return base + spreads[platform_idx]


def _history(lowest: int, seed: int) -> tuple[int, int]:
    rng = random.Random(seed)
    avg = int(lowest * rng.uniform(1.2, 1.5))
    low = int(lowest * rng.uniform(0.8, 0.95))
    return avg, low


def _make_id(flight_no: str, depart_date: str) -> str:
    raw = f"{flight_no}-{depart_date}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _build_links(origin_code: str, dest_code: str, depart_date: str, platform: str) -> tuple[str, str]:
    kw = {
        "from_code": origin_code,
        "to_code": dest_code,
        "from_code_l": origin_code.lower(),
        "to_code_l": dest_code.lower(),
        "date": depart_date,
    }
    deep = _DEEP_LINK_TPL[platform].format(**kw)
    h5 = _H5_LINK_TPL[platform].format(**kw)
    return deep, h5


def get_mock_flights(
    origin: str,
    destination: str,
    depart_date: str | None = None,
) -> list[dict[str, Any]]:
    """返回匹配 origin/destination 的 mock 航班列表。

    origin/destination 可以是城市名（北京）或 IATA 代码（BJS）。
    depart_date 默认取今天 + 7 天。
    """
    # 标准化为城市名
    origin_city = CODE_CITY.get(origin, origin)
    dest_city = CODE_CITY.get(destination, destination)

    if not depart_date:
        depart_date = (datetime.now(tz=timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")

    origin_code = CITY_CODE.get(origin_city, origin)
    dest_code = CITY_CODE.get(dest_city, destination)

    route = next(
        (r for r in _ROUTES if r["origin"] == origin_city and r["dest"] == dest_city),
        None,
    )
    if route is None:
        # 没有预置数据，生成通用 Mock
        return _generate_generic(origin_city, origin_code, dest_city, dest_code, depart_date)

    results: list[dict[str, Any]] = []
    for flight in route["flights"]:
        base = flight["base"]
        seed = int(hashlib.md5(f"{flight['flight_no']}{depart_date}".encode()).hexdigest()[:8], 16)
        # 基于 seed 小幅波动价格，模拟真实情况
        rng = random.Random(seed)
        lowest = max(int(base * rng.uniform(0.9, 1.1)), 150)

        platform_prices = [
            {"name": p, "price": _price_spread(lowest, i), **({"lowest": True} if i == 0 else {})}
            for i, p in enumerate(_PLATFORMS)
        ]
        best_platform = _PLATFORMS[0]
        avg_90d, low_90d = _history(lowest, seed)
        booking_url, h5_url = _build_links(origin_code, dest_code, depart_date, best_platform)

        results.append({
            "id": _make_id(flight["flight_no"], depart_date),
            "system_id": f"{flight['flight_no']}-{depart_date}",
            "flight_no": flight["flight_no"],
            "airline": flight["airline"],
            "platform": best_platform,
            "origin_city": origin_city,
            "origin_code": origin_code,
            "destination_city": dest_city,
            "destination_code": dest_code,
            "depart_date": depart_date,
            "depart_time": flight["dep"],
            "arrive_time": flight["arr"],
            "duration": flight["duration"],
            "stops": flight["stops"],
            "price": lowest,
            "tax": 60,
            "baggage_fee": 0,
            "has_baggage": True,
            "prices": platform_prices,
            "lowest_price": lowest,
            "history_avg_90d": avg_90d,
            "history_low_90d": low_90d,
            "recommend_score": "",
            "original_price": None,
            "discount_rate": None,
            "cabin": "economy",
            "signals": [],
            "confidence": "medium",
            "verdict": "",
            "booking_url": booking_url,
            "h5_fallback_url": h5_url,
        })

    return results


def _generate_generic(
    origin_city: str,
    origin_code: str,
    dest_city: str,
    dest_code: str,
    depart_date: str,
) -> list[dict[str, Any]]:
    seed = int(hashlib.md5(f"{origin_code}{dest_code}{depart_date}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)
    base = int(rng.uniform(300, 800))
    airlines = ["中国国航", "南方航空", "海南航空", "东方航空"]
    results = []
    for i in range(2):
        lowest = max(base + i * 40, 200)
        dep_h = 8 + i * 5
        arr_h = dep_h + 3
        s = seed + i
        avg_90d, low_90d = _history(lowest, s)
        booking_url, h5_url = _build_links(origin_code, dest_code, depart_date, _PLATFORMS[0])
        results.append({
            "id": f"gen-{seed}-{i}",
            "system_id": f"GEN{i:03d}-{depart_date}",
            "flight_no": f"GEN{seed % 9000 + 1000}",
            "airline": airlines[i % len(airlines)],
            "platform": _PLATFORMS[0],
            "origin_city": origin_city,
            "origin_code": origin_code,
            "destination_city": dest_city,
            "destination_code": dest_code,
            "depart_date": depart_date,
            "depart_time": f"{dep_h:02d}:10",
            "arrive_time": f"{arr_h:02d}:40",
            "duration": "3h30m",
            "stops": 0,
            "price": lowest,
            "tax": 60,
            "baggage_fee": 0,
            "has_baggage": True,
            "prices": [
                {"name": p, "price": _price_spread(lowest, j), **({"lowest": True} if j == 0 else {})}
                for j, p in enumerate(_PLATFORMS)
            ],
            "lowest_price": lowest,
            "history_avg_90d": avg_90d,
            "history_low_90d": low_90d,
            "recommend_score": "",
            "original_price": None,
            "discount_rate": None,
            "cabin": "economy",
            "signals": [],
            "confidence": "medium",
            "verdict": "",
            "booking_url": booking_url,
            "h5_fallback_url": h5_url,
        })
    return results
