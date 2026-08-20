from decimal import Decimal
from pydantic import BaseModel, ConfigDict

class QuoteBase(BaseModel):
    customer_id: int
    description: str
    total: Decimal = 0
    status: str = "pending"
class QuoteCreate(QuoteBase): pass
class QuoteUpdate(QuoteBase): pass
class QuoteRead(QuoteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
