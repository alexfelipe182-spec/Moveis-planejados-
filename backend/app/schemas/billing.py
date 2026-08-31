from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    monthly_price_cents: int
    max_users: int
    features: dict


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str
    provider: str
    plan_code: str
    plan_name: str
    monthly_price_cents: int
    trial_end: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool
    access_allowed: bool


class CheckoutRequest(BaseModel):
    plan_code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9-]+$")
