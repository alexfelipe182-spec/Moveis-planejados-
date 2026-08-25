from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class QuoteItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    quantity: Decimal = Field(default=1, gt=0, max_digits=10, decimal_places=2)
    width: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    height: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    depth: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)


class QuoteItemCreate(QuoteItemBase):
    pass


class QuoteItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    width: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    height: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    depth: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class QuoteItemRead(QuoteItemBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quote_id: int
    subtotal: Decimal
