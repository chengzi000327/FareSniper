from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx

from backend.application.contracts.collector import CollectorErrorCode
from backend.application.contracts.flight_provider import FlightOffer
from backend.schemas.collector import ClaimResponse, CollectorJobResponse


_TOKEN68_PATTERN = re.compile(r"[A-Za-z0-9\-._~+/]+=*\Z")


class CollectorApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        node_id: str,
        version: str = "faresniper-collector/1",
        timeout_seconds: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        normalized_url = base_url.rstrip("/")
        parsed = urlsplit(normalized_url)
        is_local_http = parsed.scheme == "http" and parsed.hostname in {
            "127.0.0.1",
            "localhost",
        }
        if (
            not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or (parsed.scheme != "https" and not is_local_http)
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("collector API URL must be HTTPS")
        if _TOKEN68_PATTERN.fullmatch(token) is None:
            raise ValueError("collector token must be a valid token68 value")
        if not node_id or len(node_id) > 128:
            raise ValueError("collector node id is invalid")

        self.node_id = node_id
        self.version = version
        self._client = httpx.AsyncClient(
            base_url=normalized_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout_seconds,
            transport=transport,
        )

    async def heartbeat(self, status: str = "idle") -> None:
        response = await self._client.post(
            "/internal/collector/heartbeat",
            json={
                "node_id": self.node_id,
                "version": self.version,
                "status": status,
            },
        )
        response.raise_for_status()

    async def claim(self) -> CollectorJobResponse | None:
        response = await self._client.post(
            "/internal/collector/claim",
            json={"node_id": self.node_id},
        )
        response.raise_for_status()
        return ClaimResponse.model_validate(response.json()).job

    async def complete(
        self,
        job_id: str,
        offers: list[FlightOffer],
    ) -> None:
        response = await self._client.post(
            f"/internal/collector/jobs/{job_id}/complete",
            json={
                "node_id": self.node_id,
                "offers": [self._wire_offer(offer) for offer in offers],
            },
        )
        response.raise_for_status()

    async def fail(
        self,
        job_id: str,
        error_code: CollectorErrorCode,
        retry_at: datetime,
    ) -> None:
        if retry_at.utcoffset() is None:
            raise ValueError("retry_at must be timezone-aware")
        retry_at_utc = retry_at.astimezone(timezone.utc)
        retry_at_wire = retry_at_utc.isoformat().replace("+00:00", "Z")
        response = await self._client.post(
            f"/internal/collector/jobs/{job_id}/fail",
            json={
                "node_id": self.node_id,
                "error_code": error_code.value,
                "retry_at": retry_at_wire,
            },
        )
        response.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _wire_offer(offer: FlightOffer) -> dict[str, object]:
        if offer.total_price is None or offer.total_price <= 0:
            raise ValueError("collector offers require a positive total price")
        return {
            "data_provider": "ctrip_snapshot",
            "seller_name": "携程",
            "flight_no": offer.flight_no,
            "airline": offer.airline,
            "origin_city": offer.origin_city,
            "origin_code": offer.origin_code,
            "origin_airport_code": offer.origin_airport_code,
            "destination_city": offer.destination_city,
            "destination_code": offer.destination_code,
            "destination_airport_code": offer.destination_airport_code,
            "depart_date": offer.depart_date,
            "depart_time": offer.depart_time,
            "arrive_time": offer.arrive_time,
            "duration_minutes": offer.duration_minutes,
            "stops": offer.stops,
            "cabin": offer.cabin,
            "currency": "CNY",
            "display_price": offer.total_price,
            "booking_url": offer.booking_url,
        }
