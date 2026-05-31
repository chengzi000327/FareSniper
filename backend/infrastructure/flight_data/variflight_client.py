"""Variflight MCP client — wraps the @variflight-ai/variflight-mcp stdio server.

Uses the Python `mcp` SDK to launch npx as a subprocess and call tools.
Each call creates a fresh session (stateless, safe for async web workers).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from backend.config import settings

logger = logging.getLogger("faresniper.variflight")

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


async def search_flights(
    origin: str,
    destination: str,
    depart_date: str,
) -> list[dict]:
    """Query flight prices via Variflight MCP.

    Args:
        origin: IATA airport or city code (e.g. "PEK", "BJS").
        destination: IATA airport or city code (e.g. "SYX").
        depart_date: Date string "YYYY-MM-DD".

    Returns:
        List of normalized flight dicts sorted by price ascending.
        Returns [] on any error (caller should fall back to mock).
    """
    api_key = settings.variflight_api_key
    if not api_key:
        logger.warning("variflight_api_key not configured, skipping")
        return []

    dep_city = _to_city_code(origin)
    arr_city = _to_city_code(destination)

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        logger.error("mcp package not installed; run: pip install mcp")
        return []

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@variflight-ai/variflight-mcp"],
        env={**os.environ, "VARIFLIGHT_API_KEY": api_key},
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "getFlightPriceByCities",
                    {"dep_city": dep_city, "arr_city": arr_city, "dep_date": depart_date},
                )
                if not result.content:
                    return []
                import json

                text = result.content[0].text if hasattr(result.content[0], "text") else ""
                payload = json.loads(text)
                if payload.get("code") != 200:
                    logger.warning("variflight_api_error payload=%s", payload)
                    return []
                data = payload.get("data") or []
                if not isinstance(data, list):
                    return []
                flights = _parse_price_rows(data)
                logger.info(
                    "variflight_search origin=%s destination=%s date=%s flights=%d",
                    origin,
                    destination,
                    depart_date,
                    len(flights),
                )
                return flights
    except Exception:
        logger.exception(
            "variflight_search_failed origin=%s destination=%s date=%s",
            origin,
            destination,
            depart_date,
        )
        return []
