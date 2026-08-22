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
    Integer,
    String,
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
    from app.models.reading import SensorReading
    from app.models.sensor_type import MeasurementDefinition, SensorType


class SensorStatus(str, enum.Enum):
    REGISTERED = "REGISTERED"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class ConfigurationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PUBLISHED = "PUBLISHED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class Sensor(Base):
    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("device_id", "sensor_uid", name="uq_sensors_device_id_sensor_uid"),
        Index("ix_sensors_device_id", "device_id"),
        Index("ix_sensors_sensor_type_id", "sensor_type_id"),
        Index("ix_sensors_status", "status"),
        Index("ix_sensors_enabled", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False)
    sensor_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sensor_types.id", ondelete="RESTRICT"), nullable=False)
    sensor_uid: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[SensorStatus] = mapped_column(Enum(SensorStatus, name="sensor_status"), nullable=False, default=SensorStatus.REGISTERED)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    device: Mapped["Device"] = relationship(back_populates="sensors")
    sensor_type: Mapped["SensorType"] = relationship(back_populates="sensors")
    channels: Mapped[list["SensorChannel"]] = relationship(back_populates="sensor", cascade="all, delete-orphan", order_by="SensorChannel.name")
    configurations: Mapped[list["SensorConfiguration"]] = relationship(back_populates="sensor", cascade="all, delete-orphan", order_by="SensorConfiguration.config_version.desc()")
    readings: Mapped[list["SensorReading"]] = relationship(back_populates="sensor")

    @property
    def current_configuration(self) -> "SensorConfiguration":
        return next(item for item in self.configurations if item.is_current)


class SensorChannel(Base):
    __tablename__ = "sensor_channels"
    __table_args__ = (
        UniqueConstraint("sensor_id", "measurement_definition_id", name="uq_sensor_channels_sensor_id_measurement_definition_id"),
        Index("ix_sensor_channels_sensor_id", "sensor_id"),
        Index("ix_sensor_channels_measurement_definition_id", "measurement_definition_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sensor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False)
    measurement_definition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("measurement_definitions.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    sensor: Mapped[Sensor] = relationship(back_populates="channels")
    measurement_definition: Mapped["MeasurementDefinition"] = relationship(back_populates="sensor_channels")
    readings: Mapped[list["SensorReading"]] = relationship(back_populates="sensor_channel")

    @property
    def key(self) -> str:
        return self.measurement_definition.key


class SensorConfiguration(Base):
    __tablename__ = "sensor_configurations"
    __table_args__ = (
        UniqueConstraint("sensor_id", "config_version", name="uq_sensor_configurations_sensor_id_config_version"),
        Index("ix_sensor_configurations_sensor_id", "sensor_id"),
        Index("uq_sensor_configurations_current", "sensor_id", unique=True, postgresql_where=text("is_current")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sensor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[ConfigurationStatus] = mapped_column(Enum(ConfigurationStatus, name="sensor_configuration_status"), nullable=False, default=ConfigurationStatus.PENDING)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sensor: Mapped[Sensor] = relationship(back_populates="configurations")
