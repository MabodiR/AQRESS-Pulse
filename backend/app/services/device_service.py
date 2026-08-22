import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.device import Device, DeviceStatus
from app.repositories.device_repository import DeviceRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.common import PaginatedResponse, Pagination
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate


class DeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.sites = SiteRepository(session)

    async def _require_site(self, site_id: uuid.UUID) -> None:
        if await self.sites.get(site_id) is None:
            raise AppError(status_code=422, code="INVALID_SITE", message="The selected site does not exist.")

    async def create(self, payload: DeviceCreate) -> Device:
        await self._require_site(payload.site_id)
        if await self.devices.get_by_uid(payload.device_uid):
            raise self._uid_exists()
        try:
            device = await self.devices.create(**payload.model_dump(), status=DeviceStatus.PROVISIONING)
            await self.session.commit()
            return device
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._uid_exists() from exc

    async def get(self, device_id: uuid.UUID) -> Device:
        device = await self.devices.get(device_id)
        if device is None:
            raise AppError(status_code=404, code="DEVICE_NOT_FOUND", message="Device was not found.")
        return device

    async def list(self, *, page: int, page_size: int, search: str | None, site_id: uuid.UUID | None, status: DeviceStatus | None, is_active: bool | None) -> PaginatedResponse[DeviceResponse]:
        items, total = await self.devices.list(page=page, page_size=page_size, search=search, site_id=site_id, status=status, is_active=is_active)
        return PaginatedResponse(items=[DeviceResponse.model_validate(item) for item in items], pagination=Pagination.create(page=page, page_size=page_size, total_items=total))

    async def update(self, device_id: uuid.UUID, payload: DeviceUpdate) -> Device:
        device = await self.get(device_id)
        await self._require_site(payload.site_id)
        duplicate = await self.devices.get_by_uid(payload.device_uid)
        if duplicate and duplicate.id != device.id:
            raise self._uid_exists()
        for key, value in payload.model_dump().items():
            setattr(device, key, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._uid_exists() from exc
        return await self.get(device.id)

    async def set_active(self, device_id: uuid.UUID, is_active: bool) -> Device:
        device = await self.get(device_id)
        device.is_active = is_active
        device.status = DeviceStatus.PROVISIONING if is_active else DeviceStatus.DISABLED
        await self.session.commit()
        return await self.get(device.id)

    @staticmethod
    def _uid_exists() -> AppError:
        return AppError(status_code=409, code="DEVICE_UID_EXISTS", message="A device with this UID already exists.")
