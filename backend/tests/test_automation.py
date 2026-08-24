from app.services.automation import AutomationAction, AutomationEngine


def test_automation_engine_emits_registered_action() -> None:
    engine = AutomationEngine()
    received = []

    engine.register(
        "quote.created",
        AutomationAction(name="capture", handler=lambda event: received.append(event.payload)),
    )

    event = engine.emit("quote.created", {"quote_id": 123})

    assert event.name == "quote.created"
    assert received == [{"quote_id": 123}]


def test_automation_engine_ignores_events_without_actions() -> None:
    engine = AutomationEngine()

    event = engine.emit("unknown.event")

    assert event.name == "unknown.event"
    assert event.payload == {}
