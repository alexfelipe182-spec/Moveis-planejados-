from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


QuoteStatus = Literal["pending", "approved", "rejected", "completed"]


class QuoteBase(BaseModel):
    customer_id: int = Field(gt=0)
    description: str = Field(min_length=3, max_length=3000)
    total: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    status: QuoteStatus = "pending"


class QuoteCreate(QuoteBase):
    pass


class QuoteUpdate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, min_length=3, max_length=3000)
    total: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    status: QuoteStatus | None = None


class QuoteRead(QuoteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
