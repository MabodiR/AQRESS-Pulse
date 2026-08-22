import json
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.device import Device
from app.models.sensor import Sensor, SensorChannel, SensorStatus
from app.models.sensor_type import MeasurementValueType
from app.mqtt.topics import parse_telemetry_topic
from app.repositories.reading_repository import TelemetryReadingRepository
from app.schemas.telemetry import TelemetryEnvelope, TelemetryReadingItem

logger = logging.getLogger(__name__)


class InvalidTelemetryMessage(ValueError):
    pass


@dataclass(frozen=True)
class TelemetryProcessingResult:
    device_uid: str
    message_id: uuid.UUID
    reading_count: int
    accepted_count: int
    rejected_count: int
    duplicate_count: int


def decode_telemetry_payload(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Invalid JSON constant: {value}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise InvalidTelemetryMessage("Payload is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise InvalidTelemetryMessage("Telemetry payload must be a JSON object.")
    return value


def process_telemetry_message(
    session: Session,
    topic: str,
    raw_payload: bytes,
    *,
    received_at: datetime | None = None,
    max_readings: int | None = None,
    max_future_skew_seconds: int | None = None,
) -> TelemetryProcessingResult:
    device_uid = parse_telemetry_topic(topic)
    if device_uid is None:
        raise InvalidTelemetryMessage("Topic is outside the Phase 7 telemetry namespace.")
    payload = decode_telemetry_payload(raw_payload)
    try:
        envelope = TelemetryEnvelope.model_validate(payload)
    except ValidationError as exc:
        raise InvalidTelemetryMessage("Telemetry envelope validation failed.") from exc
    if envelope.device_uid != device_uid:
        raise InvalidTelemetryMessage("Topic and telemetry Device UID do not match.")
    limit = max_readings or settings.telemetry_max_readings_per_message
    if len(envelope.readings) > limit:
        raise InvalidTelemetryMessage(
            f"Telemetry envelope exceeds the maximum of {limit} readings."
        )

    device = session.scalar(
        select(Device)
        .options(
            selectinload(Device.sensors)
            .selectinload(Sensor.channels)
            .selectinload(SensorChannel.measurement_definition)
        )
        .where(Device.device_uid == device_uid)
    )
    if device is None:
        raise InvalidTelemetryMessage("Telemetry references an unknown Device.")
    if not device.is_active:
        raise InvalidTelemetryMessage("Telemetry references an inactive Device.")

    now = received_at or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("received_at must be timezone aware.")
    future_cutoff = now + timedelta(
        seconds=max_future_skew_seconds
        if max_future_skew_seconds is not None
        else settings.telemetry_max_future_skew_seconds
    )
    sensors = {sensor.sensor_uid: sensor for sensor in device.sensors}
    rows: list[dict[str, Any]] = []
    rejected = 0

    for reading_index, raw_item in enumerate(envelope.readings):
        reason: str | None = None
        item: TelemetryReadingItem | None = None
        if not isinstance(raw_item, dict):
            reason = "Reading must be a JSON object."
        else:
            try:
                item = TelemetryReadingItem.model_validate(raw_item)
            except ValidationError:
                reason = "Reading schema validation failed."
        sensor = sensors.get(item.sensor_uid) if item else None
        if reason is None and sensor is None:
            reason = "Unknown Sensor."
        if reason is None and sensor is not None:
            if not sensor.enabled or sensor.status in {
                SensorStatus.DISABLED,
                SensorStatus.ERROR,
            }:
                reason = "Sensor is not accepting telemetry."
        channel = (
            next(
                (
                    candidate
                    for candidate in sensor.channels
                    if candidate.measurement_definition.key == item.channel
                ),
                None,
            )
            if sensor is not None and item is not None
            else None
        )
        if reason is None and channel is None:
            reason = "Unknown Sensor Channel."
        if reason is None and channel is not None and not channel.enabled:
            reason = "Sensor Channel is disabled."
        if reason is None and item is not None and item.recorded_at > future_cutoff:
            reason = "Reading timestamp exceeds the allowed future clock skew."
        values = _typed_values(channel, item.value) if channel and item else None
        if reason is None and values is None:
            reason = "Reading value does not match the Channel value type."
        if reason is not None:
            rejected += 1
            logger.warning(
                "Telemetry reading rejected",
                extra={
                    "device_uid": device_uid,
                    "message_id": str(envelope.message_id),
                    "reading_index": reading_index,
                    "reason": reason,
                },
            )
            continue
        assert sensor is not None and channel is not None and item is not None
        assert values is not None
        rows.append(
            {
                "id": uuid.uuid4(),
                "device_id": device.id,
                "sensor_id": sensor.id,
                "sensor_channel_id": channel.id,
                "message_id": envelope.message_id,
                "reading_index": reading_index,
                "recorded_at": item.recorded_at,
                "received_at": now,
                **values,
                "unit": channel.unit,
                "quality": item.quality,
                "raw_payload": raw_item,
            }
        )

    try:
        inserted = TelemetryReadingRepository(session).insert_idempotently(rows)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception(
            "Telemetry database failure",
            extra={
                "device_uid": device_uid,
                "message_id": str(envelope.message_id),
            },
        )
        raise
    duplicates = len(rows) - inserted
    result = TelemetryProcessingResult(
        device_uid=device_uid,
        message_id=envelope.message_id,
        reading_count=len(envelope.readings),
        accepted_count=inserted,
        rejected_count=rejected,
        duplicate_count=duplicates,
    )
    logger.info(
        "Telemetry batch processed",
        extra={
            "device_uid": result.device_uid,
            "message_id": str(result.message_id),
            "reading_count": result.reading_count,
            "accepted_count": result.accepted_count,
            "rejected_count": result.rejected_count,
            "duplicate_count": result.duplicate_count,
        },
    )
    return result


def _typed_values(
    channel: SensorChannel, value: Any
) -> dict[str, float | str | bool | None] | None:
    value_type = channel.measurement_definition.value_type
    if value_type == MeasurementValueType.NUMERIC:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return {
            "value_numeric": numeric,
            "value_text": None,
            "value_boolean": None,
        }
    if value_type == MeasurementValueType.BOOLEAN:
        if not isinstance(value, bool):
            return None
        return {
            "value_numeric": None,
            "value_text": None,
            "value_boolean": value,
        }
    if value_type == MeasurementValueType.TEXT:
        if not isinstance(value, str):
            return None
        return {
            "value_numeric": None,
            "value_text": value,
            "value_boolean": None,
        }
    return None
