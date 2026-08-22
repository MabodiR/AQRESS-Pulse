import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SiteFields(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)


class SiteCreate(SiteFields):
    pass


class SiteUpdate(SiteFields):
    pass


class StatusUpdate(BaseModel):
    is_active: bool


class SiteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    is_active: bool


class SiteResponse(SiteFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
