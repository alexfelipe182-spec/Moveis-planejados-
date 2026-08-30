from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

PlanCode = Literal["starter", "professional", "business"]
TenantStatus = Literal["trialing", "active", "past_due", "suspended", "cancelled"]


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    status: TenantStatus
    plan_code: PlanCode
    billing_email: EmailStr | None = None
    billing_provider: str
    trial_ends_at: datetime | None = None
    subscription_ends_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TenantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    billing_email: EmailStr | None = None


class SuperadminTenantUpdate(BaseModel):
    status: TenantStatus | None = None
    plan_code: PlanCode | None = None


class BusinessRegistration(BaseModel):
    business_name: str = Field(min_length=2, max_length=180)
    owner_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    plan_code: PlanCode = "starter"


class TenantUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    is_admin: bool = False
