from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

MaterialKind = Literal["mdf", "hardware", "profile", "accessory", "finish", "service", "other"]
CostCategory = Literal["material", "labor", "freight", "installation", "outsourcing", "tax", "other"]


class SupplierBase(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    contact_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MaterialBase(BaseModel):
    supplier_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=2, max_length=180)
    kind: MaterialKind
    unit: str = Field(default="un", min_length=1, max_length=30)
    unit_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    waste_percent: Decimal = Field(default=0, ge=0, le=100, max_digits=5, decimal_places=2)
    is_active: bool = True


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    supplier_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=2, max_length=180)
    kind: MaterialKind | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    waste_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    is_active: bool | None = None


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProjectCostCreate(BaseModel):
    project_id: int = Field(gt=0)
    material_id: int | None = Field(default=None, gt=0)
    category: CostCategory
    description: str = Field(min_length=2, max_length=500)
    quantity: Decimal = Field(default=1, gt=0, max_digits=12, decimal_places=3)
    unit_cost: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)


class ProjectCostUpdate(BaseModel):
    material_id: int | None = Field(default=None, gt=0)
    category: CostCategory | None = None
    description: str | None = Field(default=None, min_length=2, max_length=500)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class ProjectCostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    material_id: int | None
    category: CostCategory
    description: str
    quantity: Decimal
    unit_cost: Decimal
    total_cost: Decimal
