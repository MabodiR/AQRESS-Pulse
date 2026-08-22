import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.reading import ReadingQuality, SensorReading
from app.models.sensor_type import MeasurementValueType


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset.")
    return value


class TelemetryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: uuid.UUID
    device_uid: str = Field(min_length=1, max_length=128)
    sent_at: datetime
    readings: list[Any] = Field(min_length=1)

    _sent_at_aware = field_validator("sent_at")(require_aware)


class TelemetryReadingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensor_uid: str = Field(min_length=1, max_length=128)
    channel: str = Field(min_length=1, max_length=100)
    recorded_at: datetime
    value: Any
    quality: ReadingQuality = ReadingQuality.GOOD

    _recorded_at_aware = field_validator("recorded_at")(require_aware)


class ReadingResponse(BaseModel):
    id: uuid.UUID
    sensor_id: uuid.UUID
    channel_id: uuid.UUID
    channel: str
    name: str
    value_type: MeasurementValueType
    value: float | str | bool
    unit: str | None
    quality: ReadingQuality
    recorded_at: datetime
    received_at: datetime

    @classmethod
    def from_reading(cls, reading: SensorReading) -> "ReadingResponse":
        definition = reading.sensor_channel.measurement_definition
        return cls(
            id=reading.id,
            sensor_id=reading.sensor_id,
            channel_id=reading.sensor_channel_id,
            channel=definition.key,
            name=reading.sensor_channel.name,
            value_type=definition.value_type,
            value=reading.value,
            unit=reading.unit,
            quality=reading.quality,
            recorded_at=reading.recorded_at,
            received_at=reading.received_at,
        )


class LatestReadingsResponse(BaseModel):
    sensor_id: uuid.UUID
    sensor_uid: str
    readings: list[ReadingResponse]


class ReadingCursorResponse(BaseModel):
    items: list[ReadingResponse]
    next_cursor: str | None
    has_more: bool
