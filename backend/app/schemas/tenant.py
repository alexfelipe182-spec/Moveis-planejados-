from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import UserRead


PlanCode = Literal["starter", "professional", "business"]


class BusinessRegister(BaseModel):
    business_name: str = Field(min_length=2, max_length=160)
    owner_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    plan_code: PlanCode = "starter"


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    plan_code: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TenantUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class BusinessRegisterResponse(BaseModel):
    tenant: TenantRead
    owner: UserRead
