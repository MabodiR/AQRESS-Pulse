import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import Device, DeviceStatus


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **values: object) -> Device:
        device = Device(**values)
        self.session.add(device)
        await self.session.flush()
        return await self.get(device.id)  # type: ignore[return-value]

    async def get(self, device_id: uuid.UUID) -> Device | None:
        return await self.session.scalar(select(Device).options(selectinload(Device.site)).where(Device.id == device_id))

    async def get_by_uid(self, uid: str) -> Device | None:
        return await self.session.scalar(select(Device).where(Device.device_uid == uid))

    async def list(self, *, page: int, page_size: int, search: str | None, site_id: uuid.UUID | None, status: DeviceStatus | None, is_active: bool | None) -> tuple[list[Device], int]:
        filters = []
        if search:
            value = f"%{search.strip()}%"
            filters.append(or_(Device.device_uid.ilike(value), Device.name.ilike(value)))
        if site_id:
            filters.append(Device.site_id == site_id)
        if status:
            filters.append(Device.status == status)
        if is_active is not None:
            filters.append(Device.is_active.is_(is_active))
        total = await self.session.scalar(select(func.count()).select_from(Device).where(*filters)) or 0
        result = await self.session.scalars(select(Device).options(selectinload(Device.site)).where(*filters).order_by(Device.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return list(result), total
