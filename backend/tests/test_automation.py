from uuid import UUID

import pytest

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


def test_duplicate_action_registration_is_idempotent() -> None:
    engine = AutomationEngine()
    received = []
    action = AutomationAction(name="capture", handler=lambda event: received.append(event.payload))

    engine.register("quote.created", action)
    engine.register("quote.created", action)
    engine.emit("quote.created", {"quote_id": 123})

    assert received == [{"quote_id": 123}]


def test_automation_results_can_be_filtered_by_organization():
    engine = AutomationEngine()
    engine.register("quote.created", AutomationAction(name="capture", handler=lambda _event: {}))
    engine.emit("quote.created", {"organization_id": 10, "quote_id": 1})
    engine.emit("quote.created", {"organization_id": 20, "quote_id": 2})

    assert [row["result"] for row in engine.results_for_organization(10)] == [{}]
    assert all(row["organization_id"] == 10 for row in engine.results_for_organization(10))


def test_failed_action_is_recorded_and_does_not_block_following_action() -> None:
    engine = AutomationEngine()
    received = []

    def fail(_event):
        raise RuntimeError("provider unavailable")

    engine.register("quote.created", AutomationAction(name="external_provider", handler=fail))
    engine.register(
        "quote.created",
        AutomationAction(name="local_fallback", handler=lambda event: received.append(event.payload)),
    )

    event = engine.emit("quote.created", {"quote_id": 123})

    assert event.name == "quote.created"
    assert received == [{"quote_id": 123}]
    assert [(result["action"], result["status"]) for result in engine.results] == [
        ("external_provider", "failed"),
        ("local_fallback", "completed"),
    ]
    assert engine.results[0]["result"]["error_type"] == "RuntimeError"


def test_actions_receive_isolated_payloads_and_cannot_mutate_returned_event() -> None:
    engine = AutomationEngine()
    received = []

    def corrupt_payload(event):
        event.payload["quote"]["id"] = 999

    engine.register("quote.created", AutomationAction(name="corrupt", handler=corrupt_payload))
    engine.register(
        "quote.created",
        AutomationAction(name="capture", handler=lambda event: received.append(event.payload)),
    )

    event = engine.emit("quote.created", {"quote": {"id": 123}})

    assert received == [{"quote": {"id": 123}}]
    assert event.payload == {"quote": {"id": 123}}


def test_recorded_results_are_immutable_snapshots() -> None:
    engine = AutomationEngine()
    event = engine.emit("quote.created")
    original = {"details": {"state": "original"}}

    engine.record_result(event, "capture", original)
    original["details"]["state"] = "changed by caller"
    exposed = engine.results
    exposed[0]["result"]["details"]["state"] = "changed by reader"

    assert engine.results[0]["result"] == {"details": {"state": "original"}}


def test_successful_action_result_is_recorded_by_engine() -> None:
    engine = AutomationEngine()
    engine.register(
        "quote.created",
        AutomationAction(name="capture", handler=lambda event: {"quote_id": event.payload["quote_id"]}),
    )

    engine.emit("quote.created", {"quote_id": 123})

    assert len(engine.results) == 1
    recorded = engine.results[0]
    assert {key: recorded[key] for key in ("event", "action", "status", "result")} == {
        "event": "quote.created",
        "action": "capture",
        "status": "completed",
        "result": {"quote_id": 123},
    }
    assert recorded["created_at"].endswith("+00:00")


def test_action_registered_during_emit_only_runs_on_next_event() -> None:
    engine = AutomationEngine()
    received = []

    def register_late(_event):
        received.append("initial")
        engine.register(
            "quote.created",
            AutomationAction(name="late", handler=lambda _event: received.append("late")),
        )

    engine.register("quote.created", AutomationAction(name="initial", handler=register_late))

    engine.emit("quote.created")
    assert received == ["initial"]

    engine.emit("quote.created")
    assert received == ["initial", "initial", "late"]


def test_event_and_results_share_traceable_event_id() -> None:
    engine = AutomationEngine()
    engine.register("quote.created", AutomationAction(name="capture", handler=lambda _event: {}))

    event = engine.emit("quote.created")

    assert str(UUID(event.event_id)) == event.event_id
    assert engine.results[0]["event_id"] == event.event_id


def test_conflicting_action_registration_is_rejected() -> None:
    engine = AutomationEngine()

    def first_handler(_event):
        return {}

    def different_handler(_event):
        return {}

    engine.register("quote.created", AutomationAction(name="capture", handler=first_handler))

    with pytest.raises(ValueError, match="capture"):
        engine.register("quote.created", AutomationAction(name="capture", handler=different_handler))


def test_failed_action_does_not_store_secret_exception_message() -> None:
    engine = AutomationEngine()

    def fail_with_secret(_event):
        raise RuntimeError("api_key=super-secret-value")

    engine.register("quote.created", AutomationAction(name="provider", handler=fail_with_secret))
    engine.emit("quote.created")

    failed = engine.results[0]
    assert failed["result"]["message"] == "Falha interna da automação"
    assert "super-secret-value" not in str(failed)


def test_event_and_action_names_must_be_clean_and_non_empty() -> None:
    engine = AutomationEngine()
    action = AutomationAction(name="capture", handler=lambda _event: {})

    with pytest.raises(ValueError):
        engine.register("", action)
    with pytest.raises(ValueError):
        engine.register(" quote.created", action)
    with pytest.raises(ValueError):
        engine.register("quote.created", AutomationAction(name=" ", handler=lambda _event: {}))
    with pytest.raises(ValueError):
        engine.emit(" ")
