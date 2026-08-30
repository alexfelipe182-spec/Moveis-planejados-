from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="trialing", nullable=False, index=True)
    plan_code: Mapped[str] = mapped_column(String(30), default="starter", nullable=False, index=True)
    billing_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    billing_provider: Mapped[str] = mapped_column(String(30), default="disabled", nullable=False)
    external_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    external_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    subscription_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False
    )
