"""Lightweight automation engine for domain events."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4


@dataclass(frozen=True)
class AutomationEvent:
    event_id: str
    name: str
    payload: dict
    created_at: datetime


@dataclass(frozen=True)
class AutomationAction:
    name: str
    handler: Callable[[AutomationEvent], dict | None]


class AutomationEngine:
    def __init__(self, result_limit: int = 500) -> None:
        self._actions: dict[str, list[AutomationAction]] = {}
        self._results: list[dict] = []
        self._result_limit = max(1, result_limit)

    def register(self, event_name: str, action: AutomationAction) -> None:
        self._validate_name(event_name, "event")
        self._validate_name(action.name, "action")
        actions = self._actions.setdefault(event_name, [])
        for registered in actions:
            if registered.name != action.name:
                continue
            if registered.handler is action.handler:
                return
            raise ValueError(f"Automation action '{action.name}' is already registered with another handler")
        actions.append(action)

    def emit(self, event_name: str, payload: dict | None = None) -> AutomationEvent:
        self._validate_name(event_name, "event")
        event = AutomationEvent(
            event_id=str(uuid4()),
            name=event_name,
            payload=deepcopy(payload or {}),
            created_at=datetime.now(timezone.utc),
        )
        actions = tuple(self._actions.get(event_name, ()))
        for action in actions:
            action_event = AutomationEvent(
                event_id=event.event_id,
                name=event.name,
                payload=deepcopy(event.payload),
                created_at=event.created_at,
            )
            try:
                result = action.handler(action_event)
                if result is None:
                    result = {}
                if not isinstance(result, dict):
                    raise TypeError("Automation handlers must return a dictionary or None")
                self.record_result(action_event, action.name, result)
            except Exception as exc:
                self.record_result(
                    action_event,
                    action.name,
                    {"error_type": type(exc).__name__, "message": "Falha interna da automação"},
                    status="failed",
                )
        return event

    @staticmethod
    def _validate_name(value: str, kind: str) -> None:
        if not isinstance(value, str) or not value or value != value.strip() or len(value) > 100:
            raise ValueError(f"Automation {kind} name must be clean and non-empty")

    @property
    def results(self) -> list[dict]:
        return deepcopy(self._results)

    def results_for_organization(self, organization_id: int) -> list[dict]:
        """Return only automation outcomes carrying the caller's tenant tracer."""
        return deepcopy(
            [row for row in self._results if row.get("organization_id") == organization_id]
        )

    def record_result(
        self,
        event: AutomationEvent,
        action: str,
        result: dict,
        *,
        status: str = "completed",
    ) -> None:
        self._results.append({
            "event_id": event.event_id,
            "event": event.name,
            "organization_id": event.payload.get("organization_id"),
            "action": action,
            "status": status,
            "created_at": event.created_at.isoformat(),
            "result": deepcopy(result),
        })
        if len(self._results) > self._result_limit:
            del self._results[:-self._result_limit]


engine = AutomationEngine()


def _audit_user_created(_event: AutomationEvent) -> dict:
    return {"audited": True}


def _prepare_quote_analysis(event: AutomationEvent) -> dict:
    from app.services.quote_ai import analyze_quote

    payload = event.payload
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        analysis = analyze_quote(
            base_cost=payload["base_cost"],
            suggested_total=payload["suggested_total"],
            profit_margin=payload["profit_margin"],
            description=payload.get("description"),
            measurements=payload.get("measurements"),
            materials=payload.get("materials"),
        )
    return analysis


def register_default_automations() -> None:
    """Register safe foundation automations exactly once."""
    engine.register(
        "user.created",
        AutomationAction(name="audit_user_created", handler=_audit_user_created),
    )
    engine.register(
        "quote.created",
        AutomationAction(name="analyze_quote", handler=_prepare_quote_analysis),
    )


register_default_automations()
