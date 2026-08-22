import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.site import Site
from app.models.user import User
from app.repositories.site_repository import SiteRepository
from app.schemas.common import PaginatedResponse, Pagination
from app.schemas.site import SiteCreate, SiteResponse, SiteUpdate


class SiteService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sites = SiteRepository(session)

    async def create(self, payload: SiteCreate, user: User) -> Site:
        site = await self.sites.create(**payload.model_dump(), created_by_user_id=user.id)
        await self.session.commit()
        return site

    async def get(self, site_id: uuid.UUID) -> Site:
        site = await self.sites.get(site_id)
        if site is None:
            raise AppError(status_code=404, code="SITE_NOT_FOUND", message="Site was not found.")
        return site

    async def list(self, *, page: int, page_size: int, search: str | None, is_active: bool | None) -> PaginatedResponse[SiteResponse]:
        items, total = await self.sites.list(page=page, page_size=page_size, search=search, is_active=is_active)
        return PaginatedResponse(items=[SiteResponse.model_validate(item) for item in items], pagination=Pagination.create(page=page, page_size=page_size, total_items=total))

    async def update(self, site_id: uuid.UUID, payload: SiteUpdate) -> Site:
        site = await self.get(site_id)
        for key, value in payload.model_dump().items():
            setattr(site, key, value)
        await self.session.commit()
        await self.session.refresh(site)
        return site

    async def set_active(self, site_id: uuid.UUID, is_active: bool) -> Site:
        site = await self.get(site_id)
        site.is_active = is_active
        await self.session.commit()
        await self.session.refresh(site)
        return site
