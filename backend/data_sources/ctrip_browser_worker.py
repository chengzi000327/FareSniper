from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from typing import Any

from backend.application.contracts.collector import CollectorErrorCode


class CtripWorkerError(RuntimeError):
    def __init__(self, code: CollectorErrorCode) -> None:
        self.code = code
        super().__init__("Ctrip browser worker failed")


def collect_batch_search_payloads(
    origin: str,
    destination: str,
    date_start: str,
    date_end: str,
    *,
    headless: bool,
) -> list[dict[str, Any]]:
    try:
        from ctrip_api import CtripBrowserError, CtripFlightClient  # type: ignore
        from shared import resolve_city  # type: ignore
    except (ImportError, ModuleNotFoundError):
        raise CtripWorkerError(CollectorErrorCode.dependency_error) from None

    origin_name = resolve_city(origin) or origin
    destination_name = resolve_city(destination) or destination
    try:
        start = datetime.strptime(date_start, "%Y-%m-%d").date()
        end = datetime.strptime(date_end, "%Y-%m-%d").date()
    except ValueError:
        raise CtripWorkerError(CollectorErrorCode.parse_error) from None

    results: list[dict[str, Any]] = []
    try:
        with CtripFlightClient(headless=headless) as client:
            current = start
            while current <= end:
                payloads = client.search_batch_search(
                    dcity=origin,
                    acity=destination,
                    dcity_name=origin_name,
                    acity_name=destination_name,
                    date_str=current.isoformat(),
                )
                results.extend(
                    {"depart_date": current.isoformat(), "payload": payload}
                    for payload in payloads
                )
                current += timedelta(days=1)
    except CtripBrowserError as exc:
        raise CtripWorkerError(CollectorErrorCode(exc.code)) from None
    except Exception:
        raise CtripWorkerError(CollectorErrorCode.dependency_error) from None
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--date-start", required=True)
    parser.add_argument("--date-end", required=True)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    try:
        payloads = collect_batch_search_payloads(
            args.origin,
            args.destination,
            args.date_start,
            args.date_end,
            headless=args.headless,
        )
    except CtripWorkerError as exc:
        print(
            json.dumps(
                {"ok": False, "error_code": exc.code.value}, separators=(",", ":")
            )
        )
        return 1
    print(json.dumps({"ok": True, "payloads": payloads}, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
