from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    organization_name: str | None = Field(default=None, min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Ignorado pelo backend; o primeiro usuário administra somente a própria marcenaria.
    is_admin: bool = False


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    is_active: bool | None = None
    is_admin: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    name: str
    email: EmailStr
    is_active: bool
    is_admin: bool
    is_platform_admin: bool = False
