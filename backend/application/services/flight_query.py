from datetime import date, datetime
from zoneinfo import ZoneInfo

from backend.application.contracts.flight_provider import FlightQuery
from backend.utils.airport_codes import resolve_airport


class FlightQueryValidationError(ValueError):
    pass


def build_flight_query(
    origin: str,
    destination: str,
    depart_date: str,
    *,
    today: date | None = None,
) -> FlightQuery:
    origin_ref = resolve_airport(origin)
    destination_ref = resolve_airport(destination)
    if origin_ref is None:
        raise FlightQueryValidationError(f"无法识别出发城市：{origin}")
    if destination_ref is None:
        raise FlightQueryValidationError(f"无法识别到达城市：{destination}")

    try:
        parsed = date.fromisoformat(depart_date)
    except ValueError as exc:
        raise FlightQueryValidationError("出发日期必须使用 YYYY-MM-DD") from exc

    current = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if parsed <= current:
        raise FlightQueryValidationError("出发日期必须是未来日期")

    return FlightQuery(
        origin_city=origin_ref.city,
        origin_code=origin_ref.code,
        origin_airport_ids=list(origin_ref.airport_ids),
        destination_city=destination_ref.city,
        destination_code=destination_ref.code,
        destination_airport_ids=list(destination_ref.airport_ids),
        depart_date=parsed.isoformat(),
        is_mainland_domestic=(
            origin_ref.mainland_china and destination_ref.mainland_china
        ),
    )
