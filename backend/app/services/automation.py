"""Lightweight automation engine for domain events."""
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
        self._results: list[dict] = []

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

    @property
    def results(self) -> list[dict]:
        return list(self._results)

    def record_result(self, event: AutomationEvent, action: str, result: dict) -> None:
        self._results.append({
            "event": event.name,
            "action": action,
            "created_at": event.created_at.isoformat(),
            "result": result,
        })


engine = AutomationEngine()


def _prepare_quote_analysis(event: AutomationEvent) -> None:
    from app.services.quote_ai import analyze_quote

    payload = event.payload
    analysis = analyze_quote(
        base_cost=payload["base_cost"],
        suggested_total=payload["suggested_total"],
        profit_margin=payload["profit_margin"],
    )
    engine.record_result(event, "analyze_quote", analysis)


def register_default_automations() -> None:
    """Register safe foundation automations exactly once."""
    if engine._actions:
        return

    engine.register(
        "user.created",
        AutomationAction(name="audit_user_created", handler=lambda event: None),
    )
    engine.register(
        "quote.created",
        AutomationAction(name="prepare_quote_analysis", handler=_prepare_quote_analysis),
    )


register_default_automations()
