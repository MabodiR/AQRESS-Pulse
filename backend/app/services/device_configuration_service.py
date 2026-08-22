import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.security import utc_now
from app.models.device import Device
from app.models.sensor import ConfigurationStatus, Sensor, SensorChannel
from app.mqtt.publisher import MqttPublisher, MqttPublishError
from app.mqtt.topics import config_topic
from app.repositories.device_repository import DeviceRepository
from app.schemas.mqtt import (
    ConfigurationSyncResponse,
    DeviceConfigurationChannel,
    DeviceConfigurationSnapshot,
    DeviceSensorConfiguration,
)

logger = logging.getLogger(__name__)


class DeviceConfigurationService:
    def __init__(self, session: AsyncSession, publisher: MqttPublisher | None = None) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.publisher = publisher or MqttPublisher()

    async def synchronize(self, device_id: uuid.UUID) -> ConfigurationSyncResponse:
        device = await self.devices.get(device_id)
        if device is None:
            raise AppError(status_code=404, code="DEVICE_NOT_FOUND", message="Device was not found.")
        if not device.is_active:
            raise AppError(status_code=409, code="DEVICE_INACTIVE", message="An inactive Device cannot receive configuration.")
        snapshot, configurations = await self.build_snapshot(device)
        if not configurations:
            raise AppError(status_code=409, code="NO_SENSOR_CONFIGURATION", message="This Device has no current Sensor configurations to synchronize.")
        topic = config_topic(device.device_uid)
        try:
            await asyncio.to_thread(
                self.publisher.publish,
                topic,
                snapshot.model_dump_json(),
                qos=1,
                retain=True,
            )
        except MqttPublishError as exc:
            await self.session.rollback()
            raise AppError(status_code=503, code="MQTT_PUBLISH_FAILED", message="Device configuration could not be published.") from exc
        now = utc_now()
        changed = 0
        for configuration in configurations:
            if configuration.status != ConfigurationStatus.APPLIED:
                configuration.status = ConfigurationStatus.PUBLISHED
                configuration.published_at = now
                configuration.applied_at = None
                changed += 1
        await self.session.commit()
        logger.info("Device configuration published", extra={"device_uid": device.device_uid, "message_id": str(snapshot.message_id), "sensor_count": len(snapshot.sensors)})
        return ConfigurationSyncResponse(
            message_id=snapshot.message_id,
            topic=topic,
            sensor_count=len(snapshot.sensors),
            published_configuration_count=changed,
        )

    async def build_snapshot(self, device: Device) -> tuple[DeviceConfigurationSnapshot, list]:
        result = await self.session.scalars(
            select(Sensor)
            .options(
                selectinload(Sensor.sensor_type),
                selectinload(Sensor.channels).selectinload(SensorChannel.measurement_definition),
                selectinload(Sensor.configurations),
            )
            .where(Sensor.device_id == device.id)
            .order_by(Sensor.sensor_uid)
        )
        sensors = list(result.unique())
        configurations = [sensor.current_configuration for sensor in sensors]
        snapshot = DeviceConfigurationSnapshot(
            message_id=uuid.uuid4(),
            device_uid=device.device_uid,
            generated_at=utc_now(),
            sensors=[
                DeviceSensorConfiguration(
                    sensor_uid=sensor.sensor_uid,
                    driver_key=sensor.sensor_type.driver_key,
                    enabled=sensor.enabled,
                    configuration_version=sensor.current_configuration.config_version,
                    configuration=sensor.current_configuration.configuration,
                    channels=[
                        DeviceConfigurationChannel(key=channel.key, enabled=channel.enabled, unit=channel.unit)
                        for channel in sensor.channels
                    ],
                )
                for sensor in sensors
            ],
        )
        return snapshot, configurations
