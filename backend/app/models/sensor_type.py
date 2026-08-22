import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.sensor import Sensor, SensorChannel


class InterfaceType(str, enum.Enum):
    GPIO = "GPIO"
    ADC = "ADC"
    I2C = "I2C"
    ONE_WIRE = "ONE_WIRE"


class MeasurementValueType(str, enum.Enum):
    NUMERIC = "NUMERIC"
    BOOLEAN = "BOOLEAN"
    TEXT = "TEXT"


class SensorType(Base):
    __tablename__ = "sensor_types"
    __table_args__ = (
        Index("ix_sensor_types_name", "name"),
        Index("ix_sensor_types_interface_type", "interface_type"),
        Index("ix_sensor_types_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    interface_type: Mapped[InterfaceType] = mapped_column(Enum(InterfaceType, name="sensor_interface_type"), nullable=False)
    driver_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    configuration_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    measurements: Mapped[list["MeasurementDefinition"]] = relationship(back_populates="sensor_type", cascade="all, delete-orphan", order_by="MeasurementDefinition.name")
    sensors: Mapped[list["Sensor"]] = relationship(back_populates="sensor_type")


class MeasurementDefinition(Base):
    __tablename__ = "measurement_definitions"
    __table_args__ = (
        UniqueConstraint("sensor_type_id", "key", name="uq_measurement_definitions_sensor_type_id_key"),
        Index("ix_measurement_definitions_sensor_type_id", "sensor_type_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sensor_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sensor_types.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[MeasurementValueType] = mapped_column(Enum(MeasurementValueType, name="measurement_value_type"), nullable=False)
    default_unit: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    sensor_type: Mapped[SensorType] = relationship(back_populates="measurements")
    sensor_channels: Mapped[list["SensorChannel"]] = relationship(back_populates="measurement_definition")
