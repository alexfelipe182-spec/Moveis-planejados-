import hashlib
import re

from fastapi import HTTPException
from pydantic import BaseModel


def request_identity(key: str | None, payload: BaseModel) -> tuple[str | None, str | None]:
    if key is None:
        return None, None
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", key):
        raise HTTPException(status_code=422, detail="Idempotency-Key inválida")
    return key, hashlib.sha256(payload.model_dump_json().encode()).hexdigest()


def ensure_same_request(item, fingerprint: str) -> None:
    if item.request_fingerprint != fingerprint:
        raise HTTPException(status_code=409, detail="Idempotency-Key já utilizada com outros dados")
