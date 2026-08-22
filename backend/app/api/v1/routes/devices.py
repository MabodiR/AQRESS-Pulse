import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_admin, require_writer
from app.db.session import get_db_session
from app.models.device import DeviceStatus
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate
from app.schemas.mqtt import (
    ConfigurationSyncResponse,
    MqttCredentialSecretResponse,
    MqttCredentialStatusResponse,
)
from app.schemas.site import StatusUpdate
from app.services.device_configuration_service import DeviceConfigurationService
from app.services.device_service import DeviceService
from app.services.mqtt_credential_service import MqttCredentialService

router = APIRouter(prefix="/devices", tags=["devices"])
Session = Annotated[AsyncSession, Depends(get_db_session)]
Reader = Annotated[User, Depends(get_current_user)]
Writer = Annotated[User, Depends(require_writer)]
Admin = Annotated[User, Depends(require_admin)]


@router.get("", response_model=PaginatedResponse[DeviceResponse])
async def list_devices(session: Session, _user: Reader, page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 25, search: str | None = None, site_id: uuid.UUID | None = None, status_filter: DeviceStatus | None = Query(default=None, alias="status"), is_active: bool | None = None) -> PaginatedResponse[DeviceResponse]:
    return await DeviceService(session).list(page=page, page_size=page_size, search=search, site_id=site_id, status=status_filter, is_active=is_active)


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(payload: DeviceCreate, session: Session, _user: Writer) -> DeviceResponse:
    return DeviceResponse.model_validate(await DeviceService(session).create(payload))


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: uuid.UUID, session: Session, _user: Reader) -> DeviceResponse:
    return DeviceResponse.model_validate(await DeviceService(session).get(device_id))


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(device_id: uuid.UUID, payload: DeviceUpdate, session: Session, _user: Writer) -> DeviceResponse:
    return DeviceResponse.model_validate(await DeviceService(session).update(device_id, payload))


@router.patch("/{device_id}/status", response_model=DeviceResponse)
async def update_device_status(device_id: uuid.UUID, payload: StatusUpdate, session: Session, _user: Writer) -> DeviceResponse:
    return DeviceResponse.model_validate(await DeviceService(session).set_active(device_id, payload.is_active))


@router.get("/{device_id}/mqtt-credentials/status", response_model=MqttCredentialStatusResponse)
async def mqtt_credential_status(device_id: uuid.UUID, session: Session, _user: Reader) -> MqttCredentialStatusResponse:
    return await MqttCredentialService(session).status(device_id)


@router.post("/{device_id}/mqtt-credentials", response_model=MqttCredentialSecretResponse, status_code=status.HTTP_201_CREATED)
async def provision_mqtt_credentials(device_id: uuid.UUID, session: Session, _user: Admin) -> MqttCredentialSecretResponse:
    return await MqttCredentialService(session).provision(device_id)


@router.post("/{device_id}/mqtt-credentials/rotate", response_model=MqttCredentialSecretResponse)
async def rotate_mqtt_credentials(device_id: uuid.UUID, session: Session, _user: Admin) -> MqttCredentialSecretResponse:
    return await MqttCredentialService(session).rotate(device_id)


@router.post("/{device_id}/mqtt-credentials/revoke", response_model=MqttCredentialStatusResponse)
async def revoke_mqtt_credentials(device_id: uuid.UUID, session: Session, _user: Admin) -> MqttCredentialStatusResponse:
    return await MqttCredentialService(session).revoke(device_id)


@router.post("/{device_id}/sync-configuration", response_model=ConfigurationSyncResponse)
async def synchronize_device_configuration(device_id: uuid.UUID, session: Session, _user: Writer) -> ConfigurationSyncResponse:
    return await DeviceConfigurationService(session).synchronize(device_id)
