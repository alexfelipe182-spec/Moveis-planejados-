from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: int | None
    description: str
    created_at: datetime
