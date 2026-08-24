"""Lightweight automation engine for domain events.

Automations are deliberately small and deterministic in the foundation phase.
Long-running jobs and external integrations can be added later without coupling
business routes to the worker implementation.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass(frozen=True)
class AutomationEvent:
    name: str
    payload: dict
    created_at: datetime


@dataclass(frozen=True)
class AutomationAction:
    name: str
    handler: Callable[[AutomationEvent], None]


class AutomationEngine:
    def __init__(self) -> None:
        self._actions: dict[str, list[AutomationAction]] = {}

    def register(self, event_name: str, action: AutomationAction) -> None:
        self._actions.setdefault(event_name, []).append(action)

    def emit(self, event_name: str, payload: dict | None = None) -> AutomationEvent:
        event = AutomationEvent(
            name=event_name,
            payload=payload or {},
            created_at=datetime.now(timezone.utc),
        )
        for action in self._actions.get(event_name, []):
            action.handler(event)
        return event


engine = AutomationEngine()


def register_default_automations() -> None:
    """Register safe foundation automations exactly once."""
    if engine._actions:
        return

    engine.register(
        "user.created",
        AutomationAction(
            name="audit_user_created",
            handler=lambda event: None,
        ),
    )

    engine.register(
        "quote.created",
        AutomationAction(
            name="prepare_quote_followup",
            handler=lambda event: None,
        ),
    )


register_default_automations()
