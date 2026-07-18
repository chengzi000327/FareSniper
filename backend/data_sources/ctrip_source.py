from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import signal
import sys
from typing import Any

from backend.application.contracts.collector import (
    CollectorErrorCode,
    CollectorSearchResult,
)
from backend.application.contracts.flight_provider import FlightOffer
from backend.application.services.flight_query import (
    FlightQueryValidationError,
    build_flight_query,
)
from backend.data_sources.base import DataSource
from backend.infrastructure.flight_data.ctrip_parser import (
    CtripBatchSearchParseError,
    parse_batch_search,
)


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
    def __init__(self, code: CollectorErrorCode = CollectorErrorCode.parse_error) -> None:
        self.code = code
        super().__init__("Ctrip browser collection failed")


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

    async def search_with_status(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> CollectorSearchResult:
        if importlib.util.find_spec("selenium") is None:
            return CollectorSearchResult(
                error_code=CollectorErrorCode.dependency_error
            )
        try:
            raw_payloads = await self._run_worker_once(
                origin, destination, date_start, date_end
            )
            offers = self._parse_worker_payloads(raw_payloads, origin, destination)
        except CtripCollectionError as exc:
            return CollectorSearchResult(error_code=exc.code)
        except asyncio.TimeoutError:
            return CollectorSearchResult(error_code=CollectorErrorCode.timeout)

        if not offers:
            return CollectorSearchResult(error_code=CollectorErrorCode.empty)
        return CollectorSearchResult(offers=offers)

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> list[FlightOffer]:
        result = await self.search_with_status(
            origin, destination, date_start, date_end
        )
        return result.offers

    async def get_history_prices(self, route: str, days: int) -> list[dict[str, object]]:
        return []

    def _parse_worker_payloads(
        self,
        raw_payloads: list[dict[str, Any]],
        origin: str,
        destination: str,
    ) -> list[FlightOffer]:
        offers: list[FlightOffer] = []
        try:
            for raw_payload in raw_payloads:
                payload = raw_payload.get("payload")
                depart_date = raw_payload.get("depart_date")
                if not isinstance(payload, dict) or not isinstance(depart_date, str):
                    raise CtripBatchSearchParseError("worker payload is invalid")
                query = build_flight_query(origin, destination, depart_date)
                offers.extend(parse_batch_search(payload, query))
        except (CtripBatchSearchParseError, FlightQueryValidationError):
            raise CtripCollectionError(CollectorErrorCode.parse_error) from None
        return offers

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
            raise CtripCollectionError(CollectorErrorCode.dependency_error) from None

        try:
            try:
                stdout, _ = await asyncio.wait_for(
                    process.communicate(), timeout=self.collection_timeout_seconds
                )
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                raise CtripCollectionError(CollectorErrorCode.timeout) from None
            except Exception:
                raise CtripCollectionError(CollectorErrorCode.dependency_error) from None

            payload = self._decode_worker_result(stdout)
            if process.returncode != 0 or payload.get("ok") is not True:
                raise CtripCollectionError(self._worker_error_code(payload))
            raw_payloads = payload.get("payloads")
            if not isinstance(raw_payloads, list) or not all(
                isinstance(item, dict) for item in raw_payloads
            ):
                raise CtripCollectionError(CollectorErrorCode.parse_error)
            return raw_payloads
        finally:
            await self._terminate_worker_group(process)

    @staticmethod
    def _decode_worker_result(stdout: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise CtripCollectionError(CollectorErrorCode.parse_error) from None
        if not isinstance(payload, dict):
            raise CtripCollectionError(CollectorErrorCode.parse_error)
        return payload

    @staticmethod
    def _worker_error_code(payload: dict[str, Any]) -> CollectorErrorCode:
        try:
            return CollectorErrorCode(payload.get("error_code"))
        except (TypeError, ValueError):
            return CollectorErrorCode.parse_error

    @staticmethod
    async def _terminate_worker_group(process: asyncio.subprocess.Process) -> None:
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
