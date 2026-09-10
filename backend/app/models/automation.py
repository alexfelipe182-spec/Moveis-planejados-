from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.tenant import TenantScopedMixin, utc_now_naive


class AutomationJob(TenantScopedMixin, Base):
    __tablename__ = "automation_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_automation_tenant_key"),
        CheckConstraint("status IN ('pending', 'retry', 'completed', 'failed')", name="ck_automation_status"),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="ck_automation_attempts"),
        Index("ix_automation_due", "status", "available_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    idempotency_key: Mapped[str] = mapped_column(String(180))
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AIUsage(TenantScopedMixin, Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    operation: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    result: Mapped[str] = mapped_column(String(30))
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    consumption: Mapped[int] = mapped_column(Integer, default=0)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
