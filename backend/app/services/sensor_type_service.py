import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.sensor_type import InterfaceType, MeasurementDefinition, SensorType
from app.repositories.sensor_type_repository import SensorTypeRepository
from app.schemas.common import PaginatedResponse, Pagination
from app.schemas.sensor_type import (
    MeasurementCreate,
    MeasurementUpdate,
    SensorTypeCreate,
    SensorTypeResponse,
    SensorTypeUpdate,
)
from app.services.configuration_validation_service import ConfigurationValidationService


class SensorTypeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.catalogue = SensorTypeRepository(session)

    async def create(self, payload: SensorTypeCreate) -> SensorType:
        ConfigurationValidationService.validate_schema(payload.configuration_schema)
        await self._check_identity(payload.code, payload.driver_key)
        try:
            item = await self.catalogue.create(**payload.model_dump())
            await self.session.commit()
            return item
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._identity_error(exc) from exc

    async def get(self, item_id: uuid.UUID) -> SensorType:
        item = await self.catalogue.get(item_id)
        if item is None:
            raise AppError(status_code=404, code="SENSOR_TYPE_NOT_FOUND", message="Sensor Type was not found.")
        return item

    async def list(self, *, page: int, page_size: int, search: str | None, interface_type: InterfaceType | None, is_active: bool | None) -> PaginatedResponse[SensorTypeResponse]:
        items, total = await self.catalogue.list(page=page, page_size=page_size, search=search, interface_type=interface_type, is_active=is_active)
        return PaginatedResponse(items=[SensorTypeResponse.model_validate(item) for item in items], pagination=Pagination.create(page=page, page_size=page_size, total_items=total))

    async def update(self, item_id: uuid.UUID, payload: SensorTypeUpdate) -> SensorType:
        item = await self.get(item_id)
        ConfigurationValidationService.validate_schema(payload.configuration_schema)
        await self._check_identity(payload.code, payload.driver_key, excluding=item.id)
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._identity_error(exc) from exc
        return await self.get(item.id)

    async def set_active(self, item_id: uuid.UUID, is_active: bool) -> SensorType:
        item = await self.get(item_id)
        item.is_active = is_active
        await self.session.commit()
        return await self.get(item.id)

    async def create_measurement(self, sensor_type_id: uuid.UUID, payload: MeasurementCreate) -> MeasurementDefinition:
        await self.get(sensor_type_id)
        if await self.catalogue.get_measurement_by_key(sensor_type_id, payload.key):
            raise self._measurement_exists()
        try:
            item = await self.catalogue.create_measurement(sensor_type_id, **payload.model_dump())
            await self.session.commit()
            return item
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._measurement_exists() from exc

    async def update_measurement(self, sensor_type_id: uuid.UUID, measurement_id: uuid.UUID, payload: MeasurementUpdate) -> MeasurementDefinition:
        await self.get(sensor_type_id)
        item = await self.catalogue.get_measurement(sensor_type_id, measurement_id)
        if item is None:
            raise AppError(status_code=404, code="MEASUREMENT_NOT_FOUND", message="Measurement Definition was not found.")
        duplicate = await self.catalogue.get_measurement_by_key(sensor_type_id, payload.key)
        if duplicate and duplicate.id != item.id:
            raise self._measurement_exists()
        for key, value in payload.model_dump().items():
            setattr(item, key, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._measurement_exists() from exc
        await self.session.refresh(item)
        return item

    async def _check_identity(self, code: str, driver_key: str, excluding: uuid.UUID | None = None) -> None:
        by_code = await self.catalogue.get_by_code(code)
        if by_code and by_code.id != excluding:
            raise AppError(status_code=409, code="SENSOR_TYPE_CODE_EXISTS", message="A Sensor Type with this code already exists.")
        by_driver = await self.catalogue.get_by_driver_key(driver_key)
        if by_driver and by_driver.id != excluding:
            raise AppError(status_code=409, code="DRIVER_KEY_EXISTS", message="A Sensor Type with this driver key already exists.")

    @staticmethod
    def _identity_error(exc: IntegrityError) -> AppError:
        if "driver_key" in str(exc.orig):
            return AppError(status_code=409, code="DRIVER_KEY_EXISTS", message="A Sensor Type with this driver key already exists.")
        return AppError(status_code=409, code="SENSOR_TYPE_CODE_EXISTS", message="A Sensor Type with this code already exists.")

    @staticmethod
    def _measurement_exists() -> AppError:
        return AppError(status_code=409, code="MEASUREMENT_KEY_EXISTS", message="This Sensor Type already has a measurement with that key.")
