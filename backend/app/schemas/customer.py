from pydantic import BaseModel, ConfigDict, EmailStr

class CustomerBase(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
class CustomerCreate(CustomerBase): pass
class CustomerUpdate(CustomerBase): pass
class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
