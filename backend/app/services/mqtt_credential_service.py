import logging
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password, utc_now
from app.models.device_mqtt_credential import DeviceMqttCredential
from app.repositories.device_repository import DeviceRepository
from app.repositories.mqtt_credential_repository import MqttCredentialRepository
from app.schemas.mqtt import MqttCredentialSecretResponse, MqttCredentialStatusResponse

logger = logging.getLogger(__name__)


class MqttCredentialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.credentials = MqttCredentialRepository(session)

    async def status(self, device_id: uuid.UUID) -> MqttCredentialStatusResponse:
        await self._device(device_id)
        credential = await self.credentials.get_for_device(device_id)
        if credential is None:
            return MqttCredentialStatusResponse(provisioned=False, state="NOT_PROVISIONED")
        state = "ACTIVE" if credential.is_active and credential.revoked_at is None else "REVOKED"
        return MqttCredentialStatusResponse(
            provisioned=True,
            state=state,
            username=credential.username,
            is_active=credential.is_active,
            created_at=credential.created_at,
            updated_at=credential.updated_at,
            rotated_at=credential.rotated_at,
            revoked_at=credential.revoked_at,
        )

    async def provision(self, device_id: uuid.UUID) -> MqttCredentialSecretResponse:
        device = await self._device(device_id)
        if await self.credentials.get_for_device(device_id):
            raise AppError(status_code=409, code="MQTT_CREDENTIAL_EXISTS", message="MQTT credentials are already provisioned; rotate them instead.")
        password = self._password()
        credential = DeviceMqttCredential(
            device_id=device.id,
            username=f"device:{device.device_uid}",
            password_hash=hash_password(password),
            is_active=True,
        )
        self.session.add(credential)
        await self.session.commit()
        await self.session.refresh(credential)
        logger.info("MQTT credential provisioned", extra={"device_uid": device.device_uid})
        return MqttCredentialSecretResponse(username=credential.username, password=password, created_at=credential.created_at)

    async def rotate(self, device_id: uuid.UUID) -> MqttCredentialSecretResponse:
        device = await self._device(device_id)
        credential = await self.credentials.get_for_device(device_id)
        if credential is None:
            raise AppError(status_code=404, code="MQTT_CREDENTIAL_NOT_FOUND", message="Provision MQTT credentials before rotating them.")
        password = self._password()
        now = utc_now()
        credential.password_hash = hash_password(password)
        credential.is_active = True
        credential.rotated_at = now
        credential.revoked_at = None
        await self.session.commit()
        await self.session.refresh(credential)
        logger.info("MQTT credential rotated", extra={"device_uid": device.device_uid})
        return MqttCredentialSecretResponse(username=credential.username, password=password, created_at=credential.created_at, rotated_at=credential.rotated_at)

    async def revoke(self, device_id: uuid.UUID) -> MqttCredentialStatusResponse:
        device = await self._device(device_id)
        credential = await self.credentials.get_for_device(device_id)
        if credential is None:
            raise AppError(status_code=404, code="MQTT_CREDENTIAL_NOT_FOUND", message="MQTT credentials have not been provisioned.")
        credential.is_active = False
        credential.revoked_at = utc_now()
        await self.session.commit()
        logger.info("MQTT credential revoked", extra={"device_uid": device.device_uid})
        return await self.status(device_id)

    async def _device(self, device_id: uuid.UUID):
        device = await self.devices.get(device_id)
        if device is None:
            raise AppError(status_code=404, code="DEVICE_NOT_FOUND", message="Device was not found.")
        return device

    @staticmethod
    def _password() -> str:
        return secrets.token_urlsafe(32)
