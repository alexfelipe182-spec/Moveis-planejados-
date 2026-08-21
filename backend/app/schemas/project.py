from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

ProjectStatus = Literal["planning", "in_progress", "completed", "cancelled"]


class ProjectBase(BaseModel):
    customer_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    measurements: str | None = Field(default=None, max_length=2000)
    materials: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus = "planning"
    project_date: date | None = None
    photos: list[HttpUrl] = Field(default_factory=list, max_length=20)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    measurements: str | None = Field(default=None, max_length=2000)
    materials: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus | None = None
    project_date: date | None = None
    photos: list[HttpUrl] | None = Field(default=None, max_length=20)


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
