import httpx
from backend.config import settings


async def fetch_status(flight_no: str, date: str) -> dict:
    async with httpx.AsyncClient(timeout=5) as c:
        r = await c.get(
            settings.flight_status_api_url,
            params={"flightNo": flight_no, "date": date},
            headers={"X-API-Key": settings.flight_status_api_key},
        )
        r.raise_for_status()
        data = r.json()
    return {
        "flight_no": flight_no,
        "date": date,
        "status": data.get("status", "on_time"),
        "delay_minutes": data.get("delay", 0),
    }
