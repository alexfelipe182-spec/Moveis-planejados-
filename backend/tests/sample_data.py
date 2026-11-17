"""Stable addresses within a pytest process, distinct across repeated executions."""

from uuid import uuid4


_RUN_ID = uuid4().hex[:12]


def unique_email(address: str) -> str:
    local, domain = address.split("@")
    return f"{local}.{_RUN_ID}@{domain}"
