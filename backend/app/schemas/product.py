from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class ProductBase(BaseModel):
    category_id: int
    name: str
    description: str | None = None
    price: Decimal = 0
    image_url: str | None = None
    is_active: bool = True
class ProductCreate(ProductBase): pass
class ProductUpdate(ProductBase): pass
class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
