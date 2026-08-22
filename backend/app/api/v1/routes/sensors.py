import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_writer
from app.db.session import get_db_session
from app.models.sensor import SensorStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.sensor import (
    ChannelResponse,
    ChannelUpdate,
    ConfigurationResponse,
    ConfigurationUpdate,
    SensorCreate,
    SensorResponse,
    SensorStatusUpdate,
    SensorUpdate,
)
from app.services.sensor_service import SensorService

router = APIRouter(tags=["sensors"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Reader = Annotated[User, Depends(get_current_user)]
Writer = Annotated[User, Depends(require_writer)]


@router.get("/sensors", response_model=PaginatedResponse[SensorResponse])
async def list_sensors(session: Session, _user: Reader, page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 25, search: str | None = None, device_id: uuid.UUID | None = None, site_id: uuid.UUID | None = None, sensor_type_id: uuid.UUID | None = None, status_filter: SensorStatus | None = Query(default=None, alias="status"), enabled: bool | None = None) -> PaginatedResponse[SensorResponse]:
    return await SensorService(session).list(page=page, page_size=page_size, search=search, device_id=device_id, site_id=site_id, sensor_type_id=sensor_type_id, status=status_filter, enabled=enabled)


@router.post("/devices/{device_id}/sensors", response_model=SensorResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor(device_id: uuid.UUID, payload: SensorCreate, session: Session, _user: Writer) -> SensorResponse:
    return SensorResponse.model_validate(await SensorService(session).create(device_id, payload))


@router.get("/devices/{device_id}/sensors", response_model=PaginatedResponse[SensorResponse])
async def list_device_sensors(device_id: uuid.UUID, session: Session, _user: Reader, page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 25, search: str | None = None, enabled: bool | None = None, sensor_type_id: uuid.UUID | None = None, status_filter: SensorStatus | None = Query(default=None, alias="status")) -> PaginatedResponse[SensorResponse]:
    return await SensorService(session).list_for_device(device_id, page=page, page_size=page_size, search=search, enabled=enabled, sensor_type_id=sensor_type_id, status=status_filter)


@router.get("/sensors/{sensor_id}", response_model=SensorResponse)
async def get_sensor(sensor_id: uuid.UUID, session: Session, _user: Reader) -> SensorResponse:
    return SensorResponse.model_validate(await SensorService(session).get(sensor_id))


@router.put("/sensors/{sensor_id}", response_model=SensorResponse)
async def update_sensor(sensor_id: uuid.UUID, payload: SensorUpdate, session: Session, _user: Writer) -> SensorResponse:
    return SensorResponse.model_validate(await SensorService(session).update(sensor_id, payload))


@router.patch("/sensors/{sensor_id}/status", response_model=SensorResponse)
async def update_sensor_status(sensor_id: uuid.UUID, payload: SensorStatusUpdate, session: Session, _user: Writer) -> SensorResponse:
    return SensorResponse.model_validate(await SensorService(session).set_enabled(sensor_id, payload.enabled))


@router.get("/sensors/{sensor_id}/configuration", response_model=ConfigurationResponse)
async def get_current_configuration(sensor_id: uuid.UUID, session: Session, _user: Reader) -> ConfigurationResponse:
    return ConfigurationResponse.model_validate(await SensorService(session).current_configuration(sensor_id))


@router.get("/sensors/{sensor_id}/configurations", response_model=list[ConfigurationResponse])
async def get_configuration_history(sensor_id: uuid.UUID, session: Session, _user: Reader) -> list[ConfigurationResponse]:
    return await SensorService(session).configuration_history(sensor_id)


@router.put("/sensors/{sensor_id}/configuration", response_model=ConfigurationResponse)
async def update_configuration(sensor_id: uuid.UUID, payload: ConfigurationUpdate, session: Session, _user: Writer) -> ConfigurationResponse:
    return ConfigurationResponse.model_validate(await SensorService(session).update_configuration(sensor_id, payload.configuration))


@router.put("/sensors/{sensor_id}/channels/{channel_id}", response_model=ChannelResponse)
async def update_channel(sensor_id: uuid.UUID, channel_id: uuid.UUID, payload: ChannelUpdate, session: Session, _user: Writer) -> ChannelResponse:
    return ChannelResponse.model_validate(await SensorService(session).update_channel(sensor_id, channel_id, payload))
