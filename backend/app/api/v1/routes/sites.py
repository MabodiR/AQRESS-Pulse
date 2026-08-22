import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_writer
from app.db.session import get_db_session
from app.models.device import DeviceStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.device import DeviceResponse
from app.schemas.site import SiteCreate, SiteResponse, SiteUpdate, StatusUpdate
from app.services.device_service import DeviceService
from app.services.site_service import SiteService

router = APIRouter(prefix="/sites", tags=["sites"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Reader = Annotated[User, Depends(get_current_user)]
Writer = Annotated[User, Depends(require_writer)]


@router.get("", response_model=PaginatedResponse[SiteResponse])
async def list_sites(session: Session, _user: Reader, page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 25, search: str | None = None, is_active: bool | None = None) -> PaginatedResponse[SiteResponse]:
    return await SiteService(session).list(page=page, page_size=page_size, search=search, is_active=is_active)


@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreate, session: Session, user: Writer) -> SiteResponse:
    return SiteResponse.model_validate(await SiteService(session).create(payload, user))


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(site_id: uuid.UUID, session: Session, _user: Reader) -> SiteResponse:
    return SiteResponse.model_validate(await SiteService(session).get(site_id))


@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(site_id: uuid.UUID, payload: SiteUpdate, session: Session, _user: Writer) -> SiteResponse:
    return SiteResponse.model_validate(await SiteService(session).update(site_id, payload))


@router.patch("/{site_id}/status", response_model=SiteResponse)
async def update_site_status(site_id: uuid.UUID, payload: StatusUpdate, session: Session, _user: Writer) -> SiteResponse:
    return SiteResponse.model_validate(await SiteService(session).set_active(site_id, payload.is_active))


@router.get("/{site_id}/devices", response_model=PaginatedResponse[DeviceResponse])
async def list_site_devices(site_id: uuid.UUID, session: Session, _user: Reader, page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 25, status_filter: DeviceStatus | None = Query(default=None, alias="status"), is_active: bool | None = None) -> PaginatedResponse[DeviceResponse]:
    await SiteService(session).get(site_id)
    return await DeviceService(session).list(page=page, page_size=page_size, search=None, site_id=site_id, status=status_filter, is_active=is_active)
