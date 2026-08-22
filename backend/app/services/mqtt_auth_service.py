import logging
import secrets
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_password
from app.mqtt.topics import (
    CONTROL_SUBSCRIPTIONS,
    NAMESPACE,
    TELEMETRY_SUBSCRIPTION,
    command_topic,
    config_ack_topic,
    config_topic,
    status_topic,
    telemetry_topic,
)
from app.repositories.mqtt_credential_repository import MqttCredentialRepository

logger = logging.getLogger(__name__)


def _deny() -> dict[str, Any]:
    return {"result": "deny", "is_superuser": False}


class MqttAuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.credentials = MqttCredentialRepository(session)

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        if secrets.compare_digest(username, settings.mqtt_platform_username):
            if not secrets.compare_digest(password, settings.mqtt_platform_password):
                logger.warning("MQTT authentication failed", extra={"mqtt_username": username})
                return _deny()
            return {"result": "allow", "is_superuser": False, "acl": self._platform_acl()}

        credential = await self.credentials.get_by_username(username)
        if (
            credential is None
            or not credential.is_active
            or credential.revoked_at is not None
            or not credential.device.is_active
            or not verify_password(password, credential.password_hash)
        ):
            logger.warning("MQTT authentication failed", extra={"mqtt_username": username})
            return _deny()
        return {
            "result": "allow",
            "is_superuser": False,
            "client_attrs": {"device_uid": credential.device.device_uid},
            "acl": self._device_acl(credential.device.device_uid),
        }

    async def authorize(self, username: str, action: str, topic: str) -> dict[str, str]:
        if secrets.compare_digest(username, settings.mqtt_platform_username):
            allowed = (action == "publish" and topic.startswith(f"{NAMESPACE}/") and topic.endswith("/config")) or (
                action == "subscribe"
                and topic in (*CONTROL_SUBSCRIPTIONS, TELEMETRY_SUBSCRIPTION)
            )
            return {"result": "allow" if allowed else "deny"}
        credential = await self.credentials.get_by_username(username)
        if credential is None or not credential.is_active or not credential.device.is_active:
            return {"result": "deny"}
        uid = credential.device.device_uid
        allowed = (action == "publish" and topic in {status_topic(uid), config_ack_topic(uid), telemetry_topic(uid)}) or (
            action == "subscribe" and topic in {config_topic(uid), command_topic(uid)}
        )
        if not allowed:
            logger.warning("MQTT authorization rejected", extra={"mqtt_username": username, "action": action, "topic": topic})
        return {"result": "allow" if allowed else "deny"}

    @staticmethod
    def _device_acl(device_uid: str) -> list[dict[str, Any]]:
        return [
            {"permission": "allow", "action": "publish", "topic": status_topic(device_uid), "qos": [0, 1]},
            {"permission": "allow", "action": "publish", "topic": config_ack_topic(device_uid), "qos": [0, 1]},
            {"permission": "allow", "action": "publish", "topic": telemetry_topic(device_uid), "qos": [0, 1]},
            {"permission": "allow", "action": "subscribe", "topic": config_topic(device_uid), "qos": [0, 1]},
            {"permission": "allow", "action": "subscribe", "topic": command_topic(device_uid), "qos": [0, 1]},
            {"permission": "deny", "action": "all", "topic": "#"},
        ]

    @staticmethod
    def _platform_acl() -> list[dict[str, Any]]:
        return [
            {"permission": "allow", "action": "publish", "topic": f"{NAMESPACE}/+/config", "qos": [1], "retain": True},
            *[
                {"permission": "allow", "action": "subscribe", "topic": topic, "qos": [0, 1]}
                for topic in CONTROL_SUBSCRIPTIONS
            ],
            {
                "permission": "allow",
                "action": "subscribe",
                "topic": TELEMETRY_SUBSCRIPTION,
                "qos": [1],
            },
            {"permission": "deny", "action": "all", "topic": "#"},
        ]
