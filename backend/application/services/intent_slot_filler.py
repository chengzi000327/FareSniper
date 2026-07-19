"""Deterministic intent recognition and slot filling for flight search."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from backend.application.contracts.intent import (
    DateWindow,
    IntentConfidence,
    LocationRef,
    NormalizedIntent,
    SlotBundle,
)
from backend.application.contracts.intent_registry import IntentDefinition
from backend.application.services.default_intents import DEFAULT_INTENTS
from backend.application.services.intent_registry import (
    find_intent_definition,
    match_intent,
    required_slots_for,
)
from backend.application.services.airport_catalog import AirportCatalog
from backend.utils.airport_codes import (
    AIRPORT_TO_CITY,
    CITY_TO_AIRPORT,
    resolve_airport,
)

REQUIRED_SEARCH_SLOTS = ("origin", "destination", "depart_date")
FLIGHT_KEYWORDS = tuple(
    keyword
    for definition in DEFAULT_INTENTS
    if definition.name == "search_flight"
    for keyword in definition.keywords
)
ORIGIN_MARKERS = ("从", "自", "由")
DESTINATION_MARKERS = ("到", "去", "飞", "回", "至", "->", "→", "-", "/")
_ROUTE_SEPARATOR_PATTERN = r"(?:到|去|飞|回|至|->|→|-|/)"
_ROUTE_SEPARATOR = re.compile(_ROUTE_SEPARATOR_PATTERN)
_TZ = ZoneInfo("Asia/Shanghai")
_CHINESE_NUMERALS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_CATALOG = AirportCatalog.load_default()


@dataclass(frozen=True)
class _LocationMention:
    start: int
    end: int
    value: str
    city_id: str
    is_airport: bool


@dataclass(frozen=True)
class _LocationTerm:
    text: str
    value: str
    city_id: str
    is_airport: bool
    is_ascii_code: bool


@dataclass(frozen=True)
class LocationAmbiguity:
    """A province-level location that must be narrowed to an airport city."""

    region: str
    cities: tuple[str, ...]


def _build_location_terms() -> tuple[_LocationTerm, ...]:
    terms: set[str] = set()
    for city in _CATALOG.cities:
        terms.update((city.name, *city.aliases, *city.provider_codes.values()))
        for airport in city.airports:
            terms.update(
                value
                for value in (
                    airport.name,
                    *airport.aliases,
                    airport.iata,
                    airport.icao,
                )
                if value
            )
    terms.update(CITY_TO_AIRPORT)
    terms.update(AIRPORT_TO_CITY)
    resolved: list[_LocationTerm] = []
    for term in terms:
        location = _CATALOG.resolve_location(term)
        if location is not None:
            value = location.airport_iata or location.city_name
            city_id = location.city_id
            is_airport = location.airport_iata is not None
        else:
            ref = resolve_airport(term)
            if ref is None:
                continue
            upper = term.upper()
            is_airport = upper in ref.airport_ids
            value = upper if is_airport else ref.city
            city_id = f"international:{ref.code.lower()}"
        resolved.append(
            _LocationTerm(
                text=term,
                value=value,
                city_id=city_id,
                is_airport=is_airport,
                is_ascii_code=(
                    term.isascii()
                    and term.isalpha()
                    and len(term) in (3, 4)
                ),
            )
        )
    return tuple(
        sorted(resolved, key=lambda item: (-len(item.text), item.text))
    )


_LOCATION_TERMS = _build_location_terms()


def _build_location_matcher(
    terms: tuple[_LocationTerm, ...],
) -> tuple[dict[str, _LocationTerm], re.Pattern[str]]:
    term_by_text: dict[str, _LocationTerm] = {}
    alternatives: list[str] = []
    for term in terms:
        key = term.text.casefold()
        if key in term_by_text:
            continue
        term_by_text[key] = term
        alternatives.append(re.escape(term.text))
    return term_by_text, re.compile("|".join(alternatives), re.IGNORECASE)


_LOCATION_TERM_BY_TEXT, _LOCATION_MATCHER = _build_location_matcher(
    _LOCATION_TERMS
)


def fill_slots(
    text: str,
    accumulated: SlotBundle | None = None,
    *,
    today: date | None = None,
    intent_definitions: list[IntentDefinition] | None = None,
) -> SlotBundle:
    """Extract slots from the latest user text and merge with session slots."""
    base = accumulated or SlotBundle()
    definitions = intent_definitions or DEFAULT_INTENTS
    intent_match = match_intent(text, definitions, base)
    extracted = extract_slots(
        text,
        base,
        today=today,
        intent_definitions=definitions,
        matched_intent=intent_match.intent_name if intent_match else None,
    )
    merge_base = (
        replace(base, depart_date=None, return_date=None)
        if _requires_date_reconfirmation(base, extracted)
        else base
    )
    merged = merge_slot_bundle(merge_base, extracted)
    if merged.intent is None and intent_match:
        merged = replace(merged, intent=intent_match.intent_name)
    return merged


def _requires_date_reconfirmation(
    accumulated: SlotBundle,
    extracted: SlotBundle,
) -> bool:
    """Do not silently carry a confirmed date onto a newly stated route."""
    if (
        accumulated.intent != "search_flight"
        or not accumulated.depart_date
        or extracted.depart_date
    ):
        return False

    complete_route_restatement = bool(
        extracted.origin and extracted.destination
    )
    origin_changed = bool(
        accumulated.origin
        and extracted.origin
        and accumulated.origin != extracted.origin
    )
    destination_changed = bool(
        accumulated.destination
        and extracted.destination
        and accumulated.destination != extracted.destination
    )
    return complete_route_restatement or origin_changed or destination_changed


def extract_slots(
    text: str,
    accumulated: SlotBundle | None = None,
    *,
    today: date | None = None,
    intent_definitions: list[IntentDefinition] | None = None,
    matched_intent: str | None = None,
) -> SlotBundle:
    """Extract only the newly mentioned slots from one user message."""
    normalized = _normalize_text(text)
    current = accumulated or SlotBundle()
    definitions = intent_definitions or DEFAULT_INTENTS
    intent_match = match_intent(normalized, definitions, current)
    intent_name = matched_intent or (intent_match.intent_name if intent_match else None)
    mentions = _extract_location_mentions(normalized)
    origin, destination = _infer_origin_destination(
        normalized, mentions, current
    )
    depart_date = _extract_depart_date(normalized, today=today)
    budget = _extract_budget(normalized)
    target_price = _extract_target_price(normalized)
    constraints = _extract_constraints(normalized)

    return SlotBundle(
        intent=intent_name
        or (
            "search_flight"
            if _looks_like_flight_search(normalized, current, mentions)
            else None
        ),
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        budget=budget,
        target_price=target_price,
        constraints=constraints,
    )


def merge_slot_bundle(accumulated: SlotBundle, new_slots: SlotBundle) -> SlotBundle:
    """Merge non-empty new slots into accumulated session slots."""
    data = asdict(accumulated)
    for key, value in asdict(new_slots).items():
        if key == "constraints":
            if value:
                data[key] = list(dict.fromkeys([*data.get(key, []), *value]))
            continue
        if value not in (None, "", []):
            data[key] = value
    return SlotBundle(**data)


def missing_required_slots(
    slots: SlotBundle | None,
    intent_definitions: list[IntentDefinition] | None = None,
) -> list[str]:
    """Return missing required slots for the matched dynamic intent."""
    definitions = intent_definitions or DEFAULT_INTENTS
    if not slots or not slots.intent:
        return []
    required_slots = required_slots_for(definitions, slots.intent)
    if not required_slots and slots.intent == "search_flight":
        required_slots = list(REQUIRED_SEARCH_SLOTS)
    missing: list[str] = []
    for name in required_slots:
        if not getattr(slots, name, None):
            missing.append(name)
    return missing


def slots_to_intent(
    slots: SlotBundle,
    raw_text: str,
    intent_definitions: list[IntentDefinition] | None = None,
) -> NormalizedIntent:
    """Convert accumulated slots into the normalized intent contract."""
    missing = missing_required_slots(slots, intent_definitions)
    return NormalizedIntent(
        origin=_location(slots.origin),
        destination=_location(slots.destination),
        date_window=DateWindow(start_date=slots.depart_date, end_date=slots.return_date)
        if slots.depart_date
        else None,
        budget_cny=slots.budget,
        constraints=[],
        ambiguities=missing,
        intent_confidence=IntentConfidence.high
        if not missing
        else IntentConfidence.medium,
        raw_text=raw_text,
        parse_failed=slots.intent is None,
    )


def build_clarify_question(
    slots: SlotBundle | None,
    missing: list[str],
    user_text: str = "",
) -> str:
    """Ask one natural follow-up question, carrying already known context."""
    first = missing[0] if missing else "origin"
    destination = slots.destination if slots else None
    origin = slots.origin if slots else None
    depart_date = slots.depart_date if slots else None

    if first == "origin":
        if destination and depart_date:
            return f"{_display_date(depart_date)}去{destination}，从哪里出发？"
        if destination:
            return f"去{destination}，从哪里出发？"
        return "你想从哪个城市出发？"
    if first == "destination":
        ambiguity = location_ambiguity(user_text, missing_slot=first)
        if ambiguity:
            choices = "、".join(ambiguity.cities)
            prefix = ""
            if origin and depart_date:
                prefix = f"{_display_date(depart_date)}从{origin}出发，"
            elif origin:
                prefix = f"从{origin}出发，"
            return (
                f"{prefix}{ambiguity.region}有多个机场城市，请确认目的地："
                f"{choices}？"
            )
        if origin and depart_date:
            return f"{_display_date(depart_date)}从{origin}出发，想去哪里？"
        if origin:
            return f"从{origin}出发，想去哪里？"
        return "想去哪个城市？"
    if first == "depart_date":
        route = ""
        if origin and destination:
            route = f"{origin}到{destination}"
        elif destination:
            route = f"去{destination}"
        return f"{route}哪天出发？" if route else "哪天出发？"
    if first == "target_price":
        route = ""
        if origin and destination:
            route = f"{origin}到{destination}"
        elif destination:
            route = f"去{destination}"
        return f"{route}低于多少钱提醒你？" if route else "低于多少钱提醒你？"
    if first == "preference_value":
        return "想让我记住什么偏好？"
    if first == "preference_field":
        return "想更新哪类偏好？"
    return "还差一点信息，能补充一下吗？"


def location_ambiguity(
    text: str,
    *,
    missing_slot: str | None = None,
) -> LocationAmbiguity | None:
    """Return valid airport-city choices for an unresolved province mention."""
    normalized = _normalize_text(text)
    if not normalized:
        return None

    candidates: list[tuple[int, LocationAmbiguity]] = []
    for region in {city.province for city in _CATALOG.cities if city.province}:
        position = normalized.find(region)
        if position < 0:
            continue
        cities = tuple(
            city.name
            for city in _CATALOG.cities
            if city.province == region
            and any(airport.bookable for airport in city.airports)
        )
        if len(cities) >= 2:
            candidates.append(
                (position, LocationAmbiguity(region=region, cities=cities))
            )
    if not candidates:
        return None

    # "广东去广西" must clarify the first region as the origin and the last
    # as the destination. Municipalities such as Beijing are filtered out
    # above because they do not have multiple airport cities.
    candidates.sort(key=lambda item: (item[0], item[1].region))
    return candidates[0][1] if missing_slot == "origin" else candidates[-1][1]


def looks_like_flight_search(text: str, slots: SlotBundle | None = None) -> bool:
    """Classify whether the current turn belongs to the flight-search intent."""
    normalized = _normalize_text(text)
    mentions = _extract_location_mentions(normalized)
    return _looks_like_flight_search(normalized, slots, mentions)


def _looks_like_flight_search(
    normalized: str,
    slots: SlotBundle | None,
    mentions: list[_LocationMention],
) -> bool:
    if slots and slots.intent == "search_flight":
        return True
    if slots and slots.intent and slots.intent != "search_flight":
        return False
    if any(keyword in normalized for keyword in FLIGHT_KEYWORDS):
        return True
    if len(_select_endpoint_mentions(normalized, mentions)) >= 2:
        return True
    if _extract_depart_date(normalized) and mentions:
        return True
    return False


def intent_definition_for(
    slots: SlotBundle | None,
    intent_definitions: list[IntentDefinition] | None = None,
) -> IntentDefinition | None:
    if not slots:
        return None
    definitions = intent_definitions or DEFAULT_INTENTS
    return find_intent_definition(definitions, slots.intent)


def _normalize_text(text: str) -> str:
    return (text or "").strip().replace("号", "日")


def resolve_location_ref(value: str | None) -> LocationRef | None:
    if not value:
        return None
    location = _CATALOG.resolve_location(value)
    if location is not None:
        return LocationRef(
            city=location.city_name,
            iata_code=(
                location.airport_iata or location.provider_code("ctrip")
            ),
        )
    ref = resolve_airport(value)
    if ref is None:
        return None
    airport_code = value.upper()
    return LocationRef(
        city=ref.city,
        iata_code=(airport_code if airport_code in ref.airport_ids else ref.code),
    )


def _location(city: str | None) -> LocationRef | None:
    return resolve_location_ref(city)


def _extract_cities(text: str) -> list[str]:
    return [mention.value for mention in _extract_location_mentions(text)]


def _extract_location_mentions(text: str) -> list[_LocationMention]:
    mentions: list[_LocationMention] = []
    for match in _LOCATION_MATCHER.finditer(text):
        term = _LOCATION_TERM_BY_TEXT[match.group(0).casefold()]
        if term.is_ascii_code and not _has_ascii_code_boundaries(
            text, match.start(), match.end()
        ):
            continue
        if (
            term.is_ascii_code
            and not match.group(0).isupper()
            and not _has_route_code_context(text, match.start(), match.end())
        ):
            continue
        mentions.append(
            _LocationMention(
                start=match.start(),
                end=match.end(),
                value=term.value,
                city_id=term.city_id,
                is_airport=term.is_airport,
            )
        )
    return mentions


def _has_ascii_code_boundaries(text: str, start: int, end: int) -> bool:
    left_is_alphanumeric = start > 0 and bool(
        re.match(r"[A-Za-z0-9]", text[start - 1])
    )
    right_is_alphanumeric = end < len(text) and bool(
        re.match(r"[A-Za-z0-9]", text[end])
    )
    return not left_is_alphanumeric and not right_is_alphanumeric


def _has_route_code_context(text: str, start: int, end: int) -> bool:
    return bool(
        re.search(rf"{_ROUTE_SEPARATOR_PATTERN}\s*$", text[:start])
        or re.match(rf"\s*{_ROUTE_SEPARATOR_PATTERN}", text[end:])
        or re.search(r"(?:从|自|由)\s*$", text[:start])
    )


def _partition_endpoint_mentions(
    text: str,
    mentions: list[_LocationMention],
) -> list[list[_LocationMention]]:
    groups: list[list[_LocationMention]] = []
    for mention in mentions:
        if not groups:
            groups.append([mention])
            continue
        previous = groups[-1][-1]
        crossed_separator = bool(
            _ROUTE_SEPARATOR.search(text[previous.end : mention.start])
        )
        if crossed_separator or previous.city_id != mention.city_id:
            groups.append([mention])
        else:
            groups[-1].append(mention)
    return groups


def _select_endpoint_mention(
    mentions: list[_LocationMention],
) -> _LocationMention:
    return next(
        (mention for mention in mentions if mention.is_airport),
        mentions[0],
    )


def _select_endpoint_mentions(
    text: str,
    mentions: list[_LocationMention],
) -> list[_LocationMention]:
    return [
        _select_endpoint_mention(group)
        for group in _partition_endpoint_mentions(text, mentions)
    ]


def extract_route_locations(
    text: str, accumulated: SlotBundle | None = None
) -> tuple[str | None, str | None]:
    current = accumulated or SlotBundle()
    mentions = _extract_location_mentions(text)
    return _infer_origin_destination(text, mentions, current)


def _infer_origin_destination(
    text: str,
    mentions: list[_LocationMention],
    accumulated: SlotBundle,
) -> tuple[str | None, str | None]:
    groups = _partition_endpoint_mentions(text, mentions)
    endpoints = [_select_endpoint_mention(group) for group in groups]
    cities = [mention.value for mention in endpoints]
    origin = _extract_marked_endpoint(text, ORIGIN_MARKERS, groups)
    destination = _extract_marked_endpoint(text, DESTINATION_MARKERS, groups)

    if origin and destination and origin == destination and len(cities) > 1:
        destination = next((city for city in cities if city != origin), destination)

    if not origin and destination and len(cities) >= 2:
        origin = next((city for city in cities if city != destination), None)
    elif origin and not destination and len(cities) >= 2:
        destination = next((city for city in cities if city != origin), None)
    elif not origin and not destination and len(cities) >= 2:
        origin, destination = cities[0], cities[1]
    elif len(cities) == 1 and not origin and not destination:
        city = cities[0]
        missing = missing_required_slots(accumulated)
        if "origin" in missing and accumulated.destination != city:
            origin = city
        elif "destination" in missing and accumulated.origin != city:
            destination = city
        elif "去" in text or "到" in text or "飞" in text:
            destination = city

    return origin, destination


def _extract_marked_endpoint(
    text: str,
    markers: tuple[str, ...],
    groups: list[list[_LocationMention]],
) -> str | None:
    for group in groups:
        prefix = text[: group[0].start]
        if any(re.search(rf"{re.escape(marker)}\s*$", prefix) for marker in markers):
            return _select_endpoint_mention(group).value
    return None


def _extract_depart_date(text: str, *, today: date | None = None) -> str | None:
    base = today or datetime.now(_TZ).date()
    if "今天" in text:
        return base.isoformat()
    if "明天" in text:
        return (base + timedelta(days=1)).isoformat()
    if "后天" in text:
        return (base + timedelta(days=2)).isoformat()
    if "下周末" in text:
        return _next_weekday(base + timedelta(days=7), 5).isoformat()
    if "周末" in text or "这个周末" in text or "本周末" in text:
        return _next_weekday(base, 5).isoformat()
    if "国庆" in text:
        return date(base.year, 10, 1).isoformat()
    if "五一" in text:
        return date(base.year, 5, 1).isoformat()

    match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        return _future_date(base, month, day).isoformat()

    match = re.search(r"([一二两三四五六七八九十]{1,3})月([一二两三四五六七八九十]{1,3})日", text)
    if match:
        month = _cn_number(match.group(1))
        day = _cn_number(match.group(2))
        if month and day:
            return _future_date(base, month, day).isoformat()

    match = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?", text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()

    return None


def _future_date(base: date, month: int, day: int) -> date:
    candidate = date(base.year, month, day)
    if candidate < base:
        candidate = date(base.year + 1, month, day)
    return candidate


def _next_weekday(base: date, weekday: int) -> date:
    delta = (weekday - base.weekday()) % 7
    return base + timedelta(days=delta)


def _cn_number(value: str) -> int | None:
    if value == "十":
        return 10
    if value.startswith("十"):
        return 10 + _CHINESE_NUMERALS.get(value[1:], 0)
    if "十" in value:
        left, _, right = value.partition("十")
        return _CHINESE_NUMERALS.get(left, 1) * 10 + _CHINESE_NUMERALS.get(right, 0)
    return _CHINESE_NUMERALS.get(value)


def _extract_budget(text: str) -> int | None:
    match = re.search(r"(\d{2,5})\s*元?以?内", text)
    if match:
        return int(match.group(1))
    match = re.search(r"预算\s*(\d{2,5})", text)
    if match:
        return int(match.group(1))
    return None


def _extract_target_price(text: str) -> int | None:
    match = re.search(r"(?:低于|降到|少于|不超过|到)\s*(\d{2,5})\s*元?", text)
    if match:
        return int(match.group(1))
    if "提醒" in text or "蹲" in text:
        return _extract_budget(text)
    return None


def _extract_constraints(text: str) -> list[str]:
    constraints: list[str] = []
    if "直飞" in text or "不转机" in text:
        constraints.append("direct_only")
    if "不要红眼" in text or "不坐红眼" in text:
        constraints.append("avoid_redeye")
    if "早上" in text or "上午" in text:
        constraints.append("prefer_morning")
    return constraints


def _display_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{parsed.month}月{parsed.day}日"
