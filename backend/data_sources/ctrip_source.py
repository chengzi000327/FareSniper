from __future__ import annotations

import asyncio
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.data_sources.base import DataSource
from backend.resilience.retry import retry_with_backoff

# 把 third_party/flights_monitor 加入 sys.path（其内部用相对 import）
_FM_PATH = str(Path(__file__).resolve().parents[1] / "third_party" / "flights_monitor")
if _FM_PATH not in sys.path:
    sys.path.insert(0, _FM_PATH)

_COUNTER = 0  # system_id 自增计数器


def _next_system_id() -> str:
    global _COUNTER
    _COUNTER += 1
    return f"SYS.{_COUNTER:03d}"


def _fmt_time(dt_str: str) -> str:
    """把 '2026-05-01 08:05:00' 或 '2026-05-01T08:05:00' 转为 'HH:mm'。"""
    if not dt_str:
        return "00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt_str, fmt).strftime("%H:%M")
        except ValueError:
            continue
    parts = dt_str.replace("T", " ").split(" ")
    return parts[1][:5] if len(parts) > 1 else "00:00"


class CtripSource(DataSource):
    name = "ctrip"

    def __init__(self, enable_mock_fallback: bool = True, headless: bool = True) -> None:
        self.enable_mock_fallback = enable_mock_fallback
        self.headless = headless

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, Any]]:
        results = await self._try_third_party_search(origin, destination, date_start, date_end)
        if results:
            return results
        if not self.enable_mock_fallback:
            return []
        return self._build_mock_results(origin, destination, date_start)

    async def get_history_prices(self, route: str, days: int) -> List[Dict[str, Any]]:
        today = datetime.now(timezone.utc).date()
        seed = self._seed_from_text(route)
        baseline = 420 + (seed % 180)
        return [
            {
                "date": (today - timedelta(days=i)).isoformat(),
                "price": max(baseline + ((i * 17 + seed) % 120) - 40, 200),
            }
            for i in range(days)
        ]

    async def _try_third_party_search(
        self, origin: str, destination: str, date_start: str, date_end: str
    ) -> List[Dict[str, Any]]:
        try:
            from ctrip_api import CtripFlightClient  # type: ignore
            from shared import resolve_city  # type: ignore
        except Exception:
            return []

        def _run() -> List[Dict[str, Any]]:
            origin_name = resolve_city(origin) or origin
            dest_name = resolve_city(destination) or destination

            results: List[Dict[str, Any]] = []
            with CtripFlightClient(headless=self.headless) as client:
                try:
                    start = datetime.strptime(date_start, "%Y-%m-%d").date()
                    end = datetime.strptime(date_end, "%Y-%m-%d").date()
                except ValueError:
                    start = end = datetime.now(timezone.utc).date()

                current = start
                while current <= end:
                    flights, _ = client.search_oneway(
                        dcity=origin,
                        acity=destination,
                        dcity_name=origin_name,
                        acity_name=dest_name,
                        date_str=current.isoformat(),
                    )
                    for f in flights:
                        results.append(self._normalize(f, origin, destination))
                    current += timedelta(days=1)

            return results

        try:
            return await retry_with_backoff(
                asyncio.to_thread,
                _run,
                max_retries=2,
                base_delay=1.0,
                max_delay=10.0,
            )
        except Exception:
            return []

    def _normalize(
        self,
        item: Dict[str, Any],
        origin: str,
        destination: str,
    ) -> Dict[str, Any]:
        price = int(item.get("price") or 0)
        discount_rate = float(item.get("discount_rate") or 0.0)
        depart_date = str(item.get("date") or "")

        # 折扣率越低越便宜，confidence 越高
        if 0 < discount_rate < 0.7:
            confidence = "high"
        else:
            confidence = "medium"

        # 原价估算
        original_price: Optional[int] = None
        if 0 < discount_rate < 1.0:
            original_price = int(price / discount_rate)

        verdict = (
            f"特价！{item.get('discount_display', '')}，建议立即购买"
            if confidence == "high"
            else "价格正常，可继续观察"
        )

        dep_time = _fmt_time(str(item.get("dep_time") or ""))
        arr_time = _fmt_time(str(item.get("arr_time") or ""))
        flight_no = str(item.get("flight_number") or item.get("flight_no") or "")
        unique_key = f"{flight_no}-{depart_date}-{price}"

        return {
            "id": hashlib.md5(unique_key.encode()).hexdigest()[:12],
            "system_id": _next_system_id(),
            "platform": self.name,
            "origin_city": str(item.get("dep_city") or origin),
            "origin_code": origin,
            "destination_city": str(item.get("arr_city") or destination),
            "destination_code": destination,
            "depart_date": depart_date,
            "airline": str(item.get("airline") or "未知航司"),
            "depart_time": dep_time,
            "arrive_time": arr_time,
            "price": price,
            "tax": 120,
            "baggage_fee": 0,
            "has_baggage": True,
            "recommend_score": "9.0" if confidence == "high" else "8.0",
            "prices": [
                {"name": "携程旅行", "price": price, "lowest": True},
                {"name": "去哪儿网", "price": price + 30},
                {"name": "飞猪旅行", "price": price + 45},
            ],
            "original_price": original_price,
            "discount_rate": discount_rate if discount_rate > 0 else None,
            "cabin": "economy",
            "signals": [item["discount_display"]] if item.get("discount_display") else [],
            "confidence": confidence,
            "verdict": verdict,
            "booking_url": None,
        }

    def _build_mock_results(
        self, origin: str, destination: str, date_start: str
    ) -> List[Dict[str, Any]]:
        seed = self._seed_from_text(f"{origin}-{destination}-{date_start}")
        base_price = 360 + (seed % 220)
        airlines = ["中国国航", "南方航空", "海南航空", "东方航空"]
        city_map = {
            "PEK": "北京", "SHA": "上海", "CAN": "广州", "CTU": "成都",
            "NRT": "东京", "ICN": "首尔", "HKG": "香港", "SIN": "新加坡",
            "BKK": "曼谷", "KUL": "吉隆坡", "SYX": "三亚",
        }
        origin_city = city_map.get(origin, origin)
        dest_city = city_map.get(destination, destination)

        results = []
        for idx in range(4):
            dep_h = 7 + idx * 3
            arr_h = dep_h + 3
            price = max(base_price + idx * 35 - 20, 220)
            discount = round(0.65 + idx * 0.05, 2)
            original = int(price / discount)
            confidence = "high" if discount < 0.75 else "medium"
            has_baggage = idx % 2 == 0
            baggage_fee = 0 if has_baggage else 50
            recommend_score = f"{9.8 - idx * 0.2:.1f}"
            results.append({
                "id": f"mock-{seed}-{idx}",
                "system_id": _next_system_id(),
                "platform": self.name,
                "origin_city": origin_city,
                "origin_code": origin,
                "destination_city": dest_city,
                "destination_code": destination,
                "depart_date": date_start,
                "airline": airlines[idx % len(airlines)],
                "depart_time": f"{dep_h:02d}:10",
                "arrive_time": f"{arr_h:02d}:40",
                "price": price,
                "tax": 120,
                "baggage_fee": baggage_fee,
                "has_baggage": has_baggage,
                "recommend_score": recommend_score,
                "prices": [
                    {"name": "携程旅行", "price": price, "lowest": True},
                    {"name": "去哪儿网", "price": price + 30},
                    {"name": "飞猪旅行", "price": price + 45},
                    {"name": "同程旅行", "price": price + 60},
                ],
                "original_price": original,
                "discount_rate": discount,
                "cabin": "economy",
                "signals": [f"{discount * 10:.0f}折特价"] if confidence == "high" else [],
                "confidence": confidence,
                "verdict": "特价！建议立即购买" if confidence == "high" else "价格正常，可继续观察",
                "booking_url": None,
            })
        return results

    @staticmethod
    def _seed_from_text(value: str) -> int:
        return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)
