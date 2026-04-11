from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List

from backend.data_sources.base import DataSource


class CtripSource(DataSource):
    name = "ctrip"

    def __init__(self, enable_mock_fallback: bool = True) -> None:
        self.enable_mock_fallback = enable_mock_fallback

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, object]]:
        third_party_results = await self._try_third_party_search(
            origin=origin,
            destination=destination,
            date_start=date_start,
            date_end=date_end,
        )
        if third_party_results:
            return third_party_results
        if not self.enable_mock_fallback:
            return []
        return self._build_mock_results(origin, destination, date_start)

    async def get_history_prices(self, route: str, days: int) -> List[Dict[str, object]]:
        today = datetime.utcnow().date()
        seed = self._seed_from_text(route)
        baseline = 420 + (seed % 180)
        results: List[Dict[str, object]] = []

        for offset in range(days):
            date_value = today - timedelta(days=offset)
            price = baseline + ((offset * 17 + seed) % 120) - 40
            results.append(
                {
                    "date": date_value.isoformat(),
                    "price": max(price, 200),
                }
            )
        return results

    async def _try_third_party_search(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, object]]:
        try:
            from backend.third_party.flights_monitor import discover_api  # type: ignore
        except Exception:
            return []

        def _run() -> List[Dict[str, object]]:
            raw_results = discover_api.search(  # pragma: no cover - optional integration
                dep_city_code=origin,
                arr_city_code=destination,
                date_range=(date_start, date_end),
            )
            return [self._normalize(item, origin, destination) for item in raw_results]

        try:
            return await asyncio.to_thread(_run)
        except Exception:
            return []

    def _build_mock_results(self, origin: str, destination: str, date_start: str) -> List[Dict[str, object]]:
        seed = self._seed_from_text("-".join([origin, destination, date_start]))
        base_price = 360 + (seed % 220)
        airlines = ["中国国航", "南方航空", "海南航空", "东方航空"]
        results: List[Dict[str, object]] = []

        for idx in range(4):
            depart_hour = 7 + idx * 3
            arrive_hour = depart_hour + 3
            price = base_price + idx * 35 - 20
            results.append(
                {
                    "id": f"{self.name}-{seed}-{idx}",
                    "platform": self.name,
                    "origin": origin,
                    "destination": destination,
                    "depart_date": date_start,
                    "airline": airlines[idx % len(airlines)],
                    "depart_time": f"{depart_hour:02d}:10",
                    "arrive_time": f"{arrive_hour:02d}:40",
                    "price": max(price, 220),
                    "cabin": "经济舱",
                    "signals": [],
                    "metadata": {"source": "mock_fallback"},
                }
            )
        return results

    def _normalize(
        self,
        item: Dict[str, object],
        origin: str,
        destination: str,
    ) -> Dict[str, object]:
        return {
            "id": str(item.get("id") or item.get("flight_no") or item.get("flightNo") or "unknown"),
            "platform": self.name,
            "origin": str(item.get("origin") or origin),
            "destination": str(item.get("destination") or destination),
            "depart_date": str(item.get("depart_date") or item.get("date") or ""),
            "airline": str(item.get("airline") or item.get("carrier") or "未知航司"),
            "depart_time": str(item.get("depart_time") or item.get("dep_time") or "00:00"),
            "arrive_time": str(item.get("arrive_time") or item.get("arr_time") or "00:00"),
            "price": int(item.get("price") or 0),
            "cabin": str(item.get("cabin") or "经济舱"),
            "signals": [],
            "metadata": {"source": "third_party"},
        }

    @staticmethod
    def _seed_from_text(value: str) -> int:
        return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)
