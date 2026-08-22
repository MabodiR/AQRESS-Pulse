import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.device import Device
    from app.models.sensor import Sensor, SensorChannel


class ReadingQuality(str, enum.Enum):
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(value_numeric, value_text, value_boolean) = 1",
            name="ck_sensor_readings_exactly_one_value",
        ),
        CheckConstraint(
            "reading_index >= 0", name="ck_sensor_readings_reading_index_nonnegative"
        ),
        UniqueConstraint(
            "device_id",
            "message_id",
            "reading_index",
            name="uq_sensor_readings_device_message_index",
        ),
        Index(
            "ix_sensor_readings_channel_recorded",
            "sensor_channel_id",
            text("recorded_at DESC"),
        ),
        Index(
            "ix_sensor_readings_sensor_recorded",
            "sensor_id",
            text("recorded_at DESC"),
        ),
        Index(
            "ix_sensor_readings_device_recorded",
            "device_id",
            text("recorded_at DESC"),
        ),
        Index("ix_sensor_readings_recorded_at", text("recorded_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sensor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sensor_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensor_channels.id", ondelete="RESTRICT"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reading_index: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    value_numeric: Mapped[float | None] = mapped_column(Double)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    unit: Mapped[str | None] = mapped_column(Text)
    quality: Mapped[ReadingQuality] = mapped_column(
        Enum(ReadingQuality, name="reading_quality"),
        nullable=False,
        default=ReadingQuality.GOOD,
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    device: Mapped["Device"] = relationship(back_populates="readings")
    sensor: Mapped["Sensor"] = relationship(back_populates="readings")
    sensor_channel: Mapped["SensorChannel"] = relationship(back_populates="readings")

    @property
    def value(self) -> float | str | bool:
        if self.value_numeric is not None:
            return self.value_numeric
        if self.value_text is not None:
            return self.value_text
        if self.value_boolean is not None:
            return self.value_boolean
        raise ValueError("Sensor Reading has no typed value.")
