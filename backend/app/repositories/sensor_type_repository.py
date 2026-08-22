import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.sensor_type import InterfaceType, MeasurementDefinition, SensorType


class SensorTypeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **values: object) -> SensorType:
        item = SensorType(**values)
        self.session.add(item)
        await self.session.flush()
        return await self.get(item.id)  # type: ignore[return-value]

    async def get(self, item_id: uuid.UUID) -> SensorType | None:
        return await self.session.scalar(select(SensorType).options(selectinload(SensorType.measurements)).where(SensorType.id == item_id))

    async def get_by_code(self, code: str) -> SensorType | None:
        return await self.session.scalar(select(SensorType).options(selectinload(SensorType.measurements)).where(SensorType.code == code))

    async def get_by_driver_key(self, key: str) -> SensorType | None:
        return await self.session.scalar(select(SensorType).where(SensorType.driver_key == key))

    async def list(self, *, page: int, page_size: int, search: str | None, interface_type: InterfaceType | None, is_active: bool | None) -> tuple[list[SensorType], int]:
        filters = []
        if search:
            value = f"%{search.strip()}%"
            filters.append(or_(SensorType.name.ilike(value), SensorType.code.ilike(value), SensorType.manufacturer.ilike(value), SensorType.model.ilike(value)))
        if interface_type:
            filters.append(SensorType.interface_type == interface_type)
        if is_active is not None:
            filters.append(SensorType.is_active.is_(is_active))
        total = await self.session.scalar(select(func.count()).select_from(SensorType).where(*filters)) or 0
        items = await self.session.scalars(select(SensorType).options(selectinload(SensorType.measurements)).where(*filters).order_by(SensorType.name.asc()).offset((page - 1) * page_size).limit(page_size))
        return list(items), total

    async def get_measurement(self, sensor_type_id: uuid.UUID, measurement_id: uuid.UUID) -> MeasurementDefinition | None:
        return await self.session.scalar(select(MeasurementDefinition).where(MeasurementDefinition.id == measurement_id, MeasurementDefinition.sensor_type_id == sensor_type_id))

    async def get_measurement_by_key(self, sensor_type_id: uuid.UUID, key: str) -> MeasurementDefinition | None:
        return await self.session.scalar(select(MeasurementDefinition).where(MeasurementDefinition.sensor_type_id == sensor_type_id, MeasurementDefinition.key == key))

    async def create_measurement(self, sensor_type_id: uuid.UUID, **values: object) -> MeasurementDefinition:
        item = MeasurementDefinition(sensor_type_id=sensor_type_id, **values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item
