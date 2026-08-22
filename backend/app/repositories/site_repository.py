import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.site import Site


class SiteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, **values: object) -> Site:
        site = Site(**values)
        self.session.add(site)
        await self.session.flush()
        await self.session.refresh(site)
        return site

    async def get(self, site_id: uuid.UUID) -> Site | None:
        return await self.session.get(Site, site_id)

    async def list(self, *, page: int, page_size: int, search: str | None, is_active: bool | None) -> tuple[list[Site], int]:
        filters = []
        if search:
            filters.append(or_(Site.name.ilike(f"%{search.strip()}%"), Site.description.ilike(f"%{search.strip()}%")))
        if is_active is not None:
            filters.append(Site.is_active.is_(is_active))
        total = await self.session.scalar(select(func.count()).select_from(Site).where(*filters)) or 0
        result = await self.session.scalars(select(Site).where(*filters).order_by(Site.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return list(result), total
