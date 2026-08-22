import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.sensor_type import InterfaceType, MeasurementValueType


class MeasurementFields(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    value_type: MeasurementValueType
    default_unit: str | None = Field(default=None, max_length=50)

    @field_validator("key")
    @classmethod
    def normalize_key(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("Measurement key must be a lowercase machine identifier.")
        return value


class MeasurementCreate(MeasurementFields):
    pass


class MeasurementUpdate(MeasurementFields):
    pass


class MeasurementResponse(MeasurementFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sensor_type_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SensorTypeFields(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=200)
    interface_type: InterfaceType
    driver_key: str = Field(min_length=1, max_length=100)
    configuration_schema: dict[str, Any]

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().upper().replace(" ", "_")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            raise ValueError("Code must be an uppercase machine identifier.")
        return value

    @field_validator("driver_key")
    @classmethod
    def normalize_driver_key(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
            raise ValueError("Driver key must be a lowercase machine identifier.")
        return value


class SensorTypeCreate(SensorTypeFields):
    pass


class SensorTypeUpdate(SensorTypeFields):
    pass


class SensorTypeResponse(SensorTypeFields):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    measurements: list[MeasurementResponse] = []
