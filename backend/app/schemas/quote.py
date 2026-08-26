from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QuoteStatus = Literal["pending", "analysis", "approved", "rejected", "completed"]


class QuoteBase(BaseModel):
    customer_id: int = Field(gt=0)
    description: str = Field(min_length=3, max_length=3000)
    measurements: str | None = Field(default=None, max_length=2000)
    materials: str | None = Field(default=None, max_length=2000)
    total: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    status: QuoteStatus = "pending"


class QuoteCreate(QuoteBase):
    material_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    hardware_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    labor_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    finishing_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    profit_margin: Decimal = Field(default=Decimal("30"), ge=0, le=100, max_digits=5, decimal_places=2)


class QuoteUpdate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, min_length=3, max_length=3000)
    measurements: str | None = Field(default=None, max_length=2000)
    materials: str | None = Field(default=None, max_length=2000)
    material_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    hardware_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    labor_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    finishing_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    profit_margin: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    status: QuoteStatus | None = None


class QuoteEstimateResponse(BaseModel):
    material_cost: Decimal
    hardware_cost: Decimal
    labor_cost: Decimal
    finishing_cost: Decimal
    base_cost: Decimal
    profit_margin: Decimal
    suggested_total: Decimal
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    ai_analysis: str | None = None
    ai_analyzed_at: datetime | None = None
    requires_approval: bool = True


class QuoteRead(QuoteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    material_cost: Decimal = Decimal("0")
    hardware_cost: Decimal = Decimal("0")
    labor_cost: Decimal = Decimal("0")
    finishing_cost: Decimal = Decimal("0")
    profit_margin: Decimal = Decimal("30")
    suggested_total: Decimal = Decimal("0")
    ai_analysis: str | None = None
    ai_analyzed_at: datetime | None = None
