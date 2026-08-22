import builtins
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import Device
from app.models.sensor import (
    Sensor,
    SensorChannel,
    SensorConfiguration,
    SensorStatus,
)
from app.models.sensor_type import SensorType

SENSOR_LOAD = (
    selectinload(Sensor.device).selectinload(Device.site),
    selectinload(Sensor.sensor_type).selectinload(SensorType.measurements),
    selectinload(Sensor.channels).selectinload(SensorChannel.measurement_definition),
    selectinload(Sensor.configurations),
)


class SensorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, sensor_id: uuid.UUID, *, lock: bool = False) -> Sensor | None:
        statement = select(Sensor).options(*SENSOR_LOAD).where(Sensor.id == sensor_id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_by_device_uid(self, device_id: uuid.UUID, sensor_uid: str) -> Sensor | None:
        return await self.session.scalar(select(Sensor).where(Sensor.device_id == device_id, Sensor.sensor_uid == sensor_uid))

    async def list(self, *, page: int, page_size: int, search: str | None, device_id: uuid.UUID | None, site_id: uuid.UUID | None, sensor_type_id: uuid.UUID | None, status: SensorStatus | None, enabled: bool | None) -> tuple[list[Sensor], int]:
        filters = []
        if search:
            value = f"%{search.strip()}%"
            filters.append(or_(Sensor.sensor_uid.ilike(value), Sensor.name.ilike(value)))
        if device_id:
            filters.append(Sensor.device_id == device_id)
        if site_id:
            filters.append(Device.site_id == site_id)
        if sensor_type_id:
            filters.append(Sensor.sensor_type_id == sensor_type_id)
        if status:
            filters.append(Sensor.status == status)
        if enabled is not None:
            filters.append(Sensor.enabled.is_(enabled))
        base = select(Sensor).join(Device).where(*filters)
        total = await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0
        result = await self.session.scalars(base.options(*SENSOR_LOAD).order_by(Sensor.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return list(result.unique()), total

    async def configuration_history(
        self, sensor_id: uuid.UUID
    ) -> builtins.list[SensorConfiguration]:
        result = await self.session.scalars(select(SensorConfiguration).where(SensorConfiguration.sensor_id == sensor_id).order_by(SensorConfiguration.config_version.desc()))
        return list(result)

    async def current_configuration(self, sensor_id: uuid.UUID) -> SensorConfiguration | None:
        return await self.session.scalar(select(SensorConfiguration).where(SensorConfiguration.sensor_id == sensor_id, SensorConfiguration.is_current.is_(True)))
