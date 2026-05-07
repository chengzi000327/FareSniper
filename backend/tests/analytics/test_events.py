from backend.analytics.events import EVENT_SCHEMAS, EventName


def test_eight_events_defined():
    expected = {
        "search_submitted",
        "intent_parsed",
        "result_viewed",
        "ticket_clicked",
        "purchase_jumped",
        "memory_edited",
        "memory_cleared",
        "fallback_triggered",
    }
    assert {e.value for e in EventName} == expected


def test_each_event_has_schema():
    for evt in EventName:
        assert evt in EVENT_SCHEMAS
        assert "required" in EVENT_SCHEMAS[evt]


def test_purchase_jumped_required_fields():
    schema = EVENT_SCHEMAS[EventName.PURCHASE_JUMPED]
    assert set(schema["required"]) == {"flight_no", "platform", "price"}


def test_memory_cleared_has_no_required_fields():
    schema = EVENT_SCHEMAS[EventName.MEMORY_CLEARED]
    assert schema["required"] == []
