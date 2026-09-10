"""Allowlisted telemetry: never serialize request bodies or exception messages."""
import json
import logging
from contextvars import ContextVar

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("uvicorn.error")


def record_event(event: str, **metadata) -> None:
    allowed = {
        "tenant_id", "operation", "provider", "model", "duration_ms", "result",
        "job_id", "event_type", "attempts", "request_id", "error_code", "consumption",
    }
    data = {key: value for key, value in metadata.items() if key in allowed}
    data.setdefault("request_id", request_id_context.get())
    logger.info(json.dumps({"event": event, **data}, ensure_ascii=False))
