import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device_mqtt_credential import DeviceMqttCredential


class MqttCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_device(self, device_id: uuid.UUID) -> DeviceMqttCredential | None:
        return await self.session.scalar(
            select(DeviceMqttCredential).where(DeviceMqttCredential.device_id == device_id)
        )

    async def get_by_username(self, username: str) -> DeviceMqttCredential | None:
        return await self.session.scalar(
            select(DeviceMqttCredential)
            .options(selectinload(DeviceMqttCredential.device))
            .where(DeviceMqttCredential.username == username)
        )
