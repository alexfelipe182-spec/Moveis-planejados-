from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerPortalLogin(BaseModel):
    business_slug: str = Field(min_length=1, max_length=180)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class CustomerPortalActivate(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=8, max_length=72)


class CustomerPortalResetRequest(BaseModel):
    business_slug: str = Field(min_length=1, max_length=180)
    email: EmailStr


class CustomerPortalResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=8, max_length=72)


class CustomerPortalMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    quote_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)


class CustomerPortalMessageRead(CustomerPortalMessageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    author_type: Literal["customer", "staff"]
    created_at: datetime


class CustomerPortalQuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    description: str
    measurements: str | None = None
    materials: str | None = None
    total: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerPortalProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    quote_id: int | None = None
    name: str
    description: str | None = None
    status: str
    project_date: date | None = None
    photos: list = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CustomerPortalDecision(BaseModel):
    status: Literal["accepted", "declined"]


class CustomerPortalAdminMessage(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    quote_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
