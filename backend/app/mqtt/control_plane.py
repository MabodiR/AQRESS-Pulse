import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceStatus
from app.models.sensor import ConfigurationStatus, Sensor, SensorConfiguration
from app.mqtt.topics import ParsedControlTopic, parse_control_topic
from app.schemas.mqtt import ConfigurationAckPayload, HeartbeatPayload

logger = logging.getLogger(__name__)


class InvalidControlMessage(ValueError):
    pass


def decode_payload(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidControlMessage("Payload is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise InvalidControlMessage("Payload must be a JSON object.")
    return value


def process_control_message(session: Session, topic: str, raw_payload: bytes, *, received_at: datetime | None = None) -> None:
    parsed = parse_control_topic(topic)
    if parsed is None:
        raise InvalidControlMessage("Topic is outside the Phase 6 control namespace.")
    payload = decode_payload(raw_payload)
    if parsed.kind == "status":
        process_heartbeat(session, parsed, payload, received_at=received_at)
    else:
        process_configuration_ack(session, parsed, payload)


def process_heartbeat(session: Session, topic: ParsedControlTopic, payload: dict[str, Any], *, received_at: datetime | None = None) -> None:
    try:
        heartbeat = HeartbeatPayload.model_validate(payload)
    except ValidationError as exc:
        raise InvalidControlMessage("Heartbeat payload validation failed.") from exc
    _aware(heartbeat.timestamp)
    if heartbeat.device_uid != topic.device_uid:
        raise InvalidControlMessage("Topic and heartbeat Device UID do not match.")
    device = session.scalar(select(Device).where(Device.device_uid == topic.device_uid))
    if device is None:
        raise InvalidControlMessage("Heartbeat references an unknown Device.")
    if not device.is_active or device.status == DeviceStatus.DISABLED:
        raise InvalidControlMessage("Heartbeat references an inactive Device.")
    previous = device.status
    device.last_seen_at = received_at or datetime.now(UTC)
    device.status = DeviceStatus.ONLINE
    session.commit()
    logger.info("Device heartbeat received", extra={"device_uid": device.device_uid})
    if previous != DeviceStatus.ONLINE:
        logger.info("Device became ONLINE", extra={"device_uid": device.device_uid})


def process_configuration_ack(session: Session, topic: ParsedControlTopic, payload: dict[str, Any]) -> None:
    try:
        acknowledgement = ConfigurationAckPayload.model_validate(payload)
    except ValidationError as exc:
        raise InvalidControlMessage("Configuration acknowledgement validation failed.") from exc
    _aware(acknowledgement.timestamp)
    if acknowledgement.device_uid != topic.device_uid:
        raise InvalidControlMessage("Topic and acknowledgement Device UID do not match.")
    device = session.scalar(select(Device).where(Device.device_uid == topic.device_uid))
    if device is None:
        raise InvalidControlMessage("Acknowledgement references an unknown Device.")
    for result in acknowledgement.results:
        sensor = session.scalar(select(Sensor).where(Sensor.device_id == device.id, Sensor.sensor_uid == result.sensor_uid))
        if sensor is None:
            raise InvalidControlMessage("Acknowledgement references an unknown Sensor.")
        configuration = session.scalar(
            select(SensorConfiguration).where(
                SensorConfiguration.sensor_id == sensor.id,
                SensorConfiguration.config_version == result.configuration_version,
            )
        )
        if configuration is None:
            raise InvalidControlMessage("Acknowledgement references an unknown configuration version.")
        if configuration.status == ConfigurationStatus.SUPERSEDED or not configuration.is_current:
            logger.warning("Stale configuration acknowledgement ignored", extra={"device_uid": device.device_uid, "sensor_uid": sensor.sensor_uid, "configuration_version": configuration.config_version})
            continue
        if result.status == "APPLIED":
            configuration.status = ConfigurationStatus.APPLIED
            configuration.applied_at = acknowledgement.timestamp
            logger.info("Configuration APPLIED", extra={"device_uid": device.device_uid, "sensor_uid": sensor.sensor_uid, "configuration_version": configuration.config_version})
        else:
            configuration.status = ConfigurationStatus.FAILED
            configuration.applied_at = None
            logger.warning("Configuration FAILED", extra={"device_uid": device.device_uid, "sensor_uid": sensor.sensor_uid, "configuration_version": configuration.config_version, "device_error": result.error})
    session.commit()
    logger.info("Configuration acknowledgement received", extra={"device_uid": device.device_uid, "message_id": str(acknowledgement.message_id)})


def mark_stale_devices_offline(session: Session, *, now: datetime | None = None, timeout_seconds: int | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(seconds=timeout_seconds or settings.device_offline_timeout_seconds)
    devices = session.scalars(
        select(Device).where(
            Device.status == DeviceStatus.ONLINE,
            Device.is_active.is_(True),
            Device.last_seen_at.is_not(None),
            Device.last_seen_at < cutoff,
        )
    )
    changed = 0
    for device in devices:
        device.status = DeviceStatus.OFFLINE
        changed += 1
        logger.info("Device became OFFLINE", extra={"device_uid": device.device_uid})
    if changed:
        session.commit()
    return changed


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidControlMessage("Timestamp must include a timezone offset.")
