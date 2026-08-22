import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.device import ConnectionType, DeviceStatus
from app.schemas.site import SiteSummary


class DeviceFields(BaseModel):
    site_id: uuid.UUID
    device_uid: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    device_type: str = Field(min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    firmware_version: str | None = Field(default=None, max_length=100)
    connection_type: ConnectionType

    @field_validator("device_uid")
    @classmethod
    def validate_uid(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._:-]*", value):
            raise ValueError("Device UID may contain letters, numbers, dots, underscores, colons, and hyphens.")
        return value

    @field_validator("device_type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        value = value.strip().upper().replace(" ", "_")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9_]*", value):
            raise ValueError("Device type must be an uppercase identifier.")
        return value


class DeviceCreate(DeviceFields):
    pass


class DeviceUpdate(DeviceFields):
    pass


class DeviceResponse(DeviceFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    site: SiteSummary
    status: DeviceStatus
    is_active: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
