from decimal import Decimal

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuoteItem(Base):
    __tablename__ = "quote_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_quote_items_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "quote_id"],
            ["quotes.organization_id", "quotes.id"],
            name="fk_quote_items_quote_tenant",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)
    width: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    height: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    depth: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
