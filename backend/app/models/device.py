import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.sensor import Sensor
    from app.models.site import Site


class DeviceStatus(str, enum.Enum):
    PROVISIONING = "PROVISIONING"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"


class ConnectionType(str, enum.Enum):
    WIFI = "WIFI"
    ETHERNET = "ETHERNET"
    CELLULAR = "CELLULAR"
    LORA = "LORA"
    OTHER = "OTHER"


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        Index("ix_devices_site_id", "site_id"),
        Index("ix_devices_status", "status"),
        Index("ix_devices_is_active", "is_active"),
        Index("ix_devices_last_seen_at", "last_seen_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False)
    device_uid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    device_type: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str | None] = mapped_column(String(200))
    firmware_version: Mapped[str | None] = mapped_column(String(100))
    connection_type: Mapped[ConnectionType] = mapped_column(Enum(ConnectionType, name="connection_type"), nullable=False)
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus, name="device_status"), nullable=False, default=DeviceStatus.PROVISIONING)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    site: Mapped["Site"] = relationship(back_populates="devices")
    sensors: Mapped[list["Sensor"]] = relationship(back_populates="device")
