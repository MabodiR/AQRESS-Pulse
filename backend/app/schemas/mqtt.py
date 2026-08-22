import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MqttCredentialStatusResponse(BaseModel):
    provisioned: bool
    state: Literal["NOT_PROVISIONED", "ACTIVE", "REVOKED"]
    username: str | None = None
    is_active: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None


class MqttCredentialSecretResponse(BaseModel):
    username: str
    password: str
    created_at: datetime
    rotated_at: datetime | None = None


class HeartbeatPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_uid: str
    timestamp: datetime
    status: Literal["ONLINE"]
    uptime_seconds: int = Field(ge=0)
    firmware_version: str | None = Field(default=None, max_length=100)
    wifi_rssi: int | None = None
    free_memory: int | None = Field(default=None, ge=0)


class ConfigurationAckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sensor_uid: str
    configuration_version: int = Field(ge=1)
    status: Literal["APPLIED", "FAILED"]
    error: str | None = Field(default=None, max_length=500)


class ConfigurationAckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: uuid.UUID
    device_uid: str
    timestamp: datetime
    results: list[ConfigurationAckResult] = Field(min_length=1)


class DeviceConfigurationChannel(BaseModel):
    key: str
    enabled: bool
    unit: str | None


class DeviceSensorConfiguration(BaseModel):
    sensor_uid: str
    driver_key: str
    enabled: bool
    configuration_version: int
    configuration: dict[str, Any]
    channels: list[DeviceConfigurationChannel]


class DeviceConfigurationSnapshot(BaseModel):
    message_id: uuid.UUID
    device_uid: str
    generated_at: datetime
    sensors: list[DeviceSensorConfiguration]


class ConfigurationSyncResponse(BaseModel):
    message_id: uuid.UUID
    topic: str
    sensor_count: int
    published_configuration_count: int
