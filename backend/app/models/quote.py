from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    measurements: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    materials: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    material_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    hardware_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    finishing_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    profit_margin: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=30)
    suggested_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
