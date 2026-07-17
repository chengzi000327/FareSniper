from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.application.contracts.flight_provider import is_complete_https_url
from backend.data_sources.base import DataSource
from backend.resilience.retry import retry_with_backoff

_FM_PATH = str(
    Path(__file__).resolve().parents[1] / "third_party" / "flights_monitor"
)
if _FM_PATH not in sys.path:
    sys.path.insert(0, _FM_PATH)

_COUNTER = 0  # system_id 自增计数器

_WORKER_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "DISPLAY",
    "XDG_RUNTIME_DIR",
)


class CtripCollectionError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Ctrip browser collection failed")


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

    def __init__(
        self,
        enable_mock_fallback: bool = False,
        headless: bool = True,
        collection_timeout_seconds: float = 90.0,
    ) -> None:
        self.enable_mock_fallback = enable_mock_fallback
        self.headless = headless
        self.collection_timeout_seconds = collection_timeout_seconds

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> List[Dict[str, Any]]:
        try:
            return await self._try_third_party_search(
                origin, destination, date_start, date_end
            )
        except CtripCollectionError:
            if self.enable_mock_fallback:
                return self._build_mock_results(origin, destination, date_start)
            raise

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
            async with asyncio.timeout(self.collection_timeout_seconds):
                raw_flights = await retry_with_backoff(
                    self._run_worker_once,
                    origin,
                    destination,
                    date_start,
                    date_end,
                    max_retries=2,
                    base_delay=1.0,
                    max_delay=10.0,
                )
        except Exception:
            raise CtripCollectionError() from None
        return [
            self._normalize(flight, origin, destination)
            for flight in raw_flights
        ]

    async def _run_worker_once(
        self, origin: str, destination: str, date_start: str, date_end: str
    ) -> list[dict[str, Any]]:
        args = [
            sys.executable,
            "-m",
            "backend.data_sources.ctrip_browser_worker",
            "--origin",
            origin,
            "--destination",
            destination,
            "--date-start",
            date_start,
            "--date-end",
            date_end,
        ]
        if self.headless:
            args.append("--headless")
        env = {
            key: os.environ[key]
            for key in _WORKER_ENV_ALLOWLIST
            if key in os.environ
        }
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
                start_new_session=os.name == "posix",
            )
        except OSError:
            raise CtripCollectionError() from None

        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=self.collection_timeout_seconds,
            )
        except asyncio.CancelledError:
            await self._terminate_worker_group(process)
            raise
        except Exception:
            await self._terminate_worker_group(process)
            raise CtripCollectionError() from None

        if process.returncode != 0:
            await self._terminate_worker_group(process)
            raise CtripCollectionError()
        try:
            payload = json.loads(stdout.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            flights = payload.get("flights")
            if payload.get("ok") is not True or not isinstance(flights, list):
                raise ValueError
            if not all(isinstance(flight, dict) for flight in flights):
                raise ValueError
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            await self._terminate_worker_group(process)
            raise CtripCollectionError() from None
        return flights

    @staticmethod
    async def _terminate_worker_group(
        process: asyncio.subprocess.Process,
    ) -> None:
        pid = getattr(process, "pid", None)
        killed_group = False
        if os.name == "posix" and isinstance(pid, int):
            try:
                os.killpg(pid, signal.SIGKILL)
                killed_group = True
            except ProcessLookupError:
                killed_group = True
        if not killed_group and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        try:
            await process.wait()
        except ProcessLookupError:
            pass

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
        candidate_url = str(item.get("url") or item.get("jump_url") or "")
        booking_url = (
            candidate_url if is_complete_https_url(candidate_url) else ""
        )

        return {
            "id": hashlib.md5(unique_key.encode()).hexdigest()[:12],
            "system_id": _next_system_id(),
            "platform": "携程",
            "origin_city": str(item.get("dep_city") or origin),
            "origin_code": origin,
            "destination_city": str(item.get("arr_city") or destination),
            "destination_code": destination,
            "depart_date": depart_date,
            "airline": str(item.get("airline") or "未知航司"),
            "flight_no": flight_no,
            "dep_time": dep_time,
            "arr_time": arr_time,
            "duration": str(item.get("duration") or ""),
            "stops": int(item.get("transfer_count") or 0),
            "depart_time": dep_time,
            "arrive_time": arr_time,
            "price": price,
            "currency": "CNY",
            "tax": None,
            "baggage_fee": None,
            "has_baggage": None,
            "recommend_score": None,
            "prices": [
                {
                    "platform": "携程",
                    "price": price,
                    "currency": "CNY",
                    "url": booking_url,
                },
            ],
            "original_price": original_price,
            "discount_rate": discount_rate if discount_rate > 0 else None,
            "cabin": "economy",
            "signals": [item["discount_display"]] if item.get("discount_display") else [],
            "confidence": confidence,
            "verdict": verdict,
            "booking_url": booking_url or None,
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
                "currency": "CNY",
                "tax": 120,
                "baggage_fee": baggage_fee,
                "has_baggage": has_baggage,
                "recommend_score": None,
                "prices": [
                    {"platform": "携程旅行", "price": price, "currency": "CNY", "lowest": True},
                    {"platform": "去哪儿网", "price": price + 30, "currency": "CNY"},
                    {"platform": "飞猪旅行", "price": price + 45, "currency": "CNY"},
                    {"platform": "同程旅行", "price": price + 60, "currency": "CNY"},
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
