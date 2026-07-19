from __future__ import annotations

from datetime import date

import backend.application.services.intent_slot_filler as slot_filler
import backend.services.intent_parser as legacy_intent_parser
from backend.application.contracts.intent import SlotBundle
from backend.application.services.default_intents import DEFAULT_INTENTS
from backend.application.services.intent_registry import match_intent
from backend.application.services.intent_slot_filler import (
    build_clarify_question,
    extract_route_locations,
    fill_slots,
    location_ambiguity,
    missing_required_slots,
    slots_to_intent,
)
from backend.services.intent_parser import IntentParser


def test_extracts_complete_route_with_relative_date():
    slots = fill_slots("明天北京到三亚，预算1000以内，直飞", today=date(2026, 5, 9))

    assert slots.intent == "search_flight"
    assert slots.origin == "北京"
    assert slots.destination == "三亚"
    assert slots.depart_date == "2026-05-10"
    assert slots.budget == 1000
    assert "direct_only" in slots.constraints
    assert missing_required_slots(slots) == []


def test_extracts_next_weekday_from_complete_route():
    slots = fill_slots(
        "下周五从北京到长治",
        today=date(2026, 7, 19),
    )

    assert slots.origin == "北京"
    assert slots.destination == "长治"
    assert slots.depart_date == "2026-07-24"
    assert missing_required_slots(slots) == []


def test_date_only_next_weekday_completes_accumulated_route():
    route = fill_slots(
        "从北京到长治",
        today=date(2026, 7, 19),
    )
    completed = fill_slots(
        "下周五",
        route,
        today=date(2026, 7, 19),
    )

    assert completed.origin == "北京"
    assert completed.destination == "长治"
    assert completed.depart_date == "2026-07-24"
    assert missing_required_slots(completed) == []


def test_relative_weekday_supports_week_and_weekday_variants():
    base = date(2026, 7, 20)

    assert fill_slots("下星期五北京到长治", today=base).depart_date == "2026-07-31"
    assert fill_slots("下下周一北京到长治", today=base).depart_date == "2026-08-03"
    assert fill_slots("礼拜日北京到长治", today=base).depart_date == "2026-07-26"


def test_merges_multi_turn_slot_context():
    first = fill_slots("下周末去三亚", today=date(2026, 5, 9))
    second = fill_slots("北京", first, today=date(2026, 5, 9))

    assert first.destination == "三亚"
    assert first.origin is None
    assert second.origin == "北京"
    assert second.destination == "三亚"
    assert second.depart_date == "2026-05-16"
    assert missing_required_slots(second) == []


def test_new_route_without_date_does_not_reuse_previous_search_date():
    previous = SlotBundle(
        intent="search_flight",
        origin="北京",
        destination="上海",
        depart_date="2026-08-01",
    )

    slots = fill_slots(
        "帮我查广州到成都",
        previous,
        today=date(2026, 7, 19),
    )

    assert slots.origin == "广州"
    assert slots.destination == "成都"
    assert slots.depart_date is None
    assert missing_required_slots(slots) == ["depart_date"]


def test_changed_destination_requires_date_reconfirmation():
    previous = SlotBundle(
        intent="search_flight",
        origin="北京",
        destination="上海",
        depart_date="2026-08-01",
    )

    slots = fill_slots(
        "改去三亚",
        previous,
        today=date(2026, 7, 19),
    )

    assert slots.origin == "北京"
    assert slots.destination == "三亚"
    assert slots.depart_date is None
    assert missing_required_slots(slots) == ["depart_date"]


def test_clarify_question_carries_known_destination():
    slots = SlotBundle(intent="search_flight", destination="三亚", depart_date="2026-05-16")

    assert build_clarify_question(slots, ["origin"]) == "5月16日去三亚，从哪里出发？"


def test_province_destination_clarification_lists_catalog_airport_cities():
    slots = SlotBundle(
        intent="search_flight",
        origin="北京",
        depart_date="2026-07-20",
    )

    question = build_clarify_question(
        slots,
        ["destination"],
        "去广西桂宁",
    )
    ambiguity = location_ambiguity("去广西桂宁")

    assert ambiguity is not None
    assert ambiguity.region == "广西"
    assert {"南宁", "桂林", "北海", "柳州"} <= set(ambiguity.cities)
    assert question.startswith("7月20日从北京出发，广西有多个机场城市")
    assert all(city in question for city in ambiguity.cities)


def test_province_ambiguity_survives_an_exact_origin_in_same_message():
    ambiguity = location_ambiguity(
        "明天从北京去广西",
        missing_slot="destination",
    )

    assert ambiguity is not None
    assert ambiguity.region == "广西"
    assert "南宁" in ambiguity.cities


def test_two_provinces_select_region_for_missing_endpoint():
    origin = location_ambiguity("从广东去广西", missing_slot="origin")
    destination = location_ambiguity(
        "从广东去广西",
        missing_slot="destination",
    )

    assert origin is not None
    assert destination is not None
    assert origin.region == "广东"
    assert destination.region == "广西"


def test_slots_to_intent_uses_chinese_city_and_airport_code():
    slots = SlotBundle(
        intent="search_flight",
        origin="北京",
        destination="三亚",
        depart_date="2026-05-10",
    )

    intent = slots_to_intent(slots, "明天北京到三亚")

    assert intent.origin.city == "北京"
    assert intent.origin.iata_code == "BJS"
    assert intent.destination.city == "三亚"
    assert intent.destination.iata_code == "SYX"
    assert intent.date_window.start_date == "2026-05-10"
    assert intent.parse_failed is False


def test_dynamic_registry_matches_alert_before_search():
    match = match_intent("北京到三亚低于500提醒我", DEFAULT_INTENTS)

    assert match is not None
    assert match.intent_name == "set_alert"


def test_dynamic_required_slots_drive_alert_slot_filling():
    slots = fill_slots(
        "明天北京到三亚低于500提醒我",
        today=date(2026, 5, 9),
        intent_definitions=DEFAULT_INTENTS,
    )

    assert slots.intent == "set_alert"
    assert slots.origin == "北京"
    assert slots.destination == "三亚"
    assert slots.depart_date == "2026-05-10"
    assert slots.target_price == 500
    assert missing_required_slots(slots, DEFAULT_INTENTS) == []


def test_chitchat_does_not_fall_back_to_search_slots():
    slots = fill_slots("你是谁？", intent_definitions=DEFAULT_INTENTS)

    assert slots.intent == "chitchat"
    assert missing_required_slots(slots, DEFAULT_INTENTS) == []


def test_strong_new_intent_overrides_sticky_session_intent():
    chit = SlotBundle(intent="chitchat")
    match = match_intent("我要从北京去上海的机票", DEFAULT_INTENTS, chit)
    assert match.intent_name == "search_flight"


def test_slot_only_turn_keeps_session_intent():
    flight = SlotBundle(intent="search_flight")
    match = match_intent("北京", DEFAULT_INTENTS, flight)
    assert match.intent_name == "search_flight"


def test_same_intent_fresh_match_keeps_session():
    flight = SlotBundle(intent="search_flight")
    match = match_intent("帮我查北京到上海的机票", DEFAULT_INTENTS, flight)
    assert match.intent_name == "search_flight"


def test_catalog_aliases_fill_non_hot_route():
    slots = fill_slots(
        "明天从阿勒泰飞臺北", today=date(2026, 7, 19)
    )

    assert slots.origin == "阿勒泰"
    assert slots.destination == "台北"
    assert slots.depart_date == "2026-07-20"


def test_explicit_airport_alias_survives_slot_filling():
    slots = fill_slots(
        "明天从北京大兴机场飞上海", today=date(2026, 7, 19)
    )
    intent = slots_to_intent(slots, "明天从北京大兴机场飞上海")

    assert slots.origin == "PKX"
    assert slots.destination == "上海"
    assert intent.origin.city == "北京"
    assert intent.origin.iata_code == "PKX"


def test_legacy_intent_parser_uses_catalog_alias_and_airport_code():
    parsed = IntentParser()._parse_heuristic(
        "从北京大兴机场飞臺北"
    )

    assert parsed["origin"] == "北京"
    assert parsed["origin_code"] == "PKX"
    assert parsed["destination"] == "台北"
    assert parsed["destination_code"] == "TPE"


def test_ordinary_lowercase_english_is_not_guessed_as_airport_route():
    origin, destination = extract_route_locations("she can help")

    assert origin is None
    assert destination is None


def test_lowercase_codes_are_allowed_in_unambiguous_route_syntax():
    slots = fill_slots(
        "明天从pvg飞pek", today=date(2026, 7, 19)
    )

    assert slots.origin == "PVG"
    assert slots.destination == "PEK"


def test_contiguous_airport_mention_wins_over_broader_city():
    slots = fill_slots(
        "明天从上海浦东机场飞北京", today=date(2026, 7, 19)
    )

    assert slots.origin == "PVG"
    assert slots.destination == "北京"


def test_separated_airport_mention_wins_over_broader_city():
    slots = fill_slots(
        "明天从上海的浦东机场飞北京", today=date(2026, 7, 19)
    )

    assert slots.origin == "PVG"
    assert slots.destination == "北京"


def test_same_city_marked_airports_preserve_both_constraints():
    slots = fill_slots("从上海浦东机场到上海虹桥机场")

    assert slots.origin == "PVG"
    assert slots.destination == "SHA"


def test_same_city_delimited_airports_preserve_both_constraints():
    slots = fill_slots("上海浦东机场-上海虹桥机场")

    assert slots.origin == "PVG"
    assert slots.destination == "SHA"


def test_lowercase_code_routes_support_slash_and_zhi_separators():
    for text in ("pvg/pek", "pvg至pek"):
        origin, destination = extract_route_locations(text)

        assert origin == "PVG"
        assert destination == "PEK"


def test_slot_extraction_scans_location_terms_once(monkeypatch):
    calls = 0
    original = slot_filler._extract_location_mentions

    def counted(text):
        nonlocal calls
        calls += 1
        return original(text)

    monkeypatch.setattr(slot_filler, "_extract_location_mentions", counted)

    slots = fill_slots(
        "明天从上海的浦东机场飞北京", today=date(2026, 7, 19)
    )

    assert slots.origin == "PVG"
    assert calls == 1


def test_location_extraction_runs_one_precompiled_matcher_scan(monkeypatch):
    calls = 0
    original = slot_filler._LOCATION_MATCHER

    class CountingMatcher:
        def finditer(self, text):
            nonlocal calls
            calls += 1
            return original.finditer(text)

    monkeypatch.setattr(slot_filler, "_LOCATION_MATCHER", CountingMatcher())

    slots = fill_slots(
        "明天从上海的浦东机场飞北京", today=date(2026, 7, 19)
    )

    assert slots.origin == "PVG"
    assert slots.destination == "北京"
    assert calls == 1


def test_legacy_intent_parser_extracts_route_once(monkeypatch):
    calls = 0
    original = legacy_intent_parser.extract_route_locations

    def counted(text):
        nonlocal calls
        calls += 1
        return original(text)

    monkeypatch.setattr(
        legacy_intent_parser, "extract_route_locations", counted
    )

    parsed = legacy_intent_parser.IntentParser()._parse_heuristic(
        "从上海的浦东机场飞北京"
    )

    assert parsed["origin_code"] == "PVG"
    assert calls == 1
