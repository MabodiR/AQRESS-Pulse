import builtins
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.sensor import (
    ConfigurationStatus,
    Sensor,
    SensorChannel,
    SensorConfiguration,
    SensorStatus,
)
from app.repositories.device_repository import DeviceRepository
from app.repositories.sensor_repository import SensorRepository
from app.repositories.sensor_type_repository import SensorTypeRepository
from app.schemas.common import PaginatedResponse, Pagination
from app.schemas.sensor import (
    ChannelUpdate,
    ConfigurationResponse,
    SensorCreate,
    SensorResponse,
    SensorUpdate,
)
from app.services.configuration_validation_service import ConfigurationValidationService


class SensorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sensors = SensorRepository(session)
        self.devices = DeviceRepository(session)
        self.sensor_types = SensorTypeRepository(session)

    async def create(self, device_id: uuid.UUID, payload: SensorCreate) -> Sensor:
        try:
            device = await self.devices.get(device_id)
            if device is None:
                raise AppError(status_code=404, code="DEVICE_NOT_FOUND", message="Device was not found.")
            if not device.is_active:
                raise AppError(status_code=409, code="DEVICE_INACTIVE", message="Sensors cannot be added to an inactive Device.")
            sensor_type = await self.sensor_types.get(payload.sensor_type_id)
            if sensor_type is None:
                raise AppError(status_code=422, code="INVALID_SENSOR_TYPE", message="The selected Sensor Type does not exist.")
            if not sensor_type.is_active or not sensor_type.measurements:
                raise AppError(status_code=409, code="SENSOR_TYPE_NOT_READY", message="The selected Sensor Type is not ready for use.")
            ConfigurationValidationService.validate_schema(sensor_type.configuration_schema)
            self._validate_configuration(sensor_type.configuration_schema, payload.configuration)
            if await self.sensors.get_by_device_uid(device_id, payload.sensor_uid):
                raise self._uid_exists()

            sensor = Sensor(device_id=device_id, sensor_type_id=sensor_type.id, sensor_uid=payload.sensor_uid, name=payload.name, description=payload.description, status=SensorStatus.REGISTERED, enabled=True)
            self.session.add(sensor)
            await self.session.flush()
            self.session.add_all([SensorChannel(sensor_id=sensor.id, measurement_definition_id=item.id, name=item.name, unit=item.default_unit, enabled=True) for item in sensor_type.measurements])
            self.session.add(SensorConfiguration(sensor_id=sensor.id, config_version=1, configuration=payload.configuration, status=ConfigurationStatus.PENDING, is_current=True))
            await self.session.commit()
            return await self.get(sensor.id)
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._uid_exists() from exc
        except Exception:
            await self.session.rollback()
            raise

    async def get(self, sensor_id: uuid.UUID) -> Sensor:
        sensor = await self.sensors.get(sensor_id)
        if sensor is None:
            raise AppError(status_code=404, code="SENSOR_NOT_FOUND", message="Sensor was not found.")
        return sensor

    async def list(self, *, page: int, page_size: int, search: str | None, device_id: uuid.UUID | None, site_id: uuid.UUID | None, sensor_type_id: uuid.UUID | None, status: SensorStatus | None, enabled: bool | None) -> PaginatedResponse[SensorResponse]:
        items, total = await self.sensors.list(page=page, page_size=page_size, search=search, device_id=device_id, site_id=site_id, sensor_type_id=sensor_type_id, status=status, enabled=enabled)
        return PaginatedResponse(items=[SensorResponse.model_validate(item) for item in items], pagination=Pagination.create(page=page, page_size=page_size, total_items=total))

    async def list_for_device(self, device_id: uuid.UUID, **filters: object) -> PaginatedResponse[SensorResponse]:
        if await self.devices.get(device_id) is None:
            raise AppError(status_code=404, code="DEVICE_NOT_FOUND", message="Device was not found.")
        return await self.list(device_id=device_id, site_id=None, **filters)  # type: ignore[arg-type]

    async def update(self, sensor_id: uuid.UUID, payload: SensorUpdate) -> Sensor:
        sensor = await self.get(sensor_id)
        sensor.name = payload.name
        sensor.description = payload.description
        self._set_enabled(sensor, payload.enabled)
        await self.session.commit()
        return await self.get(sensor.id)

    async def set_enabled(self, sensor_id: uuid.UUID, enabled: bool) -> Sensor:
        sensor = await self.get(sensor_id)
        self._set_enabled(sensor, enabled)
        await self.session.commit()
        return await self.get(sensor.id)

    async def update_channel(self, sensor_id: uuid.UUID, channel_id: uuid.UUID, payload: ChannelUpdate) -> SensorChannel:
        sensor = await self.get(sensor_id)
        channel = next((item for item in sensor.channels if item.id == channel_id), None)
        if channel is None:
            raise AppError(status_code=404, code="CHANNEL_NOT_FOUND", message="Sensor Channel was not found.")
        channel.name = payload.name
        channel.unit = payload.unit
        channel.enabled = payload.enabled
        await self.session.commit()
        return next(item for item in (await self.get(sensor.id)).channels if item.id == channel_id)

    async def current_configuration(self, sensor_id: uuid.UUID) -> SensorConfiguration:
        await self.get(sensor_id)
        item = await self.sensors.current_configuration(sensor_id)
        if item is None:
            raise AppError(status_code=404, code="CONFIGURATION_NOT_FOUND", message="Current Sensor configuration was not found.")
        return item

    async def configuration_history(
        self, sensor_id: uuid.UUID
    ) -> builtins.list[ConfigurationResponse]:
        await self.get(sensor_id)
        return [ConfigurationResponse.model_validate(item) for item in await self.sensors.configuration_history(sensor_id)]

    async def update_configuration(self, sensor_id: uuid.UUID, configuration: dict[str, object]) -> SensorConfiguration:
        try:
            sensor = await self.sensors.get(sensor_id, lock=True)
            if sensor is None:
                raise AppError(status_code=404, code="SENSOR_NOT_FOUND", message="Sensor was not found.")
            self._validate_configuration(sensor.sensor_type.configuration_schema, configuration)
            current = next(item for item in sensor.configurations if item.is_current)
            next_version = max(item.config_version for item in sensor.configurations) + 1
            current.is_current = False
            current.status = ConfigurationStatus.SUPERSEDED
            await self.session.flush()
            new_configuration = SensorConfiguration(sensor_id=sensor.id, config_version=next_version, configuration=configuration, status=ConfigurationStatus.PENDING, is_current=True)
            self.session.add(new_configuration)
            await self.session.commit()
            await self.session.refresh(new_configuration)
            return new_configuration
        except IntegrityError as exc:
            await self.session.rollback()
            raise AppError(status_code=409, code="CONFIGURATION_VERSION_CONFLICT", message="The configuration changed concurrently; reload and try again.") from exc
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _validate_configuration(schema: dict[str, object], configuration: dict[str, object]) -> None:
        try:
            ConfigurationValidationService.validate_configuration(schema, configuration)
        except AppError as exc:
            raise AppError(status_code=422, code="SENSOR_CONFIGURATION_INVALID", message="Sensor configuration is invalid.", details=exc.details) from exc

    @staticmethod
    def _set_enabled(sensor: Sensor, enabled: bool) -> None:
        sensor.enabled = enabled
        sensor.status = SensorStatus.REGISTERED if enabled else SensorStatus.DISABLED

    @staticmethod
    def _uid_exists() -> AppError:
        return AppError(status_code=409, code="SENSOR_UID_EXISTS", message="This Device already has a Sensor with that UID.")
