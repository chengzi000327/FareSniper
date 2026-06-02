"""Variflight 航班数据源 — 直连飞常准 REST 网关（httpx）。

历史上走 @variflight-ai/variflight-mcp 的 stdio 子进程（npx），现已改为
直接 POST https://mcp.variflight.com/api/v1/mcp/data，免子进程、更稳更快。
每次调用无状态，适合 async web worker 并发。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from backend.config import settings

logger = logging.getLogger("faresniper.variflight")

# 飞常准 REST 网关地址（已实测 HTTP 200 + 真实票价）。
_VARIFLIGHT_GATEWAY_URL = "https://mcp.variflight.com/api/v1/mcp/data"
_REQUEST_TIMEOUT = 20.0

# City code aliases: our internal IATA airport codes → variflight city codes.
# Variflight uses 3-letter *city* codes (BJS for all Beijing airports, etc.).
_AIRPORT_TO_CITY: dict[str, str] = {
    "PEK": "BJS",
    "PKX": "BJS",
    "SHA": "SHA",
    "PVG": "SHA",
    "CAN": "CAN",
    "SZX": "SZX",
    "CTU": "CTU",
    "CKG": "CKG",
    "XIY": "SIA",
    "HGH": "HGH",
    "NKG": "NKG",
    "WUH": "WUH",
    "CSX": "CSX",
    "KMG": "KMG",
    "SYX": "SYX",
    "HAK": "HAK",
    "XMN": "XMN",
    "TAO": "TAO",
    "DLC": "DLC",
    "SHE": "SHE",
    "HRB": "HRB",
    "URC": "URC",
    "LHW": "LHW",
}


def _to_city_code(code: str) -> str:
    """Map airport IATA → variflight city code, pass through if unknown."""
    return _AIRPORT_TO_CITY.get(code.upper(), code.upper())


def _mask_key(api_key: str) -> str:
    """日志脱敏：仅保留前 4 后 4，中间用 *,绝不打印全量 key。"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def _parse_price_rows(raw_data: list[dict]) -> list[dict]:
    """Normalize getFlightPriceByCities rows into FareSniper flight dicts."""
    results: list[dict] = []
    for row in raw_data:
        flight_no = row.get("flightno", "")
        dep_ts = row.get("flightdeptimeplandate")
        arr_ts = row.get("flightarrtimeplandate")
        dep_time = (
            datetime.fromtimestamp(dep_ts, tz=timezone.utc).strftime("%H:%M")
            if isinstance(dep_ts, (int, float))
            else ""
        )
        arr_time = (
            datetime.fromtimestamp(arr_ts, tz=timezone.utc).strftime("%H:%M")
            if isinstance(arr_ts, (int, float))
            else ""
        )
        dep_date = row.get("depdate", "")
        cabins: list[dict] = row.get("cabins") or []
        economy_prices = [
            c["price"]
            for c in cabins
            if c.get("cabinclass") == "Y" and isinstance(c.get("price"), (int, float))
        ]
        if not economy_prices:
            continue
        lowest_price = int(min(economy_prices))
        results.append(
            {
                "flight_no": flight_no,
                "airline": row.get("flightcompany", ""),
                "dep_city": row.get("depaptccity", ""),
                "arr_city": row.get("arraptccity", ""),
                "dep_time": dep_time,
                "arr_time": arr_time,
                "duration": "",
                "transfer_count": int(row.get("stopflag", 0)),
                "price": lowest_price,
                "date": dep_date,
                "platform": "variflight",
                "url": "",
                "origin_code": row.get("flightdepcode", ""),
                "destination_code": row.get("flightarrcode", ""),
                "source": "variflight",
            }
        )
    results.sort(key=lambda r: r["price"])
    return results


@dataclass
class VariflightResult:
    """飞常准查询结果：区分「正常无航班」与「数据源报错」。

    - rows: 解析后的航班列表（已按 Y 舱最低价排序）。
    - error: 出错原因（API 非 200 / 网络异常 / 限流 / key 缺失）；
      正常情况下为 None,即便 rows 为空也代表「真的没航班」。
    """

    rows: list[dict] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


async def search_flights_with_status(
    origin: str,
    destination: str,
    depart_date: str,
) -> VariflightResult:
    """查询飞常准航班价格,返回带错误状态的结果。

    与 search_flights 共用同一份请求逻辑,但保留 error 字段,供爬取任务
    区分「正常无航班(empty)」与「数据源报错(error)」,从而决定 job 落库后
    应标记 success 还是 failed/降级。

    Args:
        origin: IATA airport or city code (e.g. "PEK", "BJS").
        destination: IATA airport or city code (e.g. "SYX").
        depart_date: Date string "YYYY-MM-DD".

    Returns:
        VariflightResult(rows=..., error=...)。出错时 rows 为空、error 非 None。
    """
    api_key = settings.variflight_api_key
    if not api_key:
        logger.warning("variflight_api_key not configured, skipping")
        return VariflightResult(error="missing_api_key")

    dep_city = _to_city_code(origin)
    arr_city = _to_city_code(destination)

    payload = {
        "endpoint": "getFlightPriceByCities",
        "params": {
            "dep_city": dep_city,
            "arr_city": arr_city,
            "dep_date": depart_date,
            # 仅取每条航线最低价（与 _parse_price_rows 的 Y 舱最低价语义一致）。
            "price_mode": "lowest",
        },
    }
    headers = {
        "X-VARIFLIGHT-KEY": api_key,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                _VARIFLIGHT_GATEWAY_URL, json=payload, headers=headers
            )
    except Exception as exc:
        # 网络异常 / 超时 / 连接重置等——静默回退,但保留 error 供上游感知。
        logger.warning(
            "variflight_request_failed origin=%s destination=%s date=%s key=%s err=%s",
            origin,
            destination,
            depart_date,
            _mask_key(api_key),
            exc,
        )
        return VariflightResult(error=f"request_failed: {exc}")

    if resp.status_code != 200:
        # 非 200（含 401/429 限流等）——记录状态码,不打印 body 全量以防泄漏。
        logger.warning(
            "variflight_http_error origin=%s destination=%s date=%s key=%s status=%s",
            origin,
            destination,
            depart_date,
            _mask_key(api_key),
            resp.status_code,
        )
        return VariflightResult(error=f"http_{resp.status_code}")

    try:
        body = resp.json()
    except Exception as exc:
        logger.warning("variflight_bad_json key=%s err=%s", _mask_key(api_key), exc)
        return VariflightResult(error=f"bad_json: {exc}")

    if body.get("code") != 200:
        # 业务层非 200（鉴权失败 / 参数错误 / 限流等）。
        logger.warning(
            "variflight_api_error origin=%s destination=%s date=%s key=%s code=%s message=%s",
            origin,
            destination,
            depart_date,
            _mask_key(api_key),
            body.get("code"),
            body.get("message"),
        )
        return VariflightResult(error=f"api_code_{body.get('code')}")

    data = body.get("data") or []
    if not isinstance(data, list):
        logger.warning("variflight_unexpected_data key=%s", _mask_key(api_key))
        return VariflightResult(error="unexpected_data")

    flights = _parse_price_rows(data)
    logger.info(
        "variflight_search origin=%s destination=%s date=%s key=%s flights=%d",
        origin,
        destination,
        depart_date,
        _mask_key(api_key),
        len(flights),
    )
    return VariflightResult(rows=flights)


async def search_flights(
    origin: str,
    destination: str,
    depart_date: str,
) -> list[dict]:
    """Query flight prices via Variflight REST gateway.

    Args:
        origin: IATA airport or city code (e.g. "PEK", "BJS").
        destination: IATA airport or city code (e.g. "SYX").
        depart_date: Date string "YYYY-MM-DD".

    Returns:
        List of normalized flight dicts sorted by price ascending.
        Returns [] on any error (caller should fall back to mock).
    """
    result = await search_flights_with_status(origin, destination, depart_date)
    return result.rows
