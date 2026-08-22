import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin
from app.db.session import get_db_session
from app.models.sensor_type import InterfaceType
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.sensor_type import (
    MeasurementCreate,
    MeasurementResponse,
    MeasurementUpdate,
    SensorTypeCreate,
    SensorTypeResponse,
    SensorTypeUpdate,
)
from app.schemas.site import StatusUpdate
from app.services.sensor_type_service import SensorTypeService

router = APIRouter(prefix="/sensor-types", tags=["sensor-types"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Reader = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_admin)]


@router.get("", response_model=PaginatedResponse[SensorTypeResponse])
async def list_sensor_types(session: Session, _user: Reader, page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 25, search: str | None = None, interface_type: InterfaceType | None = None, is_active: bool | None = None) -> PaginatedResponse[SensorTypeResponse]:
    return await SensorTypeService(session).list(page=page, page_size=page_size, search=search, interface_type=interface_type, is_active=is_active)


@router.post("", response_model=SensorTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor_type(payload: SensorTypeCreate, session: Session, _admin: Admin) -> SensorTypeResponse:
    return SensorTypeResponse.model_validate(await SensorTypeService(session).create(payload))


@router.get("/{sensor_type_id}", response_model=SensorTypeResponse)
async def get_sensor_type(sensor_type_id: uuid.UUID, session: Session, _user: Reader) -> SensorTypeResponse:
    return SensorTypeResponse.model_validate(await SensorTypeService(session).get(sensor_type_id))


@router.put("/{sensor_type_id}", response_model=SensorTypeResponse)
async def update_sensor_type(sensor_type_id: uuid.UUID, payload: SensorTypeUpdate, session: Session, _admin: Admin) -> SensorTypeResponse:
    return SensorTypeResponse.model_validate(await SensorTypeService(session).update(sensor_type_id, payload))


@router.patch("/{sensor_type_id}/status", response_model=SensorTypeResponse)
async def update_sensor_type_status(sensor_type_id: uuid.UUID, payload: StatusUpdate, session: Session, _admin: Admin) -> SensorTypeResponse:
    return SensorTypeResponse.model_validate(await SensorTypeService(session).set_active(sensor_type_id, payload.is_active))


@router.get("/{sensor_type_id}/measurements", response_model=list[MeasurementResponse])
async def list_measurements(sensor_type_id: uuid.UUID, session: Session, _user: Reader) -> list[MeasurementResponse]:
    item = await SensorTypeService(session).get(sensor_type_id)
    return [MeasurementResponse.model_validate(value) for value in item.measurements]


@router.post("/{sensor_type_id}/measurements", response_model=MeasurementResponse, status_code=status.HTTP_201_CREATED)
async def create_measurement(sensor_type_id: uuid.UUID, payload: MeasurementCreate, session: Session, _admin: Admin) -> MeasurementResponse:
    return MeasurementResponse.model_validate(await SensorTypeService(session).create_measurement(sensor_type_id, payload))


@router.put("/{sensor_type_id}/measurements/{measurement_id}", response_model=MeasurementResponse)
async def update_measurement(sensor_type_id: uuid.UUID, measurement_id: uuid.UUID, payload: MeasurementUpdate, session: Session, _admin: Admin) -> MeasurementResponse:
    return MeasurementResponse.model_validate(await SensorTypeService(session).update_measurement(sensor_type_id, measurement_id, payload))
