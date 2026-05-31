from __future__ import annotations

from datetime import date

from backend.application.contracts.intent import SlotBundle
from backend.application.services.default_intents import DEFAULT_INTENTS
from backend.application.services.intent_registry import match_intent
from backend.application.services.intent_slot_filler import (
    build_clarify_question,
    fill_slots,
    missing_required_slots,
    slots_to_intent,
)


def test_extracts_complete_route_with_relative_date():
    slots = fill_slots("明天北京到三亚，预算1000以内，直飞", today=date(2026, 5, 9))

    assert slots.intent == "search_flight"
    assert slots.origin == "北京"
    assert slots.destination == "三亚"
    assert slots.depart_date == "2026-05-10"
    assert slots.budget == 1000
    assert "direct_only" in slots.constraints
    assert missing_required_slots(slots) == []


def test_merges_multi_turn_slot_context():
    first = fill_slots("下周末去三亚", today=date(2026, 5, 9))
    second = fill_slots("北京", first, today=date(2026, 5, 9))

    assert first.destination == "三亚"
    assert first.origin is None
    assert second.origin == "北京"
    assert second.destination == "三亚"
    assert second.depart_date == "2026-05-16"
    assert missing_required_slots(second) == []


def test_clarify_question_carries_known_destination():
    slots = SlotBundle(intent="search_flight", destination="三亚", depart_date="2026-05-16")

    assert build_clarify_question(slots, ["origin"]) == "5月16日去三亚，从哪里出发？"


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
