from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_FM_PATH = str(
    Path(__file__).resolve().parents[1] / "third_party" / "flights_monitor"
)
if _FM_PATH not in sys.path:
    sys.path.insert(0, _FM_PATH)


class CtripWorkerError(RuntimeError):
    pass


def collect_raw_flights(
    origin: str,
    destination: str,
    date_start: str,
    date_end: str,
    *,
    headless: bool,
) -> list[dict[str, Any]]:
    try:
        from ctrip_api import CtripFlightClient  # type: ignore
        from shared import resolve_city  # type: ignore
    except Exception:
        raise CtripWorkerError() from None

    origin_name = resolve_city(origin) or origin
    destination_name = resolve_city(destination) or destination
    try:
        start = datetime.strptime(date_start, "%Y-%m-%d").date()
        end = datetime.strptime(date_end, "%Y-%m-%d").date()
    except ValueError:
        start = end = datetime.now(timezone.utc).date()

    results: list[dict[str, Any]] = []
    try:
        with CtripFlightClient(headless=headless) as client:
            current = start
            while current <= end:
                flights, got_response = client.search_oneway(
                    dcity=origin,
                    acity=destination,
                    dcity_name=origin_name,
                    acity_name=destination_name,
                    date_str=current.isoformat(),
                )
                if not got_response:
                    raise CtripWorkerError()
                results.extend(flight for flight in flights if isinstance(flight, dict))
                current += timedelta(days=1)
    except CtripWorkerError:
        raise
    except Exception:
        raise CtripWorkerError() from None
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
        flights = collect_raw_flights(
            args.origin,
            args.destination,
            args.date_start,
            args.date_end,
            headless=args.headless,
        )
    except CtripWorkerError:
        print(json.dumps({"ok": False}, separators=(",", ":")))
        return 1
    print(
        json.dumps(
            {"ok": True, "flights": flights},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
