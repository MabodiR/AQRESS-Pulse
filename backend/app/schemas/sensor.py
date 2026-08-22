import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.sensor import ConfigurationStatus, SensorStatus
from app.models.sensor_type import InterfaceType


class SensorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensor_type_id: uuid.UUID
    sensor_uid: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    configuration: dict[str, Any]

    @field_validator("sensor_uid")
    @classmethod
    def normalize_uid(cls, value: str) -> str:
        value = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._:-]*", value):
            raise ValueError("Sensor UID contains unsupported characters.")
        return value


class SensorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    enabled: bool


class SensorStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class ChannelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=50)
    enabled: bool


class ConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configuration: dict[str, Any]


class SensorSiteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class DeviceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    device_uid: str
    name: str
    site_id: uuid.UUID
    site: SensorSiteSummary


class SensorTypeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    interface_type: InterfaceType


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sensor_id: uuid.UUID
    measurement_definition_id: uuid.UUID
    key: str
    name: str
    unit: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sensor_id: uuid.UUID
    config_version: int
    configuration: dict[str, Any]
    status: ConfigurationStatus
    is_current: bool
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    applied_at: datetime | None


class SensorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    device_id: uuid.UUID
    sensor_type_id: uuid.UUID
    sensor_uid: str
    name: str
    description: str | None
    status: SensorStatus
    enabled: bool
    created_at: datetime
    updated_at: datetime
    device: DeviceSummary
    sensor_type: SensorTypeSummary
    channels: list[ChannelResponse]
    current_configuration: ConfigurationResponse
